"""Agency sales inquiry notifications."""

import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def _staff_recipients():
    """Active superuser emails for new inquiry alerts."""
    from apps.accounts.models import User

    emails = list(
        User.objects.filter(is_superuser=True, is_active=True)
        .exclude(email="")
        .values_list("email", flat=True)[:10]
    )
    override = getattr(settings, "AGENCY_SALES_NOTIFY_EMAIL", "").strip()
    if override and override not in emails:
        emails.insert(0, override)
    return emails


def notify_staff_new_inquiry(inquiry):
    """Email staff on new agency sales inquiry; fail silently if mail unavailable."""
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)
    if not from_email:
        return

    recipients = _staff_recipients()
    if not recipients:
        return

    subject = f"[Kova] New Agency sales inquiry — {inquiry.company_name or inquiry.name}"
    body_lines = [
        f"Name: {inquiry.name}",
        f"Email: {inquiry.email}",
        f"Phone: {inquiry.phone or '—'}",
        f"Company: {inquiry.company_name or '—'}",
        f"Clients: {inquiry.client_count if inquiry.client_count is not None else '—'}",
        f"Plan interest: {inquiry.plan_interest or '—'}",
        "",
        inquiry.message,
        "",
        f"Dashboard: /dashboard/billing/sales-inquiries/{inquiry.pk}/",
    ]
    if inquiry.user_id:
        body_lines.insert(5, f"Kova user: {inquiry.user.email}")

    try:
        send_mail(
            subject=subject,
            message="\n".join(body_lines),
            from_email=from_email,
            recipient_list=recipients,
            fail_silently=True,
        )
    except Exception as exc:
        logger.warning("Agency sales inquiry email failed: %s", exc)
