"""
Billing tasks — subscription lifecycle management.

Tasks:
    check_mpesa_subscriptions: Runs daily. Handles:
        1. Trial expiry → remind or downgrade
        2. Subscription expiry → send renewal STK push or downgrade
        3. Expire stale pending payments (> 5 min old)
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="billing.check_mpesa_subscriptions")
def check_mpesa_subscriptions():
    """
    Check all M-Pesa subscriptions for expiry, trials, and renewals.

    Runs daily via Celery Beat. Handles:
    - Expire stale pending payments (> 5 min, no callback)
    - Warn users 3 days before subscription ends
    - Downgrade expired subscriptions after 3-day grace period
    """
    from apps.accounts.models import UserProfile
    from apps.billing.models import MpesaPayment
    from apps.billing.mpesa_services import expire_subscription

    now = timezone.now()
    actions = {"expired_payments": 0, "expired_subs": 0, "warnings": 0}

    # ── 1. Poll stale pending payments before expiring ──
    # Instead of blindly expiring, query M-Pesa for the real status first.
    # The callback might have failed to arrive even though the user paid.
    stale_cutoff = now - timedelta(minutes=5)
    stale_payments = MpesaPayment.objects.filter(
        status=MpesaPayment.Status.PENDING,
        created_at__lt=stale_cutoff,
    )
    for payment in stale_payments:
        try:
            from apps.billing.mpesa import query_stk_push
            result = query_stk_push(payment.checkout_request_id)
            result_code = result.get("ResultCode")

            if result_code is not None and int(result_code) == 0:
                # User actually paid! Process it as if callback arrived.
                logger.info(
                    "M-Pesa poll recovered payment: checkout=%s user=%s",
                    payment.checkout_request_id, payment.user.email,
                )
                from apps.billing.mpesa_services import activate_subscription
                payment.status = MpesaPayment.Status.COMPLETED
                payment.result_code = 0
                payment.result_desc = "Recovered via status polling"
                payment.completed_at = now
                payment.save()
                activate_subscription(payment)
                actions.setdefault("recovered_payments", 0)
                actions["recovered_payments"] += 1
                continue
        except Exception as exc:
            logger.warning(
                "M-Pesa status poll failed for %s: %s",
                payment.checkout_request_id, exc,
            )

        # If poll failed or payment wasn't completed, expire it
        payment.status = MpesaPayment.Status.EXPIRED
        payment.save(update_fields=["status"])
        actions["expired_payments"] += 1

    # ── 2. Handle expiring/expired M-Pesa subscriptions ──
    mpesa_profiles = UserProfile.objects.filter(
        payment_provider="mpesa",
        subscription_status__in=("active", "trialing"),
        current_period_end__isnull=False,
    ).select_related("user")

    for profile in mpesa_profiles:
        days_until_expiry = (profile.current_period_end - now).days

        if days_until_expiry < -3:
            # Grace period expired — downgrade to starter
            expire_subscription(profile.user)
            actions["expired_subs"] += 1
            logger.info("Subscription expired (past grace): user=%s", profile.user.email)

        elif days_until_expiry < 0:
            # Expired but within 3-day grace period — mark as past_due
            if profile.subscription_status != "past_due":
                profile.subscription_status = "past_due"
                profile.save(update_fields=["subscription_status"])
                logger.info("Subscription past due: user=%s", profile.user.email)
                # Send notification — subscription expired, renew to keep plan
                from apps.emails.tasks import send_payment_reminder_email
                send_payment_reminder_email.delay(str(profile.user.pk), 0)

        elif days_until_expiry <= 3:
            # 3 days or less until expiry — send reminder
            actions["warnings"] += 1
            logger.info(
                "Subscription expiring soon: user=%s days=%d",
                profile.user.email, days_until_expiry,
            )
            # Send reminder — plan expiring soon
            from apps.emails.tasks import send_payment_reminder_email
            send_payment_reminder_email.delay(str(profile.user.pk), days_until_expiry)

    logger.info(
        "M-Pesa subscription check: expired_payments=%d expired_subs=%d warnings=%d",
        actions["expired_payments"], actions["expired_subs"], actions["warnings"],
    )
    return actions
