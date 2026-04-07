import json
import logging

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.billing.models import PLAN_LIMITS, get_all_plan_limits, get_plan_limits
from apps.billing.services import (
    create_checkout_session,
    create_portal_session,
    handle_webhook_event,
    sync_subscription,
)

logger = logging.getLogger(__name__)


@login_required
def billing_overview(request):
    """Billing overview — current plan, usage, manage subscription."""
    profile = request.user.profile
    limits = get_plan_limits(profile.plan)

    # Sync from Stripe if user has a Stripe subscription (keeps data fresh)
    if profile.stripe_subscription_id:
        try:
            sync_subscription(request.user)
        except Exception:
            pass  # Don't break the page if Stripe is down

    # Get recent M-Pesa payments
    recent_payments = []
    if profile.payment_provider == "mpesa":
        from apps.billing.models import MpesaPayment
        recent_payments = MpesaPayment.objects.filter(
            user=request.user,
        ).exclude(status=MpesaPayment.Status.EXPIRED).order_by("-created_at")[:5]

    return render(request, "billing/overview.html", {
        "page_title": "Billing & Plan",
        "profile": profile,
        "limits": limits,
        "all_plans": get_all_plan_limits(),
        "recent_payments": recent_payments,
        "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
    })


@login_required
def pricing(request):
    """Standalone pricing page (for logged-in users upgrading)."""
    return render(request, "billing/pricing.html", {
        "page_title": "Choose Your Plan",
        "all_plans": get_all_plan_limits(),
        "current_plan": request.user.profile.plan,
    })


@login_required
@require_POST
def checkout(request):
    """Create Stripe Checkout Session and redirect to Stripe."""
    plan_tier = request.POST.get("plan")
    if plan_tier not in PLAN_LIMITS:
        messages.error(request, "Invalid plan selected.")
        return redirect("billing:pricing")

    # All plans go through Stripe checkout (14-day free trial included)

    try:
        session = create_checkout_session(request.user, plan_tier, request)
        return redirect(session.url)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("billing:pricing")
    except stripe.error.StripeError as e:
        logger.exception("Stripe checkout error: %s", e)
        messages.error(request, "Payment service error. Please try again.")
        return redirect("billing:pricing")


@login_required
def checkout_success(request):
    """Post-checkout success page. Syncs subscription from Stripe."""
    session_id = request.GET.get("session_id")
    if session_id:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.subscription:
                sync_subscription(request.user, session.subscription)
        except Exception as e:
            logger.warning("Could not sync after checkout: %s", e)

    profile = request.user.profile
    plan_name = get_plan_limits(profile.plan).get("label", profile.get_plan_display())

    return render(request, "billing/checkout_success.html", {
        "page_title": "Welcome!",
        "profile": profile,
        "plan_name": plan_name,
    })


@login_required
def checkout_cancel(request):
    """User canceled the checkout flow."""
    return render(request, "billing/checkout_cancel.html", {
        "page_title": "Checkout Canceled",
    })


@login_required
def portal(request):
    """Redirect to Stripe Customer Portal for self-service billing."""
    try:
        session = create_portal_session(request.user, request)
        return redirect(session.url)
    except stripe.error.StripeError as e:
        logger.exception("Stripe portal error: %s", e)
        messages.error(request, "Could not open billing portal. Please try again.")
        return redirect("billing:overview")


@csrf_exempt
@ratelimit(key="ip", rate="30/m", block=True)
@require_POST
def stripe_webhook(request):
    """Stripe webhook endpoint. Verifies signature, routes to handler."""
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET

    if not webhook_secret:
        logger.error("STRIPE_WEBHOOK_SECRET not configured")
        return HttpResponse(status=500)

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        logger.warning("Invalid webhook payload")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        logger.warning("Invalid webhook signature")
        return HttpResponse(status=400)

    success = handle_webhook_event(event)
    return HttpResponse(status=200 if success else 500)


# ─── M-Pesa Views ────────────────────────────────────────────────────────────

