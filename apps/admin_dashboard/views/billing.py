from datetime import timedelta
from decimal import Decimal
import uuid as uuid_mod

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import User, UserProfile
from apps.admin_dashboard.decorators import senior_staff_required, staff_required, superuser_required
from apps.billing.models import PLAN_LIMITS, BillingEvent, DiscountCode, DiscountRedemption, MpesaPayment, PlanPrice, SubscriptionOverride, get_all_plan_limits


@staff_required
def billing_overview(request):
    """Revenue dashboard — MRR, subscriptions, churn, charts."""
    now = timezone.now()
    today = now.date()
    month_start = today.replace(day=1)
    last_30d = now - timedelta(days=30)

    # ── Subscription breakdown by plan ───────────────────────────────
    all_plans = get_all_plan_limits()
    plan_breakdown = []
    total_mrr_kes = Decimal("0")
    total_paying = 0
    for plan_code, plan_label in UserProfile.PlanTier.choices:
        info = all_plans.get(plan_code, {})
        count = UserProfile.objects.filter(plan=plan_code, subscription_status="active").count()
        price_kes = Decimal(str(info.get("price_kes", 0)))
        price_usd = Decimal(str(info.get("price_usd", 0)))
        rev_kes = price_kes * count
        rev_usd = price_usd * count
        total_mrr_kes += rev_kes
        if price_kes > 0:
            total_paying += count
        plan_breakdown.append({
            "code": plan_code,
            "label": info.get("label", plan_label),
            "count": count,
            "price_kes": price_kes,
            "price_usd": price_usd,
            "rev_kes": rev_kes,
            "rev_usd": rev_usd,
        })

    total_mrr_usd = sum(p["rev_usd"] for p in plan_breakdown)
    arr_usd = total_mrr_usd * 12
    arpu = total_mrr_usd / total_paying if total_paying else Decimal("0")

    # ── Subscription lifecycle ───────────────────────────────────────
    active_subs = UserProfile.objects.filter(subscription_status="active").count()
    trialing = UserProfile.objects.filter(subscription_status="trialing").count()
    past_due = UserProfile.objects.filter(subscription_status="past_due").count()
    canceled_30d = UserProfile.objects.filter(
        subscription_status="canceled", updated_at__gte=last_30d,
    ).count()

    # Trial conversion (trials ended in last 30d that became active)
    expired_trials = UserProfile.objects.filter(
        trial_ends_at__isnull=False, trial_ends_at__lte=now, trial_ends_at__gte=last_30d,
    ).count()
    converted_trials = UserProfile.objects.filter(
        trial_ends_at__isnull=False, trial_ends_at__lte=now, trial_ends_at__gte=last_30d,
        subscription_status="active",
    ).count()
    trial_conversion = round(converted_trials / expired_trials * 100, 1) if expired_trials else 0

    # ── Revenue totals ───────────────────────────────────────────────
    total_revenue = MpesaPayment.objects.filter(
        status="completed",
    ).aggregate(t=Sum("amount"))["t"] or Decimal("0")
    revenue_month = MpesaPayment.objects.filter(
        status="completed", completed_at__date__gte=month_start,
    ).aggregate(t=Sum("amount"))["t"] or Decimal("0")

    # ── Plan distribution chart ──────────────────────────────────────
    plan_chart = [
        {"label": p["label"], "count": p["count"]}
        for p in plan_breakdown if p["count"] > 0
    ]

    # ── Payment success rate (30 days) ───────────────────────────────
    mpesa_completed = MpesaPayment.objects.filter(
        created_at__gte=last_30d, status="completed",
    ).count()
    mpesa_failed = MpesaPayment.objects.filter(
        created_at__gte=last_30d, status="failed",
    ).count()
    mpesa_expired = MpesaPayment.objects.filter(
        created_at__gte=last_30d, status="expired",
    ).count()
    mpesa_pending = MpesaPayment.objects.filter(
        created_at__gte=last_30d, status="pending",
    ).count()

    # ── Monthly revenue trend (last 12 months) ───────────────────────
    revenue_trend = []
    for i in range(11, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        from calendar import monthrange
        _, last_day = monthrange(y, m)
        from datetime import date
        m_start = date(y, m, 1)
        m_end = date(y, m, last_day)
        rev = MpesaPayment.objects.filter(
            status="completed",
            completed_at__date__gte=m_start,
            completed_at__date__lte=m_end,
        ).aggregate(t=Sum("amount"))["t"] or 0
        revenue_trend.append({
            "month": m_start.strftime("%b %Y"),
            "revenue": float(rev),
        })

    context = {
        "page_title": "Billing & Revenue",
        # Revenue cards
        "total_mrr_kes": total_mrr_kes,
        "total_mrr_usd": total_mrr_usd,
        "arr_usd": arr_usd,
        "arpu": round(arpu, 2),
        "total_revenue": total_revenue,
        "revenue_month": revenue_month,
        "total_paying": total_paying,
        # Plan breakdown
        "plan_breakdown": plan_breakdown,
        "plan_chart_json": plan_chart,
        # Subscription lifecycle
        "active_subs": active_subs,
        "trialing": trialing,
        "past_due": past_due,
        "canceled_30d": canceled_30d,
        "trial_conversion": trial_conversion,
        "converted_trials": converted_trials,
        "expired_trials": expired_trials,
        # Payment success
        "mpesa_completed": mpesa_completed,
        "mpesa_failed": mpesa_failed,
        "mpesa_expired": mpesa_expired,
        "mpesa_pending": mpesa_pending,
        # Charts
        "revenue_trend_json": revenue_trend,
    }
    return render(request, "admin_dashboard/billing/overview.html", context)


@staff_required
def payment_list(request):
    """M-Pesa + billing event log with search/filter/sort/paginate."""
    qs = MpesaPayment.objects.select_related("user").all()

    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(
            Q(user__email__icontains=search)
            | Q(receipt_number__icontains=search)
            | Q(phone_number__icontains=search)
        )

    status_filter = request.GET.get("status", "")
    if status_filter:
        qs = qs.filter(status=status_filter)

    plan_filter = request.GET.get("plan", "")
    if plan_filter:
        qs = qs.filter(plan_tier=plan_filter)

    sort = request.GET.get("sort", "-created_at")
    valid_sorts = {
        "created_at", "-created_at", "amount", "-amount",
    }
    if sort not in valid_sorts:
        sort = "-created_at"
    qs = qs.order_by(sort)

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page", 1))

    context = {
        "page_title": "Payment History",
        "page_obj": page,
        "search": search,
        "current_status": status_filter,
        "current_plan": plan_filter,
        "current_sort": sort,
        "total_count": paginator.count,
        "status_choices": MpesaPayment.Status.choices,
        "plan_choices": UserProfile.PlanTier.choices,
    }
    return render(request, "admin_dashboard/billing/payments.html", context)


@staff_required
def billing_events(request):
    """Billing event audit trail — Stripe webhooks + M-Pesa callbacks."""
    qs = BillingEvent.objects.select_related("user").all()

    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(
            Q(event_type__icontains=search)
            | Q(user__email__icontains=search)
            | Q(error_message__icontains=search)
        )

    provider = request.GET.get("provider", "")
    if provider:
        qs = qs.filter(provider=provider)

    processed = request.GET.get("processed", "")
    if processed == "yes":
        qs = qs.filter(processed=True)
    elif processed == "no":
        qs = qs.filter(processed=False)

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page", 1))

    context = {
        "page_title": "Billing Events",
        "page_obj": page,
        "search": search,
        "current_provider": provider,
        "current_processed": processed,
        "total_count": paginator.count,
    }
    return render(request, "admin_dashboard/billing/events.html", context)


# ─── Subscription Management ────────────────────────────────────────────────

@staff_required
def subscription_management(request):
    """Search users and manage individual subscriptions."""
    now = timezone.now()
    last_30d = now - timedelta(days=30)

    # Stats
    total_active = UserProfile.objects.filter(subscription_status="active").count()
    total_trialing = UserProfile.objects.filter(subscription_status="trialing").count()
    total_comps = SubscriptionOverride.objects.filter(
        action="comp_access", expires_at__gt=now,
    ).values("user").distinct().count()
    overrides_month = SubscriptionOverride.objects.filter(
        created_at__gte=last_30d,
    ).count()

    # User search
    qs = User.objects.select_related("profile").none()
    search = request.GET.get("q", "").strip()
    if search:
        qs = User.objects.select_related("profile").filter(
            Q(email__icontains=search)
            | Q(full_name__icontains=search)
            | Q(profile__company_name__icontains=search)
        ).order_by("-date_joined")

    plan_filter = request.GET.get("plan", "")
    if plan_filter:
        qs = qs.filter(profile__plan=plan_filter)

    status_filter = request.GET.get("status", "")
    if status_filter:
        qs = qs.filter(profile__subscription_status=status_filter)

    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get("page", 1))

    context = {
        "page_title": "Subscription Management",
        "page_obj": page,
        "search": search,
        "current_plan": plan_filter,
        "current_status": status_filter,
        "total_count": paginator.count,
        "total_active": total_active,
        "total_trialing": total_trialing,
        "total_comps": total_comps,
        "overrides_month": overrides_month,
        "plan_choices": UserProfile.PlanTier.choices,
        "status_choices": [
            ("active", "Active"), ("trialing", "Trialing"),
            ("past_due", "Past Due"), ("canceled", "Canceled"), ("none", "None"),
        ],
    }
    return render(request, "admin_dashboard/billing/subscriptions.html", context)


