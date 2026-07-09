"""
Professional reel studio — single entry for storyboard, copy, pacing, and FFmpeg render.

Design goals (social-media-manager quality):
- Text only on dedicated hook / CTA beats — never over product hero frames
- Studio-polished assets only (no raw uploads, no carousel JPEGs with baked headlines)
- Subtle Ken Burns + fade/dissolve transitions (no random circus xfade)
- ~12–15s total runtime with beat-aligned cuts
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

# Roles that must remain text-free so the product stays the hero.
TEXT_FREE_ROLES = frozenset({"hero", "staging", "angle", "desire"})


@dataclass
class ProfessionalReelResult:
    mp4_bytes: bytes
    plan: Any | None
    meta_updates: dict[str, Any]
    thumbnail_url: str | None
    backend: str = "ffmpeg"


def professional_mode_enabled() -> bool:
    return bool(getattr(settings, "REEL_PROFESSIONAL_MODE", True))


def filter_reel_sources(urls: list[str], *, upload_only: bool = False) -> list[str]:
    """Strict source filter — studio polish & portrait story only."""
    from apps.products.reel_curation import curate_reel_image_urls

    max_slides = int(getattr(settings, "REEL_MAX_SLIDES", 5))
    curated = curate_reel_image_urls(urls, max_slides=max_slides * 2, upload_only=upload_only)

    blocked = (
        "/carousels/",
        "catalog_carousel",
        "product_carousel",
        "channel_banner",
        "channel_marketplace",
        "preflight_",
        "sandbox",
    )
    clean: list[str] = []
    for url in curated:
        low = (url or "").lower()
        if any(b in low for b in blocked):
            continue
        clean.append(url)

    # Composition hero first when present
    composition = [u for u in clean if "composition_hero" in u.lower()]
    rest = [u for u in clean if u not in composition]
    ordered = composition + rest

    return curate_reel_image_urls(ordered, max_slides=max_slides, upload_only=upload_only)


def sanitize_hooks_for_roles(
    hook_texts: list[str],
    slide_roles: list[str],
) -> list[str]:
    """Strip copy from hero / lifestyle slides — captions live on hook + CTA only."""
    out = list(hook_texts or [])
    while len(out) < len(slide_roles):
        out.append("")
    sanitized: list[str] = []
    for idx, role in enumerate(slide_roles):
        text = out[idx] if idx < len(out) else ""
        if role in TEXT_FREE_ROLES:
            sanitized.append("")
        else:
            sanitized.append(text)
    return sanitized


def build_professional_plan(post, image_sources: list[str], meta: dict):
    """Return (sources, ReelComposePlan | None, meta)."""
    from apps.content.reel_director import (
        REEL_RECIPES,
        _sources_have_baked_captions,
        build_reel_plan,
    )
    from apps.products.photoroom_plus import detect_product_category

    sources = filter_reel_sources(
        image_sources,
        upload_only=bool(
            post.product and getattr(post.product, "uses_upload_images_only", False)
        ),
    ) if professional_mode_enabled() else list(image_sources)
    if not sources:
        sources = list(image_sources)
    if not sources:
        return [], None, meta

    if not getattr(settings, "REEL_DIRECTOR_ENABLED", True):
        return sources, None, meta

    if meta.get("reel_template") == "carousel_to_video" or _sources_have_baked_captions(sources):
        return sources, None, meta

    category = "general"
    analysis = meta.get("analysis") or {}
    key_feature = ""
    if post.product:
        category = detect_product_category(post.product, analysis)
        features = analysis.get("key_features") or []
        if features:
            key_feature = str(features[0])

    brand_name = meta.get("reel_brand_name", "")
    if not brand_name and post.product:
        from apps.products.commerce_seo import brand_name as resolve_brand_name

        profile = getattr(post.product.user, "profile", None)
        brand_name = resolve_brand_name(profile, post.product.user) if profile else ""

    plan = build_reel_plan(
        sources,
        seed=str(post.pk),
        category=category,
        product_name=(post.product.name if post.product else "") or "",
        price_label=(post.product.display_price if post.product else "") or "",
        hook_override=meta.get("reel_hook_text", ""),
        brand_name=brand_name,
        cta_label=meta.get("reel_cta_label", "Order on WhatsApp"),
        recipe_id=meta.get("reel_recipe_id"),
        key_feature=key_feature,
    )
    if not plan:
        return sources, None, meta

    hooks = sanitize_hooks_for_roles(plan.hook_texts, plan.slide_roles)
    if meta.get("reel_strategy"):
        from apps.media.reel_strategy import ReelStrategy

        rs = ReelStrategy.from_dict(meta.get("reel_strategy"))
        if rs:
            strategy_hooks = rs.hook_texts_for_compose(plan.slide_roles)
            while len(strategy_hooks) < len(plan.slide_roles):
                strategy_hooks.append("")
            hooks = sanitize_hooks_for_roles(strategy_hooks, plan.slide_roles)

    from apps.content.reel_director import ReelComposePlan

    plan = ReelComposePlan(
        recipe_id=plan.recipe_id,
        template=plan.template,
        image_urls=plan.image_urls,
        slide_roles=plan.slide_roles,
        hook_texts=hooks,
        music_mood=plan.music_mood,
        transitions=plan.transitions,
        ken_burns_variants=plan.ken_burns_variants,
        cta_audio_boost=plan.cta_audio_boost,
        transition_sec=plan.transition_sec,
        slide_durations=plan.slide_durations,
    )
    meta.update(plan.to_metadata())
    meta["reel_studio"] = True
    return plan.image_urls, plan, meta


def compose_professional_reel(
    post,
    image_sources: list[str],
    meta: dict,
    *,
    audio_path: Path | None = None,
) -> ProfessionalReelResult:
    """
    Full professional pipeline: plan → overlay QA → FFmpeg render.
    """
    from apps.content.reel_director import ReelComposePlan
    from apps.content.reel_music import infer_mood_from_post, pick_music_track, resolve_track_path, ensure_audio_bed
    from apps.content.reel_frame_studio import brand_context_for_post
    from apps.content.video_compose import VideoComposeError, compose_from_plan, compose_motion_reel
    from apps.media.text_overlay import TextOverlayPass, apply_overlay_report_to_metadata

    brand = brand_context_for_post(post)

    sources, plan, meta = build_professional_plan(post, image_sources, meta)
    if not sources:
        raise VideoComposeError("No reel-ready images after professional curation")

    hook_texts = plan.hook_texts if plan else []
    template = plan.template if plan else (meta.get("reel_template") or "story_arc")
    mood = (
        plan.music_mood
        if plan
        else (meta.get("music_mood") or infer_mood_from_post(post.content_intent, post.content_text))
    )

    track = pick_music_track(mood=mood, seed=str(post.pk))
    slide_count = len(sources)
    target_sec = float(getattr(settings, "REEL_TARGET_DURATION_SEC", 14.0))
    est_duration = target_sec if slide_count > 1 else min(target_sec, 8.0)

    if audio_path is None:
        audio_path = resolve_track_path(track)
    generated_audio = audio_path is None
    if generated_audio:
        audio_path = ensure_audio_bed(track, est_duration + 2)

    overlay_pass = TextOverlayPass()
    hook_texts, overlay_report = overlay_pass.prepare_for_compose(
        hook_texts,
        slide_duration=est_duration / max(slide_count, 1),
        transition_sec=plan.transition_sec if plan and plan.transition_sec else 0.45,
    )
    meta = apply_overlay_report_to_metadata(meta, overlay_report)

    if plan:
        plan = ReelComposePlan(
            recipe_id=plan.recipe_id,
            template=plan.template,
            image_urls=plan.image_urls,
            slide_roles=plan.slide_roles,
            hook_texts=hook_texts,
            music_mood=plan.music_mood,
            transitions=plan.transitions,
            ken_burns_variants=plan.ken_burns_variants,
            cta_audio_boost=plan.cta_audio_boost,
            transition_sec=plan.transition_sec,
            slide_durations=plan.slide_durations,
        )
        mp4_bytes = compose_from_plan(plan, audio_path=audio_path, brand_context=brand.__dict__)
    else:
        mp4_bytes = compose_motion_reel(
            sources,
            audio_path=audio_path,
            template=template,
            hook_texts=hook_texts,
            brand_context=brand.__dict__,
            music_mood=mood,
        )

    thumbnail_url = None
    for url in post.media_urls or sources:
        if url and not url.lower().endswith((".mp4", ".mov", ".webm")):
            thumbnail_url = url
            break

    meta["music_mood"] = mood
    meta["music_track_id"] = track.get("id") if isinstance(track, dict) else getattr(track, "id", "")
    meta["reel_compose_backend"] = "ffmpeg"
    meta["reel_studio_version"] = 2

    return ProfessionalReelResult(
        mp4_bytes=mp4_bytes,
        plan=plan,
        meta_updates=meta,
        thumbnail_url=thumbnail_url,
        backend="ffmpeg",
    )
