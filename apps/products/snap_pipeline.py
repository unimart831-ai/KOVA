"""Snap to Sell pipeline status for the live progress modal."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone as tz

CAROUSEL_PLATFORMS = frozenset({"instagram", "facebook", "linkedin"})
REEL_PLATFORMS = frozenset({"instagram", "facebook", "tiktok", "linkedin"})
SNAP_TIMEOUT = timedelta(minutes=10)
SEED_TIMEOUT = timedelta(minutes=5)


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

    platforms = set(
        SocialAccount.objects.filter(user=user, is_active=True).values_list(
            "platform", flat=True
        )
    )
    carousel_eligible = photo_count >= 2 and bool(platforms & CAROUSEL_PLATFORMS)
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
            f"{photo_count} photo{'s' if photo_count != 1 else ''} attached",
            "completed",
        )
    )

    # 2 — Vision analysis
    if seed or vision_action:
        analyze_status = "completed"
        analyze_detail = "AI extracted product details, tags, and campaign angle"
    elif snap_stale:
        analyze_status = "failed"
        analyze_detail = "Analysis timed out — try launching Snap to Sell again"
        error_message = analyze_detail
    else:
        analyze_status = "running"
        analyze_detail = "Vision AI is reading your product photos…"

    steps.append(_step("analyze", "AI analyzing product", analyze_detail, analyze_status))

    # 3 — Quick photo post (Commerce Autopilot fast path)
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
        quick_detail = "Waiting for product name from photo…"
    elif snap_stale and seed:
        quick_status = "failed"
        quick_detail = "Quick post timed out — tap Quick Post Photo"
    else:
        quick_status = "running"
        quick_detail = "Posting your photo with name, price & Commerce Link…"

    steps.append(_step("quick_post", "Quick photo post", quick_detail, quick_status))

    # 4 — Platform posts (Create Agent)
    if analyze_status == "failed":
        writing_status = "skipped"
        writing_detail = "Skipped — analysis did not finish"
    elif not seed:
        writing_status = "pending" if analyze_status == "running" else "pending"
        writing_detail = "Waiting for analysis to finish…"
    elif seed.status == "failed":
        writing_status = "failed"
        writing_detail = seed.error_message or "Post generation failed"
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

    # 5 — Carousel slides
    if not carousel_eligible:
        carousel_status = "skipped"
        carousel_detail = (
            "Need 2+ photos and Instagram, Facebook, or LinkedIn connected"
            if photo_count < 2
            else "Connect Instagram, Facebook, or LinkedIn for carousel posts"
        )
    elif analyze_status != "completed":
        carousel_status = "pending"
        carousel_detail = "Waiting for product analysis…"
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

    # 6 — Motion reel
    if not reel_eligible:
        reel_status = "skipped"
        reel_detail = (
            "Connect Instagram, Facebook, TikTok, or LinkedIn for motion reels"
        )
    elif single_photo_reel and analyze_status != "completed":
        reel_status = "pending"
        reel_detail = "Waiting for product analysis…"
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
        if composing:
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
            reel_detail = "Creating motion reel from your product photo…"
    elif single_photo_reel and reel_action and reel_action.status == AgentAction.ActionStatus.FAILED:
        reel_status = "failed"
        reel_detail = "Reel creation failed"
    elif single_photo_reel and seed and snap_stale:
        reel_status = "failed"
        reel_detail = "Reel composition timed out"
    elif single_photo_reel and seed:
        reel_status = "running"
        reel_detail = "Creating motion reel from your product photo…"
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
        if composing:
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
            reel_detail = "Preparing motion reel from carousel slides…"
    elif reel_action and reel_action.status == AgentAction.ActionStatus.FAILED:
        reel_status = "failed"
        reel_detail = "Reel creation failed"
    elif carousel_status == "completed" and snap_stale:
        reel_status = "failed"
        reel_detail = "Reel composition timed out"
    elif carousel_status == "completed":
        reel_status = "running"
        reel_detail = "Creating motion reel posts from carousel…"
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

    return {
        "product_id": product_id,
        "product_name": product.name,
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
        "terminal": terminal,
        "progress_percent": progress_percent,
    }
