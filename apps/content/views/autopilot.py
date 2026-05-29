from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.utils import fire_task


@login_required
def autopilot_dashboard(request):
    """Autopilot overview: preview plans, approve strategy, track execution."""
    from apps.content.autopilot import (
        AUTOPILOT_ACTIVE_STATUSES,
        _next_monday,
        get_plan_live_stats,
        log_plan_step,
        plan_user_week,
        recover_stale_planning,
        _planning_worker_started,
    )
    from apps.content.models import WeeklyContentPlan

    profile = request.user.profile
    plans = list(
        WeeklyContentPlan.objects.filter(user=request.user)
        .order_by("-week_start")[:20]
    )
    for p in plans:
        if p.status == WeeklyContentPlan.Status.PLANNING:
            recover_stale_planning(p)
    current_plan = next(
        (p for p in plans if p.status in AUTOPILOT_ACTIVE_STATUSES),
        None,
    )
    pending_plan = next(
        (p for p in plans if p.status == WeeklyContentPlan.Status.PENDING_REVIEW),
        None,
    )
    planning_plan = next(
        (p for p in plans if p.status == WeeklyContentPlan.Status.PLANNING),
        None,
    )
    plan_stats = {str(p.pk): get_plan_live_stats(p) for p in plans}
    current_plan_stats = plan_stats.get(str(current_plan.pk), {}) if current_plan else {}
    plans_with_stats = [{"plan": p, "stats": plan_stats.get(str(p.pk), {})} for p in plans]

    if request.method == "POST" and request.POST.get("action") == "trigger":
        from datetime import timedelta

        week_start = _next_monday()
        week_end = week_start + timedelta(days=6)
        existing = WeeklyContentPlan.objects.filter(
            user=request.user,
            week_start=week_start,
        ).exclude(
            status__in=[
                WeeklyContentPlan.Status.FAILED,
                WeeklyContentPlan.Status.CANCELLED,
            ],
        ).first()
        if existing:
            if existing.status == WeeklyContentPlan.Status.PLANNING:
                recover_stale_planning(existing)
                existing.refresh_from_db()
                if existing.status == WeeklyContentPlan.Status.PLANNING:
                    if not _planning_worker_started(existing):
                        log_plan_step(
                            existing, "queued",
                            "Restarting your weekly strategy preview.",
                            f"Week of {week_start.strftime('%b %d, %Y')}",
                        )
                        fire_task(
                            plan_user_week,
                            str(request.user.pk),
                            week_start.isoformat(),
                            str(existing.pk),
                        )
                return redirect(f"{reverse('content:autopilot')}?planning={existing.pk}")
            if existing.status == WeeklyContentPlan.Status.PENDING_REVIEW:
                messages.info(
                    request,
                    f"A plan preview for the week of {week_start.strftime('%b %d')} is already waiting for your approval.",
                )
            else:
                messages.info(
                    request,
                    f"You already have an active plan for the week of {week_start.strftime('%b %d')}.",
                )
            return redirect("content:autopilot_detail", plan_id=existing.pk)

        failed_plan = WeeklyContentPlan.objects.filter(
            user=request.user,
            week_start=week_start,
            status=WeeklyContentPlan.Status.FAILED,
        ).first()
        if failed_plan:
            failed_plan.status = WeeklyContentPlan.Status.PLANNING
            failed_plan.error_message = ""
            failed_plan.planning_log = []
            failed_plan.strategy = {}
            failed_plan.strategy_reasoning = ""
            failed_plan.week_end = week_end
            failed_plan.save(update_fields=[
                "status", "error_message", "planning_log", "strategy",
                "strategy_reasoning", "week_end",
            ])
            log_plan_step(
                failed_plan, "queued",
                "Queued your weekly strategy preview.",
                f"Week of {week_start.strftime('%b %d, %Y')}",
            )
            fire_task(
                plan_user_week,
                str(request.user.pk),
                week_start.isoformat(),
                str(failed_plan.pk),
            )
            return redirect(f"{reverse('content:autopilot')}?planning={failed_plan.pk}")

        plan = WeeklyContentPlan.objects.create(
            user=request.user,
            week_start=week_start,
            week_end=week_end,
            status=WeeklyContentPlan.Status.PLANNING,
            planning_log=[],
        )
        log_plan_step(plan, "queued", "Queued your weekly strategy preview.", f"Week of {week_start.strftime('%b %d, %Y')}")
        fire_task(plan_user_week, str(request.user.pk), week_start.isoformat(), str(plan.pk))
        return redirect(f"{reverse('content:autopilot')}?planning={plan.pk}")

    return render(request, "content/autopilot.html", {
        "plans": plans,
        "plans_with_stats": plans_with_stats,
        "current_plan": current_plan,
        "current_plan_stats": current_plan_stats,
        "pending_plan": pending_plan,
        "planning_plan": planning_plan,
        "planning_plan_id": request.GET.get("planning", "") or (str(planning_plan.pk) if planning_plan else ""),
        "autopilot_enabled": profile.autopilot_enabled,
        "auto_approve_posts": profile.auto_approve_posts,
        "autopilot_posts_per_week": profile.autopilot_posts_per_week or 5,
    })


