"""
Stripe billing service — all Stripe API interaction lives here.

Functions:
    get_or_create_customer() — Ensure user has a Stripe customer record
    create_checkout_session() — Start a subscription checkout
    create_portal_session()  — Let user manage billing in Stripe's hosted portal
    handle_webhook_event()   — Process Stripe webhook events
    sync_subscription()      — Sync subscription state from Stripe to DB
"""

import logging
from datetime import datetime, timezone as dt_tz

import stripe
from django.conf import settings
from django.urls import reverse

from apps.core.billing.models import BillingEvent, PUBLIC_PLAN_TIERS, get_plan_limits

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY

PLAN_PRICE_MAP = {
    "kova": settings.STRIPE_PRICE_KOVA,
    "starter": settings.STRIPE_PRICE_STARTER,
    "growth": settings.STRIPE_PRICE_GROWTH,
    "pro": settings.STRIPE_PRICE_PRO,
    "agency": settings.STRIPE_PRICE_AGENCY,
}

ADDON_PRICE_MAP = {
    "boost": settings.STRIPE_PRICE_ADDON_BOOST,
    "scale": settings.STRIPE_PRICE_ADDON_SCALE,
    "burst": settings.STRIPE_PRICE_ADDON_BURST,
}

# Reverse lookup: Stripe Price ID → plan tier
PRICE_PLAN_MAP = {v: k for k, v in PLAN_PRICE_MAP.items() if v}


def get_or_create_customer(user):
    """Ensure user has a Stripe Customer. Returns customer ID string."""
    profile = user.profile
    if profile.stripe_customer_id:
        return profile.stripe_customer_id

    customer = stripe.Customer.create(
        email=user.email,
        name=user.full_name or user.username,
        metadata={"kova_user_id": str(user.id)},
    )
    profile.stripe_customer_id = customer.id
    profile.save(update_fields=["stripe_customer_id"])
    logger.info("Created Stripe customer %s for user %s", customer.id, user.email)
    return customer.id


def create_checkout_session(user, plan_tier, request):
    """Create Stripe Checkout Session for a subscription.

    Returns the Checkout Session object (use .url to redirect).
    """
    if plan_tier not in PUBLIC_PLAN_TIERS:
        raise ValueError(f"Invalid plan tier: {plan_tier}")

    price_id = PLAN_PRICE_MAP.get(plan_tier)
    if not price_id:
        raise ValueError(f"No Stripe Price ID configured for plan: {plan_tier}")

    customer_id = get_or_create_customer(user)
    plan_limits = get_plan_limits(plan_tier)
    trial_days = plan_limits.get("trial_days", 7)

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=request.build_absolute_uri(
            reverse("billing:checkout_success")
        ) + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=request.build_absolute_uri(reverse("billing:checkout_cancel")),
        subscription_data={
            "trial_period_days": trial_days,
            "metadata": {"kova_user_id": str(user.id), "plan_tier": plan_tier},
        },
        metadata={"kova_user_id": str(user.id), "plan_tier": plan_tier},
        allow_promotion_codes=True,
    )
    logger.info("Created checkout session %s for user %s (plan: %s)", session.id, user.email, plan_tier)
    return session


def create_addon_checkout_session(user, pack_id: str, request):
    """Stripe Checkout for campaign add-on packs."""
    from apps.core.billing.campaign_addons import get_addon_pack, user_can_purchase_addons
    from apps.core.billing.models import CAMPAIGN_ADDON_PACKS

    if pack_id not in CAMPAIGN_ADDON_PACKS:
        raise ValueError(f"Unknown add-on pack: {pack_id}")

    allowed, msg = user_can_purchase_addons(user)
    if not allowed:
        raise ValueError(msg)

    price_id = ADDON_PRICE_MAP.get(pack_id)
    if not price_id:
        raise ValueError(f"No Stripe Price ID configured for add-on: {pack_id}")

    pack = get_addon_pack(pack_id)
    customer_id = get_or_create_customer(user)
    mode = "subscription" if pack.get("recurring") else "payment"

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode=mode,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=request.build_absolute_uri(
            reverse("billing:checkout_success")
        ) + "?session_id={CHECKOUT_SESSION_ID}&addon=1",
        cancel_url=request.build_absolute_uri(reverse("billing:pricing")),
        metadata={
            "kova_user_id": str(user.id),
            "addon_pack_id": pack_id,
            "payment_kind": "campaign_addon",
        },
        allow_promotion_codes=True,
    )
    logger.info("Stripe add-on checkout %s for user %s pack=%s", session.id, user.email, pack_id)
    return session


