"""Moment Mode — HolidayDraft pack status for the hero modal."""

from __future__ import annotations

from django.utils import timezone


def _moment_name(draft) -> str:
    if draft.custom_event_id:
        return draft.custom_event.name
    if draft.holiday_occurrence_id:
        occ = draft.holiday_occurrence
        if occ and occ.holiday_id:
            return occ.holiday.name
    return "Cultural moment"


def build_moment_pack_status(draft, user) -> dict:
    """JSON status for Moment Pack modal polling."""
    from apps.calendar_intel.models import HolidayDraft
    from apps.content.models import Post

    if not draft or draft.user_id != user.pk:
        return {
            "status": "failed",
            "terminal": True,
            "error_message": "Moment pack not found",
            "posts": [],
            "progress_percent": 0,
        }

    today = timezone.localdate()
    days_until = (draft.target_date - today).days if draft.target_date else 0
    name = _moment_name(draft)

    posts = list(
        draft.posts_generated.filter(user=user).select_related("social_account").order_by("platform")
    )
    post_rows = []
    approved = pending = 0
    for p in posts:
        st = p.status
        if st in (Post.Status.APPROVED, Post.Status.SCHEDULED, Post.Status.PUBLISHED):
            approved += 1
            item_status = "completed"
        elif st == Post.Status.FAILED:
            item_status = "failed"
        else:
            pending += 1
            item_status = "pending"
        post_rows.append({
            "post_id": str(p.pk),
            "platform": p.platform or (p.social_account.platform if p.social_account else ""),
            "preview": (p.content_text or "")[:160],
            "status": item_status,
        })

    if draft.status == HolidayDraft.Status.GENERATING:
        overall = "processing"
        terminal = False
        progress = 45
    elif draft.status == HolidayDraft.Status.DRAFTS_READY:
        overall = "ready"
        terminal = True
        progress = 100
    elif draft.status == HolidayDraft.Status.APPROVED:
        overall = "completed"
        terminal = True
        progress = 100
    elif draft.status == HolidayDraft.Status.DISMISSED:
        overall = "dismissed"
        terminal = True
        progress = 100
    elif draft.status == HolidayDraft.Status.FAILED:
        overall = "failed"
        terminal = True
        progress = 100
    else:
        overall = "processing"
        terminal = draft.status not in (
            HolidayDraft.Status.QUEUED,
            HolidayDraft.Status.GENERATING,
        )
        progress = 20 if draft.status == HolidayDraft.Status.QUEUED else 60

    steps = [
        {
            "id": "watch",
            "message": "Moment detected",
            "detail": f"{name} · {days_until} day{'s' if days_until != 1 else ''} away",
            "status": "completed",
        },
        {
            "id": "draft",
            "message": "AI drafting posts",
            "detail": f"{len(posts)} platform post{'s' if len(posts) != 1 else ''}",
            "status": "completed" if draft.status == HolidayDraft.Status.DRAFTS_READY else (
                "running" if draft.status == HolidayDraft.Status.GENERATING else "pending"
            ),
        },
        {
            "id": "approve",
            "message": "Your approval",
            "detail": f"{approved} approved · {pending} waiting" if posts else "Waiting for drafts",
            "status": "completed" if draft.status == HolidayDraft.Status.APPROVED else (
                "running" if draft.status == HolidayDraft.Status.DRAFTS_READY else "pending"
            ),
        },
    ]

    return {
        "status": overall,
        "terminal": terminal,
        "draft_id": draft.pk,
        "moment_name": name,
        "target_date": draft.target_date.isoformat() if draft.target_date else "",
        "days_until": days_until,
        "relevance_score": draft.relevance_score,
        "draft_status": draft.status,
        "posts": post_rows,
        "post_count": len(posts),
        "approved_count": approved,
        "pending_count": pending,
        "steps": steps,
        "progress_percent": progress,
        "error_message": "" if draft.status != HolidayDraft.Status.FAILED else "Draft generation failed",
        "studio_url": "/content/studio/?source=holiday",
    }
