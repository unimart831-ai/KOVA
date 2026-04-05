import logging

from allauth.account.signals import user_signed_up
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(user_signed_up)
def link_referral_on_signup(sender, request, user, **kwargs):
    """
    When a new user signs up, check for a referral code (cookie or POST param)
    and create a Referral record linking them to the partner.
    """
    from apps.partners.models import Partner, Referral

    # Check POST data first (hidden field), then cookie
    ref_code = request.POST.get("ref_code", "").strip()
    if not ref_code:
        ref_code = request.COOKIES.get("kova_ref", "").strip()

    if not ref_code:
        return

    try:
        partner = Partner.objects.get(referral_code=ref_code, is_active=True)
    except Partner.DoesNotExist:
        logger.warning("Referral code '%s' not found or inactive", ref_code)
        return

    # Prevent self-referral
    if partner.user_id == user.pk:
        logger.warning("Self-referral attempt: user %s with code %s", user.pk, ref_code)
        return

    # Prevent duplicate referrals
    if Referral.objects.filter(referred_user=user).exists():
        return

    Referral.objects.create(
        partner=partner,
        referred_user=user,
        referral_code_used=ref_code,
    )
    logger.info(
        "Referral created: %s → partner %s (%s)",
        user.email,
        partner.referral_code,
        partner.user.email,
    )

    # Notify the partner via email (async)
    try:
        from apps.emails.tasks import send_partner_new_referral_email
        send_partner_new_referral_email.delay(
            str(partner.user.pk),
            user.email,
            partner.total_referrals_count,
        )
    except Exception:
        pass  # Don't break signup if email fails


@receiver(user_signed_up)
def auto_link_partner_application(sender, request, user, **kwargs):
    """
    When a new user signs up, check if there's an approved PartnerApplication
    with the same email. If so, link the application to this user and
    auto-create the Partner record so they can access their dashboard.
    """
    from apps.partners.models import Partner, PartnerApplication, generate_referral_code

    # Only proceed if user doesn't already have a partner profile
    if Partner.objects.filter(user=user).exists():
        return

    # Find approved application matching this email (not yet linked to a user)
    application = (
        PartnerApplication.objects
        .filter(email__iexact=user.email, status="approved", user__isnull=True)
        .first()
    )
    if not application:
        return

    # Link application to user
    application.user = user
    application.save(update_fields=["user"])

    # Create Partner record
    name = application.full_name or user.email.split("@")[0]
    partner = Partner.objects.create(
        user=user,
        application=application,
        referral_code=generate_referral_code(name),
    )
    logger.info(
        "Auto-linked partner application for %s → partner %s",
        user.email,
        partner.referral_code,
    )
