"""Platform-wide operations report for admin dashboard."""

from datetime import timedelta

from django.shortcuts import render
from django.utils import timezone

from apps.admin_dashboard.decorators import staff_required
from apps.briefs.operations_report import build_platform_operations_report


@staff_required
def operations_overview(request):
    """Cross-user task activity — Snap, restock, reels, content, leads, etc."""
    hours = request.GET.get("hours", "24")
    try:
        hours = int(hours)
    except (TypeError, ValueError):
        hours = 24
    hours = max(1, min(hours, 168))

    report = build_platform_operations_report(hours=hours)

    from apps.agents.models import AgentAction
    from apps.content.models import Post
    from apps.content.reel_music import load_music_catalog, resolve_track_path

    now = timezone.now()
    week_ago = now - timedelta(days=7)

    pipeline_stats = {
        "snap_single": AgentAction.objects.filter(action_type="snap.vision").count(),
        "snap_batch": AgentAction.objects.filter(action_type="snap.vision_batch").count(),
        "carousels": AgentAction.objects.filter(action_type="snap.carousel").count(),
        "reels": AgentAction.objects.filter(action_type="snap.reel").count(),
        "restock": AgentAction.objects.filter(action_type="receipt_to_restock").count(),
        "snap_7d": AgentAction.objects.filter(
            action_type__startswith="snap.", created_at__gte=week_ago,
        ).count(),
        "reel_posts": Post.objects.filter(post_format="reel").count(),
        "reel_posts_7d": Post.objects.filter(
            post_format="reel", created_at__gte=week_ago,
        ).count(),
    }

    tracks = load_music_catalog()
    music_health = []
    missing_files = 0
    for track in tracks:
        path_ok = bool(resolve_track_path(track))
        if not path_ok:
            missing_files += 1
        music_health.append({
            "id": track.get("id", ""),
            "title": track.get("title", ""),
            "mood": track.get("mood", ""),
            "file_ok": path_ok,
        })

    return render(request, "admin_dashboard/operations/overview.html", {
        "page_title": "Operations Report",
        "report": report,
        "hours": hours,
        "pipeline_stats": pipeline_stats,
        "music_health": music_health,
        "music_missing": missing_files,
        "music_total": len(tracks),
    })
