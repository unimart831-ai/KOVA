"""
Holiday-draft generator: orchestrates Claude call + validation + Post creation.

Public entry point: `generate_drafts_for_holiday_draft(draft_id)`. Idempotent —
if drafts have already been created for the same HolidayDraft, returns existing
posts. Failures land the draft in `Status.FAILED` with the error captured.

Flow:
  1. Resolve the moment (HolidayOccurrence or CustomEvent)
  2. Gather user context (brand voice, products, top posts, connected platforms)
  3. Compose prompts and call the LLM (json_mode)
  4. Parse + validate against schemas.HolidayDraftsOutput
  5. For each draft x platform: run quality gates -> create Post row
  6. Link Posts back to HolidayDraft.posts_generated
  7. Mark draft DRAFTS_READY (or FAILED if zero posts survived)

See KOVA_HOLIDAY_AWARENESS.md sections 14-15.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from apps.agents.llm import generate as llm_generate, get_model_for_task, parse_llm_json
from apps.calendar_intel.models import (
    CustomEvent,
    HolidayDraft,
    HolidayOccurrence,
)
from apps.calendar_intel.prompts import (
    SYSTEM_PROMPT,
    build_user_prompt,
    render_products_summary,
    render_top_posts_summary,
)
from apps.calendar_intel.quality_gates import filter_passing
from apps.calendar_intel.schemas import HolidayDraftsOutput

logger = logging.getLogger(__name__)


class DraftGenerationError(Exception):
    """Raised when a draft cycle fails irrecoverably."""


# ──────────────────────────────────────────────────────────────────────────
# Public entry point
# ──────────────────────────────────────────────────────────────────────────
def generate_drafts_for_holiday_draft(draft_id: int) -> int:
    """Run a full draft cycle for one HolidayDraft.id. Returns count of Posts created."""
    draft = HolidayDraft.objects.select_related(
        "user", "holiday_occurrence__holiday", "custom_event",
    ).get(id=draft_id)

    if draft.status in (HolidayDraft.Status.DRAFTS_READY, HolidayDraft.Status.APPROVED):
        # Idempotent: don't regenerate if drafts already exist
        return draft.posts_generated.count()

    if draft.status == HolidayDraft.Status.DISMISSED:
        logger.info("HolidayDraft %s is dismissed; skipping generation", draft_id)
        return 0

    draft.status = HolidayDraft.Status.GENERATING
    draft.generation_error = ""
    draft.save(update_fields=["status", "generation_error", "updated_at"])

    try:
        posts_created = _generate_and_persist(draft)
    except Exception as exc:
        logger.exception("HolidayDraft %s generation failed", draft_id)
        draft.status = HolidayDraft.Status.FAILED
        draft.generation_error = str(exc)[:2000]
        draft.save(update_fields=["status", "generation_error", "updated_at"])
        return 0

    if posts_created == 0:
        draft.status = HolidayDraft.Status.FAILED
        draft.generation_error = (
            draft.generation_error
            or "No drafts survived the quality gates. Check logs for blocked-reason details."
        )
        draft.save(update_fields=["status", "generation_error", "updated_at"])
        return 0

    draft.status = HolidayDraft.Status.DRAFTS_READY
    draft.save(update_fields=["status", "updated_at"])

    # Notify the user — best-effort. Never let notification failure break the cycle.
    try:
        _notify_drafts_ready(draft, posts_created)
    except Exception:
        logger.exception("Failed to create draft-ready notification for HolidayDraft %s", draft.id)

    return posts_created


def _notify_drafts_ready(draft: HolidayDraft, count: int) -> None:
    """Send an in-app notification when drafts are ready for review."""
    from apps.notifications.models import Notification

    name = draft.moment_name
    plural = "s" if count != 1 else ""
    Notification.create_for_user(
        user=draft.user,
        notification_type=Notification.NotificationType.POSTS_GENERATED,
        message=f"{count} {name} draft{plural} ready for review",
    )


# ──────────────────────────────────────────────────────────────────────────
# Internal: orchestration
# ──────────────────────────────────────────────────────────────────────────
def _generate_and_persist(draft: HolidayDraft) -> int:
    user = draft.user
    moment_ctx = _build_moment_context(draft)
    user_ctx = _build_user_context(user)

    if not user_ctx["connected_platforms"]:
        # No platforms connected -> we can't make platform-specific posts.
        raise DraftGenerationError(
            "User has no active social accounts; nothing to draft."
        )

    requested = _requested_draft_count(draft, moment_ctx)

    user_prompt = build_user_prompt(
        business_name=user_ctx["business_name"],
        industry=user_ctx["industry"],
        brand_voice=user_ctx["brand_voice"],
        location=user_ctx["location"],
        currency=user_ctx["currency"],
        connected_platforms=user_ctx["connected_platforms"],
        products_summary=user_ctx["products_summary"],
        top_posts_summary=user_ctx["top_posts_summary"],
        moment_name=moment_ctx["name"],
        moment_date=moment_ctx["date_iso"],
        days_until=moment_ctx["days_until"],
        tone_hint=moment_ctx["tone_hint"],
        angles=moment_ctx["angles"],
        avoid_phrases=moment_ctx["avoid_phrases"],
        requested_drafts=requested,
    )

    model = get_model_for_task("create.generate", user=user)
    response = llm_generate(
        prompt=user_prompt,
        system=SYSTEM_PROMPT,
        model=model,
        max_tokens=3000,
        temperature=0.6,
        json_mode=True,
        user=user,
    )

    if not response.content or not response.content.strip():
        raise DraftGenerationError("LLM returned empty content after retries.")

    try:
        raw = parse_llm_json(response.content)
    except json.JSONDecodeError as exc:
        raise DraftGenerationError(f"LLM JSON parse failed: {exc}")

    try:
        parsed = HolidayDraftsOutput.model_validate(raw)
    except Exception as exc:
        raise DraftGenerationError(f"LLM output failed schema validation: {exc}")

    return _persist_drafts(draft, parsed, user_ctx, moment_ctx)


# ──────────────────────────────────────────────────────────────────────────
# Internal: context gathering
# ──────────────────────────────────────────────────────────────────────────
def _build_moment_context(draft: HolidayDraft) -> dict:
    today = timezone.now().date()

    if draft.holiday_occurrence:
        h = draft.holiday_occurrence.holiday
        return {
            "kind": "holiday",
            "name": h.name,
            "date": draft.target_date,
            "date_iso": draft.target_date.isoformat(),
            "days_until": (draft.target_date - today).days,
            "tone_hint": h.tone_hint or "warm",
            "angles": list(h.angles or []),
            "avoid_phrases": list(h.avoid_phrases or []),
            "post_count": h.suggested_post_count or 2,
        }

    if draft.custom_event:
        ce = draft.custom_event
        return {
            "kind": "custom",
            "name": ce.name,
            "date": draft.target_date,
            "date_iso": draft.target_date.isoformat(),
            "days_until": (draft.target_date - today).days,
            "tone_hint": ce.tone_hint or "celebratory",
            "angles": list(ce.angles or [
                "Reflect on the journey to this milestone",
                "Thank a customer who shaped this moment",
                "Tease what's next",
            ]),
            "avoid_phrases": [],
            "post_count": ce.suggested_post_count or 1,
        }

    raise DraftGenerationError("HolidayDraft has neither holiday_occurrence nor custom_event")


def _build_user_context(user) -> dict:
    profile = getattr(user, "profile", None)

    # Connected platforms (active social accounts) — limit to platforms our
    # schema supports so we don't get rejected copy for unsupported channels.
    from apps.platforms.models import SocialAccount
    SUPPORTED = {"instagram", "linkedin", "twitter", "facebook"}
    connected = list(
        SocialAccount.objects
        .filter(user=user, is_active=True, platform__in=SUPPORTED)
        .values_list("platform", flat=True)
        .distinct()
    )

    products = []
    try:
        from apps.products.models import Product
        products = list(Product.objects.filter(user=user)[:5])
    except Exception:
        pass

    top_posts = []
    try:
        from apps.content.models import Post
        top_posts = list(
            Post.objects
            .filter(user=user, status="published")
            .order_by("-predicted_engagement_score", "-published_at")[:3]
        )
    except Exception:
        pass

    return {
        "business_name": getattr(profile, "company_name", "") or user.full_name or user.email,
        "industry": getattr(profile, "industry", "") or "",
        "brand_voice": getattr(profile, "brand_voice", "") or "",
        "location": ", ".join(filter(None, [
            getattr(profile, "city", "") or "",
            getattr(profile, "country", "") or "",
        ])),
        "currency": getattr(profile, "currency", "") or "USD",
        "connected_platforms": connected,
        "products": products,
        "products_summary": render_products_summary(products),
        "top_posts": top_posts,
        "top_posts_summary": render_top_posts_summary(top_posts),
    }


def _requested_draft_count(draft: HolidayDraft, moment_ctx: dict) -> int:
    """Number of distinct angles to ask for. Capped at 3 for cost control."""
    return max(1, min(3, moment_ctx["post_count"]))


# ──────────────────────────────────────────────────────────────────────────
# Internal: post creation
# ──────────────────────────────────────────────────────────────────────────
@transaction.atomic
def _persist_drafts(
    draft: HolidayDraft,
    parsed: HolidayDraftsOutput,
    user_ctx: dict,
    moment_ctx: dict,
) -> int:
    """For each draft × platform with passing copy, create a Post row.
    Returns total Posts created."""
    from apps.content.models import Post
    from apps.platforms.models import SocialAccount

    # Map platform -> first active SocialAccount of that platform for this user
    accounts_by_platform: dict = {}
    for sa in SocialAccount.objects.filter(user=draft.user, is_active=True):
        accounts_by_platform.setdefault(sa.platform, sa)

    avoid_phrases = moment_ctx["avoid_phrases"]
    created = 0

    for item in parsed.drafts:
        candidate_pairs = item.platform_versions.items_with_content()

        # Drop platforms the user doesn't actually have connected
        candidate_pairs = [
            (plat, txt) for plat, txt in candidate_pairs
            if plat in accounts_by_platform
        ]
        if not candidate_pairs:
            continue

        passing, blocked = filter_passing(candidate_pairs, moment_avoid_phrases=avoid_phrases)
        for platform, _result in blocked:
            logger.info(
                "HolidayDraft %s: blocked %s draft (angle=%r): %s",
                draft.id, platform, item.angle_used, _result.blocking_reasons,
            )

        if not passing:
            continue

        scheduled_at = _resolve_publish_time(
            item.suggested_publish_time, moment_ctx["date"], draft.user,
        )

        for platform, text in passing:
            account = accounts_by_platform[platform]
            post = Post.objects.create(
                user=draft.user,
                social_account=account,
                platform=platform,
                content_text=text,
                status="pending_approval",
                scheduled_at=scheduled_at,
                generated_by_agent="holiday_watcher",
                ai_angle=item.angle_used[:255],
                ai_reasoning=item.rationale[:5000] if item.rationale else "",
                ai_framework="Holiday-anticipation",
            )
            draft.posts_generated.add(post)
            created += 1

    return created


def _resolve_publish_time(suggested_iso: str | None, target_date, user) -> datetime:
    """Pick the suggested time if parseable, else default to 10:00 user-local on target_date."""
    if suggested_iso:
        try:
            dt = datetime.fromisoformat(suggested_iso.replace("Z", "+00:00"))
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone.get_current_timezone())
            return dt
        except (ValueError, TypeError):
            pass

    # Default: 10:00 in user's timezone on the moment's date
    user_tz_name = getattr(user, "timezone", "") or "UTC"
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(user_tz_name)
    except Exception:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("UTC")

    naive = datetime.combine(target_date, datetime.min.time()) + timedelta(hours=10)
    return naive.replace(tzinfo=tz)
