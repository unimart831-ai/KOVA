import csv
from datetime import timedelta
from itertools import chain
from operator import attrgetter

from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from apps.core.admin_dashboard.decorators import staff_required, superuser_required
from apps.create.agents.models import AgentAction
from apps.core.billing.models import BillingEvent, MpesaPayment
from apps.create.content.models import ContentSeed, Post
from apps.messaging.notifications.models import Notification
from apps.core.platforms.models import SocialAccount


def _build_activity_feed(days=7, category="", search="", limit=500):
    """
    Build a unified activity feed by merging entries from multiple models
    into a single chronological list.
    """
    cutoff = timezone.now() - timedelta(days=days)
    items = []

    # ── Agent actions ────────────────────────────────────────────────
    if not category or category == "agent":
        qs = AgentAction.objects.filter(created_at__gte=cutoff).select_related("user")
        if search:
            qs = qs.filter(
                Q(user__email__icontains=search)
                | Q(action_type__icontains=search)
                | Q(agent_type__icontains=search)
            )
        for a in qs.order_by("-created_at")[:limit]:
            status_icon = "✅" if a.status == "completed" else "❌" if a.status == "failed" else "⏳"
            items.append({
                "timestamp": a.created_at,
                "category": "Agent",
                "category_color": "indigo",
                "user_email": a.user.email if a.user else "—",
                "event": f"{a.agent_type.capitalize()} Agent: {a.action_type}",
                "detail": a.description[:120] if a.description else "",
                "status_icon": status_icon,
            })

    # ── Posts published / failed ─────────────────────────────────────
    if not category or category == "content":
        post_qs = Post.objects.filter(
            updated_at__gte=cutoff,
            status__in=["published", "failed"],
        ).select_related("user", "social_account")
        if search:
            post_qs = post_qs.filter(
                Q(user__email__icontains=search)
                | Q(content_text__icontains=search)
            )
        for p in post_qs.order_by("-updated_at")[:limit]:
            platform = p.social_account.platform if p.social_account else "—"
            if p.status == "published":
                event = f"Post published to {platform}"
                icon = "✅"
            else:
                event = f"Post failed on {platform}"
                icon = "❌"
            items.append({
                "timestamp": p.updated_at,
                "category": "Content",
                "category_color": "blue",
                "user_email": p.user.email if p.user else "—",
                "event": event,
                "detail": (p.content_text or "")[:100],
                "status_icon": icon,
            })

    # ── Seed completions / failures ──────────────────────────────────
    if not category or category == "content":
        seed_qs = ContentSeed.objects.filter(
            updated_at__gte=cutoff,
            status__in=["completed", "failed"],
        ).select_related("user")
        if search:
            seed_qs = seed_qs.filter(
                Q(user__email__icontains=search)
                | Q(idea__icontains=search)
            )
        for s in seed_qs.order_by("-updated_at")[:limit]:
            if s.status == "completed":
                event = "Seed processed → posts generated"
                icon = "✅"
            else:
                event = "Seed processing failed"
                icon = "❌"
            items.append({
                "timestamp": s.updated_at,
                "category": "Content",
                "category_color": "blue",
                "user_email": s.user.email if s.user else "—",
                "event": event,
                "detail": (s.idea or "")[:100],
                "status_icon": icon,
            })

    # ── Billing events ───────────────────────────────────────────────
    if not category or category == "billing":
        billing_qs = BillingEvent.objects.filter(created_at__gte=cutoff).select_related("user")
        if search:
            billing_qs = billing_qs.filter(
                Q(user__email__icontains=search)
                | Q(event_type__icontains=search)
            )
        for b in billing_qs.order_by("-created_at")[:limit]:
            items.append({
                "timestamp": b.created_at,
                "category": "Billing",
                "category_color": "emerald",
                "user_email": b.user.email if b.user else "—",
                "event": f"{b.provider.upper()}: {b.event_type}",
                "detail": f"{'Processed' if b.processed else 'Unprocessed'}{(' — ' + b.error_message) if b.error_message else ''}",
                "status_icon": "✅" if b.processed else "⚠️",
            })

    # ── M-Pesa payments ──────────────────────────────────────────────
    if not category or category == "billing":
        mpesa_qs = MpesaPayment.objects.filter(created_at__gte=cutoff).select_related("user")
        if search:
            mpesa_qs = mpesa_qs.filter(
                Q(user__email__icontains=search)
                | Q(receipt_number__icontains=search)
            )
        for m in mpesa_qs.order_by("-created_at")[:limit]:
            icon = "✅" if m.status == "completed" else "❌" if m.status == "failed" else "⏳"
            items.append({
                "timestamp": m.created_at,
                "category": "Billing",
                "category_color": "emerald",
                "user_email": m.user.email if m.user else "—",
                "event": f"M-Pesa payment — KES {m.amount} ({m.plan_tier})",
                "detail": f"Status: {m.status}" + (f" — {m.receipt_number}" if m.receipt_number else ""),
                "status_icon": icon,
            })

    # ── Platform events (errors) ─────────────────────────────────────
    if not category or category == "platform":
        acct_qs = SocialAccount.objects.exclude(
            last_error=""
        ).exclude(last_error__isnull=True).select_related("user")
        if search:
            acct_qs = acct_qs.filter(
                Q(user__email__icontains=search)
                | Q(platform__icontains=search)
                | Q(username__icontains=search)
            )
        for sa in acct_qs[:limit]:
            ts = sa.last_synced_at or sa.connected_at or timezone.now()
            items.append({
                "timestamp": ts,
                "category": "Platform",
                "category_color": "amber",
                "user_email": sa.user.email if sa.user else "—",
                "event": f"{sa.platform.capitalize()} error — @{sa.username}",
                "detail": (sa.last_error or "")[:120],
                "status_icon": "❌",
            })

    # Sort everything by timestamp descending
    items.sort(key=lambda x: x["timestamp"], reverse=True)
    return items


@staff_required
def activity_log(request):
    """Unified activity log — cross-model chronological feed."""
    search = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")
    days = request.GET.get("days", "7")
    try:
        days_int = int(days)
    except ValueError:
        days_int = 7

    items = _build_activity_feed(days=days_int, category=category, search=search)

    paginator = Paginator(items, 50)
    page = paginator.get_page(request.GET.get("page", 1))

    context = {
        "page_title": "Activity Log",
        "page_obj": page,
        "search": search,
        "current_category": category,
        "current_days": days,
        "total_count": len(items),
        "category_choices": [
            ("agent", "Agent"),
            ("content", "Content"),
            ("billing", "Billing"),
            ("platform", "Platform"),
        ],
    }
    return render(request, "admin_dashboard/logs/activity.html", context)


@superuser_required
def log_export_csv(request):
    """Export activity log as CSV. Requires superuser."""
    category = request.GET.get("category", "")
    days = request.GET.get("days", "30")
    try:
        days_int = int(days)
    except ValueError:
        days_int = 30

    items = _build_activity_feed(days=days_int, category=category, limit=5000)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="kova_activity_log_{timezone.now().strftime("%Y%m%d")}.csv"'

    writer = csv.writer(response)
    writer.writerow(["Timestamp", "Category", "User", "Event", "Detail"])
    for item in items:
        writer.writerow([
            item["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
            item["category"],
            item["user_email"],
            item["event"],
            item["detail"],
        ])

    return response
