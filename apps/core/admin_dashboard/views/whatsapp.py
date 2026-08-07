"""
Admin dashboard views for WhatsApp Business management.
Provides monitoring for conversations, templates, broadcasts, and messaging health.
"""

from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone

from apps.core.admin_dashboard.decorators import staff_required
from apps.messaging.whatsapp.models import (
    BroadcastSequence,
    SequenceEnrollment,
    WhatsAppBroadcast,
    WhatsAppConversation,
    WhatsAppMessage,
    WhatsAppTemplate,
)


@staff_required
def whatsapp_overview(request):
    """WhatsApp dashboard — key metrics across conversations, messages, templates, broadcasts."""
    now = timezone.now()
    last_7d = now - timedelta(days=7)
    last_24h = now - timedelta(hours=24)

    # ── Conversation metrics ─────────────────────────────────────────
    total_conversations = WhatsAppConversation.objects.count()
    active_conversations = WhatsAppConversation.objects.filter(status="active").count()
    escalated = WhatsAppConversation.objects.filter(status="escalated").count()
    conversations_7d = WhatsAppConversation.objects.filter(created_at__gte=last_7d).count()

    # Window status
    open_windows = WhatsAppConversation.objects.filter(
        window_expires_at__gt=now,
    ).count()

    # ── Message metrics ──────────────────────────────────────────────
    total_messages = WhatsAppMessage.objects.count()
    messages_7d = WhatsAppMessage.objects.filter(created_at__gte=last_7d).count()
    inbound_7d = WhatsAppMessage.objects.filter(
        created_at__gte=last_7d, direction="inbound",
    ).count()
    outbound_7d = WhatsAppMessage.objects.filter(
        created_at__gte=last_7d, direction="outbound",
    ).count()
    ai_replies_7d = WhatsAppMessage.objects.filter(
        created_at__gte=last_7d, is_ai_generated=True,
    ).count()
    failed_messages = WhatsAppMessage.objects.filter(
        created_at__gte=last_7d, status="failed",
    ).count()

    # AI confidence
    avg_confidence = WhatsAppMessage.objects.filter(
        is_ai_generated=True, confidence_score__isnull=False,
        created_at__gte=last_7d,
    ).aggregate(avg=Avg("confidence_score"))["avg"]

    # Delivery stats
    delivered_7d = WhatsAppMessage.objects.filter(
        created_at__gte=last_7d, direction="outbound",
        status__in=["delivered", "read"],
    ).count()
    read_7d = WhatsAppMessage.objects.filter(
        created_at__gte=last_7d, direction="outbound", status="read",
    ).count()
    delivery_rate = round(delivered_7d / outbound_7d * 100, 1) if outbound_7d else 100
    read_rate = round(read_7d / outbound_7d * 100, 1) if outbound_7d else 0

    # ── Template metrics ─────────────────────────────────────────────
    total_templates = WhatsAppTemplate.objects.count()
    draft_templates = WhatsAppTemplate.objects.filter(status="draft").count()
    approved_templates = WhatsAppTemplate.objects.filter(status="approved").count()
    pending_templates = WhatsAppTemplate.objects.filter(status="submitted").count()
    rejected_templates = WhatsAppTemplate.objects.filter(status="rejected").count()

    # ── Broadcast metrics ────────────────────────────────────────────
    total_broadcasts = WhatsAppBroadcast.objects.count()
    active_broadcasts = WhatsAppBroadcast.objects.filter(
        status__in=["scheduled", "sending"],
    ).count()
    # ── Broadcast sequences (drip) ───────────────────────────────────
    total_sequences = BroadcastSequence.objects.count()
    active_sequences = BroadcastSequence.objects.filter(status="active").count()
    sequence_enrollments_active = SequenceEnrollment.objects.filter(
        status=SequenceEnrollment.EnrollmentStatus.ACTIVE,
    ).count()
    sequence_due = SequenceEnrollment.objects.filter(
        status=SequenceEnrollment.EnrollmentStatus.ACTIVE,
        next_send_at__lte=now,
    ).count()

    # ── Commerce payment receipts (outbound text) ──────────────────────
    commerce_receipts_7d = WhatsAppMessage.objects.filter(
        direction="outbound",
        created_at__gte=last_7d,
        content__icontains="Payment received",
    ).count()
    broadcast_stats = WhatsAppBroadcast.objects.filter(
        status="completed",
    ).aggregate(
        total_sent=Sum("sent_count"),
        total_delivered=Sum("delivered_count"),
        total_read=Sum("read_count"),
        total_replied=Sum("replied_count"),
    )

    # ── 7-day message chart ──────────────────────────────────────────
    inbound_by_day = dict(
        WhatsAppMessage.objects.filter(
            direction="inbound", created_at__date__gte=(now - timedelta(days=6)).date(),
        ).annotate(day=TruncDate("created_at"))
        .values("day").annotate(count=Count("id"))
        .values_list("day", "count")
    )
    outbound_by_day = dict(
        WhatsAppMessage.objects.filter(
            direction="outbound", created_at__date__gte=(now - timedelta(days=6)).date(),
        ).annotate(day=TruncDate("created_at"))
        .values("day").annotate(count=Count("id"))
        .values_list("day", "count")
    )
    message_chart = []
    for i in range(6, -1, -1):
        d = (now - timedelta(days=i)).date()
        message_chart.append({
            "date": d.isoformat(),
            "inbound": inbound_by_day.get(d, 0),
            "outbound": outbound_by_day.get(d, 0),
        })

    # ── Recent conversations ─────────────────────────────────────────
    recent_conversations = (
        WhatsAppConversation.objects
        .select_related("social_account", "social_account__user")
        .order_by("-last_message_at")[:5]
    )
    escalated_conversations = (
        WhatsAppConversation.objects
        .select_related("social_account", "social_account__user")
        .filter(status="escalated")
        .order_by("-last_message_at")[:8]
    )

    # Kova plan marketing conversation caps (utility/auth templates excluded)
    from apps.core.billing.models import PLAN_LIMITS, get_all_plan_limits
    from apps.core.billing.whatsapp_marketing import MARKETING_TEMPLATE_CATEGORIES

    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    marketing_msgs_month = WhatsAppMessage.objects.filter(
        direction=WhatsAppMessage.Direction.OUTBOUND,
        message_type=WhatsAppMessage.MessageType.TEMPLATE,
        template__category__in=MARKETING_TEMPLATE_CATEGORIES,
        created_at__gte=month_start,
        status__in=[
            WhatsAppMessage.MessageStatus.SENT,
            WhatsAppMessage.MessageStatus.DELIVERED,
            WhatsAppMessage.MessageStatus.READ,
        ],
    )
    marketing_conversations_month = marketing_msgs_month.values("conversation_id").distinct().count()
    marketing_plan_caps = []
    for tier in ("kova", "starter", "growth", "pro", "agency"):
        lim = PLAN_LIMITS.get(tier, {})
        marketing_plan_caps.append({
            "tier": tier,
            "label": lim.get("label", tier),
            "cap": lim.get("whatsapp_marketing_conversations_per_month", 0),
            "whatsapp_business": lim.get("whatsapp_enabled", False),
        })

    context = {
        "page_title": "WhatsApp Management",
        # Conversations
        "total_conversations": total_conversations,
        "active_conversations": active_conversations,
        "escalated": escalated,
        "conversations_7d": conversations_7d,
        "open_windows": open_windows,
        # Messages
        "total_messages": total_messages,
        "messages_7d": messages_7d,
        "inbound_7d": inbound_7d,
        "outbound_7d": outbound_7d,
        "ai_replies_7d": ai_replies_7d,
        "failed_messages": failed_messages,
        "avg_confidence": avg_confidence,
        "delivery_rate": delivery_rate,
        "read_rate": read_rate,
        # Templates
        "total_templates": total_templates,
        "draft_templates": draft_templates,
        "approved_templates": approved_templates,
        "pending_templates": pending_templates,
        "rejected_templates": rejected_templates,
        # Broadcasts
        "total_broadcasts": total_broadcasts,
        "active_broadcasts": active_broadcasts,
        "broadcast_stats": broadcast_stats,
        # Sequences
        "total_sequences": total_sequences,
        "active_sequences": active_sequences,
        "sequence_enrollments_active": sequence_enrollments_active,
        "sequence_due": sequence_due,
        "commerce_receipts_7d": commerce_receipts_7d,
        # Chart & recent
        "message_chart_json": message_chart,
        "recent_conversations": recent_conversations,
        "escalated_conversations": escalated_conversations,
        "marketing_conversations_month": marketing_conversations_month,
        "marketing_plan_caps": marketing_plan_caps,
        "plan_limits": get_all_plan_limits(),
    }
    return render(request, "admin_dashboard/whatsapp/overview.html", context)


