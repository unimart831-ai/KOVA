"""Snap to Sell pipeline status for the live progress modal."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone as tz

CAROUSEL_PLATFORMS = frozenset({"instagram", "facebook", "linkedin"})
REEL_PLATFORMS = frozenset({"instagram", "facebook", "tiktok", "linkedin"})
SNAP_TIMEOUT = timedelta(minutes=10)
SEED_TIMEOUT = timedelta(minutes=5)
EXPAND_STALE = timedelta(minutes=6)
REEL_COMPOSE_STALE = timedelta(minutes=6)


def _friendly_writing_error(raw: str) -> str:
    """Map internal LLM errors to actionable Snap UI copy."""
    if not raw:
        return "Post generation failed"
    lower = raw.lower()
    if "openrouter" in lower and ("401" in raw or "api key" in lower or "sk-or-v1" in lower):
        return raw.split("Failed to parse AI response:", 1)[-1].strip() or raw
    if "openrouter api key rejected" in lower or "authentication failed" in lower:
        return raw
    if "failed to parse ai response" in lower and "empty response" in lower:
        return (
            "AI returned no content after retries. "
            "Check OPENROUTER_API_KEY in Railway or try again in a few minutes."
        )
    return raw


def estimate_polish_credits(
    user,
    *,
    scene_pack: str = "auto",
    plan_tier: str | None = None,
    photo_count: int = 1,
    commerce_source: str = "snap",
    analysis_preview: dict | None = None,
) -> dict:
    """
    Pre-launch credit estimate: repairs + scenes + exports (+ optional multi-angle).

    Uses typical Snap preflight repair plan and plan-tier variant/export budgets.
    """
    from django.conf import settings as django_settings

    from apps.billing.models import get_effective_plan_tier
    from apps.billing.visual_credits import get_visual_credit_usage
    from apps.products.photoroom_plus import get_max_variants_for_plan
    from apps.products.photoroom_preflight import PhotoQualityReport, build_repair_plan
    from apps.products.scene_packs import (
        multi_angle_polish_enabled,
        normalize_scene_pack,
        scene_pack_export_budget,
    )

    profile = getattr(user, "profile", None)
    plan = (plan_tier or get_effective_plan_tier(profile) if profile else "starter").lower()
    pack = normalize_scene_pack(scene_pack)
    usage = get_visual_credit_usage(user)

    preview = analysis_preview or {}
    report = PhotoQualityReport(
        lighting=preview.get("lighting", "good"),
        sharpness=preview.get("sharpness", "sharp"),
        has_distracting_text=bool(preview.get("has_distracting_text")),
        crop=preview.get("crop", "comfortable"),
    )
    repairs = build_repair_plan(
        report,
        plan_tier=plan,
        commerce_source=commerce_source,
    )
    preflight_max = int(getattr(django_settings, "PHOTOROOM_PREFLIGHT_MAX_REPAIRS", 2))
    repair_count = min(len(repairs), preflight_max)

    plan_max = get_max_variants_for_plan(plan)
    if usage.get("unlimited"):
        credit_pool = plan_max
        remaining = None
    else:
        remaining = max(0, int(usage.get("remaining", 0)))
        credit_pool = min(plan_max, remaining)

    story_slots, marketplace_slots = scene_pack_export_budget(pack, plan)
    export_slots = story_slots + marketplace_slots
    min_scenes = int(getattr(django_settings, "PHOTOROOM_MIN_SCENE_VARIANTS", 3))

    credit_after_repairs = max(0, credit_pool - repair_count)
    if credit_after_repairs > min_scenes and export_slots > 0:
        export_budget = min(export_slots, credit_after_repairs - min_scenes)
        channel_budget = min(story_slots, export_budget)
        marketplace_budget = min(
            marketplace_slots,
            max(0, export_budget - channel_budget),
        )
        scene_budget = max(1, credit_after_repairs - channel_budget - marketplace_budget)
        export_total = channel_budget + marketplace_budget
    else:
        export_total = 0
        scene_budget = max(1, credit_after_repairs)

    multi_angle = 1 if multi_angle_polish_enabled(plan) and photo_count > 1 else 0
    total = repair_count + scene_budget + export_total + multi_angle
    over_budget = (
        not usage.get("unlimited")
        and remaining is not None
        and total > remaining
    )

    parts = [
        f"{repair_count} repair" if repair_count == 1 else f"{repair_count} repairs",
        f"{scene_budget} scene" if scene_budget == 1 else f"{scene_budget} scenes",
    ]
    if export_total:
        parts.append(
            f"{export_total} export" if export_total == 1 else f"{export_total} exports"
        )
    if multi_angle:
        parts.append("1 extra angle")
    breakdown_label = f"~{total} credits: " + " + ".join(parts)

    return {
        "total": total,
        "repairs": repair_count,
        "scenes": scene_budget,
        "exports": export_total,
        "multi_angle": multi_angle,
        "remaining": remaining,
        "unlimited": bool(usage.get("unlimited")),
        "over_budget": over_budget,
        "breakdown_label": breakdown_label,
        "scene_pack": pack,
        "plan_tier": plan,
    }


def _polish_credit_snapshot(user, product_id: str) -> dict:
    """Monthly polish credits + per-product scene debits for Snap UX."""
    from apps.agents.models import AgentAction
    from apps.billing.visual_credits import get_visual_credit_usage

    usage = get_visual_credit_usage(user)
    product_actions = AgentAction.objects.filter(
        user=user,
        action_type__in=("commerce.studio_polish", "commerce.pro_scene"),
        input_data__product_id=product_id,
        status=AgentAction.ActionStatus.COMPLETED,
    ).exclude(input_data__session=True)

    session_used = product_actions.count()
    scenes: list[dict] = []
    for action in product_actions.order_by("created_at"):
        out = action.output_data or {}
        if out.get("phase") not in (None, "scene", "preflight", "channel", "marketplace"):
            continue
        variant = out.get("variant") or ""
        if not variant and out.get("phase") != "preflight":
            continue
        scenes.append({
            "variant": variant,
            "label": out.get("label") or variant or "Repair",
            "slide_role": out.get("slide_role") or out.get("phase") or "",
            "api": out.get("api") or "v2/edit",
            "needs_review": bool(out.get("needs_review")),
        })

    return {
        "used": usage.get("used", 0),
        "max": usage.get("max", 0),
        "remaining": usage.get("remaining", 0),
        "session_used": session_used,
        "scenes": scenes,
    }


def _format_polish_credit_detail(credits: dict) -> str:
    used = credits.get("session_used", 0)
    monthly_used = credits.get("used", 0)
    monthly_max = credits.get("max", 0)
    if monthly_max:
        headline = f"{monthly_used} of {monthly_max} polish credits"
    else:
        headline = f"{used} polish credit{'s' if used != 1 else ''} this Snap"
    scenes = credits.get("scenes") or []
    if not scenes:
        return headline
    labels = [s.get("label") or s.get("variant") for s in scenes[:6]]
    breakdown = ", ".join(label for label in labels if label)
    if len(scenes) > 6:
        breakdown += f" +{len(scenes) - 6} more"
    return f"{headline} · {breakdown}" if breakdown else headline


def _reel_compose_stuck(post, now):
    """True when compose was marked pending but has not finished within the stale window."""
    if post.reel_compose_status != "pending":
        return False
    ref = post.updated_at or post.created_at
    return ref < now - REEL_COMPOSE_STALE


def _offering_copy(product) -> dict:
    """User-facing pipeline labels keyed by offering_type."""
    from apps.products.models import Product

    ot = getattr(product, "offering_type", Product.OfferingType.PRODUCT) or Product.OfferingType.PRODUCT

    if ot == Product.OfferingType.SERVICE:
        return {
            "offering_type": "service",
            "item_noun": "service",
            "photos_noun": "work photos",
            "analyze_title": "AI analyzing your service",
            "analyze_running": "Vision AI is reading your work evidence…",
            "analyze_done": "AI extracted service details, tags, and campaign angle",
            "expand_running": "Running Photoroom Plus scenes for your service…",
            "expand_done": "Service scenes ready for carousel & posts",
            "reel_running": "Creating motion reel from your work photos…",
            "reel_single": "Creating motion reel from your portfolio shot…",
            "quick_waiting": "Waiting for service name from photo…",
            "carousel_waiting": "Waiting for service analysis…",
        }
    if ot == Product.OfferingType.DIGITAL:
        return {
            "offering_type": "digital",
            "item_noun": "digital product",
            "photos_noun": "screenshots",
            "analyze_title": "AI analyzing your digital product",
            "analyze_running": "Vision AI is reading your screenshots…",
            "analyze_done": "AI extracted product details, value prop, and campaign angle",
            "expand_running": "Running Photoroom Plus scenes (desk hero, device mockup…)…",
            "expand_done": "Digital product scenes ready for carousel & posts",
            "reel_running": "Creating motion reel from your screenshots…",
            "reel_single": "Creating motion reel from your screenshot…",
            "quick_waiting": "Waiting for product name from screenshot…",
            "carousel_waiting": "Waiting for digital product analysis…",
        }
    return {
        "offering_type": "product",
        "item_noun": "product",
        "photos_noun": "photos",
        "analyze_title": "AI analyzing product",
        "analyze_running": "Vision AI is reading your product photos…",
        "analyze_done": "AI extracted product details, tags, and campaign angle",
        "expand_running": "Running Photoroom Plus scene pack (AI backgrounds, studio, flat lay…)…",
        "expand_done": "Studio versions ready for carousel & posts",
        "reel_running": "Creating motion reel from your product photos…",
        "reel_single": "Creating motion reel from your product photo…",
        "quick_waiting": "Waiting for product name from photo…",
        "carousel_waiting": "Waiting for product analysis…",
    }


def _step(step_id, message, detail="", status="pending"):
    return {"id": step_id, "message": message, "detail": detail, "status": status}


def _post_payload(post):
    return {
        "id": str(post.id),
        "platform": (
            post.social_account.get_platform_display()
            if post.social_account
            else post.platform
        ),
        "angle": post.ai_angle or "",
        "preview": (post.content_text or "")[:120],
        "media_status": post.media_status,
        "post_format": post.post_format,
        "visual_strategy": post.visual_strategy or "",
        "video_compose_status": post.reel_compose_status,
        "reel_compose_pending": post.reel_compose_pending,
        "reel_has_video": post.reel_has_video,
        "status": post.status,
    }


def build_snap_pipeline_status(product, user):
    """
    Derive Snap to Sell pipeline progress from product, seed, posts, and agent actions.
    """
    from apps.agents.models import AgentAction
    from apps.platforms.models import SocialAccount

    photo_count = len(product.all_image_urls)
    product_id = str(product.pk)
    now = tz.now()
    snap_stale = product.created_at < now - SNAP_TIMEOUT
    copy = _offering_copy(product)

    platforms = set(
        SocialAccount.objects.filter(user=user, is_active=True).values_list(
            "platform", flat=True
        )
    )
    carousel_eligible = bool(platforms & CAROUSEL_PLATFORMS) and photo_count >= 1
    reel_eligible = photo_count >= 1 and bool(platforms & REEL_PLATFORMS)
    single_photo_reel = photo_count == 1 and reel_eligible

    seed = product.content_seeds.order_by("-created_at").first()

    def _action(action_type):
        return (
            AgentAction.objects.filter(
                user=user,
                action_type=action_type,
                input_data__product_id=product_id,
            )
            .order_by("-created_at")
            .first()
        )

    vision_action = _action("snap.vision")
    carousel_action = _action("snap.carousel")
    reel_action = _action("snap.reel")

    seed_posts = (
        seed.posts.select_related("social_account").order_by("created_at")
        if seed
        else product.posts.none()
    )
    carousel_posts = list(
        product.posts.filter(visual_strategy="carousel")
        .select_related("social_account")
        .order_by("-created_at")
    )
    reel_posts = list(
        product.posts.filter(post_format="reel")
        .select_related("social_account")
        .order_by("-created_at")
    )

    steps = []
    error_message = ""

    # 1 — Photos
    steps.append(
        _step(
            "photos",
            "Photos uploaded",
            f"{photo_count} {copy['photos_noun']} attached",
            "completed",
        )
    )

    # 2 — Vision analysis
    if seed or vision_action:
        analyze_status = "completed"
        analyze_detail = copy["analyze_done"]
    elif snap_stale:
        analyze_status = "failed"
        analyze_detail = "Analysis timed out — try launching Snap to Sell again"
        error_message = analyze_detail
    else:
        analyze_status = "running"
        analyze_detail = copy["analyze_running"]

    steps.append(_step("analyze", copy["analyze_title"], analyze_detail, analyze_status))

    # 3 — Photo set expansion (Photoroom Plus + promo frame)
    variation_action = _action("commerce.photo_variations")
    polish_actions = AgentAction.objects.filter(
        user=user,
        action_type__in=("commerce.studio_polish", "commerce.pro_scene"),
        input_data__product_id=product_id,
    ).order_by("-created_at")
    studio_polish_action = polish_actions.filter(
        status=AgentAction.ActionStatus.COMPLETED,
    ).first()
    polish_session_running = polish_actions.filter(
        status=AgentAction.ActionStatus.STARTED,
        input_data__session=True,
    ).first()
    polish_session_failed = polish_actions.filter(
        status=AgentAction.ActionStatus.FAILED,
        input_data__session=True,
    ).first()
    studio_count = sum(
        1 for u in (product.additional_images or [])
        if f"studio_polish/{product_id}/" in u
    )
    variation_count = sum(
        1 for u in (product.additional_images or [])
        if f"product_variations/{product_id}/" in u
    )
    enhanced_count = studio_count + variation_count

    from apps.products.photoroom_review import summarize_review_state

    polish_completed_actions = list(
        polish_actions.filter(status=AgentAction.ActionStatus.COMPLETED)
        .exclude(input_data__session=True)
        .order_by("-created_at")[:50]
    )
    review_state = summarize_review_state(polish_completed_actions)

    studio_polish_notice = ""
    from apps.products.photo_variations import is_studio_polish_mode

    if is_studio_polish_mode(getattr(product, "visual_mode", None)) and analyze_status == "completed":
        if not studio_polish_action and studio_count == 0:
            from apps.products.photoroom import studio_polish_failure_message

            out = (variation_action.output_data or {}) if variation_action else {}
            reason = out.get("reason") or out.get("error") or "photoroom_failed"
            studio_polish_notice = studio_polish_failure_message(reason) or ""

    expand_stale = False
    if vision_action and vision_action.completed_at:
        expand_stale = (
            enhanced_count == 0
            and not polish_session_running
            and vision_action.completed_at < now - EXPAND_STALE
        )

    if analyze_status == "failed":
        expand_status = "skipped"
        expand_detail = "Skipped — analysis did not finish"
    elif polish_session_failed and enhanced_count == 0:
        expand_status = "failed"
        out = polish_session_failed.output_data or {}
        reason = out.get("reason") or out.get("error") or "photoroom_failed"
        from apps.products.photoroom import studio_polish_failure_message

        expand_detail = (
            studio_polish_failure_message(reason)
            or polish_session_failed.error_message
            or "Studio polish failed — tap Expand Photo Set to retry"
        )
        if not error_message:
            error_message = expand_detail
    elif studio_polish_action or variation_action or enhanced_count >= 1:
        n = enhanced_count or (
            (variation_action.output_data or {}).get("variations_created", 1)
            if variation_action
            else 1
        )
        polish_credits = _polish_credit_snapshot(user, product_id)
        expand_status = "completed"
        if polish_credits.get("session_used") or polish_credits.get("scenes"):
            expand_detail = _format_polish_credit_detail(polish_credits)
        elif n == 1:
            expand_detail = copy["expand_done"]
        else:
            expand_detail = f"{n} scenes ready for carousel & posts"
    elif analyze_status == "running":
        expand_status = "pending"
        expand_detail = copy["carousel_waiting"]
    elif polish_session_running:
        expand_status = "running"
        expand_detail = copy["expand_running"]
    elif expand_stale or (snap_stale and seed and enhanced_count == 0):
        expand_status = "failed"
        expand_detail = "Studio polish timed out — tap Expand Photo Set"
        if not error_message:
            error_message = expand_detail
    elif analyze_status == "completed":
        expand_status = "running"
        expand_detail = copy["expand_running"]
    else:
        expand_status = "pending"
        expand_detail = "Waiting for analysis…"

    steps.append(_step("variations", "Expanding photo set", expand_detail, expand_status))

    # 4 — Quick photo post (Commerce Autopilot fast path)
    quick_post_action = _action("commerce.quick_post")
    from apps.products.commerce_autopilot import commerce_autopilot_active

    if not commerce_autopilot_active(user):
        quick_status = "skipped"
        quick_detail = "Enable Commerce Autopilot for instant photo posts"
    elif analyze_status == "failed":
        quick_status = "skipped"
        quick_detail = "Skipped — analysis did not finish"
    elif quick_post_action:
        if quick_post_action.status == AgentAction.ActionStatus.FAILED:
            quick_status = "failed"
            quick_detail = "Quick photo post failed — use the button below"
        else:
            n = (quick_post_action.output_data or {}).get("posts_created", 0)
            quick_status = "completed"
            quick_detail = f"Photo posted to {n} platform{'s' if n != 1 else ''} with name, price & shop link"
    elif analyze_status == "running":
        quick_status = "pending"
        quick_detail = copy["quick_waiting"]
    elif snap_stale and seed:
        quick_status = "failed"
        quick_detail = "Quick post timed out — tap Quick Post Photo"
    else:
        quick_status = "running"
        quick_detail = "Posting your photo with name, price & Commerce Link…"

    steps.append(_step("quick_post", "Quick photo post", quick_detail, quick_status))

    # 5 — Platform posts (Create Agent)
    if analyze_status == "failed":
        writing_status = "skipped"
        writing_detail = "Skipped — analysis did not finish"
    elif not seed:
        writing_status = "pending" if analyze_status == "running" else "pending"
        writing_detail = "Waiting for analysis to finish…"
    elif seed.status == "failed":
        writing_status = "failed"
        writing_detail = _friendly_writing_error(seed.error_message or "Post generation failed")
        error_message = writing_detail
    elif seed.status in ("new", "processing"):
        if seed.updated_at < now - SEED_TIMEOUT:
            writing_status = "failed"
            writing_detail = "Generation timed out. Please try again."
            error_message = writing_detail
        else:
            writing_status = "running"
            count = seed_posts.count()
            writing_detail = (
                f"Create Agent is writing posts… ({count} draft{'s' if count != 1 else ''} so far)"
                if count
                else "Create Agent is planning platform-specific posts…"
            )
    else:
        writing_status = "completed"
        writing_detail = f"{seed_posts.count()} platform post(s) drafted"

    steps.append(_step("writing", "Writing platform posts", writing_detail, writing_status))

    # 6 — Carousel slides
    if not carousel_eligible:
        carousel_status = "skipped"
        carousel_detail = (
            "Connect Instagram, Facebook, or LinkedIn for carousel posts"
            if not (platforms & CAROUSEL_PLATFORMS)
            else "Waiting for photos"
        )
    elif analyze_status != "completed":
        carousel_status = "pending"
        carousel_detail = copy["carousel_waiting"]
    elif review_state.get("alteration_review_required"):
        carousel_status = "pending"
        pending_n = review_state.get("review_pending_count", 0)
        carousel_detail = (
            f"Approve {pending_n} AI scene{'s' if pending_n != 1 else ''} on the product page before carousel publish"
        )
    elif carousel_action and carousel_action.status == AgentAction.ActionStatus.FAILED:
        carousel_status = "failed"
        carousel_detail = "Carousel generation failed"
    elif carousel_posts:
        pending_media = [p for p in carousel_posts if p.media_status == "pending"]
        failed_media = [p for p in carousel_posts if p.media_status == "failed"]
        if pending_media:
            carousel_status = "running"
            carousel_detail = f"Building carousel slides ({len(carousel_posts)} platform{'s' if len(carousel_posts) != 1 else ''})…"
        elif failed_media and not any(p.media_status == "generated" for p in carousel_posts):
            carousel_status = "failed"
            carousel_detail = "Carousel slide generation failed"
        else:
            carousel_status = "completed"
            carousel_detail = f"{len(carousel_posts)} carousel post(s) with slides ready"
    elif snap_stale and seed:
        carousel_status = "failed"
        carousel_detail = "Carousel generation timed out"
    else:
        carousel_status = "running"
        carousel_detail = "Creating swipeable carousel slides from your photos…"

    steps.append(_step("carousel", "Building carousel slides", carousel_detail, carousel_status))

    # 7 — Motion reel
    if not reel_eligible:
        reel_status = "skipped"
        reel_detail = (
            "Connect Instagram, Facebook, TikTok, or LinkedIn for motion reels"
        )
    elif single_photo_reel and analyze_status != "completed":
        reel_status = "pending"
        reel_detail = copy["carousel_waiting"]
    elif single_photo_reel and analyze_status == "failed":
        reel_status = "skipped"
        reel_detail = "Skipped — analysis did not finish"
    elif single_photo_reel and reel_posts:
        composing = [p for p in reel_posts if p.reel_compose_pending]
        ready = [p for p in reel_posts if p.reel_has_video]
        failed = [
            p for p in reel_posts
            if p.reel_compose_status == "failed" and not p.reel_has_video
        ]
        stuck = [p for p in composing if _reel_compose_stuck(p, now)]
        if composing and stuck and len(stuck) == len(composing):
            reel_status = "failed"
            reel_detail = "Video composition timed out — use Retry on the post"
            error_message = error_message or reel_detail
        elif composing:
            reel_status = "running"
            reel_detail = (
                f"FFmpeg is composing motion reel{'s' if len(composing) != 1 else ''} "
                f"from your photo ({len(ready)}/{len(reel_posts)} ready)…"
            )
        elif ready:
            reel_status = "completed"
            reel_detail = f"{len(ready)} motion reel{'s' if len(ready) != 1 else ''} ready to preview"
        elif failed:
            reel_status = "failed"
            reel_detail = "Video composition failed — use Retry on the post"
            error_message = error_message or reel_detail
        else:
            reel_status = "running"
            reel_detail = copy["reel_single"]
    elif single_photo_reel and reel_action and reel_action.status == AgentAction.ActionStatus.FAILED:
        reel_status = "failed"
        reel_detail = "Reel creation failed"
    elif single_photo_reel and seed and snap_stale:
        reel_status = "failed"
        reel_detail = "Reel composition timed out"
    elif single_photo_reel and seed:
        reel_status = "running"
        reel_detail = copy["reel_single"]
    elif carousel_status in ("pending", "running"):
        reel_status = "pending"
        reel_detail = "Waiting for carousel slides…"
    elif carousel_status == "skipped":
        reel_status = "skipped"
        reel_detail = "Carousel required before motion reel"
    elif carousel_status == "failed":
        reel_status = "skipped"
        reel_detail = "Skipped — carousel did not complete"
    elif reel_posts:
        composing = [p for p in reel_posts if p.reel_compose_pending]
        ready = [p for p in reel_posts if p.reel_has_video]
        failed = [
            p for p in reel_posts
            if p.reel_compose_status == "failed" and not p.reel_has_video
        ]
        stuck = [p for p in composing if _reel_compose_stuck(p, now)]
        if composing and stuck and len(stuck) == len(composing):
            reel_status = "failed"
            reel_detail = "Video composition timed out — use Retry on the post"
            error_message = error_message or reel_detail
        elif composing:
            reel_status = "running"
            reel_detail = (
                f"FFmpeg is composing motion reel{'s' if len(composing) != 1 else ''} "
                f"with Ken Burns + music ({len(ready)}/{len(reel_posts)} ready)…"
            )
        elif ready:
            reel_status = "completed"
            reel_detail = f"{len(ready)} motion reel{'s' if len(ready) != 1 else ''} ready to preview"
        elif failed:
            reel_status = "failed"
            reel_detail = "Video composition failed — use Retry on the post"
            error_message = error_message or reel_detail
        else:
            reel_status = "running"
            reel_detail = copy["reel_running"]
    elif reel_action and reel_action.status == AgentAction.ActionStatus.FAILED:
        reel_status = "failed"
        reel_detail = "Reel creation failed"
    elif carousel_status == "completed" and snap_stale:
        reel_status = "failed"
        reel_detail = "Reel composition timed out"
    elif carousel_status == "completed":
        reel_status = "running"
        reel_detail = copy["reel_running"]
    else:
        reel_status = "pending"
        reel_detail = "Waiting for carousel to finish…"

    steps.append(_step("reel", "Composing motion reel", reel_detail, reel_status))

    # Overall status
    active_steps = [s for s in steps if s["status"] not in ("skipped",)]
    if any(s["status"] == "failed" for s in active_steps):
        overall = "failed"
    elif all(s["status"] in ("completed", "skipped") for s in steps):
        overall = "completed"
    else:
        overall = "processing"

    terminal = overall in ("completed", "failed")

    # Thought process log — pipeline steps + seed generation log
    log = []
    for step in steps:
        if step["status"] == "skipped":
            continue
        entry = {"step": step["id"], "message": step["message"], "detail": step["detail"]}
        if step["status"] == "running":
            log.append(entry)
            break
        if step["status"] in ("completed", "failed"):
            log.append(entry)
    if seed and seed.generation_log:
        seen = {e.get("step") for e in log}
        for entry in seed.generation_log:
            if entry.get("step") not in seen:
                log.append(entry)

    posts = [_post_payload(p) for p in seed_posts] if seed else []
    if not posts:
        posts = [_post_payload(p) for p in product.posts.select_related("social_account").order_by("-created_at")[:12]]

    profile = getattr(user, "profile", None)
    from apps.products.commerce_autopilot import should_auto_publish_commerce
    auto_approve_posts = should_auto_publish_commerce(user)
    pending_count = sum(
        1 for p in (seed_posts if seed else product.posts.all())
        if p.status in ("pending_approval", "draft")
    )

    completed_steps = sum(1 for s in steps if s["status"] == "completed")
    progress_percent = min(
        98 if overall == "processing" else 100,
        round((completed_steps / max(len(steps), 1)) * 100),
    )

    polish_credits = _polish_credit_snapshot(user, product_id)
    review_notice = ""
    if review_state.get("alteration_review_required"):
        pending = review_state.get("review_pending_count", 0)
        review_notice = (
            f"{pending} AI scene{'s' if pending != 1 else ''} need your review before publishing."
        )

    return {
        "product_id": product_id,
        "product_name": product.name,
        "offering_type": copy["offering_type"],
        "item_noun": copy["item_noun"],
        "photo_count": photo_count,
        "carousel_eligible": carousel_eligible,
        "reel_eligible": reel_eligible,
        "single_photo_reel": single_photo_reel,
        "seed_id": str(seed.pk) if seed else "",
        "seed_status": seed.status if seed else "",
        "status": overall,
        "steps": steps,
        "log": log,
        "generation_log": seed.generation_log if seed else [],
        "idea": (seed.idea[:200] if seed and seed.idea else ""),
        "posts": posts,
        "post_count": len(posts),
        "pending_count": pending_count,
        "auto_approve_posts": auto_approve_posts,
        "error_message": error_message,
        "studio_polish_notice": studio_polish_notice or review_notice,
        "polish_credits": polish_credits,
        "polish_credit_summary": _format_polish_credit_detail(polish_credits)
        if expand_status == "completed" and polish_credits.get("scenes")
        else "",
        "scene_breakdown": polish_credits.get("scenes") or [],
        "alteration_review_required": bool(review_state.get("alteration_review_required")),
        "terminal": terminal,
        "progress_percent": progress_percent,
    }


def build_batch_item_gallery_payload(product, user) -> dict:
    """Per-item gallery scenes for batch hero picker after polish completes (P1-4)."""
    from apps.products.gallery_preferences import build_gallery_scenes, hero_image_url_override

    status = build_snap_pipeline_status(product, user)
    expand_step = next((s for s in status["steps"] if s["id"] == "variations"), None)
    expand_done = expand_step is not None and expand_step["status"] == "completed"

    if not expand_done:
        return {
            "hero_picker_ready": False,
            "gallery_scenes": [],
            "hero_image_url": "",
            "scene_breakdown": [],
        }

    scenes = build_gallery_scenes(product)
    polish_scenes = [s for s in scenes if not s["is_original"]]
    return {
        "hero_picker_ready": len(polish_scenes) >= 1,
        "gallery_scenes": scenes,
        "hero_image_url": hero_image_url_override(product),
        "scene_breakdown": status.get("scene_breakdown") or [],
    }
