"""
Celery tasks for the calendar_intel app.

Tasks:
  - run_holiday_watcher: nightly fan-out task. For every active user, find
    upcoming moments in the active draft window and queue
    generate_drafts_for_moment for each.
  - generate_drafts_for_moment: per-(user, moment) generation. Creates
    HolidayDraft + invokes generator.
  - generate_drafts_for_holiday_draft: per-draft generation (called
    when a draft already exists, e.g. for retries).

See KOVA_HOLIDAY_AWARENESS.md section 14.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone

from apps.calendar_intel.generator import generate_drafts_for_holiday_draft
from apps.calendar_intel.models import (
    CustomEvent,
    HolidayDraft,
    HolidayOccurrence,
)
from apps.calendar_intel.relevance import (
    ELIGIBLE_FOR_DRAFT,
    compute_score,
)
from apps.calendar_intel.selectors import applicable_holidays_for

logger = logging.getLogger(__name__)
User = get_user_model()


# ──────────────────────────────────────────────────────────────────────────
# Watcher (nightly fan-out)
# ──────────────────────────────────────────────────────────────────────────
@shared_task(name="calendar_intel.run_holiday_watcher")
def run_holiday_watcher() -> dict:
    """
    Fan out per-user holiday detection.
    Returns a summary dict {users_processed, drafts_queued, errors}.
    Idempotent — duplicate-safe via HolidayDraft uniqueness.
    """
    today = timezone.now().date()
    users_processed = 0
    drafts_queued = 0
    errors = 0

    # Phase 1 scope: process every active user. Phase 4 will filter by plan
    # (e.g., only Growth+ get auto-drafts). For now, the user must have
    # `onboarding_completed` and a country set to be processed.
    user_qs = User.objects.filter(
        is_active=True, onboarding_completed=True,
    ).exclude(profile__country="").exclude(profile__country__isnull=True)

    for user in user_qs.iterator():
        users_processed += 1
        try:
            queued = _process_user(user, today)
            drafts_queued += queued
        except Exception:
            errors += 1
            logger.exception("Holiday watcher failed for user_id=%s", user.id)

    logger.info(
        "Holiday watcher complete: users=%d drafts_queued=%d errors=%d",
        users_processed, drafts_queued, errors,
    )
    return {
        "users_processed": users_processed,
        "drafts_queued": drafts_queued,
        "errors": errors,
    }


def _process_user(user, today) -> int:
    """For one user: find top eligible moments in active draft windows,
    create HolidayDrafts (if missing), enqueue generation."""
    queued = 0

    # 1. Score upcoming holidays in the next 30 days
    horizon = today + timedelta(days=30)
    applicable = list(applicable_holidays_for(user))
    applicable_ids = [h.id for h in applicable]

    occurrences = (
        HolidayOccurrence.objects
        .filter(date__range=(today, horizon), holiday_id__in=applicable_ids)
        .select_related("holiday")
    )

    # Each entry: (kind, score, moment) where kind is "holiday" or "custom"
    candidates: list[tuple[str, int, object]] = []

    for occ in occurrences:
        score = compute_score(occ.holiday, user, occ.date, today=today)
        days_until = (occ.date - today).days
        lead = occ.holiday.lead_time_days or 7
        if score >= ELIGIBLE_FOR_DRAFT and days_until <= lead:
            candidates.append(("holiday", score, occ))

    # 2. Custom events in the next 30 days within their lead window
    for ce in CustomEvent.objects.filter(
        user=user, is_active=True, auto_draft_posts=True,
        date__range=(today, horizon),
    ):
        days_until = (ce.date - today).days
        lead = ce.lead_time_days or 3
        if days_until <= lead:
            candidates.append(("custom", 100, ce))

    # 3. Sort by score desc and cap at top 3 per night to control cost
    candidates.sort(key=lambda t: -t[1])
    candidates = candidates[:3]

    for kind, score, moment in candidates:
        draft = _ensure_draft(user, kind, moment, score)
        if draft and draft.status in (HolidayDraft.Status.QUEUED,):
            generate_drafts_for_moment.delay(draft.id)
            queued += 1

    return queued


def _ensure_draft(user, kind: str, moment, score: int) -> HolidayDraft | None:
    """Create-or-fetch the HolidayDraft for (user, moment). Returns None if
    one already exists with terminal status (DISMISSED / APPROVED / DRAFTS_READY)."""
    if kind == "holiday":
        target_date = moment.date
        existing = HolidayDraft.objects.filter(
            user=user, holiday_occurrence=moment, target_date=target_date,
        ).first()
    else:
        target_date = moment.date
        existing = HolidayDraft.objects.filter(
            user=user, custom_event=moment, target_date=target_date,
        ).first()

    if existing:
        if existing.status in (
            HolidayDraft.Status.DISMISSED,
            HolidayDraft.Status.APPROVED,
            HolidayDraft.Status.DRAFTS_READY,
            HolidayDraft.Status.GENERATING,
        ):
            return None
        return existing

    try:
        return HolidayDraft.objects.create(
            user=user,
            target_date=target_date,
            relevance_score=score,
            status=HolidayDraft.Status.QUEUED,
            holiday_occurrence=moment if kind == "holiday" else None,
            custom_event=moment if kind == "custom" else None,
        )
    except IntegrityError:
        # Race condition — another worker just created it. Re-fetch.
        if kind == "holiday":
            return HolidayDraft.objects.filter(
                user=user, holiday_occurrence=moment, target_date=target_date,
            ).first()
        return HolidayDraft.objects.filter(
            user=user, custom_event=moment, target_date=target_date,
        ).first()


# ──────────────────────────────────────────────────────────────────────────
# Per-draft generation
# ──────────────────────────────────────────────────────────────────────────
@shared_task(
    name="calendar_intel.generate_drafts_for_moment",
    autoretry_for=(Exception,),
    retry_backoff=60,
    max_retries=2,
)
def generate_drafts_for_moment(draft_id: int) -> int:
    """Generate post drafts for one HolidayDraft. Wraps the generator orchestrator."""
    return generate_drafts_for_holiday_draft(draft_id)
