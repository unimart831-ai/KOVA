import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.engage.models import Interaction, Superfan
from apps.platforms.providers.registry import get_provider

logger = logging.getLogger(__name__)


@login_required
def engage_inbox(request):
    """Engagement inbox — view and respond to interactions with filter support."""
    from apps.engage.lead_escalation import escalate_flagged_threads

    escalate_flagged_threads(request.user)

    interactions = request.user.interactions.select_related(
        "social_account", "post"
    )

    # Filters
    status_filter = request.GET.get("status", "")
    needs_reply_filter = request.GET.get("needs_reply", "")
    sentiment_filter = request.GET.get("sentiment", "")
    platform_filter = request.GET.get("platform", "")

    if needs_reply_filter in ("1", "true", "yes"):
        interactions = interactions.filter(status__in=["new", "flagged"])
    elif status_filter:
        interactions = interactions.filter(status=status_filter)
    if sentiment_filter:
        interactions = interactions.filter(sentiment=sentiment_filter)
    if platform_filter:
        interactions = interactions.filter(social_account__platform=platform_filter)

    interactions = interactions.all()[:50]

    from django.db.models import Count, Q

    stats_row = request.user.interactions.aggregate(
        total=Count("id"),
        new=Count("id", filter=Q(status="new")),
        flagged=Count("id", filter=Q(status="flagged")),
        needs_reply=Count(
            "id",
            filter=Q(ai_suggested_reply="")
            & ~Q(status__in=["ignored", "ai_replied", "user_replied"])
            & ~Q(sentiment=""),
        ),
    )
    stats = {
        "total": stats_row["total"],
        "new": stats_row["new"],
        "flagged": stats_row["flagged"],
        "needs_reply": stats_row["needs_reply"],
    }

    # Superfans tracked by the Engage Agent
    superfans = Superfan.objects.filter(user=request.user)[:10]

    return render(request, "engage/inbox.html", {
        "interactions": interactions,
        "page_title": "Engagement Inbox",
        "stats": stats,
        "superfans": superfans,
        "status_filter": status_filter,
        "sentiment_filter": sentiment_filter,
        "platform_filter": platform_filter,
    })


@login_required
def trigger_engage(request):
    """Manually trigger the Engage Agent cycle for the current user (HTMX)."""
    if request.method != "POST":
        return HttpResponse(status=405)

    from apps.agents.engage_agent import run_engage_cycle
    from apps.utils import fire_task

    fire_task(run_engage_cycle, request.user)
    return HttpResponse(
        '<div class="text-sm text-green-600 dark:text-green-400 px-4 py-2">'
        "Engage cycle started — refresh in a moment to see new interactions."
        "</div>",
    )


@login_required
def send_reply(request, pk):
    """Send an AI-suggested reply via the platform API."""
    if request.method != "POST":
        return HttpResponse(status=405)

    interaction = get_object_or_404(
        Interaction.objects.select_related("social_account"), pk=pk, user=request.user
    )

    if not interaction.ai_suggested_reply:
        return HttpResponse(
            '<div class="text-sm text-red-600 px-4 py-2">No suggested reply to send.</div>',
            status=422,
        )

    # Intelligence: allow user to edit the reply before sending
    reply_text = request.POST.get("reply_text", "").strip()
    if reply_text and reply_text != interaction.ai_suggested_reply:
        interaction.user_edited_reply = True
        interaction.ai_reply_sent = reply_text
    else:
        reply_text = interaction.ai_suggested_reply

    account = interaction.social_account
    provider = get_provider(account.platform)

    if not provider:
        return HttpResponse(
            '<div class="text-sm text-red-600 px-4 py-2">Provider not available.</div>',
            status=422,
        )

    try:
        # For Facebook/Instagram, use page token instead of user token
        token = account.access_token
        if account.platform in ("facebook", "instagram"):
            pages = (account.metadata or {}).get("pages", [])
            if pages:
                token = pages[0].get("access_token", account.access_token)

        if interaction.interaction_type in ("comment", "reply"):
            # Reply to comment via provider
            result = provider.reply_to_comment(
                access_token=token,
                comment_id=interaction.platform_interaction_id,
                message=reply_text,
            )
            if not result.get("success"):
                error_msg = result.get("error", "Unknown error")[:200]
                return HttpResponse(
                    f'<div class="text-sm text-red-600 px-4 py-2">Reply failed: {error_msg}</div>',
                    status=500,
                )
        elif interaction.interaction_type == "dm":
            # Send DM via provider
            result = provider.send_message(
                access_token=token,
                recipient_id=interaction.author_username or interaction.author_name,
                message=reply_text,
            )
            if isinstance(result, dict) and not result.get("success", True):
                error_msg = result.get("error", "Unknown error")[:200]
                return HttpResponse(
                    f'<div class="text-sm text-red-600 px-4 py-2">DM failed: {error_msg}</div>',
                    status=500,
                )
        else:
            return HttpResponse(
                '<div class="text-sm text-amber-600 px-4 py-2">Reply not supported for this interaction type.</div>',
                status=422,
            )

        # Mark as replied
        interaction.ai_reply_sent = reply_text
        interaction.status = Interaction.Status.AI_REPLIED
        if not interaction.responded_at:
            interaction.responded_at = timezone.now()
        interaction.save(update_fields=["ai_reply_sent", "status", "user_edited_reply", "responded_at"])

        # Re-render the interaction item
        return render(request, "engage/_interaction_item.html", {
            "interaction": interaction,
        })

    except Exception as exc:
        logger.error("Failed to send reply for interaction %s: %s", pk, exc, exc_info=True)
        return HttpResponse(
            f'<div class="text-sm text-red-600 px-4 py-2">Failed to send: {exc}</div>',
            status=500,
        )


