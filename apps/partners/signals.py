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