@senior_staff_required
@require_POST
def subscription_action(request):
    """Handle individual subscription actions: plan change, trial extend, status change, comp access. Requires senior staff."""
    user = get_object_or_404(User, pk=request.POST.get("user_id"))
    action = request.POST.get("action", "")
    reason = request.POST.get("reason", "").strip()
    profile = user.profile

    if not reason:
        messages.error(request, "Reason is required for all subscription changes.")
        return redirect("admin_dashboard:subscription_management")

    if action == "plan_change":
        new_plan = request.POST.get("new_plan", "")
        if new_plan not in dict(UserProfile.PlanTier.choices):
            messages.error(request, "Invalid plan tier.")
            return redirect("admin_dashboard:subscription_management")

        SubscriptionOverride.objects.create(
            user=user, admin=request.user, action="plan_change",
            previous_plan=profile.plan, new_plan=new_plan,
            previous_status=profile.subscription_status,
            new_status=profile.subscription_status,
            reason=reason,
        )
        profile.plan = new_plan
        profile.save(update_fields=["plan", "updated_at"])
        messages.success(request, f"Plan changed to {new_plan.title()} for {user.email}")

    elif action == "trial_extension":
        extra_days = int(request.POST.get("extra_days", 0))
        if extra_days < 1 or extra_days > 365:
            messages.error(request, "Days must be between 1 and 365.")
            return redirect("admin_dashboard:subscription_management")

        now = timezone.now()
        base = profile.trial_ends_at if profile.trial_ends_at and profile.trial_ends_at > now else now
        new_end = base + timedelta(days=extra_days)

        SubscriptionOverride.objects.create(
            user=user, admin=request.user, action="trial_extension",
            previous_plan=profile.plan, new_plan=profile.plan,
            previous_status=profile.subscription_status,
            new_status="trialing",
            days_granted=extra_days, expires_at=new_end,
            reason=reason,
        )
        profile.trial_ends_at = new_end
        profile.subscription_status = "trialing"
        profile.save(update_fields=["trial_ends_at", "subscription_status", "updated_at"])
        messages.success(request, f"Trial extended by {extra_days} days for {user.email}")

    elif action == "status_change":
        new_status = request.POST.get("new_status", "")
        valid = dict([
            ("active", "Active"), ("trialing", "Trialing"),
            ("past_due", "Past Due"), ("canceled", "Canceled"), ("none", "None"),
        ])
        if new_status not in valid:
            messages.error(request, "Invalid status.")
            return redirect("admin_dashboard:subscription_management")

        SubscriptionOverride.objects.create(
            user=user, admin=request.user, action="status_change",
            previous_plan=profile.plan, new_plan=profile.plan,
            previous_status=profile.subscription_status,
            new_status=new_status,
            reason=reason,
        )
        profile.subscription_status = new_status
        profile.save(update_fields=["subscription_status", "updated_at"])
        messages.success(request, f"Status changed to {valid[new_status]} for {user.email}")

    elif action == "comp_access":
        comp_plan = request.POST.get("comp_plan", "")
        comp_days = int(request.POST.get("comp_days", 0))
        if comp_plan not in dict(UserProfile.PlanTier.choices):
            messages.error(request, "Invalid plan tier.")
            return redirect("admin_dashboard:subscription_management")
        if comp_days < 1 or comp_days > 730:
            messages.error(request, "Days must be between 1 and 730.")
            return redirect("admin_dashboard:subscription_management")

        expires = timezone.now() + timedelta(days=comp_days)
        SubscriptionOverride.objects.create(
            user=user, admin=request.user, action="comp_access",
            previous_plan=profile.plan, new_plan=comp_plan,
            previous_status=profile.subscription_status,
            new_status="active",
            days_granted=comp_days, expires_at=expires,
            reason=reason,
        )
        profile.plan = comp_plan
        profile.subscription_status = "active"
        profile.current_period_end = expires
        profile.save(update_fields=["plan", "subscription_status", "current_period_end", "updated_at"])
        messages.success(request, f"Comp access granted: {comp_plan.title()} for {comp_days} days to {user.email}")

    else:
        messages.error(request, "Unknown action.")

    return redirect(f"{request.META.get('HTTP_REFERER', '')}") if request.META.get("HTTP_REFERER") else redirect("admin_dashboard:subscription_management")