@login_required
def autopilot_plan_status(request, plan_id):
    """JSON status for live planning modal (polled from the dashboard)."""
    from apps.content.autopilot import recover_stale_planning
    from apps.content.models import WeeklyContentPlan

    plan = get_object_or_404(WeeklyContentPlan, pk=plan_id, user=request.user)
    recover_stale_planning(plan)
    plan.refresh_from_db()
    strategy = plan.strategy or {}
    topics = strategy.get("daily_topics", [])
    terminal = plan.status in (
        WeeklyContentPlan.Status.PENDING_REVIEW,
        WeeklyContentPlan.Status.FAILED,
        WeeklyContentPlan.Status.CANCELLED,
    )
    return JsonResponse({
        "plan_id": str(plan.pk),
        "status": plan.status,
        "status_label": plan.get_status_display(),
        "week_start": plan.week_start.isoformat(),
        "planning_log": plan.planning_log or [],
        "theme": strategy.get("theme", ""),
        "reasoning": plan.strategy_reasoning or strategy.get("reasoning", ""),
        "content_mix": strategy.get("content_mix", {}),
        "topics": topics,
        "topics_count": len(topics),
        "error_message": plan.error_message,
        "terminal": terminal,
        "detail_url": reverse("content:autopilot_detail", kwargs={"plan_id": plan.pk}),
        "approve_url": reverse("content:autopilot_approve", kwargs={"plan_id": plan.pk}),
    })


@login_required
def autopilot_plan_detail(request, plan_id):
    """View a weekly plan — full strategy preview or generated posts."""
    from apps.content.autopilot import get_plan_live_stats, get_plan_posts
    from apps.content.models import WeeklyContentPlan

    plan = get_object_or_404(WeeklyContentPlan, pk=plan_id, user=request.user)
    profile = request.user.profile
    posts = get_plan_posts(plan)
    live_stats = get_plan_live_stats(plan)

    return render(request, "content/autopilot_detail.html", {
        "plan": plan,
        "posts": posts,
        "live_stats": live_stats,
        "auto_approve_posts": profile.auto_approve_posts,
        "is_preview": plan.status == WeeklyContentPlan.Status.PENDING_REVIEW,
    })


@login_required
@require_POST
def autopilot_approve(request, plan_id):
    """User approved the strategy preview — queue post generation."""
    from apps.content.autopilot import execute_autopilot_plan
    from apps.content.models import WeeklyContentPlan

    plan = get_object_or_404(WeeklyContentPlan, pk=plan_id, user=request.user)
    if plan.status != WeeklyContentPlan.Status.PENDING_REVIEW:
        messages.error(request, "This plan is not waiting for approval.")
        return redirect("content:autopilot_detail", plan_id=plan.pk)

    fire_task(execute_autopilot_plan, str(plan.pk))
    if request.user.profile.auto_approve_posts:
        messages.success(
            request,
            "Strategy approved. Kova is generating and scheduling your posts now.",
        )
    else:
        messages.success(
            request,
            "Strategy approved. Kova is generating your posts — you'll review them in Studio before publishing.",
        )
    return redirect("content:autopilot_detail", plan_id=plan.pk)


@login_required
@require_POST
def autopilot_cancel(request, plan_id):
    """Cancel a pending or active autopilot plan."""
    from apps.content.models import WeeklyContentPlan

    plan = get_object_or_404(WeeklyContentPlan, pk=plan_id, user=request.user)
    cancellable = (
        WeeklyContentPlan.Status.PENDING_REVIEW,
        WeeklyContentPlan.Status.PLANNING,
        WeeklyContentPlan.Status.GENERATING,
        WeeklyContentPlan.Status.SCHEDULING,
        WeeklyContentPlan.Status.ACTIVE,
    )
    if plan.status in cancellable:
        plan.status = WeeklyContentPlan.Status.CANCELLED
        plan.save(update_fields=["status"])
        messages.info(request, "Autopilot plan cancelled.")
    return redirect("content:autopilot")
