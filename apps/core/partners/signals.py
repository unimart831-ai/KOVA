import logging

from allauth.account.signals import user_signed_up
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(user_signed_up)
def link_referral_on_signup(sender, request, user, **kwargs):
    """
    When a new user signs up, check for a referral code (cookie or POST param)
    and create a Referral record linking them to the partner.

    Anti-fraud checks:
      1. Self-referral prevention (partner can't refer themselves)
      2. Duplicate referral prevention (user can only be referred once)
      3. IP-based sybil detection (flag if same IP referred multiple times)
      4. Email domain clustering (flag disposable/same-domain patterns)
    """
    from apps.core.partners.models import Partner, Referral

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

    # Anti-fraud check 1: Prevent self-referral
    if partner.user_id == user.pk:
        logger.warning("Self-referral attempt: user %s with code %s", user.pk, ref_code)
        return

    # Anti-fraud check 2: Prevent duplicate referrals
    if Referral.objects.filter(referred_user=user).exists():
        return

    # Anti-fraud check 3: IP-based sybil detection
    client_ip = (
        request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
        or request.META.get("REMOTE_ADDR", "")
    )
    is_flagged = False
    flag_reason = ""

    if client_ip:
        # Count how many referrals from this IP in the last 30 days
        from datetime import timedelta
        from django.utils import timezone as tz

        recent_same_ip = Referral.objects.filter(
            partner=partner,
            signup_ip=client_ip,
            signed_up_at__gte=tz.now() - timedelta(days=30),
        ).count()

        if recent_same_ip >= 3:
            is_flagged = True
            flag_reason = f"Same IP ({client_ip}) used for {recent_same_ip + 1} referrals in 30 days"
            logger.warning(
                "SYBIL ALERT: Partner %s — %s", partner.referral_code, flag_reason
            )

    # Anti-fraud check 4: Email domain clustering
    email_domain = user.email.split("@")[-1].lower() if user.email else ""
    DISPOSABLE_DOMAINS = {
        "tempmail.com", "throwaway.email", "guerrillamail.com", "mailinator.com",
        "yopmail.com", "10minutemail.com", "trashmail.com", "fakeinbox.com",
        "sharklasers.com", "guerrillamailblock.com", "grr.la", "dispostable.com",
    }
    if email_domain in DISPOSABLE_DOMAINS:
        is_flagged = True
        flag_reason += f"; Disposable email domain: {email_domain}"
        logger.warning("SYBIL ALERT: Disposable email %s for partner %s", user.email, partner.referral_code)

    # Check for same-domain clustering (>5 referrals from same domain)
    if email_domain and email_domain not in ("gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com"):
        from django.db.models import Q
        same_domain_count = Referral.objects.filter(
            partner=partner,
            referred_user__email__iendswith=f"@{email_domain}",
        ).count()
        if same_domain_count >= 5:
            is_flagged = True
            flag_reason += f"; {same_domain_count + 1} referrals from @{email_domain}"

    Referral.objects.create(
        partner=partner,
        referred_user=user,
        referral_code_used=ref_code,
        signup_ip=client_ip,
        is_flagged=is_flagged,
        flag_reason=flag_reason.strip("; "),
    )
    logger.info(
        "Referral created: %s → partner %s (%s)%s",
        user.email,
        partner.referral_code,
        partner.user.email,
        " [FLAGGED]" if is_flagged else "",
    )

    # Notify the partner via email (async)
    try:
        from apps.messaging.emails.tasks import send_partner_new_referral_email
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
    from apps.core.partners.models import Partner, PartnerApplication, generate_referral_code

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
