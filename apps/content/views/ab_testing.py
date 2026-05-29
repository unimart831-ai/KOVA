from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.content.models import Post
from apps.utils import fire_task


@login_required
def ab_test_list(request):
    """List user's A/B tests."""
    from apps.billing.enforcement import check_ab_testing, enforce_or_redirect

    allowed, msg = check_ab_testing(request.user)
    if blocked := enforce_or_redirect(request, allowed, msg, "content:ab_test_list"):
        return blocked

    tests = request.user.ab_tests.select_related(
        "social_account", "seed", "winner",
    ).order_by("-created_at")

    return render(request, "content/ab_tests/list.html", {
        "tests": tests,
        "page_title": "A/B Tests",
    })


@login_required
def ab_test_create(request):
    """Create a new A/B test."""
    from apps.billing.enforcement import check_ab_testing, check_seed_limit, enforce_or_redirect
    from apps.content.models import ABTest, ContentSeed
    from apps.content.tasks import generate_ab_test_variants
    from apps.platforms.models import SocialAccount

    allowed, msg = check_ab_testing(request.user)
    if blocked := enforce_or_redirect(request, allowed, msg, "content:ab_test_list"):
        return blocked

    accounts = SocialAccount.objects.filter(user=request.user, is_active=True)
    if not accounts.exists():
        messages.error(request, "Connect a social account first.")
        return redirect("content:ab_test_list")

    if request.method == "POST":
        idea = request.POST.get("idea", "").strip()
        notes = request.POST.get("notes", "").strip()
        account_id = request.POST.get("social_account", "")
        variant_count = int(request.POST.get("variant_count", "3"))
        duration = int(request.POST.get("test_duration_hours", "48"))

        if not idea:
            messages.error(request, "Please enter a content idea.")
            return redirect("content:ab_test_create")

        seed_allowed, seed_msg = check_seed_limit(request.user)
        if blocked := enforce_or_redirect(request, seed_allowed, seed_msg, "content:ab_test_list"):
            return blocked

        account = get_object_or_404(SocialAccount, id=account_id, user=request.user)
        variant_count = max(2, min(variant_count, 5))
        duration = max(12, min(duration, 168))

        seed = ContentSeed.objects.create(
            user=request.user,
            idea=idea,
            notes=notes,
            target_platforms=[account.platform],
            status=ContentSeed.SeedStatus.PROCESSING,
        )

        ab_test = ABTest.objects.create(
            user=request.user,
            name=idea[:255],
            seed=seed,
            social_account=account,
            variant_count=variant_count,
            test_duration_hours=duration,
            status=ABTest.Status.GENERATING,
        )

        fire_task(generate_ab_test_variants, str(ab_test.id))

        messages.success(request, f"A/B test created! Generating {variant_count} variants...")
        return redirect("content:ab_test_detail", test_id=ab_test.id)

    return render(request, "content/ab_tests/create.html", {
        "accounts": accounts,
        "page_title": "New A/B Test",
    })


@login_required
def ab_test_detail(request, test_id):
    """View A/B test with variant comparison."""
    from apps.content.models import ABTest

    ab_test = get_object_or_404(
        ABTest.objects.select_related("social_account", "seed", "winner"),
        id=test_id, user=request.user,
    )

    variants = (
        ab_test.variants.select_related("social_account", "metrics")
        .order_by("variant_label")
    )

    variant_data = []
    for v in variants:
        entry = {
            "post": v,
            "metrics": None,
            "total_engagement": 0,
        }
        try:
            m = v.metrics
            entry["metrics"] = m
            entry["total_engagement"] = m.likes + m.comments + m.shares + m.saves
        except Exception:
            pass
        variant_data.append(entry)

    return render(request, "content/ab_tests/detail.html", {
        "ab_test": ab_test,
        "variant_data": variant_data,
        "page_title": f"A/B Test: {ab_test.name[:50]}",
    })


@login_required
@require_POST
def ab_test_conclude(request, test_id):
    """Manually conclude an A/B test (evaluate and pick winner)."""
    from apps.content.models import ABTest
    from apps.agents.analyst_agent import evaluate_ab_test

    ab_test = get_object_or_404(ABTest, id=test_id, user=request.user)

    if ab_test.status not in (ABTest.Status.RUNNING, ABTest.Status.DRAFT):
        messages.info(request, "This test has already been concluded.")
        return redirect("content:ab_test_detail", test_id=ab_test.id)

    result = evaluate_ab_test(ab_test)

    if "error" in result:
        messages.warning(request, result["error"])
    else:
        messages.success(
            request,
            f"Test concluded! Variant {result['winner_label']} wins."
        )

    return redirect("content:ab_test_detail", test_id=ab_test.id)


@login_required
@require_POST
def ab_test_start(request, test_id):
    """Mark an A/B test as running (after user publishes all variants)."""
    from apps.content.models import ABTest
    from django.utils import timezone as tz

    ab_test = get_object_or_404(ABTest, id=test_id, user=request.user)

    if ab_test.status != ABTest.Status.DRAFT:
        messages.info(request, "This test is not in draft state.")
        return redirect("content:ab_test_detail", test_id=ab_test.id)

    ready = ab_test.variants.filter(
        status__in=[Post.Status.APPROVED, Post.Status.SCHEDULED, Post.Status.PUBLISHED]
    ).count()

    if ready < 2:
        messages.error(request, "Approve at least 2 variants before starting the test.")
        return redirect("content:ab_test_detail", test_id=ab_test.id)

    ab_test.status = ABTest.Status.RUNNING
    ab_test.started_at = tz.now()
    ab_test.save(update_fields=["status", "started_at", "updated_at"])

    messages.success(request, f"A/B test started! Results will be evaluated in {ab_test.test_duration_hours} hours.")
    return redirect("content:ab_test_detail", test_id=ab_test.id)


@login_required
@require_POST
def ab_test_cancel(request, test_id):
    """Cancel an A/B test."""
    from apps.content.models import ABTest

    ab_test = get_object_or_404(ABTest, id=test_id, user=request.user)

    if ab_test.status in (ABTest.Status.CONCLUDED,):
        messages.info(request, "Cannot cancel a concluded test.")
        return redirect("content:ab_test_detail", test_id=ab_test.id)

    ab_test.status = ABTest.Status.CANCELLED
    ab_test.save(update_fields=["status", "updated_at"])

    messages.success(request, "A/B test cancelled.")
    return redirect("content:ab_test_list")
