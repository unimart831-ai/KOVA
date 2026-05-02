"""
Billing tasks — subscription lifecycle management.

Tasks:
    check_mpesa_subscriptions: Runs daily. Handles:
        1. Trial expiry → remind or downgrade
        2. Subscription expiry → send renewal STK push or downgrade
        3. Expire stale pending payments (> 5 min old)
        4. Reconciliation sweep: re-poll recently-EXPIRED payments in
           case our poll itself failed and the user actually paid.
"""

import logging
from datetime import timedelta

import sentry_sdk
from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.utils.locks import single_run

logger = logging.getLogger(__name__)


def _try_recover_payment(payment, reason: str):
    """Poll M-Pesa for the true status of a payment and activate if paid.

    Returns True if the payment was recovered (i.e. M-Pesa confirms it
    succeeded and we activated the subscription). False otherwise.

    Used both for expiring stale-pending payments and for the
    reconciliation sweep over recently-EXPIRED payments.
    """
    from apps.billing.models import MpesaPayment
    from apps.billing.mpesa import query_stk_push
    from apps.billing.mpesa_services import activate_subscription

    try:
        result = query_stk_push(payment.checkout_request_id)
    except Exception as exc:
        logger.warning(
            "M-Pesa status poll failed for %s: %s",
            payment.checkout_request_id, exc,
        )
        sentry_sdk.capture_exception(exc)
        return False

    result_code = result.get("ResultCode")
    if result_code is None or int(result_code) != 0:
        return False

    # M-Pesa says this payment succeeded. Promote it under a row lock so
    # we can't race a (late-arriving) real callback to activation.
    with transaction.atomic():
        locked = (
            MpesaPayment.objects
            .select_for_update()
            .select_related("user", "user__profile")
            .get(pk=payment.pk)
        )
        if locked.status == MpesaPayment.Status.COMPLETED:
            return False  # Some other path got here first.
        locked.status = MpesaPayment.Status.COMPLETED
        locked.result_code = 0
        locked.result_desc = f"Recovered via status polling ({reason})"
        locked.completed_at = timezone.now()
        locked.save(update_fields=[
            "status", "result_code", "result_desc", "completed_at",
        ])
        activate_subscription(locked)

    logger.info(
        "M-Pesa poll recovered payment (%s): checkout=%s user=%s",
        reason, payment.checkout_request_id, payment.user.email,
    )
    sentry_sdk.capture_message(
        f"M-Pesa orphan payment recovered ({reason}): "
        f"checkout={payment.checkout_request_id} user={payment.user.email}",
        level="info",
    )
    return True


@shared_task(
    name="billing.check_mpesa_subscriptions",
    soft_time_limit=15 * 60,
    time_limit=18 * 60,
    autoretry_for=(Exception,),
    retry_backoff=60,
    max_retries=2,
)
@single_run("billing.check_mpesa_subscriptions", timeout=20 * 60)
def check_mpesa_subscriptions():
    """
    Check all M-Pesa subscriptions for expiry, trials, and renewals.

    Runs daily via Celery Beat. Handles:
    - Expire stale pending payments (> 5 min, no callback)
    - Reconciliation sweep over recently-EXPIRED payments (catches the
      case where our own poll failed earlier and the user did pay)
    - Warn users 3 days before subscription ends
    - Downgrade expired subscriptions after 3-day grace period
    """
    from apps.accounts.models import UserProfile
    from apps.billing.models import MpesaPayment
    from apps.billing.mpesa_services import expire_subscription

    now = timezone.now()
    actions = {
        "expired_payments": 0,
        "expired_subs": 0,
        "warnings": 0,
        "recovered_payments": 0,
        "reconciled_payments": 0,
    }

    # ── 1. Poll stale pending payments before expiring ──
    # Instead of blindly expiring, query M-Pesa for the real status first.
    # The callback might have failed to arrive even though the user paid.
    stale_cutoff = now - timedelta(minutes=5)
    stale_payments = MpesaPayment.objects.filter(
        status=MpesaPayment.Status.PENDING,
        created_at__lt=stale_cutoff,
    )
    for payment in stale_payments:
        if _try_recover_payment(payment, reason="stale_pending"):
            actions["recovered_payments"] += 1
            continue

        # If poll failed or payment wasn't completed, expire it.
        payment.status = MpesaPayment.Status.EXPIRED
        payment.save(update_fields=["status"])
        actions["expired_payments"] += 1

    # ── 1b. Reconciliation sweep ──
    # Re-poll payments expired in the last 24 hours. If our earlier poll
    # itself failed (Daraja 5xx, network timeout, rate limit), the user
    # was charged but we have no record of completion. Daraja's STK
    # Query API only works within ~24h of the original push, so the
    # window matches that.
    reconcile_cutoff = now - timedelta(hours=24)
    expired_recent = MpesaPayment.objects.filter(
        status=MpesaPayment.Status.EXPIRED,
        created_at__gte=reconcile_cutoff,
    )
    for payment in expired_recent:
        if _try_recover_payment(payment, reason="reconciliation_sweep"):
            actions["reconciled_payments"] += 1

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
