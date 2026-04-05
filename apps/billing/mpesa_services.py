"""
M-Pesa billing service — subscription management via M-Pesa payments.

Unlike Stripe (which handles recurring billing automatically), M-Pesa requires
manual subscription tracking:
    1. User initiates payment → STK Push → user confirms on phone
    2. Callback activates/renews subscription for 30 days
    3. Celery Beat task checks expiring subs → sends reminder → prompts renewal

Functions:
    initiate_mpesa_checkout() — Start STK Push for a plan
    process_mpesa_callback()  — Handle callback from Daraja
    check_expiring_subscriptions() — Find and remind about expiring subs
    activate_subscription()   — Set plan + period after successful payment
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.billing.models import BillingEvent, MpesaPayment, get_plan_limits
from apps.billing.mpesa import format_phone_number, initiate_stk_push, parse_stk_callback

logger = logging.getLogger(__name__)


def initiate_mpesa_checkout(user, plan_tier, phone_number):
    """
    Start an M-Pesa STK Push payment for a subscription.

    Args:
        user: Django User instance
        plan_tier: 'starter', 'growth', 'pro', or 'agency'
        phone_number: Customer's phone (any Kenyan format)

    Returns:
        MpesaPayment instance (status=pending)

    Raises:
        ValueError: Invalid plan or phone number
        ConnectionError: M-Pesa API failure
    """
    limits = get_plan_limits(plan_tier)
    amount = limits["price_kes"]

    # Validate and format phone
    formatted_phone = format_phone_number(phone_number)

    # Check if user has an existing pending payment
    MpesaPayment.objects.filter(
        user=user,
        status=MpesaPayment.Status.PENDING,
    ).update(status=MpesaPayment.Status.EXPIRED)

    # Determine if this is a renewal
    is_renewal = user.profile.subscription_status in ("active", "trialing")

    # Initiate STK Push
    result = initiate_stk_push(
        phone_number=formatted_phone,
        amount=amount,
        account_reference="KovaAgent",
        transaction_desc=f"Kova {limits['label'].split('/')[0].strip()}",
    )

    # Save payment record
    payment = MpesaPayment.objects.create(
        user=user,
        checkout_request_id=result["CheckoutRequestID"],
        merchant_request_id=result.get("MerchantRequestID", ""),
        phone_number=formatted_phone,
        amount=amount,
        plan_tier=plan_tier,
        is_renewal=is_renewal,
        status=MpesaPayment.Status.PENDING,
    )

    # Save phone to profile for future renewals
    profile = user.profile
    profile.mpesa_phone = formatted_phone
    profile.save(update_fields=["mpesa_phone"])

    logger.info(
        "M-Pesa checkout initiated: user=%s plan=%s amount=%s phone=%s",
        user.email, plan_tier, amount, formatted_phone[-4:],
    )
    return payment


def process_mpesa_callback(callback_data):
    """
    Process M-Pesa STK Push callback.

    Called when Daraja sends the payment result to our webhook endpoint.

    Args:
        callback_data: Raw JSON from M-Pesa callback POST

    Returns:
        bool: True if processed successfully
    """
    parsed = parse_stk_callback(callback_data)
    checkout_id = parsed["checkout_request_id"]

    # Find the payment record
    try:
        payment = MpesaPayment.objects.select_related("user", "user__profile").get(
            checkout_request_id=checkout_id,
        )
    except MpesaPayment.DoesNotExist:
        logger.warning("M-Pesa callback for unknown checkout: %s", checkout_id)
        return False

    # Create billing event for audit trail
    billing_event = BillingEvent.objects.create(
        stripe_event_id=f"mpesa_{checkout_id}",
        event_type="mpesa.stk_callback",
        provider="mpesa",
        user=payment.user,
        data=callback_data,
        processed=True,
    )

    if parsed["success"]:
        # Payment successful
        payment.status = MpesaPayment.Status.COMPLETED
        payment.result_code = parsed["result_code"]
        payment.result_desc = parsed["result_desc"]
        payment.receipt_number = parsed.get("receipt_number", "")
        payment.completed_at = timezone.now()

        # Activate subscription
        activate_subscription(payment)

        # Send payment confirmation email
        from apps.emails.tasks import send_payment_confirmation_email
        send_payment_confirmation_email.delay(
            str(payment.user.pk),
            payment.plan,
            str(payment.amount),
            "mpesa",
        )

        logger.info(
            "M-Pesa payment SUCCESS: user=%s amount=%s receipt=%s",
            payment.user.email, payment.amount, payment.receipt_number,
        )
    else:
        # Payment failed (user canceled, timeout, insufficient funds, etc.)
        payment.status = MpesaPayment.Status.FAILED
        payment.result_code = parsed["result_code"]
        payment.result_desc = parsed["result_desc"]

        logger.warning(
            "M-Pesa payment FAILED: user=%s code=%s desc=%s",
            payment.user.email, parsed["result_code"], parsed["result_desc"],
        )

    payment.save()
    return True


def activate_subscription(payment):
    """
    Activate or renew a user's subscription after successful M-Pesa payment.

    Sets the plan tier, subscription period (30 days), and status.
    """
    profile = payment.user.profile
    now = timezone.now()

    # If renewing an active subscription, extend from current period end
    if payment.is_renewal and profile.current_period_end and profile.current_period_end > now:
        period_start = profile.current_period_end
    else:
        period_start = now

    period_end = period_start + timedelta(days=30)

    # Update payment record
    payment.subscription_period_start = period_start
    payment.subscription_period_end = period_end
    payment.save(update_fields=["subscription_period_start", "subscription_period_end"])

    # Update user profile
    profile.plan = payment.plan_tier
    profile.payment_provider = "mpesa"
    profile.subscription_status = "active"
    profile.current_period_end = period_end
    profile.trial_ends_at = None  # No longer trialing
    profile.save(update_fields=[
        "plan", "payment_provider", "subscription_status",
        "current_period_end", "trial_ends_at",
    ])

    logger.info(
        "Subscription activated: user=%s plan=%s period=%s to %s",
        payment.user.email, payment.plan_tier,
        period_start.strftime("%Y-%m-%d"), period_end.strftime("%Y-%m-%d"),
    )


def activate_trial(user, plan_tier, phone_number):
    """
    Activate a free trial for a plan (no payment required).

    Trial length is defined by MPESA_TRIAL_DAYS setting (default 14).
    After trial, user must pay via M-Pesa to continue.
    """
    formatted_phone = format_phone_number(phone_number)
    trial_days = getattr(settings, "MPESA_TRIAL_DAYS", 14)
    now = timezone.now()

    profile = user.profile
    profile.plan = plan_tier
    profile.payment_provider = "mpesa"
    profile.subscription_status = "trialing"
    profile.mpesa_phone = formatted_phone
    profile.trial_ends_at = now + timedelta(days=trial_days)
    profile.current_period_end = now + timedelta(days=trial_days)
    profile.save(update_fields=[
        "plan", "payment_provider", "subscription_status",
        "mpesa_phone", "trial_ends_at", "current_period_end",
    ])

    logger.info(
        "Trial activated: user=%s plan=%s trial_ends=%s",
        user.email, plan_tier,
        profile.trial_ends_at.strftime("%Y-%m-%d"),
    )
    return profile


def expire_subscription(user):
    """
    Expire a subscription — revert to starter plan.

    Called when payment is overdue after grace period.
    """
    profile = user.profile
    profile.plan = "starter"
    profile.subscription_status = "canceled"
    profile.save(update_fields=["plan", "subscription_status"])

    logger.info("Subscription expired: user=%s reverted to starter", user.email)
