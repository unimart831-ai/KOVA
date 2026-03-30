import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from apps.engage.models import Interaction
from apps.platforms.providers.registry import get_provider

logger = logging.getLogger(__name__)


@login_required
def engage_inbox(request):
    """Engagement inbox — view and respond to interactions."""
    interactions = request.user.interactions.select_related(
        "social_account", "post"
    ).all()[:50]
    return render(request, "engage/inbox.html", {
        "interactions": interactions,
        "page_title": "Engagement Inbox",
    })


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
                account=account,
                comment_id=interaction.platform_interaction_id,
                message=interaction.ai_suggested_reply,
            )
        elif interaction.interaction_type == "dm":
            # Send DM via provider
            provider.send_message(
                account=account,
                recipient_id=interaction.author_username or interaction.author_name,
                message=interaction.ai_suggested_reply,
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
