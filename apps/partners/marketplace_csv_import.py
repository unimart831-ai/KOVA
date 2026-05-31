"""File-based marketplace seller and product import (no Partner API required)."""

from __future__ import annotations

import csv
import io
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import BinaryIO, TextIO

from django.utils import timezone

from apps.partners.models import MarketplacePartner, MarketplaceSellerAccount
from apps.partners.seller_provisioning import provision_marketplace_seller
from apps.products.marketplace_sync import apply_sync_images_to_product_data, trigger_marketplace_autopilot
from apps.products.models import Product

SELLER_CSV_COLUMNS = (
    "external_seller_id",
    "full_name",
    "email",
    "business_name",
    "business_url",
    "campus_codes",
    "business_description",
    "location",
)

PRODUCT_CSV_COLUMNS = (
    "external_seller_id",
    "external_id",
    "name",
    "description",
    "price",
    "image_url",
    "product_url",
    "category",
    "condition",
    "campus_codes",
    "stock_status",
    "quantity",
)

DEFAULT_USK_PATTERN = re.compile(r"^USK-[A-Za-z0-9-]+$", re.IGNORECASE)


@dataclass
class ImportSummary:
    """Aggregate result for CSV seller/product import."""

    provisioned: int = 0
    already_exists: int = 0
    failed: int = 0
    pending_added: int = 0
    products_created: int = 0
    products_updated: int = 0
    results: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "summary": {
                "provisioned": self.provisioned,
                "already_exists": self.already_exists,
                "failed": self.failed,
                "pending_added": self.pending_added,
                "products_created": self.products_created,
                "products_updated": self.products_updated,
            },
            "results": self.results,
            "errors": self.errors,
        }


def _normalize_header(name: str) -> str:
    return (name or "").strip().lower().replace(" ", "_")


def _read_csv_rows(source: str | TextIO | BinaryIO) -> list[dict[str, str]]:
    """Parse CSV from path, text stream, or uploaded file."""
    if isinstance(source, str):
        with open(source, newline="", encoding="utf-8-sig") as handle:
            return _read_csv_rows(handle)
    if hasattr(source, "read"):
        raw = source.read()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(raw))
    else:
        raise TypeError("source must be a file path or file-like object")

    rows: list[dict[str, str]] = []
    if not reader.fieldnames:
        return rows

    for row in reader:
        normalized = {_normalize_header(k): (v or "").strip() for k, v in row.items() if k}
        if any(normalized.values()):
            rows.append(normalized)
    return rows


def parse_campus_codes(raw: str) -> list[str]:
    """Parse campus codes from JSON array or comma-separated string."""
    raw = (raw or "").strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(c).strip() for c in parsed if str(c).strip()]
        except json.JSONDecodeError:
            pass
    return [c.strip() for c in raw.split(",") if c.strip()]


def row_to_seller_payload(row: dict[str, str]) -> dict | None:
    """Convert a CSV row to provision_marketplace_seller() payload."""
    ext_id = row.get("external_seller_id", "").strip()
    if not ext_id:
        return None

    metadata: dict = {}
    campus_codes = parse_campus_codes(row.get("campus_codes", ""))
    if campus_codes:
        metadata["campus_codes"] = campus_codes

    payload = {
        "external_seller_id": ext_id,
        "full_name": row.get("full_name", "").strip(),
        "business_name": row.get("business_name", "").strip(),
        "business_url": row.get("business_url", "").strip(),
        "seller_metadata": metadata,
    }
    email = row.get("email", "").strip()
    if email:
        payload["email"] = email
    if row.get("business_description", "").strip():
        payload["business_description"] = row["business_description"].strip()
    if row.get("location", "").strip():
        payload["location"] = row["location"].strip()
    return payload


def is_pending_only_row(row: dict[str, str]) -> bool:
    """Row flagged to add USK to invite list without provisioning."""
    flag = row.get("pending_only", row.get("invite_only", "")).strip().lower()
    return flag in ("1", "true", "yes", "y")


