import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

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
        interaction.save(update_fields=["ai_reply_sent", "status", "user_edited_reply"])

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