# ─── Bulk Grant ──────────────────────────────────────────────────────────────

@superuser_required
def bulk_grant(request):
    """Bulk grant plan access — for partnerships, promotions, etc. Requires superuser."""
    if request.method == "POST":
        step = request.POST.get("step", "preview")

        plan = request.POST.get("plan", "")
        days = request.POST.get("days", "")
        reason = request.POST.get("reason", "").strip()
        emails_raw = request.POST.get("emails", "").strip()

        # Validate inputs
        errors = []
        if plan not in dict(UserProfile.PlanTier.choices):
            errors.append("Invalid plan tier.")
        try:
            days = int(days)
            if days < 1 or days > 730:
                errors.append("Days must be between 1 and 730.")
        except (TypeError, ValueError):
            errors.append("Days must be a valid number.")
            days = 0
        if not reason:
            errors.append("Reason is required.")
        if not emails_raw:
            errors.append("At least one email is required.")

        # Parse emails
        emails = [e.strip().lower() for e in emails_raw.replace(",", "\n").splitlines() if e.strip()]
        emails = list(dict.fromkeys(emails))  # dedupe preserving order

        if errors:
            for e in errors:
                messages.error(request, e)
            context = {
                "page_title": "Bulk Grant Access",
                "plan_choices": UserProfile.PlanTier.choices,
                "form_plan": plan, "form_days": days,
                "form_reason": reason, "form_emails": emails_raw,
            }
            return render(request, "admin_dashboard/billing/bulk_grant.html", context)

        # Look up users
        found_users = User.objects.select_related("profile").filter(
            email__in=emails
        )
        found_emails = set(found_users.values_list("email", flat=True))
        not_found = [e for e in emails if e not in found_emails]

        if step == "preview":
            plan_info = PLAN_LIMITS.get(plan, {})
            context = {
                "page_title": "Bulk Grant Access",
                "plan_choices": UserProfile.PlanTier.choices,
                "step": "confirm",
                "preview_users": found_users,
                "not_found_emails": not_found,
                "plan": plan,
                "plan_label": plan_info.get("label", plan.title()),
                "days": days,
                "reason": reason,
                "emails_raw": emails_raw,
                "total_found": found_users.count(),
                "total_not_found": len(not_found),
            }
            return render(request, "admin_dashboard/billing/bulk_grant.html", context)

        elif step == "confirm":
            if not found_users.exists():
                messages.error(request, "No valid users to update.")
                return redirect("admin_dashboard:bulk_grant")

            batch_id = f"bulk_{uuid_mod.uuid4().hex[:12]}"
            expires = timezone.now() + timedelta(days=days)
            applied = 0

            for u in found_users:
                p = u.profile
                SubscriptionOverride.objects.create(
                    user=u, admin=request.user, action="bulk_grant",
                    previous_plan=p.plan, new_plan=plan,
                    previous_status=p.subscription_status,
                    new_status="active",
                    days_granted=days, expires_at=expires,
                    reason=reason, batch_id=batch_id,
                )
                p.plan = plan
                p.subscription_status = "active"
                p.current_period_end = expires
                p.save(update_fields=["plan", "subscription_status", "current_period_end", "updated_at"])
                applied += 1

            messages.success(
                request,
                f"Bulk grant complete: {applied} user{'s' if applied != 1 else ''} "
                f"upgraded to {plan.title()} for {days} days. Batch: {batch_id}"
            )
            return redirect("admin_dashboard:override_log")

    context = {
        "page_title": "Bulk Grant Access",
        "plan_choices": UserProfile.PlanTier.choices,
    }
    return render(request, "admin_dashboard/billing/bulk_grant.html", context)