def get_marketplace_partner(slug: str, *, create_if_missing: bool = False) -> MarketplacePartner:
    """Resolve marketplace by slug; optionally create a minimal UNIMART-style partner."""
    try:
        return MarketplacePartner.objects.get(slug=slug)
    except MarketplacePartner.DoesNotExist:
        if not create_if_missing:
            raise
        from apps.partners.models import Partner, generate_api_key, hash_api_key, generate_referral_code

        partner = Partner.objects.select_related("user").first()
        if not partner:
            raise ValueError(
                f"Marketplace '{slug}' not found and no Partner exists to attach a new marketplace."
            )
        raw_key = generate_api_key()
        return MarketplacePartner.objects.create(
            name=slug.replace("-", " ").title(),
            slug=slug,
            partner=partner,
            api_key_hash=hash_api_key(raw_key),
            api_key_prefix=raw_key[:8],
            seller_identity_field=MarketplacePartner.SellerIdentity.EXTERNAL_ID,
            auto_activate_sellers=True,
            seller_default_plan="growth",
            seller_welcome_email=True,
            notes=f"Auto-created by import_unimart_vendors (referral: {generate_referral_code(slug)})",
        )


def _append_pending_usks(mp: MarketplacePartner, usks: list[str]) -> int:
    settings_data = dict(mp.settings or {})
    pending = list(settings_data.get("vendor_join_pending_usks", []))
    added = 0
    for usk in usks:
        normalized = usk.strip().upper()
        if normalized and normalized not in pending:
            pending.append(normalized)
            added += 1
    if added:
        settings_data["vendor_join_pending_usks"] = pending
        mp.settings = settings_data
        mp.save(update_fields=["settings"])
    return added


def import_sellers_csv(
    mp: MarketplacePartner,
    source: str | TextIO | BinaryIO,
    *,
    dry_run: bool = False,
) -> ImportSummary:
    """Import sellers from CSV using provision_marketplace_seller()."""
    summary = ImportSummary()
    rows = _read_csv_rows(source)
    if not rows:
        summary.errors.append("CSV is empty or has no data rows.")
        return summary

    pending_usks: list[str] = []

    for index, row in enumerate(rows):
        ext_id = row.get("external_seller_id", "").strip()
        if not ext_id:
            summary.failed += 1
            summary.results.append({
                "index": index,
                "status": "validation_error",
                "error": "Missing external_seller_id",
            })
            continue

        if is_pending_only_row(row):
            pending_usks.append(ext_id)
            summary.results.append({
                "index": index,
                "external_seller_id": ext_id,
                "status": "pending_queued",
            })
            continue

        payload = row_to_seller_payload(row)
        if not payload:
            summary.failed += 1
            summary.results.append({
                "index": index,
                "status": "validation_error",
                "error": "Invalid row",
            })
            continue

        if dry_run:
            summary.provisioned += 1
            summary.results.append({
                "index": index,
                "external_seller_id": ext_id,
                "status": "dry_run",
            })
            continue

        result = provision_marketplace_seller(mp, payload)
        entry = {
            "index": index,
            "external_seller_id": ext_id,
            "status": result.status,
            "email": result.email,
            "business_name": result.business_name,
        }
        if result.error:
            entry["error"] = result.error

        if result.ok:
            if result.status == "already_exists":
                summary.already_exists += 1
            else:
                summary.provisioned += 1
        else:
            summary.failed += 1

        summary.results.append(entry)

    if pending_usks and not dry_run:
        summary.pending_added = _append_pending_usks(mp, pending_usks)

    return summary