@staff_required
def whatsapp_conversations(request):
    """All WhatsApp conversations with search, filter, sort."""
    qs = (
        WhatsAppConversation.objects
        .select_related("social_account", "social_account__user")
        .annotate(message_count=Count("messages"))
    )

    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(
            Q(contact_name__icontains=search)
            | Q(contact_phone__icontains=search)
            | Q(contact_wa_id__icontains=search)
        )

    status = request.GET.get("status", "")
    if status:
        qs = qs.filter(status=status)

    ai_filter = request.GET.get("ai", "")
    if ai_filter == "ai":
        qs = qs.filter(ai_handling=True)
    elif ai_filter == "human":
        qs = qs.filter(ai_handling=False)

    sort = request.GET.get("sort", "-last_message_at")
    valid_sorts = {
        "last_message_at", "-last_message_at",
        "created_at", "-created_at",
        "contact_name", "-contact_name",
        "message_count", "-message_count",
    }
    if sort not in valid_sorts:
        sort = "-last_message_at"
    qs = qs.order_by(sort)

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page", 1))

    context = {
        "page_title": "WhatsApp Conversations",
        "page_obj": page,
        "search": search,
        "current_status": status,
        "current_ai": ai_filter,
        "current_sort": sort,
        "total_count": paginator.count,
    }
    return render(request, "admin_dashboard/whatsapp/conversations.html", context)


