"""
Admin dashboard — Feature Usage Analytics.

Shows which sections of the platform users actually use,
daily/weekly trends, top users per feature, and adoption gaps.
"""

from collections import defaultdict
from datetime import timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone
from django.utils.safestring import mark_safe

import json

from apps.admin_dashboard.decorators import staff_required


@staff_required
def feature_usage(request):
    """Feature usage overview — what's being used, by whom, and how much."""
    from apps.accounts.models import User
    from apps.analytics.models import PageView

    now = timezone.now()

    # Period selector
    days = int(request.GET.get("days", 30))
    if days not in (7, 14, 30, 90):
        days = 30
    cutoff = now - timedelta(days=days)

    views_qs = PageView.objects.filter(viewed_at__gte=cutoff)
    total_views = views_qs.count()
    total_active_users = views_qs.values("user").distinct().count()
    total_registered = User.objects.count()
    adoption_rate = round(total_active_users / total_registered * 100, 1) if total_registered else 0

    # ── Section breakdown ────────────────────────────────────────────────
    section_labels = dict(PageView.SECTION_CHOICES)
    section_data = (
        views_qs
        .values("section")
        .annotate(
            views=Count("id"),
            users=Count("user", distinct=True),
        )
        .order_by("-views")
    )

    sections = []
    max_views = 1
    for row in section_data:
        if row["views"] > max_views:
            max_views = row["views"]

    for row in section_data:
        sections.append({
            "key": row["section"],
            "label": section_labels.get(row["section"], row["section"]),
            "views": row["views"],
            "users": row["users"],
            "bar_pct": round(row["views"] / max_views * 100),
            "avg_per_user": round(row["views"] / row["users"], 1) if row["users"] else 0,
        })

    # ── Unused features (0 views in period) ──────────────────────────────
    used_keys = {s["key"] for s in sections}
    unused = [
        {"key": key, "label": label}
        for key, label in PageView.SECTION_CHOICES
        if key not in used_keys
    ]

    # ── Daily trend (views per day) ──────────────────────────────────────
    daily_views = (
        views_qs
        .annotate(day=TruncDate("viewed_at"))
        .values("day")
        .annotate(count=Count("id"), users=Count("user", distinct=True))
        .order_by("day")
    )
    daily_labels = [row["day"].strftime("%b %d") for row in daily_views]
    daily_counts = [row["count"] for row in daily_views]
    daily_users = [row["users"] for row in daily_views]

    # ── Top users by total views ─────────────────────────────────────────
    top_users = (
        views_qs
        .values("user__email", "user__full_name", "user__id")
        .annotate(views=Count("id"), sections=Count("section", distinct=True))
        .order_by("-views")[:15]
    )

    # ── Section trend (top 5 sections, daily) ────────────────────────────
    top_5_keys = [s["key"] for s in sections[:5]]
    section_daily = (
        views_qs
        .filter(section__in=top_5_keys)
        .annotate(day=TruncDate("viewed_at"))
        .values("day", "section")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    # Build dict: {section: {date_str: count}}
    section_trend = defaultdict(lambda: defaultdict(int))
    for row in section_daily:
        section_trend[row["section"]][row["day"].strftime("%b %d")] = row["count"]

    # Format for Chart.js: list of {label, data[]}
    section_trend_datasets = []
    colors = ["#7c3aed", "#2563eb", "#059669", "#d97706", "#dc2626"]
    for i, key in enumerate(top_5_keys):
        section_trend_datasets.append({
            "label": section_labels.get(key, key),
            "color": colors[i % len(colors)],
            "data": [section_trend[key].get(d, 0) for d in daily_labels],
        })

    # ── User journey depth — how many sections each user visits ──────────
    depth_dist_raw = (
        views_qs
        .values("user")
        .annotate(section_count=Count("section", distinct=True))
        .values("section_count")
        .annotate(user_count=Count("user", distinct=True))
        .order_by("section_count")
    )
    depth_dist = [
        {"sections": row["section_count"], "users": row["user_count"]}
        for row in depth_dist_raw
    ]

    # ── Peak hours ───────────────────────────────────────────────────────
    from django.db.models.functions import ExtractHour
    peak_hours = (
        views_qs
        .annotate(hour=ExtractHour("viewed_at"))
        .values("hour")
        .annotate(count=Count("id"))
        .order_by("hour")
    )
    # Fill missing hours so the bar chart always has 24 buckets
    hour_counts = {row["hour"]: row["count"] for row in peak_hours}
    hours_labels = [f"{h:02d}:00" for h in range(24)]
    hours_data = [hour_counts.get(h, 0) for h in range(24)]

    context = {
        "page_title": "Surface Usage",
        "days": days,
        "total_views": total_views,
        "total_active_users": total_active_users,
        "total_registered": total_registered,
        "adoption_rate": adoption_rate,
        "sections": sections,
        "unused": unused,
        "daily_labels": daily_labels,
        "daily_counts": daily_counts,
        "daily_users": daily_users,
        "top_users": top_users,
        "section_trend_datasets": section_trend_datasets,
        "depth_dist": depth_dist,
        "hours_labels_json": mark_safe(json.dumps(hours_labels)),
        "hours_data_json": mark_safe(json.dumps(hours_data)),
        "daily_labels_json": mark_safe(json.dumps(daily_labels)),
        "daily_counts_json": mark_safe(json.dumps(daily_counts)),
        "daily_users_json": mark_safe(json.dumps(daily_users)),
        "section_trend_datasets_json": mark_safe(json.dumps([
            {"label": ds["label"], "data": ds["data"], "color": ds["color"]}
            for ds in section_trend_datasets
        ])),
    }
    return render(request, "admin_dashboard/feature_usage.html", context)
