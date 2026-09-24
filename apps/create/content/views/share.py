"""Quick Share — dedicated list and bundle detail pages."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.create.content.models import ContentSeed, Post
from apps.create.content.share_bundle import (
    build_share_bundle_detail,
    is_meaningless_share_label,
    is_share_bundle_seed,
    reschedule_share_bundle,
    summarize_share_bundle,
)
from apps.core.accounts.access import get_teammate_ids


def _share_seed_queryset(user):
    visible_user_ids = get_teammate_ids(user)
    return (
        ContentSeed.objects.filter(
            user_id__in=visible_user_ids,
            blueprint__share_bundle=True,
        )
        .select_related("marketing_campaign", "user")
        .order_by("-created_at")
    )


def _posts_for_seed(seed):
    return (
        Post.objects.filter(seed=seed, generated_by_agent="user_share")
        .select_related("social_account", "user")
        .order_by("created_at")
    )


@login_required
def share_list(request):
    """All Quick Share bundles — separate from Studio/Queue."""
    seeds = list(_share_seed_queryset(request.user)[:60])
    seed_ids = [s.id for s in seeds]
    posts_by_seed: dict = {sid: [] for sid in seed_ids}
    if seed_ids:
        for post in Post.objects.filter(seed_id__in=seed_ids).select_related("social_account"):
            posts_by_seed.setdefault(post.seed_id, []).append(post)

    bundles = [
        summarize_share_bundle(seed, posts_by_seed.get(seed.id, []))
        for seed in seeds
    ]
    attention_count = sum(1 for b in bundles if b["needs_attention"])

    return render(request, "dashboard/content/share_list.html", {
        "bundles": bundles,
        "attention_count": attention_count,
        "active_tab": "shares",
    })


@login_required
def share_detail(request, seed_id):
    """Single Quick Share bundle — timeline, status, edit & reschedule."""
    seed = get_object_or_404(
        ContentSeed.objects.select_related("marketing_campaign", "user"),
        id=seed_id,
    )
    if seed.user_id not in get_teammate_ids(request.user):
        raise Http404
    if not is_share_bundle_seed(seed):
        raise Http404

    posts = list(_posts_for_seed(seed))
    detail = build_share_bundle_detail(seed, posts)

    return render(request, "dashboard/content/share_detail.html", {
        **detail,
        "active_tab": "shares",
    })


@login_required
@require_POST
@ratelimit(key="user", rate="10/m", block=True)
def share_reschedule_bundle(request, seed_id):
    """Re-stagger all posts in a Quick Share bundle."""
    seed = get_object_or_404(ContentSeed, id=seed_id)
    if seed.user_id not in get_teammate_ids(request.user):
        raise Http404
    if not is_share_bundle_seed(seed):
        raise Http404

    try:
        gap_hours = int(request.POST.get("gap_hours") or 4)
    except (TypeError, ValueError):
        gap_hours = 4
    publish_first = request.POST.get("publish_first") == "1"

    count = reschedule_share_bundle(
        seed.user,
        seed,
        gap_hours=gap_hours,
        publish_first=publish_first,
    )
    if count:
        messages.success(
            request,
            f"Rescheduled {count} post{'s' if count != 1 else ''} — "
            f"staggered {gap_hours}h apart.",
        )
    else:
        messages.warning(request, "No posts were eligible to reschedule.")

    return redirect("content:share_detail", seed_id=seed.id)


@login_required
@require_POST
@ratelimit(key="user", rate="10/m", block=True)
def share_update_context(request, seed_id):
    """Update bundle title/context and sync caption on draft posts."""
    seed = get_object_or_404(ContentSeed, id=seed_id)
    if seed.user_id not in get_teammate_ids(request.user):
        raise Http404
    if not is_share_bundle_seed(seed):
        raise Http404

    title = (request.POST.get("title") or "").strip()
    context = (request.POST.get("context") or "").strip()
    caption = (request.POST.get("caption") or "").strip()

    from apps.create.content.share_bundle import human_share_title

    bundle_posts = list(Post.objects.filter(seed=seed, generated_by_agent="user_share"))
    if title and is_meaningless_share_label(title):
        title = human_share_title(seed, bundle_posts, user=seed.user)

    if title:
        seed.idea = title[:500]
    if context:
        seed.notes = context[:2000]
    seed.save(update_fields=["idea", "notes", "updated_at"])

    if caption:
        from apps.create.content.post_copy import polish_post_caption

        editable = Post.objects.filter(
            seed=seed,
            status__in=(
                Post.Status.DRAFT,
                Post.Status.PENDING_APPROVAL,
                Post.Status.APPROVED,
                Post.Status.SCHEDULED,
            ),
        )
        for post in editable:
            polished = polish_post_caption(
                caption,
                post.platform or "instagram",
                post_format=post.post_format or "image",
            )
            post.content_text = polished
            post.save(update_fields=["content_text", "updated_at"])

        if seed.marketing_campaign and title:
            seed.marketing_campaign.title = title[:200]
            seed.marketing_campaign.save(update_fields=["title", "updated_at"])

    messages.success(request, "Quick Share updated.")
    return redirect("content:share_detail", seed_id=seed.id)
