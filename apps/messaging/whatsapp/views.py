"""
WhatsApp views — inbox, conversations, Status Studio, broadcasts, analytics, channels.
"""

import logging
from datetime import timedelta

from django.contrib import messages as django_messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.platforms.models import SocialAccount
from apps.core.platforms.providers.registry import get_provider
from apps.core.utils import fire_task
from apps.messaging.whatsapp.models import (
    StatusContent,
    WeeklyDigest,
    WhatsAppAnalytics,
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

    from apps.messaging.whatsapp.draft_actions import pending_draft_count

    stats["pending_ai_drafts"] = pending_draft_count(request.user)

    return render(request, "dashboard/whatsapp/inbox.html", {
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

    from apps.commerce.leads.bridges import find_lead_for_whatsapp_conversation
    linked_lead = find_lead_for_whatsapp_conversation(conversation)

    return render(request, "dashboard/whatsapp/conversation.html", {
        "conversation": conversation,
        "messages": messages,
        "pending_drafts": pending_drafts,
        "linked_lead": linked_lead,
        "page_title": f"Chat with {conversation.contact_name or conversation.contact_wa_id}",
    })


# ─── Send Message ───────────────────────────────────────────────────────────

@login_required
@require_POST
def save_as_lead(request, pk):
    """Create or link a REACH lead from this WhatsApp conversation."""
    conversation = get_object_or_404(
        WhatsAppConversation.objects.select_related("social_account"),
        pk=pk,
        social_account__user=request.user,
    )
    from apps.commerce.leads.bridges import create_lead_from_whatsapp_conversation

    lead = create_lead_from_whatsapp_conversation(conversation)
    if not lead:
        django_messages.error(request, "Could not create lead — check your plan limits.")
        return redirect("whatsapp:conversation", pk=pk)

    django_messages.success(request, f"Saved {lead.name or lead.phone or 'contact'} as a lead.")
    return redirect("leads:detail", lead_id=lead.pk)


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
        return render(request, "dashboard/whatsapp/_message_bubble.html", {
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

    return render(request, "dashboard/whatsapp/template_list.html", {
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
    from apps.create.agents.llm import generate, get_model_for_task, parse_llm_json

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
        model=get_model_for_task("create", user=account.user),
        temperature=0.7,
        json_mode=True,
        user=account.user,
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


@login_required
@require_POST
def template_submit(request, pk):
    """Submit a draft template to Meta for approval."""
    wa_accounts = SocialAccount.objects.filter(
        user=request.user, platform="whatsapp", is_active=True,
    )
    template = get_object_or_404(
        WhatsAppTemplate,
        pk=pk,
        social_account__in=wa_accounts,
    )
    if template.status not in (
        WhatsAppTemplate.TemplateStatus.DRAFT,
        WhatsAppTemplate.TemplateStatus.REJECTED,
    ):
        django_messages.warning(request, "Only draft or rejected templates can be submitted.")
        return redirect("whatsapp:template_list")

    try:
        from apps.messaging.whatsapp.services import submit_template_to_meta
        submit_template_to_meta(template)
        django_messages.success(request, f"Template “{template.name}” submitted to Meta for review.")
    except Exception as e:
        django_messages.error(request, f"Submission failed: {e}")

    return redirect("whatsapp:template_list")


@login_required
@require_POST
def template_sync(request):
    """Sync template approval statuses from Meta."""
    wa_accounts = SocialAccount.objects.filter(
        user=request.user, platform="whatsapp", is_active=True,
    )
    account = wa_accounts.first()
    if not account:
        django_messages.error(request, "Connect a WhatsApp account first.")
        return redirect("whatsapp:template_list")

    try:
        from apps.messaging.whatsapp.services import sync_templates_from_meta
        count = sync_templates_from_meta(account)
        django_messages.success(request, f"Synced {count} template(s) from Meta.")
    except Exception as e:
        django_messages.error(request, f"Sync failed: {e}")

    return redirect("whatsapp:template_list")


# ═════════════════════════════════════════════════════════════════════════════
# SPRINT 5C — STATUS CONTENT STUDIO
# ═════════════════════════════════════════════════════════════════════════════

def _get_wa_accounts(user):
    """Helper — get user's active WhatsApp accounts."""
    return SocialAccount.objects.filter(user=user, platform="whatsapp", is_active=True)


@login_required
def status_studio(request):
    """Status Content Studio — AI-curated content ready for WhatsApp Status."""
    # Queue of status content
    statuses = StatusContent.objects.filter(user=request.user)

    state_filter = request.GET.get("state", "")
    category_filter = request.GET.get("category", "")
    if state_filter:
        statuses = statuses.filter(state=state_filter)
    if category_filter:
        statuses = statuses.filter(category=category_filter)

    # Stats
    all_statuses = StatusContent.objects.filter(user=request.user)
    stats = {
        "total": all_statuses.count(),
        "ready": all_statuses.filter(state="ready").count(),
        "shared": all_statuses.filter(state="shared").count(),
        "draft": all_statuses.filter(state="draft").count(),
    }

    # Today's calendar (next 7 days)
    now = timezone.now()
    week_ahead = now + timedelta(days=7)
    upcoming = StatusContent.objects.filter(
        user=request.user,
        state__in=["draft", "ready"],
        scheduled_for__gte=now,
        scheduled_for__lte=week_ahead,
    ).order_by("scheduled_for")[:20]

    # StatusTemplate gallery archived — campaign narrative uses Template Families
    paginator = Paginator(statuses, 20)
    page = paginator.get_page(request.GET.get("page", 1))

    return render(request, "dashboard/whatsapp/status/studio.html", {
        "page_obj": page,
        "stats": stats,
        "upcoming": upcoming,
        "templates": [],
        "state_filter": state_filter,
        "category_filter": category_filter,
        "categories": StatusContent.ContentCategory.choices,
    })


@login_required
@require_POST
def status_create(request):
    """Create a new Status content item (manual or AI-generated)."""
    ai_prompt = request.POST.get("ai_prompt", "").strip()
    category = request.POST.get("category", "announcement")
    text = request.POST.get("text", "").strip()

    if ai_prompt:
        # AI-generate the status content
        from apps.messaging.whatsapp.tasks import generate_status_content
        fire_task(generate_status_content, request.user.id, ai_prompt, category)
        django_messages.success(request, "AI is generating your Status content...")
        return redirect("whatsapp:status_studio")

    if not text:
        django_messages.error(request, "Status text is required.")
        return redirect("whatsapp:status_studio")

    status_obj = StatusContent.objects.create(
        user=request.user,
        text=text[:700],
        category=category,
        state=StatusContent.StatusState.READY,
    )
    status_obj.generate_share_url()
    status_obj.save(update_fields=["share_url"])

    django_messages.success(request, "Status created! Tap the share link to post to WhatsApp.")
    return redirect("whatsapp:status_studio")


@login_required
@require_POST
def status_share(request, pk):
    """Mark a Status as shared and generate the share URL."""
    status_obj = get_object_or_404(StatusContent, pk=pk, user=request.user)

    if not status_obj.share_url:
        status_obj.generate_share_url()

    status_obj.state = StatusContent.StatusState.SHARED
    status_obj.shared_at = timezone.now()
    status_obj.save(update_fields=["state", "shared_at", "share_url", "updated_at"])

    # Return HTMX partial with the share link
    return HttpResponse(
        f'<a href="{status_obj.share_url}" target="_blank" rel="noopener" '
        f'class="btn-primary btn-sm inline-flex items-center gap-1">'
        f'<svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/><path d="M12 2C6.477 2 2 6.477 2 12c0 1.89.525 3.66 1.438 5.168L2 22l4.832-1.438A9.955 9.955 0 0012 22c5.523 0 10-4.477 10-10S17.523 2 12 2zm0 18a8 8 0 01-4.29-1.24l-.28-.17-2.93.77.78-2.85-.18-.29A8 8 0 1112 20z"/></svg>'
        f'Open in WhatsApp</a>',
    )


@login_required
@require_POST
def status_skip(request, pk):
    """Skip a status content item."""
    status_obj = get_object_or_404(StatusContent, pk=pk, user=request.user)
    status_obj.state = StatusContent.StatusState.SKIPPED
    status_obj.save(update_fields=["state", "updated_at"])
    return HttpResponse('<span class="text-xs text-gray-400">Skipped</span>')


@login_required
@require_POST
def status_repurpose(request, post_id):
    """Repurpose an existing post from another platform into Status format."""
    from apps.create.content.models import Post
    from apps.messaging.whatsapp.tasks import repurpose_post_to_status

    post = get_object_or_404(Post, pk=post_id, user=request.user)
    fire_task(repurpose_post_to_status, request.user.id, str(post.id))
    django_messages.success(request, "AI is adapting your post for WhatsApp Status...")
    return redirect("whatsapp:status_studio")


@login_required
def status_calendar(request):
    """7-day visual planner for Status content with mix optimization."""
    now = timezone.now()
    days = []
    for i in range(7):
        day_start = (now + timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        day_statuses = StatusContent.objects.filter(
            user=request.user,
            scheduled_for__gte=day_start,
            scheduled_for__lt=day_end,
            state__in=["draft", "ready"],
        ).order_by("scheduled_for")
        days.append({
            "date": day_start.date(),
            "day_name": day_start.strftime("%A"),
            "statuses": day_statuses,
            "count": day_statuses.count(),
        })

    # Mix analysis — check for category streaks
    mix_warnings = []
    recent = StatusContent.objects.filter(
        user=request.user,
        state__in=["draft", "ready"],
        scheduled_for__gte=now,
    ).order_by("scheduled_for")[:10]

    last_category = None
    streak = 0
    for s in recent:
        if s.category == last_category:
            streak += 1
            if streak >= 3:
                mix_warnings.append(
                    f"3+ consecutive '{s.get_category_display()}' statuses — consider mixing in something different."
                )
                break
        else:
            streak = 1
        last_category = s.category

    return render(request, "dashboard/whatsapp/status/calendar.html", {
        "days": days,
        "mix_warnings": mix_warnings,
    })


# ═════════════════════════════════════════════════════════════════════════════
# SPRINT 5D — BROADCASTS / SEQUENCES (V1: UI removed; models kept)
# ═════════════════════════════════════════════════════════════════════════════

def _v1_broadcasts_removed(request):
    django_messages.info(request, "Broadcasts are not available in Kova V1.")
    return redirect("whatsapp:inbox")


@login_required
def broadcast_list(request):
    return _v1_broadcasts_removed(request)


@login_required
@require_POST
def broadcast_create(request):
    return _v1_broadcasts_removed(request)


@login_required
def broadcast_detail(request, pk):
    return _v1_broadcasts_removed(request)


@login_required
@require_POST
def broadcast_launch(request, pk):
    return _v1_broadcasts_removed(request)


@login_required
@require_POST
def broadcast_pause(request, pk):
    return _v1_broadcasts_removed(request)


@login_required
@require_POST
def sequence_create(request):
    return _v1_broadcasts_removed(request)


@login_required
def sequence_detail(request, pk):
    return _v1_broadcasts_removed(request)


@login_required
@require_POST
def sequence_add_step(request, pk):
    return _v1_broadcasts_removed(request)


@login_required
@require_POST
def sequence_toggle(request, pk):
    return _v1_broadcasts_removed(request)


# ─── Analytics ───────────────────────────────────────────────────────────────

@login_required
def wa_analytics(request):
    """WhatsApp analytics dashboard — message stats, AI performance, sentiment."""
    wa_accounts = _get_wa_accounts(request.user)

    # Date range
    days = int(request.GET.get("days", 30))
    days = min(days, 90)
    date_from = (timezone.now() - timedelta(days=days)).date()

    analytics = WhatsAppAnalytics.objects.filter(
        social_account__in=wa_accounts,
        date__gte=date_from,
    ).order_by("date")

    # Aggregate stats
    totals = analytics.aggregate(
        total_inbound=Sum("messages_inbound"),
        total_outbound=Sum("messages_outbound"),
        total_ai_replies=Sum("ai_replies"),
        total_escalated=Sum("conversations_escalated"),
        total_conversions=Sum("conversions"),
        total_revenue=Sum("revenue_attributed"),
        avg_response=Avg("avg_response_time_seconds"),
        avg_sentiment=Avg("avg_sentiment"),
        avg_confidence=Avg("avg_ai_confidence"),
        total_delivered=Sum("messages_delivered"),
        total_read=Sum("messages_read"),
        total_failed=Sum("messages_failed"),
        total_statuses=Sum("statuses_shared"),
    )

    # Chart data (daily time series)
    chart_data = list(analytics.values(
        "date", "messages_inbound", "messages_outbound",
        "ai_replies", "avg_sentiment", "conversations_new",
    ))

    # Weekly digests
    digests = WeeklyDigest.objects.filter(user=request.user).order_by("-week_start")[:8]

    return render(request, "dashboard/whatsapp/analytics/dashboard.html", {
        "totals": totals,
        "chart_data": chart_data,
        "analytics": analytics,
        "digests": digests,
        "days": days,
        "wa_accounts": wa_accounts,
    })


@login_required
def wa_digest_detail(request, pk):
    """View a weekly digest in detail."""
    digest = get_object_or_404(WeeklyDigest, pk=pk, user=request.user)
    return render(request, "dashboard/whatsapp/analytics/digest.html", {
        "digest": digest,
    })


# ═════════════════════════════════════════════════════════════════════════════
# SPRINT 5E — WHATSAPP CHANNELS (V1: UI removed; models kept)
# ═════════════════════════════════════════════════════════════════════════════

def _v1_channels_removed(request):
    django_messages.info(request, "WhatsApp Channels are not available in Kova V1.")
    return redirect("whatsapp:inbox")


@login_required
def channel_dashboard(request):
    return _v1_channels_removed(request)


@login_required
@require_POST
def channel_create(request):
    return _v1_channels_removed(request)


@login_required
def channel_detail(request, pk):
    return _v1_channels_removed(request)


@login_required
@require_POST
def channel_post_create(request, pk):
    return _v1_channels_removed(request)


@login_required
@require_POST
def channel_post_publish(request, channel_pk, post_pk):
    return _v1_channels_removed(request)


@login_required
@require_POST
def channel_toggle_curate(request, pk):
    return _v1_channels_removed(request)
