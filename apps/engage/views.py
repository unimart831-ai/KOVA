import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from apps.engage.models import Interaction
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

    return render(request, "engage/inbox.html", {
        "interactions": interactions,
        "page_title": "Engagement Inbox",
        "stats": stats,
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
            msg = f"Found {result['fetched']} new interactions, generated {result['replies_generated']} replies."
        else:
            msg = "No new interactions found."
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
        Interaction, pk=pk, user=request.user
    )

    if not interaction.ai_suggested_reply:
        return HttpResponse(
            '<div class="text-sm text-red-600 px-4 py-2">No suggested reply to send.</div>',
            status=422,
        )

    account = interaction.social_account
    provider = get_provider(account.platform)

    if not provider:
        return HttpResponse(
            '<div class="text-sm text-red-600 px-4 py-2">Provider not available.</div>',
            status=422,
        )

    try:
        if interaction.interaction_type in ("comment", "reply"):
            # Reply to comment via provider
            provider.reply_to_comment(
                access_token=account.access_token,
                comment_id=interaction.platform_interaction_id,
                message=interaction.ai_suggested_reply,
                account=account,
            )
        elif interaction.interaction_type == "dm":
            # Send DM via provider
            provider.send_message(
                access_token=account.access_token,
                recipient_id=interaction.author_username or interaction.author_name,
                message=interaction.ai_suggested_reply,
                account=account,
            )
        else:
            return HttpResponse(
                '<div class="text-sm text-amber-600 px-4 py-2">Reply not supported for this interaction type.</div>',
                status=422,
            )

        # Mark as replied
        interaction.ai_reply_sent = interaction.ai_suggested_reply
        interaction.status = Interaction.Status.AI_REPLIED
        interaction.save(update_fields=["ai_reply_sent", "status"])

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
