from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone

from apps.accounts.forms import (
    UserSettingsForm,
    BrandProfileForm,
    CTASettingsForm,
    OnboardingStep1Form,
    OnboardingStep2Form,
    OnboardingStep3Form,
)


@login_required
def settings_view(request):
    """User settings page with two forms: account info + brand profile."""
    if request.method == "POST":
        user_form = UserSettingsForm(request.POST, request.FILES, instance=request.user)
        brand_form = BrandProfileForm(request.POST, instance=request.user.profile)
        if user_form.is_valid() and brand_form.is_valid():
            user_form.save()
            brand_form.save()
            messages.success(request, "Settings saved.")
            return redirect("accounts:settings")
    else:
        user_form = UserSettingsForm(instance=request.user)
        brand_form = BrandProfileForm(instance=request.user.profile)

    return render(request, "accounts/settings.html", {
        "user_form": user_form,
        "brand_form": brand_form,
        "page_title": "Settings",
    })


@login_required
def cta_settings_view(request):
    """CTA default settings for post generation."""
    profile = request.user.profile
    if request.method == "POST":
        form = CTASettingsForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "CTA defaults saved.")
            return redirect("accounts:cta_settings")
    else:
        form = CTASettingsForm(instance=profile)

    kova_pages = request.user.kova_pages.filter(is_published=True).only("slug", "title")[:10]

    return render(request, "accounts/cta_settings.html", {
        "form": form,
        "kova_pages": kova_pages,
        "page_title": "CTA Settings",
    })


@login_required
def onboarding_view(request):
    """Multi-step onboarding wizard."""
    profile = request.user.profile
    step = int(request.GET.get("step", 1))
    total_steps = 4

    # Step 4 is a template-only step (connect platforms)
    if step == 4:
        if request.method == "POST":
            # ── Complete onboarding ──────────────────────────────────
            request.user.onboarding_completed = True
            request.user.save(update_fields=["onboarding_completed"])

            # ── Auto-create all 6 agent configs ──────────────────────
            from apps.agents.models import AgentConfig
            for agent_type in AgentConfig.AgentType.values:
                AgentConfig.objects.get_or_create(
                    user=request.user,
                    agent_type=agent_type,
                    defaults={"is_active": True},
                )

            # ── Initialize 14-day trial ──────────────────────────────
            from datetime import timedelta
            profile = request.user.profile
            if not profile.trial_ends_at:
                profile.trial_ends_at = timezone.now() + timedelta(days=14)
                profile.subscription_status = "trialing"
                profile.save(update_fields=["trial_ends_at", "subscription_status"])

            # ── Send welcome email (after onboarding, not at signup) ─
            from apps.emails.tasks import send_welcome_email
            send_welcome_email.delay(str(request.user.pk))

            # ── Fire the Agency Intelligence task chain ──────────────
            # Research → Starter Seeds → Content → Welcome Brief
            from apps.agents.onboarding_tasks import run_onboarding_intelligence
            from apps.utils import fire_task
            fire_task(run_onboarding_intelligence, str(request.user.pk))

            messages.success(request, "Welcome to Kova Agent! Your AI agency is analyzing your industry now.")
            return redirect("accounts:onboarding_complete")

        from apps.platforms.models import SocialAccount
        connected = SocialAccount.objects.filter(user=request.user, is_active=True)
        return render(request, "accounts/onboarding.html", {
            "step": 4,
            "total_steps": total_steps,
            "connected_accounts": connected,
            "page_title": "Connect a Platform",
        })

    if step == 1:
        form_class = OnboardingStep1Form
    elif step == 2:
        form_class = OnboardingStep2Form
    elif step == 3:
        form_class = OnboardingStep3Form
    else:
        return redirect("accounts:onboarding")

    # Forms that also update User fields receive `user` kwarg
    extra_kwargs = {}
    if step in (1, 3):
        extra_kwargs["user"] = request.user

    if request.method == "POST":
        form = form_class(request.POST, instance=profile, **extra_kwargs)
        if form.is_valid():
            form.save()
            return redirect(f"/accounts/onboarding/?step={step + 1}")
    else:
        form = form_class(instance=profile, **extra_kwargs)

    return render(request, "accounts/onboarding.html", {
        "form": form,
        "step": step,
        "total_steps": total_steps,
        "page_title": "Setup Your Brand",
    })


@login_required
def profile_industry_api(request):
    """Tiny JSON endpoint returning the user's industry for pillar suggestions."""
    profile = getattr(request.user, "profile", None)
    industry = getattr(profile, "industry", "") if profile else ""
    return JsonResponse({"industry": industry})


@login_required
def onboarding_complete(request):
    """
    The "Agency First Meeting" page — shown after onboarding Step 4.
    Displays animated progress as the AI agency analyzes the user's
    industry, creates starter content, and prepares a welcome brief.
    Uses HTMX polling to check progress.
    """
    from apps.agents.onboarding_tasks import get_onboarding_progress
    from apps.briefs.models import DailyBrief

    progress = get_onboarding_progress(request.user)
    today = timezone.now().date()
    brief = DailyBrief.objects.filter(user=request.user, date=today).first()

    # If everything is done, redirect to brief home after a few visits
    if progress["all_done"] and brief and request.GET.get("completed"):
        return redirect("brief:home")

    return render(request, "accounts/onboarding_complete.html", {
        "progress": progress,
        "brief": brief,
        "page_title": "Your AI Agency is Starting",
    })


@login_required
def onboarding_progress_api(request):
    """HTMX polling endpoint — returns progress fragment."""
    from apps.agents.onboarding_tasks import get_onboarding_progress
    from apps.briefs.models import DailyBrief
    from apps.content.models import Post
    from apps.platforms.models import SocialAccount

    progress = get_onboarding_progress(request.user)
    today = timezone.now().date()
    brief = DailyBrief.objects.filter(user=request.user, date=today).first()
    posts_ready = Post.objects.filter(
        user=request.user,
        status__in=[Post.Status.PENDING_APPROVAL, Post.Status.DRAFT],
    ).count()
    has_platforms = SocialAccount.objects.filter(
        user=request.user, is_active=True
    ).exists()

    return render(request, "accounts/_onboarding_progress.html", {
        "progress": progress,
        "brief": brief,
        "posts_ready": posts_ready,
        "has_platforms": has_platforms,
    })