@login_required
@require_POST
def mpesa_checkout(request):
    """Initiate M-Pesa STK Push payment for a plan."""
    from apps.billing.mpesa_services import activate_trial, initiate_mpesa_checkout
    from apps.billing.models import DiscountCode, DiscountRedemption

    plan_tier = request.POST.get("plan")
    phone_number = request.POST.get("phone_number", "").strip()
    is_trial = request.POST.get("trial") == "1"
    discount_code_str = request.POST.get("discount_code", "").strip().upper()

    if plan_tier not in PLAN_LIMITS:
        messages.error(request, "Invalid plan selected.")
        return redirect("billing:pricing")

    if not phone_number:
        messages.error(request, "Please enter your M-Pesa phone number.")
        return redirect("billing:pricing")

    # Validate phone number
    from apps.billing.mpesa import format_phone_number
    try:
        formatted_phone = format_phone_number(phone_number)
    except ValueError:
        messages.error(request, "Invalid phone number. Use format: 07XXXXXXXX or 254XXXXXXXXX")
        return redirect("billing:pricing")

    # Free trial — no payment needed
    if is_trial and request.user.profile.subscription_status == "none":
        try:
            activate_trial(request.user, plan_tier, formatted_phone)
            messages.success(request, f"🎉 Your 14-day free trial is active!")
            return redirect("billing:mpesa_success")
        except Exception as e:
            logger.exception("Trial activation error: %s", e)
            messages.error(request, "Could not activate trial. Please try again.")
            return redirect("billing:pricing")

    # Validate discount code if provided
    discount_obj = None
    if discount_code_str:
        try:
            discount_obj = DiscountCode.objects.get(code=discount_code_str)
        except DiscountCode.DoesNotExist:
            messages.error(request, f"Discount code '{discount_code_str}' not found.")
            return redirect("billing:pricing")

        if not discount_obj.can_user_use(request.user):
            messages.error(request, "This discount code is no longer valid or you've already used it.")
            return redirect("billing:pricing")

        if not discount_obj.applies_to_plan(plan_tier):
            messages.error(request, f"This discount code doesn't apply to the {plan_tier.title()} plan.")
            return redirect("billing:pricing")

    # Paid subscription — initiate STK Push
    try:
        payment = initiate_mpesa_checkout(
            request.user, plan_tier, formatted_phone,
            discount=discount_obj,
        )
        # Store checkout_request_id in session for the waiting page
        request.session["mpesa_checkout_id"] = payment.checkout_request_id
        request.session["mpesa_plan"] = plan_tier
        return redirect("billing:mpesa_waiting")
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("billing:pricing")
    except ConnectionError as e:
        logger.exception("M-Pesa STK Push error: %s", e)
        messages.error(request, "M-Pesa service unavailable. Please try again in a moment.")
        return redirect("billing:pricing")


@login_required
def mpesa_waiting(request):
    """Waiting page — shown after STK Push is sent. Polls for completion."""
    checkout_id = request.session.get("mpesa_checkout_id", "")
    plan_tier = request.session.get("mpesa_plan", "starter")

    if not checkout_id:
        return redirect("billing:pricing")

    return render(request, "billing/mpesa_waiting.html", {
        "page_title": "Confirming Payment",
        "checkout_id": checkout_id,
        "plan_name": get_plan_limits(plan_tier).get("label", plan_tier),
    })


@login_required
def mpesa_check_status(request):
    """HTMX endpoint — check if M-Pesa payment completed."""
    from apps.billing.models import MpesaPayment

    checkout_id = request.session.get("mpesa_checkout_id", "")
    if not checkout_id:
        return HttpResponse('<div id="mpesa-status">Error: No pending payment</div>', status=400)

    try:
        payment = MpesaPayment.objects.get(checkout_request_id=checkout_id)
    except MpesaPayment.DoesNotExist:
        return HttpResponse('<div id="mpesa-status">Payment not found</div>', status=404)

    if payment.status == MpesaPayment.Status.COMPLETED:
        # Payment successful — redirect via HX-Redirect
        response = HttpResponse()
        response["HX-Redirect"] = "/billing/mpesa/success/"
        return response
    elif payment.status == MpesaPayment.Status.FAILED:
        return HttpResponse(
            '<div id="mpesa-status" class="text-red-600 dark:text-red-400 text-center">'
            f'<p class="text-lg font-semibold">Payment failed</p>'
            f'<p class="text-sm mt-1">{payment.result_desc}</p>'
            f'<a href="/billing/pricing/" class="btn-primary text-sm px-4 py-2 mt-4 inline-block">Try again</a>'
            '</div>'
        )
    else:
        # Still pending — keep polling
        return HttpResponse(
            '<div id="mpesa-status" hx-get="/billing/mpesa/status/" hx-trigger="every 3s" hx-swap="outerHTML">'
            '<div class="flex flex-col items-center">'
            '<div class="animate-spin rounded-full h-8 w-8 border-b-2 border-green-600 mb-3"></div>'
            '<p class="text-sm text-gray-600 dark:text-gray-400">Waiting for M-Pesa confirmation...</p>'
            '<p class="text-xs text-gray-400 dark:text-gray-500 mt-1">Check your phone and enter your M-Pesa PIN</p>'
            '</div>'
            '</div>'
        )


@login_required
def mpesa_success(request):
    """Success page after M-Pesa payment."""
    # Clear session
    request.session.pop("mpesa_checkout_id", None)
    request.session.pop("mpesa_plan", None)

    profile = request.user.profile
    plan_name = get_plan_limits(profile.plan).get("label", profile.get_plan_display())

    return render(request, "billing/mpesa_success.html", {
        "page_title": "Payment Successful!",
        "profile": profile,
        "plan_name": plan_name,
    })


@csrf_exempt
@ratelimit(key="ip", rate="30/m", block=True)
@require_POST
def mpesa_webhook(request):
    """
    M-Pesa callback endpoint.

    Daraja sends the STK Push result here after the user confirms or cancels.
    No signature verification needed — M-Pesa uses URL-based security
    (only Safaricom knows your callback URL).
    """
    from apps.billing.mpesa_services import process_mpesa_callback

    try:
        callback_data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        logger.warning("Invalid M-Pesa callback payload")
        return HttpResponse(status=400)

    # Log the raw callback for debugging
    logger.info("M-Pesa callback received: %s", json.dumps(callback_data)[:500])

    success = process_mpesa_callback(callback_data)
    # M-Pesa expects a 200 OK response — always acknowledge
    return HttpResponse(status=200)
