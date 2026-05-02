from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

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
            profile.record_onboarding_step("step_4_completed")

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
            profile.onboarding_intelligence_started_at = timezone.now()
            profile.save(update_fields=["onboarding_intelligence_started_at"])
            profile.record_onboarding_step("intelligence_started")
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
            profile.record_onboarding_step(f"step_{step}_completed")
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
@require_POST
def ai_brand_builder(request):
    """
    AI Brand Builder — generates brand voice, target audience, content pillars,
    tone attributes, and brand restrictions from minimal user input.

    Called via HTMX from onboarding Step 2. Returns JSON that populates the form.
    """
    import json
    import logging
    from apps.agents.llm import generate, _get_llm_config

    logger = logging.getLogger(__name__)

    # Pre-flight: ensure an LLM provider is actually configured
    config = _get_llm_config()
    has_config = config and config.pk
    if not has_config:
        from django.conf import settings as s
        provider = getattr(s, "DEFAULT_LLM_PROVIDER", "openai")
        has_key = bool(
            (provider == "openai" and getattr(s, "OPENAI_API_KEY", ""))
            or (provider == "anthropic" and getattr(s, "ANTHROPIC_API_KEY", ""))
            or (provider == "openrouter" and getattr(s, "OPENROUTER_API_KEY", ""))
        )
        if not has_key:
            logger.error("AI Brand Builder: no API key for provider '%s'", provider)
            return JsonResponse(
                {"error": f"AI is not configured yet — no API key for {provider}. Contact support."},
                status=503,
            )

    profile = request.user.profile

    # Collect context from Step 1 data + user hint
    company_name = profile.company_name or "my business"
    industry = profile.get_industry_display() if profile.industry else "general"
    website = profile.website_url or ""
    offerings = ", ".join(profile.key_offerings) if profile.key_offerings else ""
    hint = request.POST.get("hint", "").strip()
    language = profile.get_content_language_display() if profile.content_language else "English"

    system_prompt = (
        "You are a brand strategist helping a business define their social media voice and identity. "
        "Analyze the information provided and generate a complete brand identity profile. "
        "Be specific, actionable, and tailored — never generic. "
        f"The primary content language is {language}. Tailor tone advice accordingly.\n\n"
        "Return ONLY valid JSON with these exact keys:\n"
        "{\n"
        '  "brand_voice": "2-4 sentence description of how the brand sounds on social media. '
        'Be vivid and specific — use analogies, describe the personality.",\n'
        '  "target_audience": "Specific demographic + psychographic description. '
        'Age range, location hints, interests, pain points, where they hang out online.",\n'
        '  "content_pillars": ["pillar 1", "pillar 2", "pillar 3", "pillar 4", "pillar 5"],\n'
        '  "tone_attributes": ["tone1", "tone2", "tone3"],\n'
        '  "brand_voice_examples": ["Example social media post 1", "Example post 2", "Example post 3"],\n'
        '  "brand_restrictions": "2-4 practical guardrails for what the AI should never do or say."\n'
        "}\n\n"
        "For tone_attributes, choose 3-5 from EXACTLY these values: "
        "confident, approachable, witty, professional, casual, bold, educational, "
        "inspirational, empathetic, authoritative, playful, minimalist.\n\n"
        "For content_pillars, suggest 4-6 specific, actionable topics relevant to this exact business — "
        "not generic marketing buzzwords.\n\n"
        "For brand_voice_examples, write 2-3 realistic sample social media posts that demonstrate "
        "the brand voice in action. Make them sound natural and platform-ready — not templated. "
        "Each should be a complete post (1-3 sentences) the brand could actually publish."
    )

    user_prompt_parts = [f"Business: {company_name}"]
    if industry != "general":
        user_prompt_parts.append(f"Industry: {industry}")
    if website:
        user_prompt_parts.append(f"Website: {website}")
    if offerings:
        user_prompt_parts.append(f"Products/Services: {offerings}")
    if hint:
        user_prompt_parts.append(f"Owner's description: {hint}")

    user_prompt = "\n".join(user_prompt_parts)

    from apps.billing.exceptions import PlanLimitExceeded

    try:
        response = generate(
            prompt=user_prompt,
            system=system_prompt,
            temperature=0.8,
            max_tokens=1024,
            json_mode=True,
            user=request.user,
        )

        if not response.content:
            return JsonResponse({"error": "AI returned an empty response. Try again."}, status=500)

        result = json.loads(response.content)

        # Validate tone_attributes are from allowed set
        allowed_tones = {
            "confident", "approachable", "witty", "professional", "casual",
            "bold", "educational", "inspirational", "empathetic",
            "authoritative", "playful", "minimalist",
        }
        result["tone_attributes"] = [
            t for t in result.get("tone_attributes", []) if t in allowed_tones
        ]

        return JsonResponse({
            "brand_voice": result.get("brand_voice", ""),
            "target_audience": result.get("target_audience", ""),
            "content_pillars": result.get("content_pillars", []),
            "tone_attributes": result.get("tone_attributes", []),
            "brand_voice_examples": result.get("brand_voice_examples", []),
            "brand_restrictions": result.get("brand_restrictions", ""),
        })

    except PlanLimitExceeded as e:
        # 402 Payment Required is the right semantic for "out of allowance".
        # Front-end can show the message verbatim plus an upgrade CTA.
        return JsonResponse(
            {
                "error": e.message,
                "error_type": "plan_limit",
                "limit_type": e.limit_type,
                "suggested_plan": e.suggested_plan,
                "upgrade_url": "/billing/pricing/",
            },
            status=402,
        )
    except json.JSONDecodeError:
        logger.warning("AI brand builder returned invalid JSON: %s", response.content[:200])
        return JsonResponse({"error": "AI returned invalid data. Try again."}, status=500)
    except Exception as e:
        logger.error("AI brand builder failed (%s): %s", type(e).__name__, e, exc_info=True)
        return JsonResponse({"error": f"AI error: {type(e).__name__}. Try again in a moment."}, status=500)


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

    # If everything is done, redirect to Content Studio where their posts are waiting
    if progress["all_done"] and request.GET.get("completed"):
        return redirect("content:studio")

    return render(request, "accounts/onboarding_complete.html", {
        "progress": progress,
        "brief": brief,
        "page_title": "Your AI Agency is Starting",
    })