# ─── Override Log ────────────────────────────────────────────────────────────

@staff_required
def override_log(request):
    """Audit trail of all admin subscription overrides."""
    qs = SubscriptionOverride.objects.select_related("user", "admin").all()

    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(
            Q(user__email__icontains=search)
            | Q(admin__email__icontains=search)
            | Q(reason__icontains=search)
            | Q(batch_id__icontains=search)
        )

    action_filter = request.GET.get("action", "")
    if action_filter:
        qs = qs.filter(action=action_filter)

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page", 1))

    context = {
        "page_title": "Override Log",
        "page_obj": page,
        "search": search,
        "current_action": action_filter,
        "total_count": paginator.count,
        "action_choices": SubscriptionOverride.ActionType.choices,
    }
    return render(request, "admin_dashboard/billing/overrides.html", context)


# ─── Plan Pricing Management ────────────────────────────────────────────────

@senior_staff_required
def plan_pricing(request):
    """Manage plan prices from the dashboard."""
    from django.core.cache import cache

    all_plans = get_all_plan_limits()
    db_prices = {p.tier: p for p in PlanPrice.objects.all()}

    plans = []
    for tier, info in PLAN_LIMITS.items():
        db = db_prices.get(tier)
        plans.append({
            "tier": tier,
            "label": info["label"],
            "default_kes": info["price_kes"],
            "default_usd": info["price_usd"],
            "current_kes": all_plans[tier]["price_kes"],
            "current_usd": all_plans[tier]["price_usd"],
            "has_override": db is not None and db.is_active,
            "db_obj": db,
        })

    context = {
        "page_title": "Plan Pricing",
        "plans": plans,
    }
    return render(request, "admin_dashboard/billing/pricing.html", context)


