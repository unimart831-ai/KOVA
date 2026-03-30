import logging

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.billing.models import PLAN_LIMITS, get_plan_limits
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

    # Sync from Stripe if user has a subscription (keeps data fresh)
    if profile.stripe_subscription_id:
        try:
            sync_subscription(request.user)
        except Exception:
            pass  # Don't break the page if Stripe is down

    return render(request, "billing/overview.html", {
        "page_title": "Billing & Plan",
        "profile": profile,
        "limits": limits,
        "all_plans": PLAN_LIMITS,
        "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
    })


@login_required
def pricing(request):
    """Standalone pricing page (for logged-in users upgrading)."""
    return render(request, "billing/pricing.html", {
        "page_title": "Choose Your Plan",
        "all_plans": PLAN_LIMITS,
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
