"""
WhatsApp views — inbox, conversation detail, manual reply, template management.
"""

import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.platforms.models import SocialAccount
from apps.platforms.providers.registry import get_provider
from apps.whatsapp.models import (
    WhatsAppBroadcast,
    WhatsAppConversation,
    WhatsAppMessage,
    WhatsAppTemplate,
)

logger = logging.getLogger(__name__)


# ─── Inbox ───────────────────────────────────────────────────────────────────

@login_required
def whatsapp_inbox(request):
    """WhatsApp conversations inbox — all active conversations."""
    wa_accounts = SocialAccount.objects.filter(
        user=request.user, platform="whatsapp", is_active=True,
    )

    conversations = WhatsAppConversation.objects.filter(
        social_account__in=wa_accounts,
    ).select_related("social_account")

    # Filters
    status_filter = request.GET.get("status", "")
    language_filter = request.GET.get("language", "")

    if status_filter:
        conversations = conversations.filter(status=status_filter)
    if language_filter:
        conversations = conversations.filter(language=language_filter)

    conversations = conversations[:50]

    # Stats
    all_convos = WhatsAppConversation.objects.filter(social_account__in=wa_accounts)
    stats = {
        "total": all_convos.count(),
        "active": all_convos.filter(status="active").count(),
        "escalated": all_convos.filter(status="escalated").count(),
        "ai_handling": all_convos.filter(ai_handling=True).count(),
    }

    # Message counts for today
    today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    stats["messages_today"] = WhatsAppMessage.objects.filter(
        conversation__social_account__in=wa_accounts,
        created_at__gte=today,
    ).count()
    stats["ai_replies_today"] = WhatsAppMessage.objects.filter(
        conversation__social_account__in=wa_accounts,
        created_at__gte=today,
        direction="outbound",
        is_ai_generated=True,
    ).count()

    return render(request, "whatsapp/inbox.html", {
        "conversations": conversations,
        "stats": stats,
        "wa_accounts": wa_accounts,
        "status_filter": status_filter,
        "language_filter": language_filter,
        "page_title": "WhatsApp Inbox",
    })


# ─── Conversation Detail ────────────────────────────────────────────────────

@login_required
def whatsapp_conversation(request, pk):
    """View a single conversation thread with all messages."""
    conversation = get_object_or_404(
        WhatsAppConversation.objects.select_related("social_account"),
        pk=pk,
        social_account__user=request.user,
    )

    messages = WhatsAppMessage.objects.filter(
        conversation=conversation,
    ).order_by("created_at")[:200]

    # Check for pending AI drafts (medium confidence, not yet sent)
    pending_drafts = WhatsAppMessage.objects.filter(
        conversation=conversation,
        direction="outbound",
        status="pending",
        is_ai_generated=True,
    )

    return render(request, "whatsapp/conversation.html", {
        "conversation": conversation,
        "messages": messages,
        "pending_drafts": pending_drafts,
        "page_title": f"Chat with {conversation.contact_name or conversation.contact_wa_id}",
    })


# ─── Send Message ───────────────────────────────────────────────────────────

@login_required
@require_POST
def send_message(request, pk):
    """Send a manual message or approve an AI draft."""
    conversation = get_object_or_404(
        WhatsAppConversation.objects.select_related("social_account"),
        pk=pk,
        social_account__user=request.user,
    )

    message_text = request.POST.get("message", "").strip()
    draft_id = request.POST.get("draft_id", "")

    if draft_id:
        # Approve and send an AI draft
        try:
            draft = WhatsAppMessage.objects.get(
                id=draft_id,
                conversation=conversation,
                status="pending",
            )
            # Allow user to edit the draft
            edited_text = request.POST.get("message", "").strip()
            if edited_text:
                draft.content = edited_text
            message_text = draft.content
        except WhatsAppMessage.DoesNotExist:
            return HttpResponse(
                '<div class="text-sm text-red-500 p-2">Draft not found.</div>',
                status=404,
            )
    elif not message_text:
        return HttpResponse(
            '<div class="text-sm text-red-500 p-2">Message cannot be empty.</div>',
            status=422,
        )

    # Check if we're within the 24-hour window
    if not conversation.is_window_open:
        return HttpResponse(
            '<div class="text-sm text-amber-500 p-2">'
            '24-hour window expired. Use a template message to re-engage.'
            '</div>',
            status=422,
        )

    # Send via WhatsApp Cloud API
    provider = get_provider("whatsapp")
    if not provider:
        return HttpResponse(
            '<div class="text-sm text-red-500 p-2">WhatsApp provider not available.</div>',
            status=500,
        )

    result = provider.send_text_message(
        access_token=conversation.social_account.access_token,
        to=conversation.contact_wa_id,
        body=message_text,
    )

    if result.get("success"):
        if draft_id:
            # Update the draft
            draft.wamid = result.get("wamid", "")
            draft.status = WhatsAppMessage.MessageStatus.SENT
            draft.save(update_fields=["content", "wamid", "status"])
        else:
            # Create new outbound message
            WhatsAppMessage.objects.create(
                conversation=conversation,
                direction=WhatsAppMessage.Direction.OUTBOUND,
                message_type=WhatsAppMessage.MessageType.TEXT,
                content=message_text,
                wamid=result.get("wamid", ""),
                status=WhatsAppMessage.MessageStatus.SENT,
                is_ai_generated=False,
            )

        conversation.last_message_at = timezone.now()
        conversation.save(update_fields=["last_message_at", "updated_at"])

        # Return the new message bubble (HTMX swap)
        return render(request, "whatsapp/_message_bubble.html", {
            "msg": {
                "direction": "outbound",
                "content": message_text,
                "is_ai_generated": bool(draft_id),
                "status": "sent",
                "created_at": timezone.now(),
            },
        })
    else:
        error = result.get("error", "Unknown error")[:200]
        return HttpResponse(
            f'<div class="text-sm text-red-500 p-2">Send failed: {error}</div>',
            status=500,
        )


