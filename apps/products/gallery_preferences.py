"""Merchant gallery hero + scene visibility and alteration review filtering."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.products.models import Product

POLISH_ACTION_TYPES = ("commerce.studio_polish", "commerce.pro_scene")
REVIEW_BLOCKED_STATUSES = frozenset({"pending", "rejected"})


def _coerce_url(value) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def variant_id_from_url(url: str, product_id: str) -> str:
    """Extract variant id from studio_polish or product_variations storage paths."""
    url = _coerce_url(url)
    if not url:
        return ""
    marker = f"/{product_id}/"
    if marker not in url:
        return ""
    name = url.rsplit("/", 1)[-1]
    match = re.match(r"^(.+?)_[a-f0-9]{6,10}\.(jpg|jpeg|png|webp)$", name, re.I)
    if match:
        return match.group(1)
    if "." in name:
        return name.rsplit(".", 1)[0]
    return name


def get_gallery_preferences(product: Product) -> dict:
    prefs = product.gallery_preferences
    if not isinstance(prefs, dict):
        return {}
    return prefs


def excluded_urls(product: Product) -> set[str]:
    prefs = get_gallery_preferences(product)
    urls = {_coerce_url(u) for u in (prefs.get("excluded_urls") or []) if _coerce_url(u)}
    variant_ids = {v for v in (prefs.get("excluded_variant_ids") or []) if v}
    if not variant_ids:
        return urls
    pid = str(product.pk)
    for url in product.additional_images or []:
        url = _coerce_url(url)
        if url and variant_id_from_url(url, pid) in variant_ids:
            urls.add(url)
    return urls


def hero_image_url_override(product: Product) -> str:
    return _coerce_url(get_gallery_preferences(product).get("hero_image_url"))


def polish_actions_for_product(product: Product):
    from apps.agents.models import AgentAction

    return AgentAction.objects.filter(
        user=product.user,
        action_type__in=POLISH_ACTION_TYPES,
        input_data__product_id=str(product.pk),
        status=AgentAction.ActionStatus.COMPLETED,
    ).exclude(input_data__session=True).order_by("-completed_at")


def polish_metadata_by_url(product: Product) -> dict[str, dict]:
    """Latest AgentAction output_data keyed by scene URL."""
    by_url: dict[str, dict] = {}
    for action in polish_actions_for_product(product):
        out = action.output_data or {}
        url = _coerce_url(out.get("url"))
        if url and url not in by_url:
            by_url[url] = {**out, "_action_id": str(action.pk)}
    return by_url


def review_status_for_url(product: Product, url: str) -> str:
    meta = polish_metadata_by_url(product).get(_coerce_url(url), {})
    if not meta.get("needs_review"):
        return ""
    return meta.get("review_status") or "pending"


def is_review_blocked_url(product: Product, url: str) -> bool:
    status = review_status_for_url(product, url)
    return status in REVIEW_BLOCKED_STATUSES


def filter_review_blocked_urls(product: Product, urls: list[str]) -> list[str]:
    if not urls:
        return []
    blocked = {u for u in urls if is_review_blocked_url(product, u)}
    if not blocked:
        return list(urls)
    return [u for u in urls if u not in blocked]


def filter_merchant_excluded_urls(product: Product, urls: list[str]) -> list[str]:
    excluded = excluded_urls(product)
    if not excluded:
        return list(urls)
    return [u for u in urls if u not in excluded]


def order_hero_first(urls: list[str], product: Product) -> list[str]:
    hero = hero_image_url_override(product)
    if not hero or hero not in urls:
        return list(urls)
    rest = [u for u in urls if u != hero]
    return [hero, *rest]


def filter_gallery_urls(urls: list[str], product: Product) -> list[str]:
    """Apply merchant exclusions and review gate, then hero ordering."""
    urls = filter_merchant_excluded_urls(product, urls)
    urls = filter_review_blocked_urls(product, urls)
    return order_hero_first(urls, product)


def build_gallery_scenes(product: Product) -> list[dict]:
    """Scene rows for product detail hero picker and review UI."""
    meta_by_url = polish_metadata_by_url(product)
    excluded = excluded_urls(product)
    hero_override = hero_image_url_override(product)
    pid = str(product.pk)
    original_url = ""
    if product.image:
        try:
            original_url = _coerce_url(product.image.url)
        except Exception:
            original_url = ""
    scenes: list[dict] = []

    if product.image:
        try:
            primary_url = _coerce_url(product.image.url)
        except Exception:
            primary_url = ""
        if primary_url:
            scenes.append({
                "url": primary_url,
                "variant_id": "original",
                "label": "Original",
                "slide_role": "original",
                "is_original": True,
                "is_hero": hero_override == primary_url,
                "included": primary_url not in excluded,
                "primary_hidden": product.exclude_primary_image,
                "needs_review": False,
                "review_status": "",
                "review_reason": "",
                "action_id": "",
            })

    for item in product.additional_images or []:
        url = _coerce_url(item)
        if not url:
            continue
        meta = meta_by_url.get(url, {})
        variant_id = meta.get("variant") or variant_id_from_url(url, pid)
        review_status = ""
        needs_review = bool(meta.get("needs_review"))
        if needs_review:
            review_status = meta.get("review_status") or "pending"
        scenes.append({
            "url": url,
            "variant_id": variant_id,
            "label": meta.get("label") or variant_id or "Scene",
            "slide_role": meta.get("slide_role") or "",
            "is_original": False,
            "is_hero": hero_override == url,
            "included": url not in excluded,
            "primary_hidden": False,
            "needs_review": needs_review,
            "review_status": review_status,
            "review_reason": meta.get("review_reason") or "",
            "action_id": meta.get("_action_id") or "",
            "original_url": original_url if original_url and original_url != url else "",
            "show_compare": bool(original_url and original_url != url and needs_review),
        })

    if not hero_override:
        for scene in scenes:
            if scene["included"] and not (scene["is_original"] and scene["primary_hidden"]):
                scene["is_hero"] = True
                break

    return scenes


def set_hero_image(product: Product, url: str) -> None:
    url = _coerce_url(url)
    prefs = dict(get_gallery_preferences(product))
    prefs["hero_image_url"] = url
    product.gallery_preferences = prefs
    product.save(update_fields=["gallery_preferences", "updated_at"])


def set_scene_included(product: Product, url: str, *, included: bool) -> None:
    url = _coerce_url(url)
    prefs = dict(get_gallery_preferences(product))
    excluded = set(_coerce_url(u) for u in (prefs.get("excluded_urls") or []))
    variant_ids = set(prefs.get("excluded_variant_ids") or [])
    variant_id = variant_id_from_url(url, str(product.pk))
    meta = polish_metadata_by_url(product).get(url, {})
    if not variant_id:
        variant_id = meta.get("variant") or ""

    if included:
        excluded.discard(url)
        if variant_id:
            variant_ids.discard(variant_id)
    else:
        excluded.add(url)
        if variant_id:
            variant_ids.add(variant_id)

    prefs["excluded_urls"] = sorted(excluded)
    prefs["excluded_variant_ids"] = sorted(variant_ids)
    product.gallery_preferences = prefs
    product.save(update_fields=["gallery_preferences", "updated_at"])


def set_variant_review_status(product: Product, url: str, status: str) -> bool:
    """Approve or reject a flagged polish scene (updates AgentAction output_data)."""
    from apps.agents.models import AgentAction

    url = _coerce_url(url)
    if status not in ("approved", "rejected"):
        return False

    action = (
        AgentAction.objects.filter(
            user=product.user,
            action_type__in=POLISH_ACTION_TYPES,
            input_data__product_id=str(product.pk),
            status=AgentAction.ActionStatus.COMPLETED,
        )
        .exclude(input_data__session=True)
        .order_by("-completed_at")
    )
    target = None
    for row in action:
        out = row.output_data or {}
        if _coerce_url(out.get("url")) == url:
            target = row
            break
    if not target:
        return False

    out = dict(target.output_data or {})
    out["review_status"] = status
    if status == "approved":
        out["needs_review"] = False
    target.output_data = out
    target.save(update_fields=["output_data"])
    return True
