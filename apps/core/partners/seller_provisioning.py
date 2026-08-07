"""Post-provision hooks for marketplace sellers — webhooks and welcome email."""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass, field

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.db import IntegrityError
from django.utils import timezone

from apps.core.accounts.models import User
from apps.core.partners.models import MarketplacePartner, MarketplaceSellerAccount

logger = logging.getLogger(__name__)


def build_password_reset_url(user) -> str:
    from allauth.account.utils import user_pk_to_url_str

    site_url = getattr(settings, "SITE_URL", "https://kovaagent.com").rstrip("/")
    uid = user_pk_to_url_str(user)
    token = default_token_generator.make_token(user)
    return f"{site_url}/accounts/password/reset/key/{uid}-{token}/"


@dataclass
class SellerProvisionResult:
    """Outcome of provisioning one marketplace seller."""

    ok: bool
    status: str
    external_seller_id: str
    http_status: int = 201
    email: str = ""
    business_name: str = ""
    seller_status: str = ""
    plan: str = ""
    auto_activated: bool = False
    error: str = ""
    errors: dict = field(default_factory=dict)


def _find_or_create_user(mp: MarketplacePartner, data: dict, ext_id: str) -> User | None:
    identity_field = mp.seller_identity_field

    if identity_field == "email" and data.get("email"):
        user = User.objects.filter(email__iexact=data["email"]).first()
        if not user:
            user = User.objects.create_user(
                email=data["email"],
                username=data["email"],
                password=secrets.token_urlsafe(16),
                full_name=data.get("full_name", ""),
            )
        return user

    if identity_field == "phone" and data.get("phone"):
        user = User.objects.filter(phone_number=data["phone"]).first()
        if not user:
            placeholder_email = f"{ext_id}@{mp.slug}.marketplace.kova.co.ke"
            user = User.objects.create_user(
                email=placeholder_email,
                username=placeholder_email,
                password=secrets.token_urlsafe(16),
                full_name=data.get("full_name", ""),
                phone_number=data["phone"],
            )
        return user

    if identity_field == "external_id":
        linked = MarketplaceSellerAccount.objects.filter(
            marketplace=mp, external_seller_id=ext_id,
        ).select_related("user").first()
        if linked:
            return linked.user
        if data.get("email"):
            user = User.objects.filter(email__iexact=data["email"]).first()
            if user:
                return user
        email = data.get("email") or f"{ext_id}@{mp.slug}.marketplace.kova.co.ke"
        return User.objects.create_user(
            email=email,
            username=email,
            password=secrets.token_urlsafe(16),
            full_name=data.get("full_name", ""),
        )

    return None


def _build_seller_metadata(mp: MarketplacePartner, data: dict) -> dict:
    enriched_metadata = dict(data.get("seller_metadata") or {})
    if data.get("business_description"):
        enriched_metadata["business_description"] = data["business_description"]
    if data.get("location"):
        enriched_metadata["location"] = data["location"]
    if mp.seller_data_mapping:
        for src_key, dst_key in mp.seller_data_mapping.items():
            if src_key in enriched_metadata:
                enriched_metadata[dst_key] = enriched_metadata.pop(src_key)
    return enriched_metadata


def provision_marketplace_seller(mp: MarketplacePartner, data: dict) -> SellerProvisionResult:
    """
    Provision one seller for a marketplace partner.

    Returns a SellerProvisionResult with ok/status/http_status for API responses.
    """
    ext_id = data["external_seller_id"]

    existing = mp.seller_accounts.filter(external_seller_id=ext_id).first()
    if existing:
        return SellerProvisionResult(
            ok=True,
            status="already_exists",
            external_seller_id=ext_id,
            http_status=200,
            email=existing.user.email,
            business_name=existing.business_name,
            seller_status=existing.status,
            plan=existing.user.profile.plan,
            auto_activated=mp.auto_activate_sellers,
        )

    if not mp.can_provision_sellers:
        return SellerProvisionResult(
            ok=False,
            status="limit_reached",
            external_seller_id=ext_id,
            http_status=403,
            error=f"Seller limit reached ({mp.max_sellers}). Contact Kova to increase.",
        )

    user = _find_or_create_user(mp, data, ext_id)
    if not user:
        return SellerProvisionResult(
            ok=False,
            status="user_error",
            external_seller_id=ext_id,
            http_status=400,
            error="Could not create or find user for this seller.",
        )

    profile = user.profile
    profile.plan = mp.seller_default_plan
    profile.save(update_fields=["plan"])

    seller_status = (
        MarketplaceSellerAccount.Status.ACTIVE
        if mp.auto_activate_sellers
        else MarketplaceSellerAccount.Status.INVITED
    )

    try:
        seller = MarketplaceSellerAccount.objects.create(
            marketplace=mp,
            user=user,
            external_seller_id=ext_id,
            status=seller_status,
            business_name=data.get("business_name", ""),
            business_url=data.get("business_url", ""),
            seller_metadata=_build_seller_metadata(mp, data),
            activated_at=timezone.now() if mp.auto_activate_sellers else None,
        )
    except IntegrityError:
        return SellerProvisionResult(
            ok=False,
            status="conflict",
            external_seller_id=ext_id,
            http_status=409,
            error=f"Seller {ext_id} already linked to a different user in this marketplace.",
        )

    if seller.status == MarketplaceSellerAccount.Status.ACTIVE:
        on_seller_activated(mp, seller, auto_activated=mp.auto_activate_sellers)

    return SellerProvisionResult(
        ok=True,
        status="provisioned",
        external_seller_id=ext_id,
        http_status=201,
        email=user.email,
        business_name=seller.business_name,
        seller_status=seller.status,
        plan=profile.plan,
        auto_activated=mp.auto_activate_sellers,
    )


def provision_result_to_response(result: SellerProvisionResult) -> dict:
    """Serialize a provision result for Partner API JSON responses."""
    if not result.ok:
        payload = {"status": result.status, "external_seller_id": result.external_seller_id}
        if result.error:
            payload["error"] = result.error
        if result.errors:
            payload["errors"] = result.errors
        return payload

    payload = {
        "status": result.status,
        "external_seller_id": result.external_seller_id,
        "email": result.email,
        "business_name": result.business_name,
        "seller_status": result.seller_status,
        "plan": result.plan,
        "auto_activated": result.auto_activated,
    }
    return payload


def on_seller_activated(mp, seller, *, auto_activated: bool = False, send_welcome: bool | None = None):
    """
    Fire seller.activated webhook and optional welcome email after provision/activate.
    """
    from apps.core.partners.webhooks import notify_seller_activated

    notify_seller_activated(mp, seller, auto_activated=auto_activated)

    should_welcome = mp.seller_welcome_email if send_welcome is None else send_welcome
    if not should_welcome:
        return

    try:
        from apps.messaging.emails.tasks import send_marketplace_seller_welcome_email

        branding = (mp.settings or {}).get("branding", {})
        send_marketplace_seller_welcome_email.delay(
            str(seller.user.pk),
            mp.name,
            mp.slug,
            branding,
        )
    except Exception:
        logger.exception(
            "Failed to queue seller welcome email for %s @ %s",
            seller.external_seller_id,
            mp.slug,
        )