# ─── Toggle AI ──────────────────────────────────────────────────────────────

@login_required
@require_POST
def toggle_ai(request, pk):
    """Toggle AI auto-reply on/off for a conversation."""
    conversation = get_object_or_404(
        WhatsAppConversation,
        pk=pk,
        social_account__user=request.user,
    )

    conversation.ai_handling = not conversation.ai_handling
    if conversation.ai_handling and conversation.status == WhatsAppConversation.Status.ESCALATED:
        conversation.status = WhatsAppConversation.Status.ACTIVE
    conversation.save(update_fields=["ai_handling", "status", "updated_at"])

    state = "enabled" if conversation.ai_handling else "disabled"
    color = "green" if conversation.ai_handling else "amber"
    return HttpResponse(
        f'<div class="text-sm text-{color}-500 p-2">AI auto-reply {state}.</div>',
    )


# ─── Template Management ────────────────────────────────────────────────────

@login_required
def template_list(request):
    """List all WhatsApp message templates."""
    wa_accounts = SocialAccount.objects.filter(
        user=request.user, platform="whatsapp", is_active=True,
    )

    templates = WhatsAppTemplate.objects.filter(
        social_account__in=wa_accounts,
    ).order_by("-created_at")

    status_filter = request.GET.get("status", "")
    if status_filter:
        templates = templates.filter(status=status_filter)

    return render(request, "whatsapp/template_list.html", {
        "templates": templates,
        "wa_accounts": wa_accounts,
        "status_filter": status_filter,
        "page_title": "WhatsApp Templates",
    })


@login_required
@require_POST
def template_create(request):
    """Create a new WhatsApp template (manual or AI-assisted)."""
    wa_accounts = SocialAccount.objects.filter(
        user=request.user, platform="whatsapp", is_active=True,
    )

    if not wa_accounts.exists():
        return HttpResponse(
            '<div class="text-sm text-red-500 p-2">Connect a WhatsApp account first.</div>',
            status=422,
        )

    account = wa_accounts.first()
    name = request.POST.get("name", "").strip().lower().replace(" ", "_")
    category = request.POST.get("category", "marketing")
    language = request.POST.get("language", "en")
    body_text = request.POST.get("body_text", "").strip()
    footer_text = request.POST.get("footer_text", "").strip()
    ai_prompt = request.POST.get("ai_prompt", "").strip()

    if ai_prompt:
        # AI-assisted template creation
        template_obj = _ai_generate_template(account, ai_prompt, category, language)
        if template_obj:
            return redirect("whatsapp:template_list")
        return HttpResponse(
            '<div class="text-sm text-red-500 p-2">AI template generation failed. Try again.</div>',
            status=500,
        )

    if not name or not body_text:
        return HttpResponse(
            '<div class="text-sm text-red-500 p-2">Name and body text are required.</div>',
            status=422,
        )

    WhatsAppTemplate.objects.create(
        social_account=account,
        name=name,
        category=category,
        language=language,
        body_text=body_text,
        footer_text=footer_text,
    )

    return redirect("whatsapp:template_list")


def _ai_generate_template(account, prompt, category, language):
    """Use the Create Agent to draft a WhatsApp template."""
    from apps.agents.llm import generate, get_model_for_task, parse_llm_json

    profile = getattr(account.user, "profile", None)
    brand_name = profile.company_name if profile else "the business"

    system = f"""You are a WhatsApp template expert for {brand_name}.
Generate a Meta-policy-compliant WhatsApp message template.

Rules:
- Template names must be lowercase with underscores only
- Body can use {{{{1}}}}, {{{{2}}}}, etc. for variable slots
- Keep body under 1024 characters
- Marketing templates need clear opt-out instructions
- No misleading content, threats, or prohibited topics
- Language: {'Swahili' if language == 'sw' else 'English'}

Respond in JSON:
  "name": "template_name_here",
  "body_text": "Template body with {{{{1}}}} variables",
  "footer_text": "Optional footer",
  "header_text": "Optional header",
  "buttons": [{{"type": "QUICK_REPLY", "text": "Button text"}}]
"""

    response = generate(
        prompt=f"Create a {category} WhatsApp template for: {prompt}",
        system=system,
        model=get_model_for_task("create"),
        temperature=0.7,
        json_mode=True,
    )

    parsed = parse_llm_json(response.content) if response.content else None
    if not parsed:
        return None

    template = WhatsAppTemplate.objects.create(
        social_account=account,
        name=parsed.get("name", "ai_template")[:512],
        category=category,
        language=language,
        body_text=parsed.get("body_text", ""),
        footer_text=parsed.get("footer_text", ""),
        header_text=parsed.get("header_text", ""),
        buttons=parsed.get("buttons", []),
        created_by_ai=True,
        ai_prompt_used=prompt,
    )
    return template
