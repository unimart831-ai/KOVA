"""Decision Stream — single prioritized queue of everything needing owner attention.

Replaces the 4+ overlapping "your move" surfaces (money board, standup hero,
quick_actions, extract_your_move) with one deterministic, DB-first stream.

Used by: briefs/views.py (brief_home), WhatsApp standup (future).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)

STREAM_CAP = 12


@dataclass
class StreamItem:
    kind: str           # approve_post | reply_message | review_lead | fix_failed | confirm_booking | review_draft | strategic | onboarding | connect_platform
    urgency: str        # critical | today | later
    title: str
    subtitle: str = ""
    action_url: str = ""
    inline_actions: list = field(default_factory=list)
    source_id: str = ""
    dismissible: bool = False
    meta: dict = field(default_factory=dict)


def build_decision_stream(user, brief=None) -> list[StreamItem]:
    """Build a single prioritized queue of owner-actionable items.

    Sources are queried in priority order. Each source appends to the
    stream and is capped individually so no single category floods the
    list. The final stream is capped at STREAM_CAP items.
    """
    stream: list[StreamItem] = []

    stream += _failed_posts(user)
    stream += _flagged_interactions(user)
    stream += _pending_posts(user)
    stream += _needs_reply_interactions(user)
    stream += _escalated_whatsapp(user)
    stream += _new_leads(user)
    stream += _pending_bookings(user)
    stream += _strategic_decisions(brief)
    stream += _connect_platform_nudge(user)
    stream += _onboarding_next_step(user)

    return stream[:STREAM_CAP]


def _failed_posts(user) -> list[StreamItem]:
    try:
        from apps.content.models import Post
        failed = (
            Post.objects.filter(user=user, status=Post.Status.FAILED)
            .select_related("social_account")
            .order_by("-updated_at")[:3]
        )
        items = []
        for p in failed:
            platform = p.social_account.get_platform_display() if p.social_account else "Post"
            preview = (p.content_text or "")[:50].strip()
            items.append(StreamItem(
                kind="fix_failed",
                urgency="critical",
                title=f"Failed: {preview}..." if len(p.content_text or "") > 50 else f"Failed: {preview or 'Untitled post'}",
                subtitle=f"{platform} · failed to publish",
                action_url=reverse("content:post_detail", kwargs={"post_id": p.id}),
                inline_actions=[
                    {"label": "Retry", "method": "post", "url": reverse("content:republish", kwargs={"post_id": p.id}), "variant": "primary"},
                ],
                source_id=str(p.id),
                meta={"platform": p.social_account.platform if p.social_account else ""},
            ))
        return items
    except Exception:
        logger.exception("Decision stream: failed_posts error")
        return []


def _flagged_interactions(user) -> list[StreamItem]:
    try:
        from apps.engage.models import Interaction
        flagged = (
            Interaction.objects.filter(user=user, status=Interaction.Status.FLAGGED)
            .select_related("social_account")
            .order_by("-created_at")[:3]
        )
        items = []
        for i in flagged:
            platform = i.social_account.get_platform_display() if i.social_account else i.platform
            items.append(StreamItem(
                kind="reply_message",
                urgency="critical",
                title=f"Flagged: {i.author_name} — {(i.content or '')[:40]}",
                subtitle=f"{platform} · {i.get_interaction_type_display()}",
                action_url=reverse("engage:inbox"),
                source_id=str(i.id),
                meta={"platform": i.platform, "sentiment": getattr(i, "sentiment", "")},
            ))
        return items
    except Exception:
        logger.exception("Decision stream: flagged_interactions error")
        return []


def _pending_posts(user) -> list[StreamItem]:
    try:
        from apps.content.models import Post
        pending = (
            Post.objects.filter(
                user=user, status__in=[Post.Status.DRAFT, Post.Status.PENDING_APPROVAL],
            )
            .select_related("social_account")
            .order_by("-created_at")[:4]
        )
        items = []
        for p in pending:
            platform = p.social_account.get_platform_display() if p.social_account else "Post"
            preview = (p.content_text or "")[:50].strip()
            items.append(StreamItem(
                kind="approve_post",
                urgency="today",
                title=preview or "Untitled post",
                subtitle=f"{platform} · awaiting approval",
                action_url=reverse("content:post_detail", kwargs={"post_id": p.id}),
                inline_actions=[
                    {"label": "Approve", "method": "post", "url": reverse("content:approve", kwargs={"post_id": p.id}), "variant": "primary"},
                    {"label": "Reject", "method": "post", "url": reverse("content:reject", kwargs={"post_id": p.id}), "variant": "ghost"},
                ],
                source_id=str(p.id),
                meta={"platform": p.social_account.platform if p.social_account else ""},
            ))
        return items
    except Exception:
        logger.exception("Decision stream: pending_posts error")
        return []


def _needs_reply_interactions(user) -> list[StreamItem]:
    try:
        from apps.engage.models import Interaction
        needs_reply = (
            Interaction.objects.filter(user=user, status=Interaction.Status.NEW)
            .select_related("social_account")
            .order_by("-created_at")[:3]
        )
        count = Interaction.objects.filter(
            user=user, status=Interaction.Status.NEW,
        ).count()
        if not needs_reply:
            return []
        first = needs_reply[0]
        platform = first.social_account.get_platform_display() if first.social_account else first.platform
        if count == 1:
            return [StreamItem(
                kind="reply_message",
                urgency="today",
                title=f"{first.author_name}: {(first.content or '')[:40]}",
                subtitle=f"{platform} · {first.get_interaction_type_display()}",
                action_url=reverse("engage:inbox"),
                source_id=str(first.id),
                meta={"count": 1},
            )]
        return [StreamItem(
            kind="reply_message",
            urgency="today",
            title=f"{count} messages need your reply",
            subtitle=f"Latest from {first.author_name} on {platform}",
            action_url=reverse("engage:inbox"),
            source_id="",
            meta={"count": count},
        )]
    except Exception:
        logger.exception("Decision stream: needs_reply error")
        return []


def _escalated_whatsapp(user) -> list[StreamItem]:
    try:
        from apps.whatsapp.models import WhatsAppConversation
        escalated = (
            WhatsAppConversation.objects.filter(
                social_account__user=user,
                status=WhatsAppConversation.Status.ESCALATED,
            )
            .order_by("-last_message_at")[:3]
        )
        count = escalated.count()
        if not count:
            return []
        first = escalated[0] if escalated else None
        if count == 1 and first:
            return [StreamItem(
                kind="review_draft",
                urgency="today",
                title=f"WhatsApp: {first.contact_name or first.contact_phone} needs you",
                subtitle="Escalated by AI — human reply needed",
                action_url=reverse("whatsapp:inbox"),
                source_id=str(first.id),
                meta={"count": 1},
            )]
        return [StreamItem(
            kind="review_draft",
            urgency="today",
            title=f"{count} WhatsApp conversations escalated",
            subtitle="AI needs your help with these",
            action_url=reverse("whatsapp:inbox"),
            source_id="",
            meta={"count": count},
        )]
    except Exception:
        logger.exception("Decision stream: escalated_whatsapp error")
        return []


def _new_leads(user) -> list[StreamItem]:
    try:
        from apps.leads.models import Lead
        cutoff = timezone.now() - timedelta(hours=24)
        count = Lead.objects.filter(user=user, status=Lead.Status.NEW, created_at__gte=cutoff).count()
        if not count:
            return []
        hot = Lead.objects.filter(
            user=user, status=Lead.Status.NEW, temperature="hot", created_at__gte=cutoff,
        ).count()
        subtitle = f"{hot} hot" if hot else "New in the last 24h"
        return [StreamItem(
            kind="review_lead",
            urgency="today",
            title=f"{count} new lead{'s' if count != 1 else ''} to review",
            subtitle=subtitle,
            action_url=reverse("leads:list"),
            meta={"count": count, "hot": hot},
        )]
    except Exception:
        logger.exception("Decision stream: new_leads error")
        return []


def _pending_bookings(user) -> list[StreamItem]:
    try:
        from apps.bookings.models import Booking
        today = timezone.now().date()
        count = Booking.objects.filter(
            booking_link__user=user, status="pending", scheduled_at__date=today,
        ).count()
        if not count:
            return []
        return [StreamItem(
            kind="confirm_booking",
            urgency="today",
            title=f"{count} booking{'s' if count != 1 else ''} to confirm today",
            subtitle="Clients waiting for confirmation",
            action_url=reverse("bookings:list"),
            meta={"count": count},
        )]
    except Exception:
        logger.exception("Decision stream: pending_bookings error")
        return []


def _strategic_decisions(brief) -> list[StreamItem]:
    """LLM-generated strategic decisions — only items that require human judgment
    beyond what the DB-sourced items above already cover."""
    if not brief:
        return []
    decisions = (brief.performance_summary or {}).get("decisions_needed", [])
    if not decisions:
        return []

    from apps.briefs.standup import enrich_decisions
    enriched = enrich_decisions(decisions)

    items = []
    for d in enriched[:3]:
        urgency_map = {"now": "critical", "today": "today", "this_week": "later"}
        urgency = urgency_map.get(d.get("urgency", ""), "later")
        items.append(StreamItem(
            kind="strategic",
            urgency=urgency,
            title=d.get("item", "Decision needed"),
            subtitle=d.get("context", ""),
            action_url=d.get("action_url", ""),
            dismissible=True,
            meta={"recommended_action": d.get("recommended_action", "")},
        ))
    return items


def _connect_platform_nudge(user) -> list[StreamItem]:
    try:
        from apps.platforms.models import SocialAccount
        has_platform = SocialAccount.objects.filter(user=user, is_active=True).exists()
        if has_platform:
            return []
        return [StreamItem(
            kind="onboarding",
            urgency="today",
            title="Connect your first social account",
            subtitle="Your AI team needs at least one platform to start working",
            action_url=reverse("platforms:list"),
            meta={"step": "connect_platform"},
        )]
    except Exception:
        return []


def _onboarding_next_step(user) -> list[StreamItem]:
    try:
        from datetime import timedelta as _td

        from apps.accounts.wedge_checklist import build_wedge_checklist
        from apps.briefs.dashboard import _collect_home_stats

        today = timezone.now().date()
        stats = _collect_home_stats(user, today, today - _td(days=7))
        checklist = build_wedge_checklist(user, stats)
        if not checklist or checklist.get("completed", 0) >= checklist.get("total", 5):
            return []
        next_step = checklist.get("next_step")
        if not next_step:
            return []
        return [StreamItem(
            kind="onboarding",
            urgency="later",
            title=next_step.get("label", "Complete setup"),
            subtitle=f"Step {checklist['completed'] + 1} of {checklist['total']}",
            action_url=reverse(next_step["url_name"]) if next_step.get("url_name") else reverse("brief:home"),
            meta={"progress_pct": checklist.get("percent", 0)},
        )]
    except Exception:
        logger.exception("Decision stream: onboarding error")
        return []