def _parse_decimal(value: str) -> Decimal | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def _parse_int(value: str) -> int | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def row_to_product_payload(row: dict[str, str]) -> dict | None:
    ext_id = row.get("external_id", row.get("sku", "")).strip()
    name = row.get("name", "").strip()
    if not ext_id or not name:
        return None

    payload = {
        "external_id": ext_id,
        "name": name,
        "description": row.get("description", "").strip(),
        "image_url": row.get("image_url", "").strip(),
        "product_url": row.get("product_url", "").strip(),
        "category": row.get("category", "").strip(),
        "condition": row.get("condition", "").strip(),
        "stock_status": row.get("stock_status", "in_stock").strip() or "in_stock",
        "campus_codes": parse_campus_codes(row.get("campus_codes", "")),
    }
    price = _parse_decimal(row.get("price", ""))
    if price is not None:
        payload["price"] = price
    qty = _parse_int(row.get("quantity", ""))
    if qty is not None:
        payload["quantity"] = qty
    return payload


def _upsert_marketplace_product(mp: MarketplacePartner, seller: MarketplaceSellerAccount, data: dict) -> tuple[str, str | None]:
    """Create or update one product. Returns ('created'|'updated'|'skipped', product_id)."""
    ext_id = data["external_id"]
    meta: dict = {}
    if data.get("condition"):
        meta["condition"] = data["condition"]
    if data.get("campus_codes"):
        meta["campus_codes"] = data["campus_codes"]

    description = data.get("description", "")
    if mp.enrich_descriptions and data.get("condition") and data["condition"] != "new":
        description = description.rstrip() + f"\n\nCondition: {data['condition']}"

    product_data = {
        "name": data["name"],
        "description": description,
        "offering_type": "product",
        "stock_status": data.get("stock_status", "in_stock"),
        "source": Product.Source.MARKETPLACE,
        "marketplace_partner": mp,
        "marketplace_metadata": meta,
        "last_synced_at": timezone.now(),
        "currency": mp.default_product_currency,
    }
    if data.get("price") is not None:
        product_data["price"] = data["price"]
    if data.get("quantity") is not None:
        product_data["quantity"] = data["quantity"]
    if data.get("product_url"):
        product_data["product_url"] = data["product_url"]
    apply_sync_images_to_product_data(product_data, data)

    existing = Product.objects.filter(user=seller.user, external_id=ext_id).first()
    if existing:
        for key, value in product_data.items():
            setattr(existing, key, value)
        existing.save()
        existing.check_low_stock()
        existing.save(update_fields=["stock_status"])
        return "updated", str(existing.pk)

    product = Product.objects.create(
        user=seller.user,
        external_id=ext_id,
        **product_data,
    )
    product.check_low_stock()
    product.save(update_fields=["stock_status"])
    return "created", str(product.pk)


def import_products_csv(
    mp: MarketplacePartner,
    source: str | TextIO | BinaryIO,
    *,
    dry_run: bool = False,
) -> ImportSummary:
    """Import products grouped by external_seller_id."""
    summary = ImportSummary()
    rows = _read_csv_rows(source)
    by_seller: dict[str, list[dict]] = defaultdict(list)

    for row in rows:
        seller_id = row.get("external_seller_id", "").strip()
        if not seller_id:
            summary.failed += 1
            summary.errors.append("Product row missing external_seller_id")
            continue
        payload = row_to_product_payload(row)
        if not payload:
            summary.failed += 1
            continue
        by_seller[seller_id].append(payload)

    for seller_id, products in by_seller.items():
        seller = mp.seller_accounts.filter(external_seller_id=seller_id).select_related("user").first()
        if not seller:
            summary.failed += len(products)
            summary.errors.append(f"Seller {seller_id} not found — import sellers first.")
            continue
        if seller.status != MarketplaceSellerAccount.Status.ACTIVE:
            summary.failed += len(products)
            summary.errors.append(f"Seller {seller_id} is {seller.status}, not active.")
            continue

        synced_ids: list[str] = []
        for data in products:
            if dry_run:
                summary.products_created += 1
                continue
            action, pid = _upsert_marketplace_product(mp, seller, data)
            if action == "created":
                summary.products_created += 1
            elif action == "updated":
                summary.products_updated += 1
            if pid:
                synced_ids.append(pid)

        if not dry_run and synced_ids:
            seller.products_synced = Product.objects.filter(
                user=seller.user, marketplace_partner=mp, is_active=True,
            ).count()
            seller.last_product_sync = timezone.now()
            seller.save(update_fields=["products_synced", "last_product_sync"])
            if mp.auto_snap_on_sync:
                trigger_marketplace_autopilot(seller.user, mp, synced_ids)

    return summary


