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
from django.db import transaction
from django.utils import timezone

from apps.core.billing.models import BillingEvent, MpesaPayment, get_plan_limits
from apps.core.billing.mpesa import format_phone_number, initiate_stk_push, parse_stk_callback
from apps.core.billing.campaign_addons import get_addon_pack, user_can_purchase_addons

logger = logging.getLogger(__name__)


def initiate_mpesa_checkout(user, plan_tier, phone_number, discount=None):
    """
    Start an M-Pesa STK Push payment for a subscription.

    Args:
        user: Django User instance
        plan_tier: 'starter', 'growth', 'pro', or 'agency'
        phone_number: Customer's phone (any Kenyan format)
        discount: Optional DiscountCode instance for price reduction

    Returns:
        MpesaPayment instance (status=pending)

    Raises:
        ValueError: Invalid plan or phone number
        ConnectionError: M-Pesa API failure
    """
    limits = get_plan_limits(plan_tier)
    amount = limits["price_kes"]

    # Apply discount if provided
    discount_amount_saved = 0
    if discount:
        discounted_kes, _, saved_kes, _ = discount.calculate_discount(amount, limits["price_usd"])
        discount_amount_saved = saved_kes
        amount = discounted_kes

    # Validate and format phone
    formatted_phone = format_phone_number(phone_number)

    # Idempotency guard: reject if user has a pending payment created < 2 min ago
    # This prevents double-tap STK pushes that could lead to double charges
    recent_cutoff = timezone.now() - timedelta(minutes=2)
    recent_pending = MpesaPayment.objects.filter(
        user=user,
        status=MpesaPayment.Status.PENDING,
        created_at__gte=recent_cutoff,
    ).exists()
    if recent_pending:
        raise ValueError(
            "A payment is already in progress. Please check your phone for the M-Pesa prompt, "
            "or wait 2 minutes before trying again."
        )

    # Expire any older pending payments
    MpesaPayment.objects.filter(
        user=user,
        status=MpesaPayment.Status.PENDING,
        created_at__lt=recent_cutoff,
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

    # Record discount redemption
    if discount and discount_amount_saved > 0:
        from apps.core.billing.models import DiscountRedemption
        from django.db.models import F
        DiscountRedemption.objects.create(
            discount_code=discount,
            user=user,
            plan_tier=plan_tier,
            original_amount=limits["price_kes"],
            discounted_amount=amount,
            amount_saved=discount_amount_saved,
            currency="KES",
        )
        discount.current_uses = F("current_uses") + 1
        discount.save(update_fields=["current_uses", "updated_at"])

    # Save phone to profile for future renewals
    profile = user.profile
    profile.mpesa_phone = formatted_phone
    profile.save(update_fields=["mpesa_phone"])

    logger.info(
        "M-Pesa checkout initiated: user=%s plan=%s amount=%s phone=%s",
        user.email, plan_tier, amount, formatted_phone[-4:],
    )
    return payment


def initiate_mpesa_addon_checkout(user, pack_id, phone_number):
    """
    Start M-Pesa STK Push for a campaign add-on pack (boost / scale / burst).

    Returns:
        MpesaPayment (status=pending, payment_kind=campaign_addon)
    """
    pack = get_addon_pack(pack_id)
    if not pack:
        raise ValueError("Invalid campaign add-on selected.")

    allowed, message = user_can_purchase_addons(user)
    if not allowed:
        raise ValueError(message)

    amount = pack["price_kes"]
    formatted_phone = format_phone_number(phone_number)

    recent_cutoff = timezone.now() - timedelta(minutes=2)
    recent_pending = MpesaPayment.objects.filter(
        user=user,
        status=MpesaPayment.Status.PENDING,
        created_at__gte=recent_cutoff,
    ).exists()
    if recent_pending:
        raise ValueError(
            "A payment is already in progress. Please check your phone for the M-Pesa prompt, "
            "or wait 2 minutes before trying again."
        )

    MpesaPayment.objects.filter(
        user=user,
        status=MpesaPayment.Status.PENDING,
        created_at__lt=recent_cutoff,
    ).update(status=MpesaPayment.Status.EXPIRED)

    profile = user.profile
    result = initiate_stk_push(
        phone_number=formatted_phone,
        amount=amount,
        account_reference="KovaAddon",
        transaction_desc=f"Kova {pack['label'][:40]}",
    )

    payment = MpesaPayment.objects.create(
        user=user,
        checkout_request_id=result["CheckoutRequestID"],
        merchant_request_id=result.get("MerchantRequestID", ""),
        phone_number=formatted_phone,
        amount=amount,
        plan_tier=profile.plan or "kova",
        payment_kind=MpesaPayment.PaymentKind.CAMPAIGN_ADDON,
        addon_pack_id=pack_id,
        is_renewal=False,
        status=MpesaPayment.Status.PENDING,
    )

    profile.mpesa_phone = formatted_phone
    profile.save(update_fields=["mpesa_phone"])

    logger.info(
        "M-Pesa add-on checkout: user=%s pack=%s amount=%s",
        user.email, pack_id, amount,
    )
    return payment


def process_mpesa_callback(callback_data):
    """
    Process M-Pesa STK Push callback.

    Called when Daraja sends the payment result to our webhook endpoint.

    The whole flow runs inside a single transaction with ``select_for_update``
    on the payment row. This is the only way to make the read-modify-write
    safe against two callbacks arriving for the same CheckoutRequestID
    within milliseconds of each other (rare in practice, but the cost when
    it happens is double-activation + duplicate confirmation emails).

    Args:
        callback_data: Raw JSON from M-Pesa callback POST

    Returns:
        bool: True if processed successfully
    """
    parsed = parse_stk_callback(callback_data)
    checkout_id = parsed["checkout_request_id"]

    with transaction.atomic():
        # Lock the payment row for the duration of this transaction so a
        # concurrent callback for the same checkout_id blocks instead of
        # racing past our terminal-state check.
        try:
            payment = (
                MpesaPayment.objects
                .select_for_update()
                .select_related("user", "user__profile")
                .get(checkout_request_id=checkout_id)
            )
        except MpesaPayment.DoesNotExist:
            logger.warning("M-Pesa callback for unknown checkout: %s", checkout_id)
            return False

        # Replay protection: reject callbacks for payments already in a
        # terminal state. Holding the row lock above guarantees that this
        # check is correct even with concurrent callbacks.
        if payment.status in (MpesaPayment.Status.COMPLETED, MpesaPayment.Status.FAILED):
            logger.info(
                "M-Pesa callback replay ignored: checkout=%s status=%s",
                checkout_id, payment.status,
            )
            return True

        # Race-safe audit record — unique stripe_event_id makes the second
        # winner of a race a no-op, in addition to the row lock above.
        _, created = BillingEvent.objects.get_or_create(
            stripe_event_id=f"mpesa_{checkout_id}",
            defaults={
                "event_type": "mpesa.stk_callback",
                "provider": "mpesa",
                "user": payment.user,
                "data": callback_data,
                "processed": True,
            },
        )
        if not created:
            logger.info("M-Pesa callback duplicate for checkout %s, skipping", checkout_id)
            return True

        succeeded = parsed["success"]
        if succeeded:
            payment.status = MpesaPayment.Status.COMPLETED
            payment.result_code = parsed["result_code"]
            payment.result_desc = parsed["result_desc"]
            payment.receipt_number = parsed.get("receipt_number", "")
            payment.completed_at = timezone.now()
            if payment.is_campaign_addon:
                from apps.core.billing.campaign_addons import apply_campaign_addon_purchase
                apply_campaign_addon_purchase(payment)
            else:
                activate_subscription(payment)
            logger.info(
                "M-Pesa payment SUCCESS: user=%s kind=%s amount=%s receipt=%s",
                payment.user.email,
                payment.payment_kind,
                payment.amount,
                payment.receipt_number,
            )
        else:
            payment.status = MpesaPayment.Status.FAILED
            payment.result_code = parsed["result_code"]
            payment.result_desc = parsed["result_desc"]
            logger.warning(
                "M-Pesa payment FAILED: user=%s code=%s desc=%s",
                payment.user.email, parsed["result_code"], parsed["result_desc"],
            )

        payment.save()

    # Side-effects fire only after the transaction commits — sending the
    # confirmation email mid-transaction would leak through if a later
    # rollback fired. ``transaction.on_commit`` would be cleaner, but
    # placing the email here (post-atomic block) is equivalent and avoids
    # closure capture surprises.
    if succeeded and not payment.is_campaign_addon:
        from apps.messaging.emails.tasks import send_payment_confirmation_email
        send_payment_confirmation_email.delay(
            str(payment.user.pk),
            payment.plan_tier,
            str(payment.amount),
            "mpesa",
        )

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

    from apps.core.billing.campaign_renewal import maybe_grandfather_to_kova, sync_campaign_bonus_totals

    maybe_grandfather_to_kova(profile, on_renewal=payment.is_renewal)
    sync_campaign_bonus_totals(profile, reason="mpesa_renewal")

    logger.info(
        "Subscription activated: user=%s plan=%s period=%s to %s",
        payment.user.email, payment.plan_tier,
        period_start.strftime("%Y-%m-%d"), period_end.strftime("%Y-%m-%d"),
    )

    from apps.core.partners.referral_billing import record_referral_payment_safe
    record_referral_payment_safe(payment.user, payment.plan_tier, payment.amount)


def activate_trial(user, plan_tier, phone_number):
    """
    Activate a free trial for a plan (no payment required).

    Trial length is defined by MPESA_TRIAL_DAYS setting (default 7).
    During trial, feature limits match Kazi (growth) via get_effective_plan_tier().
    """
    formatted_phone = format_phone_number(phone_number)
    trial_days = getattr(settings, "MPESA_TRIAL_DAYS", 7)
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

    Called when payment is overdue past the 3-day grace period. To avoid
    cascading publish failures (where every queued post hits a plan-limit
    error at publish time and the user sees a wall of red notifications),
    we pause future-scheduled posts back to PENDING_APPROVAL. The user's
    content isn't lost — they can re-approve once they renew or accept
    being on Starter.
    """
    profile = user.profile
    profile.plan = "starter"
    profile.subscription_status = "canceled"
    profile.save(update_fields=["plan", "subscription_status"])

    paused = _pause_scheduled_posts_on_downgrade(user)
    logger.info(
        "Subscription expired: user=%s reverted to starter (paused %d scheduled posts)",
        user.email, paused,
    )


def _pause_scheduled_posts_on_downgrade(user) -> int:
    """Move APPROVED/SCHEDULED posts with a future scheduled_at back to
    PENDING_APPROVAL so they don't fail at publish time on the new plan.

    Returns the number of posts paused. Best-effort — any failure here is
    logged but never re-raised, since the downgrade itself has already
    committed and a swallowed pause is far better than a stuck rollback.
    """
    try:
        from apps.create.content.models import Post
        from apps.messaging.notifications.models import Notification

        now = timezone.now()
        future_scheduled = Post.objects.filter(
            user=user,
            status__in=[Post.Status.APPROVED, Post.Status.SCHEDULED],
            scheduled_at__gt=now,
        )
        count = future_scheduled.count()
        if not count:
            return 0

        future_scheduled.update(
            status=Post.Status.PENDING_APPROVAL,
            ai_reasoning=(
                "Paused: subscription expired and was downgraded to Starter. "
                "Renew your plan or re-approve to schedule again."
            ),
            updated_at=now,
        )
        try:
            Notification.create_for_user(
                user, "system",
                f"{count} scheduled posts were paused after your subscription "
                f"expired. Renew your plan to keep autopublishing.",
            )
        except Exception:
            pass  # Notifications are best-effort; don't break the pause flow.
        return count
    except Exception as exc:
        logger.exception(
            "Failed to pause scheduled posts on downgrade for %s: %s",
            user.email, exc,
        )
        return 0