# ── Engage Agent v2 — Auto-sent log + Undo + Correction (W2 May 2026) ──────


@login_required
def auto_sent_list(request):
    """Recent Engage Agent auto-sends, with inline undo + correction.

    The user gets to see exactly what the AI said on their behalf, undo
    within 5 minutes, and post a correction even after the window closes.
    Corrections feed back into the Engage Agent's prompt as few-shot
    examples (see apps/agents/engage_agent.py:_recent_corrections_for_brand).
    """
    from datetime import timedelta
    from apps.engage.models import EngageReply

    recent = (
        EngageReply.objects
        .filter(interaction__user=request.user)
        .select_related("interaction", "interaction__social_account")
        .order_by("-sent_at")[:50]
    )
    return render(request, "engage/auto_sent_list.html", {
        "replies": recent,
        "page_title": "AI auto-sent replies",
    })


@login_required
def auto_sent_undo(request, pk):
    """Try to retract an auto-sent reply via the platform's delete API.

    Idempotent against re-clicks. If the undo window has closed, returns
    422 with a friendly message and points the user at the correction
    flow as the remaining option.
    """
    from apps.engage.models import EngageReply
    from apps.engage.models import Interaction
    from apps.platforms.providers.registry import get_provider

    reply = get_object_or_404(
        EngageReply, pk=pk, interaction__user=request.user,
    )
    if reply.undone_at:
        return HttpResponse(
            "Already undone.", status=200, content_type="text/plain",
        )
    if not reply.can_undo():
        return HttpResponse(
            "Undo window closed (5 minutes). You can still leave a correction below.",
            status=422, content_type="text/plain",
        )

    account = reply.interaction.social_account
    if not account or not reply.platform_reply_id:
        reply.undo_error = "Missing account or platform_reply_id"
        reply.save(update_fields=["undo_error"])
        return HttpResponse("Couldn't reach the platform. Try again later.", status=502)

    provider = get_provider(account.platform)
    if not provider or not hasattr(provider, "delete_comment"):
        reply.undo_error = f"Provider {account.platform} has no delete_comment"
        reply.save(update_fields=["undo_error"])
        return HttpResponse(
            f"{account.get_platform_display()} doesn't support remote delete from Kova yet. "
            "Delete the comment manually and leave a correction below.",
            status=422,
        )

    try:
        result = provider.delete_comment(
            access_token=account.access_token,
            comment_id=reply.platform_reply_id,
            account=account,
        ) or {}
    except Exception as exc:
        reply.undo_error = str(exc)
        reply.save(update_fields=["undo_error"])
        logger.exception("Undo crashed for EngageReply %s: %s", reply.pk, exc)
        return HttpResponse("Undo failed — try again in a moment.", status=502)

    if not result.get("success"):
        reply.undo_error = result.get("error", "unknown error")[:500]
        reply.save(update_fields=["undo_error"])
        return HttpResponse(
            f"Platform rejected the delete: {result.get('error', 'unknown error')[:200]}",
            status=502,
        )

    reply.undone_at = timezone.now()
    reply.undo_error = ""
    reply.save(update_fields=["undone_at", "undo_error"])

    # Bump the interaction back to FLAGGED so the user can replace the reply
    reply.interaction.status = Interaction.Status.FLAGGED
    reply.interaction.ai_reply_sent = ""
    reply.interaction.responded_at = None
    reply.interaction.save(update_fields=["status", "ai_reply_sent", "responded_at"])

    return HttpResponse("Undone — the reply was retracted.", status=200, content_type="text/plain")