def validate_usk_format(usk: str, mp: MarketplacePartner | None = None) -> bool:
    """Validate UNIMART-style USK ID format."""
    usk = (usk or "").strip()
    if not usk:
        return False
    pattern_raw = None
    if mp and mp.settings:
        pattern_raw = mp.settings.get("vendor_join_usk_pattern")
    if pattern_raw:
        return bool(re.match(pattern_raw, usk, re.IGNORECASE))
    return bool(DEFAULT_USK_PATTERN.match(usk))


def is_usk_pending(usk: str, mp: MarketplacePartner) -> bool:
    pending = [p.upper() for p in (mp.settings or {}).get("vendor_join_pending_usks", [])]
    return usk.strip().upper() in pending


def remove_pending_usk(usk: str, mp: MarketplacePartner) -> None:
    settings_data = dict(mp.settings or {})
    pending = settings_data.get("vendor_join_pending_usks", [])
    normalized = usk.strip().upper()
    settings_data["vendor_join_pending_usks"] = [
        p for p in pending if p.upper() != normalized
    ]
    mp.settings = settings_data
    mp.save(update_fields=["settings"])


def allow_open_vendor_join(mp: MarketplacePartner) -> bool:
    return bool((mp.settings or {}).get("allow_open_vendor_join", True))


def provision_vendor_self_serve(
    mp: MarketplacePartner,
    *,
    external_seller_id: str,
    full_name: str,
    email: str,
    business_name: str,
    business_url: str = "",
) -> tuple[dict, int]:
    """
    Self-serve vendor signup. Returns (response_dict, http_status_hint).

    - Pending USK → provision per marketplace auto_activate settings
    - Open join → provision as invited if not on pending list (approval queue)
    """
    ext_id = external_seller_id.strip()
    if not validate_usk_format(ext_id, mp):
        return {"status": "invalid_usk", "error": "Invalid seller ID format."}, 400

    existing = mp.seller_accounts.filter(external_seller_id__iexact=ext_id).first()
    if existing:
        return {
            "status": "already_exists",
            "external_seller_id": ext_id,
            "email": existing.user.email,
            "message": "This seller is already on Kova. Check your email for login instructions.",
        }, 200

    on_pending = is_usk_pending(ext_id, mp)
    if not on_pending and not allow_open_vendor_join(mp):
        return {
            "status": "not_invited",
            "error": "This seller ID is not on the invite list. Contact UNIMART support.",
        }, 403

    payload = {
        "external_seller_id": ext_id,
        "full_name": full_name.strip(),
        "email": email.strip(),
        "business_name": business_name.strip(),
        "business_url": business_url.strip(),
    }

    if on_pending:
        result = provision_marketplace_seller(mp, payload)
        if result.ok:
            remove_pending_usk(ext_id, mp)
        from apps.partners.seller_provisioning import provision_result_to_response
        return provision_result_to_response(result), result.http_status

    # Open join — force invited status for approval queue
    was_auto = mp.auto_activate_sellers
    try:
        mp.auto_activate_sellers = False
        result = provision_marketplace_seller(mp, payload)
    finally:
        mp.auto_activate_sellers = was_auto

    from apps.partners.seller_provisioning import provision_result_to_response
    response = provision_result_to_response(result)
    if result.ok:
        response["approval_required"] = True
    return response, result.http_status
