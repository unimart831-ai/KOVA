"""Blog Studio — founder-facing editorial dashboard for the Educator agent."""

from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.admin_dashboard.decorators import staff_required
from apps.help.models import Article, ArticleTopic


@staff_required
def blog_studio(request):
    counts = {
        "draft": Article.objects.filter(status=Article.Status.DRAFT).count(),
        "review": Article.objects.filter(status=Article.Status.REVIEW).count(),
        "published_blog": Article.objects.filter(
            status=Article.Status.PUBLISHED,
            audience__in=[Article.Audience.PROSPECT, Article.Audience.BOTH],
        ).count(),
        "topics": ArticleTopic.objects.filter(status=ArticleTopic.Status.PENDING).count(),
    }

    pending_review = list(
        Article.objects.filter(
            status__in=[Article.Status.DRAFT, Article.Status.REVIEW],
        ).order_by("-created_at")[:12]
    )

    published_blog = list(
        Article.objects.filter(
            status=Article.Status.PUBLISHED,
            audience__in=[Article.Audience.PROSPECT, Article.Audience.BOTH],
        ).order_by("-published_at")[:15]
    )

    topic_qs = ArticleTopic.objects.filter(
        status=ArticleTopic.Status.PENDING,
    ).order_by("-priority", "created_at")

    paginator = Paginator(topic_qs, 15)
    topics_page = paginator.get_page(request.GET.get("tp", 1))

    return render(request, "admin_dashboard/blog/studio.html", {
        "page_title": "Blog Studio",
        "counts": counts,
        "pending_review": pending_review,
        "published_blog": published_blog,
        "topics_page": topics_page,
        "audience_choices": Article.Audience.choices,
        "category_choices": Article.Category.choices,
    })


@staff_required
@require_POST
def blog_draft_next(request):
    """Trigger the Educator to draft the highest-priority pending topic. HTMX."""
    from apps.agents.educator_agent import draft_next_topic

    try:
        result = draft_next_topic(min_backlog=2, suggest_batch=8)
    except Exception as exc:
        return HttpResponse(
            f'<div class="rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 '
            f'px-4 py-3 text-sm text-red-800 dark:text-red-300">'
            f"Error drafting article: {exc}</div>",
            status=500,
        )

    if result is None:
        return HttpResponse(
            '<div class="rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900 '
            'px-4 py-3 text-sm text-amber-800 dark:text-amber-300">'
            "No topics in backlog. Generate topics first.</div>"
        )

    a = result.article
    return HttpResponse(
        f'<div class="rounded-lg bg-green-50 dark:bg-green-950/40 border border-green-200 dark:border-green-900 '
        f'px-4 py-3 text-sm text-green-800 dark:text-green-300">'
        f'Draft created: <strong>{a.title}</strong> &mdash; {a.reading_minutes} min read. '
        f'<a href="/dashboard/blog/articles/{a.pk}/" class="underline font-medium">Review it &rarr;</a>'
        f"</div>"
    )


@staff_required
@require_POST
def blog_suggest_topics(request):
    """Ask the Educator to generate fresh prospect-focused topics. HTMX."""
    from apps.agents.educator_agent import suggest_topics

    try:
        topics = suggest_topics(n=8)
    except Exception as exc:
        return HttpResponse(
            f'<div class="rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 '
            f'px-4 py-3 text-sm text-red-800 dark:text-red-300">'
            f"Error generating topics: {exc}</div>",
            status=500,
        )

    if not topics:
        return HttpResponse(
            '<div class="rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900 '
            'px-4 py-3 text-sm text-amber-800 dark:text-amber-300">'
            "Agent returned no new topics (all may already exist in backlog).</div>"
        )

    preview = "; ".join(f'"{t.title}"' for t in topics[:4])
    suffix = f" + {len(topics) - 4} more" if len(topics) > 4 else ""
    return HttpResponse(
        f'<div class="rounded-lg bg-green-50 dark:bg-green-950/40 border border-green-200 dark:border-green-900 '
        f'px-4 py-3 text-sm text-green-800 dark:text-green-300">'
        f"Added {len(topics)} topics: {preview}{suffix}. "
        f'<a href="/dashboard/blog/" class="underline font-medium">Refresh to see them &rarr;</a>'
        f"</div>"
    )


@staff_required
@require_POST
def blog_draft_topic(request, pk):
    """Draft a specific topic from the backlog. HTMX."""
    from apps.agents.educator_agent import draft_article

    topic = get_object_or_404(ArticleTopic, pk=pk)

    try:
        result = draft_article(topic)
    except Exception as exc:
        return HttpResponse(
            f'<span class="text-xs text-red-600 dark:text-red-400">Error: {exc}</span>',
            status=500,
        )

    a = result.article
    return HttpResponse(
        f'<span class="text-xs text-green-700 dark:text-green-400 font-medium">'
        f'Drafted &rarr; <a href="/dashboard/blog/articles/{a.pk}/" class="underline">{a.title[:60]}</a>'
        f"</span>"
    )


@staff_required
@require_POST
def blog_skip_topic(request, pk):
    """Skip a backlog topic so it won't be drafted. HTMX."""
    topic = get_object_or_404(ArticleTopic, pk=pk)
    topic.status = ArticleTopic.Status.SKIPPED
    topic.save(update_fields=["status"])
    return HttpResponse(
        '<span class="text-xs text-gray-400 dark:text-gray-500 italic">Skipped</span>'
    )


@staff_required
def blog_article_review(request, pk):
    """Full-page article preview with publish controls."""
    article = get_object_or_404(Article, pk=pk)
    return render(request, "admin_dashboard/blog/article_review.html", {
        "page_title": f"Review: {article.title[:60]}",
        "article": article,
        "audience_choices": Article.Audience.choices,
        "category_choices": Article.Category.choices,
        "status_choices": Article.Status.choices,
    })


@staff_required
@require_POST
def blog_article_publish(request, pk):
    """Publish an article. Sets audience to PROSPECT if it was USER-only."""
    article = get_object_or_404(Article, pk=pk)

    new_audience = request.POST.get("audience", article.audience)
    if new_audience in [c[0] for c in Article.Audience.choices]:
        article.audience = new_audience
        article.save(update_fields=["audience"])

    article.mark_published(reviewer=request.user)
    return redirect("admin_dashboard:blog_studio")


@staff_required
@require_POST
def blog_article_unpublish(request, pk):
    """Revert a published article back to draft."""
    article = get_object_or_404(Article, pk=pk)
    if article.status == Article.Status.PUBLISHED:
        article.status = Article.Status.DRAFT
        article.published_at = None
        article.save(update_fields=["status", "published_at", "updated_at"])
    return redirect("admin_dashboard:blog_studio")


@staff_required
@require_POST
def blog_article_delete(request, pk):
    """Delete a draft or review article entirely."""
    article = get_object_or_404(Article, pk=pk)
    if article.status in (Article.Status.DRAFT, Article.Status.REVIEW):
        article.delete()
    return redirect("admin_dashboard:blog_studio")
