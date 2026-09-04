"""Content archive — published, failed, and other inactive posts."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_POST

from apps.create.content.models import Post
from apps.create.content.views.queue import (
    QUEUE_SECTION_CAP,
    _apply_queue_filters,
    _group_queue_by_seed,
)
from apps.core.teams.permissions import get_teammate_ids

ARCHIVE_SECTION_CAP = 60


def _get_archive_context(user, section_filter=None, platform_filter=None, format_filter=None, search_query=None):
    visible_user_ids = get_teammate_ids(user)
    base = Post.objects.filter(user_id__in=visible_user_ids).select_related(
        "social_account", "seed", "user",
    )
    from apps.create.content.share_bundle import exclude_share_bundle_posts
    base = exclude_share_bundle_posts(base, visible_user_ids)

    published_qs = _apply_queue_filters(
        base.filter(status="published").order_by("-published_at"),
        platform_filter, format_filter, search_query,
    )
    failed_qs = _apply_queue_filters(
        base.filter(status__in=("failed", "blocked", "rate_limited")).order_by("-updated_at"),
        platform_filter, format_filter, search_query,
    )
    others_qs = _apply_queue_filters(
        base.filter(status="rejected").order_by("-updated_at"),
        platform_filter, format_filter, search_query,
    )

    section = section_filter if section_filter in ("published", "failed", "others") else "all"
    load_all = section == "all"

    published_count = published_qs.count()
    failed_count = failed_qs.count()
    others_count = others_qs.count()

    published = list(published_qs[:ARCHIVE_SECTION_CAP]) if load_all or section == "published" else []
    failed = list(failed_qs[:ARCHIVE_SECTION_CAP]) if load_all or section == "failed" else []
    others = list(others_qs[:ARCHIVE_SECTION_CAP]) if load_all or section == "others" else []

    published_batches, published_ungrouped = _group_queue_by_seed(published)
    failed_batches, failed_ungrouped = _group_queue_by_seed(failed)
    others_batches, others_ungrouped = _group_queue_by_seed(others)

    filtered_total = published_count + failed_count + others_count

    return {
        "section": section,
        "current_section": section,
        "published": published,
        "published_batches": published_batches,
        "published_ungrouped": published_ungrouped,
        "published_count": published_count,
        "failed": failed,
        "failed_batches": failed_batches,
        "failed_ungrouped": failed_ungrouped,
        "failed_count": failed_count,
        "others": others,
        "others_batches": others_batches,
        "others_ungrouped": others_ungrouped,
        "others_count": others_count,
        "filtered_total": filtered_total,
        "current_platform": platform_filter or "",
        "current_format": format_filter or "",
        "current_search": search_query or "",
    }


@login_required
def content_archive(request):
    ctx = _get_archive_context(
        request.user,
        section_filter=request.GET.get("section"),
        platform_filter=request.GET.get("platform"),
        format_filter=request.GET.get("post_format"),
        search_query=request.GET.get("q"),
    )
    ctx["active_tab"] = "archive"
    ctx["page_title"] = "Archive"
    return render(request, "dashboard/content/archive.html", ctx)


@login_required
def archive_sections(request):
    ctx = _get_archive_context(
        request.user,
        section_filter=request.GET.get("section"),
        platform_filter=request.GET.get("platform"),
        format_filter=request.GET.get("post_format"),
        search_query=request.GET.get("q"),
    )
    return render(request, "dashboard/content/_archive_content.html", ctx)


@login_required
@require_POST
def archive_clear_failed(request):
    """Bulk soft-delete failed archive posts."""
    from apps.core.teams.permissions import get_teammate_ids

    visible_user_ids = get_teammate_ids(request.user)
    qs = Post.objects.filter(
        user_id__in=visible_user_ids,
        status__in=(Post.Status.FAILED, Post.Status.BLOCKED, Post.Status.RATE_LIMITED),
    )

    platform_filter = request.POST.get("platform") or request.GET.get("platform")
    if platform_filter:
        qs = qs.filter(platform=platform_filter)

    cleared = 0
    for post in qs:
        post.soft_delete()
        cleared += 1

    if request.headers.get("HX-Request") == "true":
        ctx = _get_archive_context(
            request.user,
            section_filter=request.GET.get("section"),
            platform_filter=platform_filter,
            format_filter=request.GET.get("post_format"),
            search_query=request.GET.get("q"),
        )
        return render(request, "dashboard/content/_archive_content.html", ctx)

    if cleared:
        messages.success(request, f"Cleared {cleared} failed post{'s' if cleared != 1 else ''}.")
    return content_archive(request)