def create_portal_session(user, request):
    """Create Stripe Customer Portal session for self-service billing management."""
    customer_id = get_or_create_customer(user)

    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=request.build_absolute_uri(reverse("billing:overview")),
    )
    return session


def sync_subscription(user, subscription_id=None):
    """Sync Stripe subscription state to UserProfile.

    If subscription_id is given, fetch that. Otherwise use stored ID.
    """
    profile = user.profile
    sub_id = subscription_id or profile.stripe_subscription_id
    if not sub_id:
        return

    try:
        sub = stripe.Subscription.retrieve(sub_id)
    except stripe.error.InvalidRequestError:
        logger.warning("Subscription %s not found in Stripe", sub_id)
        return

    # Determine plan tier from Stripe Price ID
    price_id = sub["items"]["data"][0]["price"]["id"] if sub["items"]["data"] else ""
    plan_tier = PRICE_PLAN_MAP.get(price_id, profile.plan)

    profile.stripe_subscription_id = sub.id
    profile.plan = plan_tier
    profile.payment_provider = "stripe"
    profile.subscription_status = sub.status  # active, trialing, past_due, canceled, etc.
    profile.current_period_end = datetime.fromtimestamp(
        sub.current_period_end, tz=dt_tz.utc
    )
    if sub.trial_end:
        profile.trial_ends_at = datetime.fromtimestamp(sub.trial_end, tz=dt_tz.utc)
    profile.save(update_fields=[
        "stripe_subscription_id", "plan", "payment_provider", "subscription_status",
        "current_period_end", "trial_ends_at",
    ])
    logger.info("Synced subscription %s → plan=%s status=%s", sub.id, plan_tier, sub.status)


def handle_webhook_event(event):
    """Process a verified Stripe webhook event. Returns True if processed.

    Idempotency: uses an atomic get_or_create against stripe_event_id
    (unique=True) to race-protect against simultaneous webhook retries.
    The old pattern (exists() check then later save()) had a ~handler-runtime
    window where duplicate emails / side-effects could fire.
    """
    billing_event, created = BillingEvent.objects.get_or_create(
        stripe_event_id=event.id,
        defaults={
            "event_type": event.type,
            "data": event.data.get("object", {}),
            "provider": "stripe",
        },
    )
    if not created:
        logger.info("Duplicate webhook event %s, skipping", event.id)
        return True

    try:
        handler = EVENT_HANDLERS.get(event.type)
        if handler:
            handler(event, billing_event)
            billing_event.processed = True
        else:
            logger.debug("Unhandled event type: %s", event.type)
            billing_event.processed = True  # Acknowledge even if we don't handle it

        billing_event.save()
        return True

    except Exception as e:
        logger.exception("Webhook processing failed for %s: %s", event.id, e)
        billing_event.error_message = str(e)
        billing_event.save()
        return False


# ─── Event Handlers ──────────────────────────────────────────────────────────

def _find_user_from_customer(customer_id):
    """Look up a Kova user by their Stripe customer ID."""
    from apps.core.accounts.models import UserProfile
    try:
        return UserProfile.objects.select_related("user").get(
            stripe_customer_id=customer_id,
        ).user
    except UserProfile.DoesNotExist:
        logger.warning("No user found for Stripe customer %s", customer_id)
        return None