@login_required
def auto_sent_correct(request, pk):
    """Record a user correction on an auto-sent reply.

    Persists the user's "I would have said this instead" text. The next
    Engage Agent run picks it up via _recent_corrections_for_brand and
    biases future replies toward the user's style. Available even after
    the undo window has closed — the platform reply stays but the AI
    learns.
    """
    from apps.engage.models import EngageReply

    if request.method != "POST":
        return HttpResponse(status=405)

    reply = get_object_or_404(
        EngageReply, pk=pk, interaction__user=request.user,
    )

    correction_text = (request.POST.get("correction_text") or "").strip()
    reason = (request.POST.get("correction_reason") or "other").lower()
    if reason not in dict(EngageReply.CorrectionReason.choices):
        reason = "other"

    if not correction_text:
        return HttpResponse("Correction text required.", status=400, content_type="text/plain")

    reply.correction_text = correction_text[:2000]
    reply.correction_reason = reason
    reply.corrected_at = timezone.now()
    reply.save(update_fields=["correction_text", "correction_reason", "corrected_at"])

    return HttpResponse(
        "Thanks — Kova will use this to learn your style.",
        status=200, content_type="text/plain",
    )


# ── Unified needs-reply inbox (WA + Engage) ───────────────────────────────────


@login_required
def unified_needs_reply(request):
    """Single queue for WhatsApp escalations and social inbox items needing reply."""
    from datetime import timedelta

    from django.urls import reverse
    from django.utils.timesince import timesince

    from apps.whatsapp.models import WhatsAppConversation, WhatsAppMessage

    items = []
    week_ago = timezone.now() - timedelta(days=7)

    wa_convs = (
        WhatsAppConversation.objects.filter(
            social_account__user=request.user,
            status=WhatsAppConversation.Status.ESCALATED,
        )
        .select_related("social_account")
        .order_by("-last_message_at")[:25]
    )
    for conv in wa_convs:
        last_msg = (
            WhatsAppMessage.objects.filter(conversation=conv)
            .order_by("-created_at")
            .first()
        )
        preview = (last_msg.content if last_msg else "")[:160]
        items.append({
            "source": "whatsapp",
            "source_label": "WhatsApp",
            "title": conv.contact_name or conv.contact_phone,
            "preview": preview or "Escalated conversation",
            "time_ago": timesince(conv.last_message_at or conv.created_at),
            "sort_at": conv.last_message_at or conv.created_at,
            "url": reverse("whatsapp:inbox") + f"?status=escalated&conv={conv.pk}",
        })

    engage_qs = (
        request.user.interactions.filter(status__in=["new", "flagged"])
        .select_related("social_account")
        .order_by("-created_at")[:25]
    )
    for interaction in engage_qs:
        items.append({
            "source": "engage",
            "source_label": interaction.platform.title(),
            "title": interaction.author_name or interaction.author_username or "Unknown",
            "preview": (interaction.content or "")[:160],
            "time_ago": timesince(interaction.created_at),
            "sort_at": interaction.created_at,
            "url": reverse("engage:inbox") + f"?needs_reply=1",
        })

    items.sort(key=lambda i: i["sort_at"], reverse=True)

    stats = {
        "total": len(items),
        "wa_count": wa_convs.count(),
        "engage_count": engage_qs.count(),
    }

    return render(request, "engage/unified_inbox.html", {
        "items": items,
        "stats": stats,
        "page_title": "Needs reply",
    })


# ── Phase 5 — Unified DM Inbox / Messenger threads ──────────────────────────


@login_required
def messenger_threads(request):
    """Thin MVP: Facebook Messenger threads via DM inbox pipeline."""
    from apps.engage.dm_inbox import get_dm_threads

    threads = get_dm_threads(request.user, platform="facebook", limit=30)
    stats = {
        "total_threads": len(threads),
        "unread": sum(t["unread_count"] for t in threads),
        "platforms": ["facebook"],
    }
    return render(request, "engage/dm_inbox.html", {
        "threads": threads,
        "messages": [],
        "stats": stats,
        "platform_filter": "facebook",
        "selected_sender": "",
        "page_title": "Messenger threads",
        "messenger_mode": True,
    })


@login_required
def dm_inbox_view(request):
    """Unified DM inbox across platforms (FB, IG, WhatsApp)."""
    from apps.engage.dm_inbox import get_dm_threads

    platform_filter = request.GET.get("platform", "")
    threads = get_dm_threads(
        request.user,
        platform=platform_filter or None,
        limit=30,
    )

    dm_interactions = request.user.interactions.filter(
        interaction_type=Interaction.InteractionType.DM,
    ).select_related("social_account")

    if platform_filter:
        dm_interactions = dm_interactions.filter(platform=platform_filter)

    sender = request.GET.get("sender", "")
    messages = []
    if sender:
        messages = dm_interactions.filter(
            author_username=sender,
        ).order_by("created_at")[:50]

    stats = {
        "total_threads": len(threads),
        "unread": sum(t["unread_count"] for t in threads),
        "platforms": list(set(t["platform"] for t in threads)),
    }

    return render(request, "engage/dm_inbox.html", {
        "threads": threads,
        "messages": messages,
        "stats": stats,
        "platform_filter": platform_filter,
        "selected_sender": sender,
        "page_title": "Messages",
    })