@login_required
@require_POST
def onboarding_retry(request):
    """Re-dispatch the onboarding intelligence chain when the first run wedged.

    Clears stale in-flight AgentAction rows so get_onboarding_progress stops
    reporting them as "running" and resets the dispatch clock.
    """
    from apps.agents.models import AgentAction
    from apps.agents.onboarding_tasks import run_onboarding_intelligence
    from apps.utils import fire_task

    # Remove any non-terminal onboarding actions so the poll UI resets cleanly.
    AgentAction.objects.filter(
        user=request.user,
        action_type__startswith="onboarding_",
    ).exclude(
        status__in=[AgentAction.ActionStatus.COMPLETED, AgentAction.ActionStatus.FAILED],
    ).delete()

    profile = request.user.profile
    profile.onboarding_intelligence_started_at = timezone.now()
    profile.save(update_fields=["onboarding_intelligence_started_at"])
    profile.record_onboarding_step("intelligence_retried")

    fire_task(run_onboarding_intelligence, str(request.user.pk))
    messages.info(request, "Retrying — your AI agency is starting again.")
    return redirect("accounts:onboarding_complete")


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


@login_required
@require_POST
def toggle_emergency_pause(request):
    """
    Toggle the emergency pause — instantly halts or resumes all autonomous
    agent actions (publishing, strategist seeds, engage replies, media queue).
    """
    profile = request.user.profile
    profile.emergency_pause = not profile.emergency_pause
    profile.save(update_fields=["emergency_pause"])

    if profile.emergency_pause:
        messages.warning(request, "⚠️ Emergency pause ACTIVATED — all autonomous actions are halted.")
    else:
        messages.success(request, "✅ Emergency pause deactivated — agents are running again.")

    return redirect(request.META.get("HTTP_REFERER", "accounts:settings"))
