"""
Photoroom preflight — assess upload quality and run repair chain before scene pack.

See docs/Photoroom upgrade.md (Phase A).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from io import BytesIO

from django.conf import settings

logger = logging.getLogger(__name__)

REPAIR_ORDER = ("photofix", "text_removal", "relight", "upscale", "uncrop")
GROWTH_PLUS_TIERS = frozenset({"growth", "pro", "agency"})


@dataclass
class PhotoQualityReport:
    """Merged vision + local quality assessment."""

    lighting: str = "good"  # good | dark | uneven
    sharpness: str = "sharp"  # sharp | soft | blurry
    has_distracting_text: bool = False
    crop: str = "comfortable"  # comfortable | tight | very_tight
    mean_brightness: float = 128.0
    blur_score: float = 200.0
    whatsapp_compressed: bool = False
    aspect_ratio: float = 1.0
    repair_plan: list[str] = field(default_factory=list)


@dataclass
class PreflightResult:
    master_url: str
    repairs_run: list[str]
    repairs_failed: list[str]
    quality: PhotoQualityReport


def _local_metrics(image_bytes: bytes) -> dict:
    """Brightness, blur, compression heuristics from raw bytes."""
    try:
        from PIL import Image, ImageFilter, ImageStat

        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        stat = ImageStat.Stat(img)
        mean_brightness = sum(stat.mean) / 3.0

        gray = img.convert("L")
        thumb_w = 320
        thumb_h = max(1, int(thumb_w * h / max(w, 1)))
        small = gray.resize((thumb_w, thumb_h))
        edges = small.filter(ImageFilter.FIND_EDGES)
        edge_stat = ImageStat.Stat(edges)
        blur_score = sum(edge_stat.var) / max(len(edge_stat.var), 1)
    except Exception as exc:
        logger.debug("Local quality metrics failed: %s", exc)
        return {
            "mean_brightness": 128.0,
            "blur_score": 200.0,
            "whatsapp_compressed": False,
            "aspect_ratio": 1.0,
        }

    aspect = w / max(h, 1)
    whatsapp = len(image_bytes) < 90_000 and min(w, h) >= 800
    return {
        "mean_brightness": mean_brightness,
        "blur_score": blur_score,
        "whatsapp_compressed": whatsapp,
        "aspect_ratio": aspect,
    }


def _vision_quality(analysis: dict | None) -> dict:
    analysis = analysis or {}
    pq = analysis.get("photo_quality") or {}
    if not isinstance(pq, dict):
        pq = {}
    return {
        "lighting": (pq.get("lighting") or "good").lower(),
        "sharpness": (pq.get("sharpness") or "sharp").lower(),
        "has_distracting_text": bool(pq.get("has_distracting_text")),
        "crop": (pq.get("crop") or "comfortable").lower(),
    }


def assess_photo_quality(image_source: str, analysis: dict | None = None) -> PhotoQualityReport:
    """Merge vision photo_quality with local PIL metrics."""
    from apps.products.photoroom import _download_bytes_for_preflight

    vision = _vision_quality(analysis)
    local = {
        "mean_brightness": 128.0,
        "blur_score": 200.0,
        "whatsapp_compressed": False,
        "aspect_ratio": 1.0,
    }
    try:
        raw = _download_bytes_for_preflight(image_source)
        if raw:
            local = _local_metrics(raw)
    except Exception as exc:
        logger.debug("Preflight download for metrics failed: %s", exc)

    lighting = vision["lighting"]
    if local["mean_brightness"] < 85 and lighting == "good":
        lighting = "dark"
    elif local["mean_brightness"] < 105 and lighting == "good":
        lighting = "uneven"

    sharpness = vision["sharpness"]
    if local["blur_score"] < 120 and sharpness in ("sharp", "soft"):
        sharpness = "blurry"
    elif local["blur_score"] < 200 and sharpness == "sharp":
        sharpness = "soft"
    if local["whatsapp_compressed"] and sharpness != "blurry":
        sharpness = "soft"

    crop = vision["crop"]
    ar = local["aspect_ratio"]
    if crop == "comfortable" and (ar < 0.55 or ar > 1.85):
        crop = "tight"

    report = PhotoQualityReport(
        lighting=lighting,
        sharpness=sharpness,
        has_distracting_text=vision["has_distracting_text"],
        crop=crop,
        mean_brightness=local["mean_brightness"],
        blur_score=local["blur_score"],
        whatsapp_compressed=local["whatsapp_compressed"],
        aspect_ratio=ar,
    )
    report.repair_plan = build_repair_plan(report, plan_tier="growth", commerce_source=None)
    return report


def build_repair_plan(
    report: PhotoQualityReport,
    *,
    plan_tier: str = "starter",
    commerce_source: str | None = None,
) -> list[str]:
    """Ordered repair variant ids based on quality triggers."""
    from apps.products.photoroom_photofix import should_run_photofix_for_commerce
    from apps.products.photoroom_plus import PLUS_VARIANT_CATALOG, _plan_rank

    plan = (plan_tier or "starter").lower()
    plan_ok_for_uncrop = plan in GROWTH_PLUS_TIERS
    force_photofix = should_run_photofix_for_commerce(commerce_source=commerce_source)

    triggers: dict[str, bool] = {
        "photofix": force_photofix
        or report.lighting in ("dark", "uneven")
        or report.sharpness in ("blurry", "soft")
        or report.whatsapp_compressed,
        "text_removal": report.has_distracting_text,
        "relight": report.lighting in ("dark", "uneven"),
        "upscale": report.sharpness in ("blurry", "soft") or report.whatsapp_compressed,
        "uncrop": plan_ok_for_uncrop and report.crop in ("tight", "very_tight"),
    }

    ordered: list[str] = []
    for vid in REPAIR_ORDER:
        if not triggers.get(vid):
            continue
        spec = PLUS_VARIANT_CATALOG.get(vid)
        if spec and _plan_rank(spec.min_plan) > _plan_rank(plan):
            continue
        ordered.append(vid)
    return ordered


def run_preflight_repairs(
    source_url: str,
    product,
    analysis: dict | None,
    brand_colors: dict | None,
    *,
    budget: int,
    plan_tier: str = "starter",
    brand_template=None,
    commerce_source: str | None = None,
) -> PreflightResult:
    """
    Run up to `budget` repair Plus calls; return master URL for scene pack.
    """
    from apps.billing.visual_credits import check_visual_credit_limit, record_studio_polish
    from apps.products.photoroom import save_studio_polish_image
    from apps.products.photoroom_plus import PLUS_VARIANT_CATALOG, run_plus_variant

    if not getattr(settings, "PHOTOROOM_PREFLIGHT_ENABLED", True) or budget <= 0:
        report = assess_photo_quality(source_url, analysis)
        return PreflightResult(
            master_url=source_url,
            repairs_run=[],
            repairs_failed=[],
            quality=report,
        )

    report = assess_photo_quality(source_url, analysis)
    plan = build_repair_plan(
        report, plan_tier=plan_tier, commerce_source=commerce_source,
    )[: max(0, budget)]

    master_url = source_url
    repairs_run: list[str] = []
    repairs_failed: list[str] = []

    for variant_id in plan:
        ok, _ = check_visual_credit_limit(product.user)
        if not ok:
            break

        spec = PLUS_VARIANT_CATALOG.get(variant_id)
        if not spec:
            repairs_failed.append(variant_id)
            continue

        image_bytes = run_plus_variant(
            master_url, spec, product, analysis, brand_colors, brand_template=brand_template
        )
        if not image_bytes:
            repairs_failed.append(variant_id)
            continue

        try:
            hero_url = save_studio_polish_image(
                product.pk,
                image_bytes,
                suffix=f"preflight_{variant_id}",
            )
        except Exception as exc:
            logger.error("Preflight save failed [%s]: %s", variant_id, exc)
            repairs_failed.append(variant_id)
            continue

        record_studio_polish(
            product.user,
            product_id=product.pk,
            provider="photoroom_plus",
            output_data={
                "variant": variant_id,
                "label": spec.label,
                "url": hero_url,
                "phase": "preflight",
                "api": "v2/edit",
            },
        )
        master_url = hero_url
        repairs_run.append(variant_id)

    logger.info(
        "Preflight: product=%s repairs=%s failed=%s lighting=%s sharpness=%s",
        product.pk,
        repairs_run,
        repairs_failed,
        report.lighting,
        report.sharpness,
    )
    return PreflightResult(
        master_url=master_url,
        repairs_run=repairs_run,
        repairs_failed=repairs_failed,
        quality=report,
    )


def channel_export_budget(plan_tier: str) -> int:
    """Story + banner slots (Growth+ only)."""
    if not getattr(settings, "PHOTOROOM_CHANNEL_EXPORTS_ENABLED", True):
        return 0
    if (plan_tier or "starter").lower() not in GROWTH_PLUS_TIERS:
        return 0
    return 2


def select_channel_variant_ids(aspect_ratio: float) -> list[str]:
    """Story export may use uncrop for portrait heroes."""
    if aspect_ratio < 0.75:
        return ["channel_story_uncrop", "channel_banner"]
    return ["channel_story", "channel_banner"]


def run_channel_exports(
    hero_url: str,
    product,
    analysis: dict | None,
    brand_colors: dict | None,
    *,
    budget: int,
    aspect_ratio: float = 1.0,
    brand_template=None,
) -> tuple[list[str], list[str]]:
    """
    Export story + banner from best scene hero. Returns (urls, variant_ids).
    """
    from apps.billing.visual_credits import check_visual_credit_limit, record_studio_polish
    from apps.products.photoroom import save_studio_polish_image
    from apps.products.photoroom_plus import PLUS_VARIANT_CATALOG, run_plus_variant

    if budget <= 0:
        return [], []

    variant_ids = select_channel_variant_ids(aspect_ratio)[:budget]
    urls: list[str] = []
    ran: list[str] = []

    for variant_id in variant_ids:
        ok, _ = check_visual_credit_limit(product.user)
        if not ok:
            break

        spec = PLUS_VARIANT_CATALOG.get(variant_id)
        if not spec:
            continue

        image_bytes = run_plus_variant(
            hero_url, spec, product, analysis, brand_colors, brand_template=brand_template
        )
        if not image_bytes:
            continue

        try:
            saved_url = save_studio_polish_image(product.pk, image_bytes, suffix=variant_id)
        except Exception as exc:
            logger.error("Channel export save failed [%s]: %s", variant_id, exc)
            continue

        record_studio_polish(
            product.user,
            product_id=product.pk,
            provider="photoroom_plus",
            output_data={
                "variant": variant_id,
                "label": spec.label,
                "url": saved_url,
                "phase": "channel",
                "api": "v2/edit",
            },
        )
        urls.append(saved_url)
        ran.append(variant_id)

    return urls, ran