@staff_required
def whatsapp_templates(request):
    """All WhatsApp message templates with filtering."""
    qs = WhatsAppTemplate.objects.select_related("social_account", "social_account__user")

    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(
            Q(name__icontains=search)
            | Q(body_text__icontains=search)
        )

    status = request.GET.get("status", "")
    if status:
        qs = qs.filter(status=status)

    category = request.GET.get("category", "")
    if category:
        qs = qs.filter(category=category)

    qs = qs.order_by("-created_at")

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page", 1))

    context = {
        "page_title": "WhatsApp Templates",
        "page_obj": page,
        "search": search,
        "current_status": status,
        "current_category": category,
        "total_count": paginator.count,
        "status_choices": WhatsAppTemplate.TemplateStatus.choices,
        "category_choices": WhatsAppTemplate.Category.choices,
    }
    return render(request, "admin_dashboard/whatsapp/templates.html", context)


@staff_required
def whatsapp_broadcasts(request):
    """All WhatsApp broadcasts with filtering."""
    qs = (
        WhatsAppBroadcast.objects
        .select_related("social_account", "social_account__user", "template")
    )

    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(name__icontains=search)

    status = request.GET.get("status", "")
    if status:
        qs = qs.filter(status=status)

    qs = qs.order_by("-created_at")

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page", 1))

    context = {
        "page_title": "WhatsApp Broadcasts",
        "page_obj": page,
        "search": search,
        "current_status": status,
        "total_count": paginator.count,
        "status_choices": WhatsAppBroadcast.BroadcastStatus.choices,
    }
    return render(request, "admin_dashboard/whatsapp/broadcasts.html", context)


@staff_required
def whatsapp_sequences(request):
    """Broadcast drip sequences and enrollment health."""
    now = timezone.now()
    qs = (
        BroadcastSequence.objects
        .select_related("social_account", "social_account__user")
        .annotate(
            step_count=Count("steps"),
            active_enrollments=Count(
                "enrollments",
                filter=Q(enrollments__status=SequenceEnrollment.EnrollmentStatus.ACTIVE),
            ),
            due_enrollments=Count(
                "enrollments",
                filter=Q(
                    enrollments__status=SequenceEnrollment.EnrollmentStatus.ACTIVE,
                    enrollments__next_send_at__lte=now,
                ),
            ),
        )
        .order_by("-created_at")
    )

    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(
            Q(name__icontains=search)
            | Q(social_account__user__email__icontains=search),
        )

    status = request.GET.get("status", "")
    if status:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page", 1))

    enrollment_summary = SequenceEnrollment.objects.values("status").annotate(
        count=Count("id"),
    ).order_by("status")

    context = {
        "page_title": "WhatsApp Sequences",
        "page_obj": page,
        "search": search,
        "current_status": status,
        "total_count": paginator.count,
        "status_choices": BroadcastSequence.SequenceStatus.choices,
        "enrollment_summary": enrollment_summary,
        "due_total": SequenceEnrollment.objects.filter(
            status=SequenceEnrollment.EnrollmentStatus.ACTIVE,
            next_send_at__lte=now,
        ).count(),
    }
    return render(request, "admin_dashboard/whatsapp/sequences.html", context)