@senior_staff_required
@require_POST
def plan_pricing_update(request):
    """Update a single plan's price."""
    from django.core.cache import cache

    tier = request.POST.get("tier", "")
    if tier not in PLAN_LIMITS:
        messages.error(request, "Invalid plan tier.")
        return redirect("admin_dashboard:plan_pricing")

    action = request.POST.get("action", "")

    if action == "reset":
        PlanPrice.objects.filter(tier=tier).delete()
        cache.delete("plan_price_overrides")
        messages.success(request, f"Price for {PLAN_LIMITS[tier]['label']} reset to default.")
        return redirect("admin_dashboard:plan_pricing")

    try:
        price_kes = int(request.POST.get("price_kes", 0))
        price_usd = int(request.POST.get("price_usd", 0))
    except (ValueError, TypeError):
        messages.error(request, "Prices must be valid numbers.")
        return redirect("admin_dashboard:plan_pricing")

    if price_kes < 0 or price_usd < 0:
        messages.error(request, "Prices cannot be negative.")
        return redirect("admin_dashboard:plan_pricing")

    obj, created = PlanPrice.objects.update_or_create(
        tier=tier,
        defaults={
            "price_kes": price_kes,
            "price_usd": price_usd,
            "is_active": True,
            "updated_by": request.user,
        },
    )
    cache.delete("plan_price_overrides")
    messages.success(
        request,
        f"{'Created' if created else 'Updated'} price for {PLAN_LIMITS[tier]['label']}: "
        f"KES {price_kes} / ${price_usd}",
    )
    return redirect("admin_dashboard:plan_pricing")


