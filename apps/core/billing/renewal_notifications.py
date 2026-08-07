"""M-Pesa subscription renewal warnings — email + in-app (+ optional WA digest)."""

from __future__ import annotations

import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)


def send_mpesa_renewal_warning(user, days_until_expiry: int) -> bool:
    """
    Send renewal warning once per day per expiry tier.
    Returns True if a notification was sent.
    """
    from apps.messaging.emails.tasks import send_payment_reminder_email
    from apps.messaging.notifications.models import Notification

    cache_key = f"mpesa_renewal_warn:{user.pk}:{days_until_expiry}"
    if cache.get(cache_key):
        return False

    if days_until_expiry <= 0:
        message = (
            "Your M-Pesa plan has expired. Renew within 3 days to keep your "
            f"{user.profile.get_plan_display()} features."
        )
    elif days_until_expiry == 1:
        message = "Your M-Pesa plan expires tomorrow. Renew now to avoid interruption."
    else:
        message = (
            f"Your M-Pesa plan expires in {days_until_expiry} days. "
            "Renew from Billing to keep your plan active."
        )

    Notification.create_for_user(
        user,
        Notification.NotificationType.SYSTEM,
        message,
    )
    send_payment_reminder_email.delay(str(user.pk), days_until_expiry)
    cache.set(cache_key, 1, 86400)
    logger.info(
        "M-Pesa renewal warning sent: user=%s days=%d",
        user.email,
        days_until_expiry,
    )
    return True
