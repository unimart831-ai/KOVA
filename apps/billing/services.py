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

from apps.billing.models import BillingEvent, get_plan_limits

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY

# ─── Stripe Price ID mapping ────────────────────────────────────────────────
# These are set via env vars. Create Products + Prices in Stripe Dashboard first.
PLAN_PRICE_MAP = {
    "starter": settings.STRIPE_PRICE_STARTER,
    "growth": settings.STRIPE_PRICE_GROWTH,
    "pro": settings.STRIPE_PRICE_PRO,
    "agency": settings.STRIPE_PRICE_AGENCY,
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
    price_id = PLAN_PRICE_MAP.get(plan_tier)
    if not price_id:
        raise ValueError(f"No Stripe Price ID configured for plan: {plan_tier}")

    customer_id = get_or_create_customer(user)
    plan_limits = get_plan_limits(plan_tier)
    trial_days = plan_limits.get("trial_days", 14)

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
    profile.subscription_status = sub.status  # active, trialing, past_due, canceled, etc.
    profile.current_period_end = datetime.fromtimestamp(
        sub.current_period_end, tz=dt_tz.utc
    )
    if sub.trial_end:
        profile.trial_ends_at = datetime.fromtimestamp(sub.trial_end, tz=dt_tz.utc)
    profile.save(update_fields=[
        "stripe_subscription_id", "plan", "subscription_status",
        "current_period_end", "trial_ends_at",
    ])
    logger.info("Synced subscription %s → plan=%s status=%s", sub.id, plan_tier, sub.status)


def handle_webhook_event(event):
    """Process a verified Stripe webhook event. Returns True if processed."""

    # Idempotency: skip if already processed
    if BillingEvent.objects.filter(stripe_event_id=event.id).exists():
        logger.info("Duplicate webhook event %s, skipping", event.id)
        return True

    billing_event = BillingEvent(
        stripe_event_id=event.id,
        event_type=event.type,
        data=event.data.get("object", {}),
    )

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
    from apps.accounts.models import UserProfile
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
        logger.info("Checkout completed for user %s", user.email)


def _handle_subscription_updated(event, billing_event):
    """customer.subscription.updated — Plan change, renewal, trial end, etc."""
    sub = event.data.object
    customer_id = sub.get("customer")

    user = _find_user_from_customer(customer_id)
    if user:
        billing_event.user = user
        sync_subscription(user, sub["id"])


def _handle_subscription_deleted(event, billing_event):
    """customer.subscription.deleted — Subscription canceled/expired."""
    sub = event.data.object
    customer_id = sub.get("customer")

    user = _find_user_from_customer(customer_id)
    if user:
        billing_event.user = user
        profile = user.profile
        profile.plan = "starter"
        profile.subscription_status = "canceled"
        profile.stripe_subscription_id = ""
        profile.save(update_fields=["plan", "subscription_status", "stripe_subscription_id"])
        logger.info("Subscription canceled for user %s, reverted to starter", user.email)


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


EVENT_HANDLERS = {
    "checkout.session.completed": _handle_checkout_completed,
    "customer.subscription.updated": _handle_subscription_updated,
    "customer.subscription.deleted": _handle_subscription_deleted,
    "invoice.paid": _handle_invoice_paid,
    "invoice.payment_failed": _handle_invoice_failed,
}