# ─── Discount Code Management ───────────────────────────────────────────────

@staff_required
def discount_list(request):
    """List and search discount codes."""
    qs = DiscountCode.objects.all()

    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(
            Q(code__icontains=search) | Q(description__icontains=search)
        )

    status_filter = request.GET.get("status", "")
    if status_filter == "active":
        now = timezone.now()
        qs = qs.filter(is_active=True, valid_from__lte=now, valid_until__gte=now)
    elif status_filter == "expired":
        qs = qs.filter(valid_until__lt=timezone.now())
    elif status_filter == "inactive":
        qs = qs.filter(is_active=False)

    # Stats
    now = timezone.now()
    total_codes = DiscountCode.objects.count()
    active_codes = DiscountCode.objects.filter(
        is_active=True, valid_from__lte=now, valid_until__gte=now,
    ).count()
    total_redemptions = DiscountRedemption.objects.count()
    total_savings_kes = DiscountRedemption.objects.filter(
        currency="KES",
    ).aggregate(t=Sum("amount_saved"))["t"] or 0

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page", 1))

    context = {
        "page_title": "Discount Codes",
        "page_obj": page,
        "search": search,
        "current_status": status_filter,
        "total_count": paginator.count,
        "total_codes": total_codes,
        "active_codes": active_codes,
        "total_redemptions": total_redemptions,
        "total_savings_kes": total_savings_kes,
    }
    return render(request, "admin_dashboard/billing/discounts.html", context)


