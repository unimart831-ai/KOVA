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
    interactions = request.user.interactions.select_related(
        "social_account", "post"
    )

    # Filters
    status_filter = request.GET.get("status", "")
    sentiment_filter = request.GET.get("sentiment", "")
    platform_filter = request.GET.get("platform", "")

    if status_filter:
        interactions = interactions.filter(status=status_filter)
    if sentiment_filter:
        interactions = interactions.filter(sentiment=sentiment_filter)
    if platform_filter:
        interactions = interactions.filter(social_account__platform=platform_filter)

    interactions = interactions.all()[:50]

    # Stats for the header
    stats = {
        "total": request.user.interactions.count(),
        "new": request.user.interactions.filter(status="new").count(),
        "flagged": request.user.interactions.filter(status="flagged").count(),
        "needs_reply": request.user.interactions.filter(
            ai_suggested_reply="",
        ).exclude(status__in=["ignored", "ai_replied", "user_replied"]).exclude(sentiment="").count(),
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

    try:
        result = run_engage_cycle(request.user)
        total = result["fetched"] + result["replies_generated"]
        if total > 0:
            parts = []
            if result["fetched"]:
                parts.append(f"{result['fetched']} new interaction{'s' if result['fetched'] != 1 else ''}")
            if result["analyzed"]:
                parts.append(f"{result['analyzed']} analyzed")
            if result["replies_generated"]:
                parts.append(f"{result['replies_generated']} repl{'ies' if result['replies_generated'] != 1 else 'y'} generated")
            if result["auto_sent"]:
                parts.append(f"{result['auto_sent']} auto-sent")
            msg = ", ".join(parts) + "."
        else:
            msg = "No new comments found on your recent posts. Comments are checked on posts from the last 14 days."
        return HttpResponse(
            f'<div class="text-sm text-green-600 dark:text-green-400 px-4 py-2">{msg}</div>',
        )
    except Exception as e:
        logger.error("Manual engage cycle failed: %s", e)
        return HttpResponse(
            '<div class="text-sm text-red-600 px-4 py-2">Engage cycle failed. Try again later.</div>',
            status=500,
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


# ── Phase 5 — Unified DM Inbox ─────────────────────────────────────────────


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