def _handle_checkout_completed(event, billing_event):
    """checkout.session.completed — User finished the checkout flow."""
    session = event.data.object
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")

    user = _find_user_from_customer(customer_id)
    if user:
        billing_event.user = user
        if subscription_id:
            sync_subscription(user, subscription_id)
        addon_pack = session.get("metadata", {}).get("addon_pack_id")
        if addon_pack:
            from apps.core.billing.campaign_addons import get_addon_pack
            from apps.core.billing.campaign_renewal import apply_addon_purchase_bonus

            pack = get_addon_pack(addon_pack)
            if pack:
                apply_addon_purchase_bonus(user.profile, pack)
        logger.info("Checkout completed for user %s", user.email)

        # Send payment confirmation email
        from apps.messaging.emails.tasks import send_payment_confirmation_email
        send_payment_confirmation_email.delay(
            str(user.pk),
            user.profile.get_plan_display(),
            str(session.get("amount_total", 0) / 100),
            "stripe",
        )


def _handle_subscription_updated(event, billing_event):
    """customer.subscription.updated — Plan change, renewal, trial end, etc."""
    sub = event.data.object
    customer_id = sub.get("customer")

    user = _find_user_from_customer(customer_id)
    if user:
        billing_event.user = user
        old_plan = user.profile.plan
        sync_subscription(user, sub["id"])
        user.profile.refresh_from_db()
        new_plan = user.profile.plan

        if old_plan != new_plan:
            from apps.messaging.emails.tasks import send_plan_changed_email
            send_plan_changed_email.delay(str(user.pk), old_plan, new_plan)


def _handle_subscription_deleted(event, billing_event):
    """customer.subscription.deleted — Subscription canceled/expired."""
    sub = event.data.object
    customer_id = sub.get("customer")

    user = _find_user_from_customer(customer_id)
    if user:
        billing_event.user = user
        profile = user.profile
        profile.plan = "kova"
        profile.subscription_status = "canceled"
        profile.payment_provider = "none"
        profile.stripe_subscription_id = ""
        profile.save(update_fields=["plan", "subscription_status", "payment_provider", "stripe_subscription_id"])
        logger.info("Subscription canceled for user %s, reverted to starter", user.email)

        # Send cancellation email
        from apps.messaging.emails.tasks import send_subscription_canceled_email
        send_subscription_canceled_email.delay(str(user.pk))


def _handle_invoice_paid(event, billing_event):
    """invoice.paid — Successful payment."""
    invoice = event.data.object
    customer_id = invoice.get("customer")

    user = _find_user_from_customer(customer_id)
    if user:
        billing_event.user = user
        # Sync in case plan changed
        sub_id = invoice.get("subscription")
        if sub_id:
            sync_subscription(user, sub_id)

        from apps.core.billing.campaign_renewal import maybe_grandfather_to_kova, sync_campaign_bonus_totals

        profile = user.profile
        maybe_grandfather_to_kova(profile, on_renewal=True)
        sync_campaign_bonus_totals(profile, reason="stripe_invoice_paid")

        # Send receipt email
        from apps.messaging.emails.tasks import send_email_task
        send_email_task.delay(
            email_type="receipt",
            to_email=user.email,
            context={
                "first_name": user.first_name,
                "plan": user.profile.get_plan_display(),
                "amount": str((invoice.get("amount_paid", 0) or 0) / 100),
                "receipt_number": invoice.get("number", ""),
                "payment_date": invoice.get("status_transitions", {}).get("paid_at", ""),
            },
            user_id=str(user.pk),
        )

        from decimal import Decimal
        # Partner referral commissions removed from V1 billing path.


def _handle_invoice_failed(event, billing_event):
    """invoice.payment_failed — Payment failed (card declined, etc.)."""
    invoice = event.data.object
    customer_id = invoice.get("customer")

    user = _find_user_from_customer(customer_id)
    if user:
        billing_event.user = user
        profile = user.profile
        profile.subscription_status = "past_due"
        profile.save(update_fields=["subscription_status"])
        logger.warning("Payment failed for user %s", user.email)

        # Send payment failed email
        from apps.messaging.emails.tasks import send_payment_failed_email
        send_payment_failed_email.delay(str(user.pk))


EVENT_HANDLERS = {
    "checkout.session.completed": _handle_checkout_completed,
    "customer.subscription.updated": _handle_subscription_updated,
    "customer.subscription.deleted": _handle_subscription_deleted,
    "invoice.paid": _handle_invoice_paid,
    "invoice.payment_failed": _handle_invoice_failed,
}