@senior_staff_required
def discount_create(request):
    """Create a new discount code."""
    if request.method == "POST":
        code = request.POST.get("code", "").strip().upper()
        description = request.POST.get("description", "").strip()
        discount_type = request.POST.get("discount_type", "")
        discount_value = request.POST.get("discount_value", "")
        applicable_plans = request.POST.getlist("applicable_plans")
        max_uses = request.POST.get("max_uses", "0")
        max_uses_per_user = request.POST.get("max_uses_per_user", "1")
        valid_from = request.POST.get("valid_from", "")
        valid_until = request.POST.get("valid_until", "")

        errors = []
        if not code or len(code) < 3:
            errors.append("Code must be at least 3 characters.")
        if DiscountCode.objects.filter(code=code).exists():
            errors.append(f"Code '{code}' already exists.")
        if discount_type not in dict(DiscountCode.DiscountType.choices):
            errors.append("Invalid discount type.")
        try:
            discount_value = float(discount_value)
            if discount_value <= 0:
                errors.append("Discount value must be positive.")
            if discount_type == "percentage" and discount_value > 100:
                errors.append("Percentage cannot exceed 100%.")
        except (ValueError, TypeError):
            errors.append("Discount value must be a valid number.")
            discount_value = 0
        try:
            max_uses = int(max_uses)
            max_uses_per_user = int(max_uses_per_user)
        except (ValueError, TypeError):
            errors.append("Max uses must be valid numbers.")
            max_uses, max_uses_per_user = 0, 1
        if not valid_from or not valid_until:
            errors.append("Start and end dates are required.")

        if errors:
            for e in errors:
                messages.error(request, e)
            context = {
                "page_title": "Create Discount Code",
                "plan_choices": UserProfile.PlanTier.choices,
                "discount_types": DiscountCode.DiscountType.choices,
                "form": request.POST,
            }
            return render(request, "admin_dashboard/billing/discount_form.html", context)

        from django.utils.dateparse import parse_datetime
        parsed_from = parse_datetime(valid_from) or timezone.datetime.fromisoformat(valid_from).replace(tzinfo=timezone.utc)
        parsed_until = parse_datetime(valid_until) or timezone.datetime.fromisoformat(valid_until).replace(tzinfo=timezone.utc)

        DiscountCode.objects.create(
            code=code,
            description=description,
            discount_type=discount_type,
            discount_value=discount_value,
            applicable_plans=applicable_plans if applicable_plans else [],
            max_uses=max_uses,
            max_uses_per_user=max_uses_per_user,
            valid_from=parsed_from,
            valid_until=parsed_until,
            created_by=request.user,
        )
        messages.success(request, f"Discount code '{code}' created successfully.")
        return redirect("admin_dashboard:discount_list")

    context = {
        "page_title": "Create Discount Code",
        "plan_choices": UserProfile.PlanTier.choices,
        "discount_types": DiscountCode.DiscountType.choices,
    }
    return render(request, "admin_dashboard/billing/discount_form.html", context)


@senior_staff_required
def discount_edit(request, pk):
    """Edit an existing discount code."""
    code_obj = get_object_or_404(DiscountCode, pk=pk)

    if request.method == "POST":
        code_obj.description = request.POST.get("description", "").strip()
        discount_type = request.POST.get("discount_type", "")
        if discount_type in dict(DiscountCode.DiscountType.choices):
            code_obj.discount_type = discount_type

        try:
            code_obj.discount_value = float(request.POST.get("discount_value", code_obj.discount_value))
        except (ValueError, TypeError):
            messages.error(request, "Invalid discount value.")
            return redirect("admin_dashboard:discount_edit", pk=pk)

        code_obj.applicable_plans = request.POST.getlist("applicable_plans") or []
        try:
            code_obj.max_uses = int(request.POST.get("max_uses", 0))
            code_obj.max_uses_per_user = int(request.POST.get("max_uses_per_user", 1))
        except (ValueError, TypeError):
            pass

        valid_from = request.POST.get("valid_from", "")
        valid_until = request.POST.get("valid_until", "")
        if valid_from:
            from django.utils.dateparse import parse_datetime
            parsed = parse_datetime(valid_from)
            if parsed:
                code_obj.valid_from = parsed
        if valid_until:
            from django.utils.dateparse import parse_datetime
            parsed = parse_datetime(valid_until)
            if parsed:
                code_obj.valid_until = parsed

        code_obj.save()
        messages.success(request, f"Discount code '{code_obj.code}' updated.")
        return redirect("admin_dashboard:discount_list")

    context = {
        "page_title": f"Edit Discount: {code_obj.code}",
        "code_obj": code_obj,
        "plan_choices": UserProfile.PlanTier.choices,
        "discount_types": DiscountCode.DiscountType.choices,
        "is_edit": True,
    }
    return render(request, "admin_dashboard/billing/discount_form.html", context)


@senior_staff_required
@require_POST
def discount_toggle(request, pk):
    """Toggle a discount code active/inactive."""
    code_obj = get_object_or_404(DiscountCode, pk=pk)
    code_obj.is_active = not code_obj.is_active
    code_obj.save(update_fields=["is_active", "updated_at"])
    status = "activated" if code_obj.is_active else "deactivated"
    messages.success(request, f"Discount code '{code_obj.code}' {status}.")
    return redirect("admin_dashboard:discount_list")
