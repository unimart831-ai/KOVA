"""Admin dashboard — Review request loop."""

from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone

from apps.admin_dashboard.decorators import staff_required
from apps.reviews.models import ReviewRequest


@staff_required
def reviews_overview(request):
    now = timezone.now()
    week_ago = now - timedelta(days=7)

    total = ReviewRequest.objects.count()
    sent_7d = ReviewRequest.objects.filter(sent_at__gte=week_ago).count()
    pending = ReviewRequest.objects.filter(status=ReviewRequest.Status.PENDING).count()
    responded = ReviewRequest.objects.filter(status=ReviewRequest.Status.RESPONDED).count()
    failed = ReviewRequest.objects.filter(status=ReviewRequest.Status.FAILED).count()
    positive = ReviewRequest.objects.filter(sentiment=ReviewRequest.Sentiment.POSITIVE).count()
    negative = ReviewRequest.objects.filter(sentiment=ReviewRequest.Sentiment.NEGATIVE).count()
    seeds_created = ReviewRequest.objects.filter(content_seed__isnull=False).count()

    by_status = list(
        ReviewRequest.objects.values("status").annotate(count=Count("id")).order_by("-count")
    )
    by_channel = list(
        ReviewRequest.objects.values("channel").annotate(count=Count("id")).order_by("-count")
    )

    top_users = list(
        ReviewRequest.objects.values("user__email", "user__full_name", "user__id")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )

    recent = (
        ReviewRequest.objects.select_related("user", "lead", "booking")
        .order_by("-created_at")[:15]
    )

    return render(request, "admin_dashboard/reviews/overview.html", {
        "page_title": "Reviews",
        "total": total,
        "sent_7d": sent_7d,
        "pending": pending,
        "responded": responded,
        "failed": failed,
        "positive": positive,
        "negative": negative,
        "seeds_created": seeds_created,
        "by_status": by_status,
        "by_channel": by_channel,
        "top_users": top_users,
        "recent": recent,
    })


@staff_required
def review_list(request):
    qs = ReviewRequest.objects.select_related("user").order_by("-created_at")

    status = request.GET.get("status")
    if status in dict(ReviewRequest.Status.choices):
        qs = qs.filter(status=status)

    sentiment = request.GET.get("sentiment")
    if sentiment in dict(ReviewRequest.Sentiment.choices):
        qs = qs.filter(sentiment=sentiment)

    email = request.GET.get("email")
    if email:
        qs = qs.filter(user__email__icontains=email)

    q = request.GET.get("q")
    if q:
        qs = qs.filter(
            Q(customer_name__icontains=q)
            | Q(customer_email__icontains=q)
            | Q(customer_phone__icontains=q),
        )

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get("page", 1))

    return render(request, "admin_dashboard/reviews/list.html", {
        "page_title": "All Review Requests",
        "page_obj": page,
        "current_status": status,
        "current_sentiment": sentiment,
        "current_email": email or "",
        "current_q": q or "",
    })