@staff_required
def whatsapp_commerce_receipts(request):
    """Recent commerce payment confirmation messages sent via WhatsApp."""
    qs = (
        WhatsAppMessage.objects.filter(
            direction="outbound",
            content__icontains="Payment received",
        )
        .select_related("conversation", "conversation__social_account", "conversation__social_account__user")
        .order_by("-created_at")
    )

    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(
            Q(content__icontains=search)
            | Q(conversation__contact_phone__icontains=search)
            | Q(conversation__social_account__user__email__icontains=search),
        )

    last_7d = timezone.now() - timedelta(days=7)
    receipts_7d = qs.filter(created_at__gte=last_7d).count()

    paginator = Paginator(qs, 40)
    page = paginator.get_page(request.GET.get("page", 1))

    context = {
        "page_title": "Commerce WhatsApp Receipts",
        "page_obj": page,
        "search": search,
        "total_count": paginator.count,
        "receipts_7d": receipts_7d,
    }
    return render(request, "admin_dashboard/whatsapp/commerce_receipts.html", context)


@staff_required
def whatsapp_brief_delivery(request):
    """Daily Brief WhatsApp delivery + reply-to-act command logs."""
    from django.conf import settings

    from apps.create.briefs.models import BriefWhatsAppLog, DailyBrief
    from apps.core.billing.models import get_plan_limits

    now = timezone.now()
    last_7d = now - timedelta(days=7)
    last_24h = now - timedelta(hours=24)

    briefs_7d = DailyBrief.objects.filter(created_at__gte=last_7d).count()
    recent_briefs = DailyBrief.objects.filter(created_at__gte=last_7d).only("performance_summary")
    wa_delivered_7d = sum(
        1 for b in recent_briefs if (b.performance_summary or {}).get("last_whatsapp_delivery")
    )

    commands_7d = BriefWhatsAppLog.objects.filter(created_at__gte=last_7d)
    commands_24h = commands_7d.filter(created_at__gte=last_24h)
    total_commands_7d = commands_7d.count()
    success_commands_7d = commands_7d.filter(success=True).count()
    approve_commands_7d = commands_7d.filter(command__startswith="approve").count()
    idea_commands_7d = commands_7d.filter(command__startswith="idea").count()

    by_command = (
        commands_7d.values("command")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )

    qs = BriefWhatsAppLog.objects.select_related("user", "brief").order_by("-created_at")
    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(
            Q(user__email__icontains=search)
            | Q(wa_id__icontains=search)
            | Q(inbound_text__icontains=search)
            | Q(command__icontains=search)
        )

    command_filter = request.GET.get("command", "")
    if command_filter:
        qs = qs.filter(command__startswith=command_filter)

    paginator = Paginator(qs, 40)
    page = paginator.get_page(request.GET.get("page", 1))

    pro_limits = get_plan_limits("pro")

    context = {
        "page_title": "Daily Brief WhatsApp",
        "briefs_7d": briefs_7d,
        "wa_delivered_7d": wa_delivered_7d,
        "total_commands_7d": total_commands_7d,
        "commands_24h": commands_24h.count(),
        "success_commands_7d": success_commands_7d,
        "approve_commands_7d": approve_commands_7d,
        "idea_commands_7d": idea_commands_7d,
        "by_command": by_command,
        "page_obj": page,
        "search": search,
        "current_command": command_filter,
        "total_count": paginator.count,
        "master_phone_id": getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", ""),
        "brief_template": getattr(settings, "KOVA_DAILY_BRIEF_TEMPLATE_NAME", ""),
        "onboarding_template": getattr(settings, "KOVA_ONBOARDING_TEMPLATE_NAME", ""),
        "whatsapp_brief_pro": pro_limits.get("whatsapp_brief"),
    }
    return render(request, "admin_dashboard/whatsapp/brief_delivery.html", context)
