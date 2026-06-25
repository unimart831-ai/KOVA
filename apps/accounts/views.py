from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.accounts.facebook_oauth import start_facebook_platform_oauth

from apps.accounts.forms import (
    AutopilotSettingsForm,
    UserSettingsForm,
    BrandProfileForm,
    CTASettingsForm,
    OnboardingExpressStep1Form,
    PhoneCaptureForm,
)
from apps.billing.models import get_user_plan_limits
from apps.accounts.onboarding_flow import (
    SETUP_TOTAL_STEPS,
    apply_url_inference_to_profile,
    finish_onboarding,
    setup_step_for_wizard,
)


def _onboarding_setup_context(*, step=None, path_choice=False, complete=False):
    if path_choice:
        return {
            "setup_step": 1,
            "setup_total": SETUP_TOTAL_STEPS,
            "setup_label": "Hire your AI marketer",
        }
    if complete:
        return {
            "setup_step": SETUP_TOTAL_STEPS,
            "setup_total": SETUP_TOTAL_STEPS,
            "setup_label": "First results loading",
        }
    labels = {
        1: "About your business",
        2: "Confirm — looks good?",
    }
    return {
        "setup_step": setup_step_for_wizard(step),
        "setup_total": SETUP_TOTAL_STEPS,
        "setup_label": labels.get(step, ""),
    }


@login_required
def settings_view(request):
    """User settings page with two forms: account info + brand profile."""
    from apps.accounts.forms import PhotoroomBrandKitForm
    from apps.products.photoroom_brand_template import build_photoroom_brand_template

    profile = request.user.profile
    if request.method == "POST":
        user_form = UserSettingsForm(request.POST, request.FILES, instance=request.user)
        brand_form = BrandProfileForm(request.POST, instance=profile)
        brand_kit_form = PhotoroomBrandKitForm(request.POST, profile=profile)
        autopilot_form = AutopilotSettingsForm(
            request.POST, instance=profile, user=request.user,
        )
        if (
            user_form.is_valid()
            and brand_form.is_valid()
            and brand_kit_form.is_valid()
            and autopilot_form.is_valid()
        ):
            user_form.save()
            brand_form.save()
            brand_kit_form.save(profile)
            autopilot_form.save()
            messages.success(request, "Settings saved.")
            return redirect("accounts:settings")
    else:
        user_form = UserSettingsForm(instance=request.user)
        brand_form = BrandProfileForm(instance=profile)
        brand_kit_form = PhotoroomBrandKitForm(profile=profile)
        autopilot_form = AutopilotSettingsForm(instance=profile, user=request.user)

    brand_template = build_photoroom_brand_template(profile, request.user.pk)
    preview_bg = f"#{brand_template.studio_color_hex}"
    shadow_labels = dict(PhotoroomBrandKitForm.SHADOW_CHOICES)

    from apps.billing.enforcement import get_seed_usage

    seed_usage = get_seed_usage(request.user)

    return render(request, "accounts/settings.html", {
        "user_form": user_form,
        "brand_form": brand_form,
        "brand_kit_form": brand_kit_form,
        "autopilot_form": autopilot_form,
        "brand_kit_preview": {
            "bg_color": preview_bg,
            "shadow_mode": brand_template.shadow_mode,
            "shadow_label": shadow_labels.get(brand_template.shadow_mode, "Soft shadow"),
            "padding": brand_template.padding,
            "enabled": brand_template.enabled,
        },
        "plan_limits": get_user_plan_limits(request.user),
        "seed_usage": seed_usage,
        "page_title": "Settings",
        "business_model": getattr(profile, "business_model", ""),
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


def _user_has_phone(user) -> bool:
    return bool((getattr(user, "phone_number", "") or "").strip())


def _redirect_if_phone_required(user):
    if not _user_has_phone(user):
        return redirect("accounts:collect_phone")
    return None


def _is_facebook_phone_only_signup(user) -> bool:
    from apps.accounts.facebook_oauth import is_facebook_synthetic_email

    return is_facebook_synthetic_email(getattr(user, "email", ""))


def _looks_like_social_profile_url(value: str) -> bool:
    value = (value or "").strip().lower()
    if not value:
        return False
    social_hosts = (
        "instagram.com",
        "facebook.com",
        "fb.com",
        "linkedin.com",
        "x.com",
        "twitter.com",
        "tiktok.com",
        "youtube.com",
        "youtu.be",
        "threads.net",
    )
    return any(host in value for host in social_hosts)


@login_required
def collect_phone(request):
    """Required for OAuth signups — email signup collects phone on the form."""
    if _user_has_phone(request.user):
        return redirect("accounts:onboarding_choose_path")

    if request.method == "POST":
        form = PhoneCaptureForm(request.POST)
        if form.is_valid():
            from apps.accounts.phone_utils import apply_phone_to_user

            apply_phone_to_user(request.user, form.cleaned_data["phone_number"])
            request.user.profile.record_onboarding_step("phone_collected")
            messages.success(request, "Thanks — we'll use this number for updates and support.")
            return redirect("accounts:onboarding_choose_path")
    else:
        form = PhoneCaptureForm()

    return render(request, "accounts/collect_phone.html", {
        "form": form,
        "page_title": "Your phone number",
        "facebook_phone_signup": _is_facebook_phone_only_signup(request.user),
    })


@login_required
def onboarding_choose_path(request):
    """Hire Kova — business type + goal in one conversational screen."""
    phone_redirect = _redirect_if_phone_required(request.user)
    if phone_redirect:
        return phone_redirect

    from apps.accounts.onboarding_discovery import (
        BUSINESS_TYPE_PRESETS,
        GOAL_OPTIONS,
        apply_business_type,
        apply_goal_choice,
        get_business_type_preset,
    )

    profile = request.user.profile
    if (profile.company_name or "").strip() and profile.industry:
        return redirect("/accounts/onboarding/?step=2")

    # If user already has platforms auto-connected from social sign-up,
    # skip path choice and go straight to magic-connect (shows connected state).
    from apps.platforms.models import SocialAccount
    auto_connected = SocialAccount.objects.filter(
        user=request.user, is_active=True, metadata__auto_connected=True,
    ).exists()
    if auto_connected and request.method == "GET":
        return redirect("accounts:onboarding_magic_connect")

    if request.method == "POST":
        from apps.accounts.onboarding_express import (
            VALID_BUSINESS_MODELS,
            VALID_INTENTS,
            BUSINESS_MODEL_PRODUCT,
            BUSINESS_MODEL_SERVICE,
            BUSINESS_MODEL_PROFESSIONAL,
            apply_business_model_defaults,
            ensure_brand_defaults,
            record_business_model,
            record_intent,
        )

        business_type = (request.POST.get("business_type") or "").strip()
        goal = (request.POST.get("goal") or "").strip()
        company_name = (request.POST.get("company_name") or "").strip()
        link = (request.POST.get("link") or "").strip()
        industry_override = (request.POST.get("industry") or "").strip()
        industry_other = (request.POST.get("industry_other") or "").strip()

        # ── New conversational flow (primary) ──
        if business_type:
            preset = get_business_type_preset(business_type)
            if not preset:
                messages.error(request, "Pick a business type to continue.")
                return redirect("accounts:onboarding_choose_path")

            if not company_name:
                messages.error(request, "What should we call your business?")
                return redirect("accounts:onboarding_choose_path")

            if business_type == "other" and not industry_override:
                messages.error(request, "Pick your industry to continue.")
                return redirect("accounts:onboarding_choose_path")

            apply_business_type(
                profile,
                preset,
                company_name=company_name,
                industry=industry_override,
                industry_other=industry_other,
            )
            if goal:
                apply_goal_choice(profile, goal)
            if preset.get("business_model"):
                record_business_model(profile, preset["business_model"])
            apply_business_model_defaults(profile, request.user)
            ensure_brand_defaults(profile, request.user)
            profile.record_onboarding_step("discovery_completed")

            if link:
                if _looks_like_social_profile_url(link):
                    messages.info(
                        request,
                        "Connect that profile directly — we'll pull your brand details automatically.",
                    )
                    return redirect("accounts:onboarding_magic_connect")
                profile.website_url = link
                profile.save(update_fields=["website_url"])
                request.session["onboarding_express_link"] = link

            return redirect("/accounts/onboarding/?step=2")

        # ── Legacy express paths (tests + deep links) ──
        business_model = (request.POST.get("business_model") or "").strip()
        intent = (request.POST.get("intent") or "").strip()

        if business_model in VALID_BUSINESS_MODELS:
            record_business_model(profile, business_model)
            apply_business_model_defaults(profile, request.user)
        elif intent in VALID_INTENTS:
            record_intent(profile, intent)

        if link:
            if _looks_like_social_profile_url(link):
                messages.info(
                    request,
                    "That looks like a social profile. Connect it directly for the smoothest auto-fill.",
                )
                return redirect("accounts:onboarding_magic_connect")
            request.session["onboarding_express_link"] = link
            return redirect("/accounts/onboarding/?step=1&via=url")

        if business_model == BUSINESS_MODEL_PRODUCT:
            return redirect("/accounts/onboarding/?step=1&via=sell")
        if business_model == BUSINESS_MODEL_SERVICE:
            return redirect("/accounts/onboarding/?step=1&via=service")
        if business_model == BUSINESS_MODEL_PROFESSIONAL:
            return redirect("accounts:onboarding_magic_connect")
        if intent == "sell":
            return redirect("/accounts/onboarding/?step=1&via=sell")
        if intent in ("grow", "both"):
            return redirect("accounts:onboarding_magic_connect")
        return redirect("/accounts/onboarding/?step=1&via=manual")

    business_hint = (request.session.pop("onboarding_business_hint", "") or "").strip()[:280]

    from apps.accounts.models import UserProfile

    return render(request, "accounts/onboarding_choose_path.html", {
        "page_title": "Welcome to Kova",
        "business_hint": business_hint,
        "business_types": BUSINESS_TYPE_PRESETS,
        "goal_options": GOAL_OPTIONS,
        "industry_choices": UserProfile.Industry.choices,
        **_onboarding_setup_context(path_choice=True),
    })


@login_required
def onboarding_magic_connect(request):
    """Magic-Fill platform grid — connect a social account so we can auto-fill."""
    phone_redirect = _redirect_if_phone_required(request.user)
    if phone_redirect:
        return phone_redirect

    request.session["onboarding_magic_fill"] = True
    request.user.profile.record_onboarding_step("path_choice_magic")

    from apps.platforms.models import SocialAccount
    connected = SocialAccount.objects.filter(user=request.user, is_active=True)

    # If platforms were auto-connected from social sign-up and user clicks
    # "Continue", skip directly to step 1 so they can confirm brand details.
    if request.GET.get("auto_advance") and connected.exists():
        return redirect("/accounts/onboarding/?step=1&via=url")

    return render(request, "accounts/onboarding_magic_connect.html", {
        "page_title": "Connect to auto-fill your brand",
        "connected_accounts": connected,
        "has_auto_connected": connected.filter(metadata__auto_connected=True).exists(),
        **_onboarding_setup_context(path_choice=True),
    })


@login_required
def onboarding_view(request):
    """Express onboarding — Step 1 basics, Step 2 preview + confirm."""
    from apps.accounts.brand_preview import build_brand_preview
    from apps.accounts.onboarding_express import ensure_brand_defaults
    from apps.platforms.models import SocialAccount

    profile = request.user.profile

    phone_redirect = _redirect_if_phone_required(request.user)
    if phone_redirect:
        return phone_redirect

    if "step" not in request.GET:
        if not (profile.company_name or profile.industry):
            return redirect("accounts:onboarding_choose_path")

    # Magic-Fill handoff — OAuth callback lands on step=2 with session flag set.
    if request.session.get("onboarding_magic_fill"):
        latest = (
            SocialAccount.objects.filter(user=request.user, is_active=True)
            .order_by("-updated_at")
            .first()
        )
        if latest:
            from apps.accounts.magic_fill import apply_magic_fill

            try:
                applied = apply_magic_fill(request.user, latest)
            except Exception as exc:
                import logging

                logging.getLogger(__name__).exception(
                    "Magic Fill failed for %s: %s", request.user.email, exc
                )
                applied = []
            request.session.pop("onboarding_magic_fill", None)
            if applied:
                messages.success(
                    request,
                    f"We've pre-filled {len(applied)} fields from your "
                    f"{latest.get_platform_display()} profile. Confirm on the next screen.",
                )
            else:
                messages.info(
                    request,
                    "We couldn't pull much from your profile — confirm your details below.",
                )
            if not (profile.company_name or "").strip():
                return redirect("/accounts/onboarding/?step=1")
            return redirect("/accounts/onboarding/?step=2")
        request.session.pop("onboarding_magic_fill", None)

    step = int(request.GET.get("step", 1))
    total_steps = 2

    if step > total_steps:
        return redirect(f"/accounts/onboarding/?step={total_steps}")

    via = request.GET.get("via")
    if via in ("url", "manual", "sell"):
        marker = "path_choice_sell" if via == "sell" else f"path_choice_{via}"
        if not (profile.onboarding_step_timestamps or {}).get(marker):
            profile.record_onboarding_step(marker)

    if step == 1:
        express_link = request.session.pop("onboarding_express_link", None)
        if express_link and request.method == "GET" and _looks_like_social_profile_url(express_link):
            messages.info(
                request,
                "That link looks social-first. Connect the platform directly and we'll pull cleaner brand details.",
            )
            return redirect("accounts:onboarding_magic_connect")
        if express_link and request.method == "GET" and not (profile.website_url or "").strip():
            profile.website_url = express_link
            profile.save(update_fields=["website_url"])

        form_class = OnboardingExpressStep1Form
        extra_kwargs = {"user": request.user}

        if request.method == "POST":
            form = form_class(request.POST, instance=profile, **extra_kwargs)
            if form.is_valid():
                form.save()
                profile.record_onboarding_step("step_1_completed")
                ensure_brand_defaults(profile, request.user)
                applied = getattr(form, "applied_pack_fields", None)
                if applied:
                    messages.info(
                        request,
                        f"We've pre-filled {len(applied)} brand defaults for your industry.",
                    )
                return redirect("/accounts/onboarding/?step=2")
        else:
            form = form_class(instance=profile, **extra_kwargs)

        return render(request, "accounts/onboarding.html", {
            "form": form,
            "step": step,
            "total_steps": total_steps,
            "page_title": "About your business",
            "prefill_url": express_link or (profile.website_url or ""),
            "phone_on_file": bool((request.user.phone_number or "").strip()),
            **_onboarding_setup_context(step=step),
        })

    if step == 2:
        if not (profile.company_name or "").strip() or not profile.industry:
            return redirect("/accounts/onboarding/?step=1")

        ensure_brand_defaults(profile, request.user)
        brand_preview = build_brand_preview(profile, request.user)

        if request.method == "POST":
            profile.record_onboarding_step("step_2_completed")
            profile.record_onboarding_step("step_3_completed")

            has_platform = SocialAccount.objects.filter(
                user=request.user, is_active=True
            ).exists()
            finish_onboarding(
                request.user,
                skipped_platform_connect=not has_platform,
            )
            messages.success(
                request,
                "Welcome to Kova! Your AI agency is analyzing your industry now.",
            )
            return redirect("accounts:onboarding_complete")

        return render(request, "accounts/onboarding.html", {
            "step": step,
            "total_steps": total_steps,
            "brand_preview": brand_preview,
            "page_title": "Confirm your brand",
            **_onboarding_setup_context(step=step),
        })

    return redirect("/accounts/onboarding/?step=1")


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
    from apps.agents.llm import generate, parse_llm_json, _get_llm_config

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

        try:
            result = parse_llm_json(response.content)
        except json.JSONDecodeError:
            retry_resp = generate(
                prompt=user_prompt + "\n\nReturn ONLY valid JSON, no markdown fences or explanation.",
                system=system_prompt,
                temperature=0.4,
                max_tokens=1024,
                json_mode=True,
                user=request.user,
            )
            result = parse_llm_json(retry_resp.content) if retry_resp.content else json.loads("")

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
@require_POST
def infer_brand_from_url(request):
    """Fetch a public URL, infer brand attributes via LLM, return as JSON.

    HTMX-friendly endpoint called from Step 1 when the user pastes a website
    URL and clicks "Auto-fill from this URL." The view:

      1. Validates the URL (must be http/https).
      2. Fetches the page with a tight timeout and 1 MB cap.
      3. Strips HTML to title + meta description + visible text (truncated).
      4. Calls the LLM with a JSON-mode prompt that maps content to our
         Industry choices + voice/audience/pillars/offerings.
      5. Returns a JSON dict that the front-end pours into form fields.

    No fields are overwritten server-side if the user already edited them — the
    user reviews and submits the Step 1 form normally. Voice/audience/pillars
    are also persisted to the profile (empty fields only) so Step 2 is pre-filled.
    """
    import json
    import logging
    import re
    import urllib.parse

    import requests

    from apps.agents.llm import generate, parse_llm_json, _get_llm_config
    from apps.accounts.models import UserProfile
    from apps.billing.exceptions import PlanLimitExceeded

    logger = logging.getLogger(__name__)

    url = (request.POST.get("url") or "").strip()
    if not url:
        return JsonResponse({"error": "Paste a URL first."}, status=400)

    # Accept bare domains — prepend https:// if scheme missing.
    parsed = urllib.parse.urlparse(url)
    if not parsed.scheme:
        url = "https://" + url
        parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return JsonResponse({"error": "That URL doesn't look right."}, status=400)

    if _looks_like_social_profile_url(url):
        return JsonResponse(
            {
                "error": "That link looks like a social profile. Connect the platform directly for the best auto-fill.",
                "error_type": "social_profile",
                "redirect_url": "/accounts/onboarding/magic/",
            },
            status=400,
        )

    # ── SSRF protection — block private/reserved IPs ─────────────
    from apps.utils.url_safety import validate_url_for_ssrf

    ssrf_error = validate_url_for_ssrf(url)
    if ssrf_error:
        return JsonResponse({"error": ssrf_error}, status=400)

    # Pre-flight: ensure an LLM provider is configured.
    config = _get_llm_config()
    if not (config and config.pk):
        from django.conf import settings as s
        provider = getattr(s, "DEFAULT_LLM_PROVIDER", "openai")
        has_key = bool(
            (provider == "openai" and getattr(s, "OPENAI_API_KEY", ""))
            or (provider == "anthropic" and getattr(s, "ANTHROPIC_API_KEY", ""))
            or (provider == "openrouter" and getattr(s, "OPENROUTER_API_KEY", ""))
        )
        if not has_key:
            return JsonResponse(
                {"error": f"AI isn't configured ({provider}). Contact support."},
                status=503,
            )

    # ── Fetch the page with strict caps ──────────────────────────────
    try:
        resp = requests.get(
            url,
            timeout=8,
            headers={"User-Agent": "KovaBot/1.0 (+https://kova.ai)"},
            allow_redirects=True,
            stream=True,
        )
        resp.raise_for_status()
        # Cap at 1 MB so a giant page can't OOM us.
        raw = resp.raw.read(1024 * 1024, decode_content=True)
        html = raw.decode(resp.encoding or "utf-8", errors="replace")
    except requests.Timeout:
        return JsonResponse({"error": "That site took too long to respond."}, status=504)
    except requests.RequestException as exc:
        logger.info("URL inference fetch failed for %s: %s", url, exc)
        return JsonResponse(
            {"error": "Couldn't reach that site. Check the URL and try again."},
            status=502,
        )

    # ── Extract a compact text representation for the LLM ────────────
    def _meta(name: str, *, prop: bool = False) -> str:
        pattern = (
            rf'<meta\s+[^>]*?property=["\']{re.escape(name)}["\'][^>]*?content=["\']([^"\']+)["\']'
            if prop else
            rf'<meta\s+[^>]*?name=["\']{re.escape(name)}["\'][^>]*?content=["\']([^"\']+)["\']'
        )
        m = re.search(pattern, html, flags=re.IGNORECASE)
        return m.group(1).strip() if m else ""

    title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, flags=re.IGNORECASE)
    title = (title_match.group(1).strip() if title_match else "")
    og_title = _meta("og:title", prop=True)
    og_description = _meta("og:description", prop=True)
    og_site_name = _meta("og:site_name", prop=True)
    meta_description = _meta("description")
    h1_match = re.search(r"<h1[^>]*>([^<]+)</h1>", html, flags=re.IGNORECASE)
    h1 = (h1_match.group(1).strip() if h1_match else "")

    # Strip tags for body content, truncate aggressively.
    text_only = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    text_only = re.sub(r"<[^>]+>", " ", text_only)
    text_only = re.sub(r"\s+", " ", text_only).strip()
    body_excerpt = text_only[:4000]

    # ── LLM inference ────────────────────────────────────────────────
    industry_choices = ", ".join(
        f'"{value}" ({label})' for value, label in UserProfile.Industry.choices
    )

    system_prompt = (
        "You are a brand strategist analysing a business website for an onboarding "
        "tool. From the page content below, infer the business's brand profile. "
        "Be specific. Prefer evidence from the page over generic guesses. "
        "If the page is too thin to infer a field confidently, return an empty "
        "string or empty list for that field — DO NOT fabricate.\n\n"
        f"Industry MUST be one of these exact values: {industry_choices}.\n\n"
        "Tone attributes MUST be from this set (pick 3-4): confident, approachable, "
        "witty, professional, casual, bold, educational, inspirational, empathetic, "
        "authoritative, playful, minimalist.\n\n"
        "Respond with valid JSON only:\n"
        "{\n"
        '  "company_name": "...",\n'
        '  "industry": "one_of_the_values_above_or_empty",\n'
        '  "brand_voice": "2-3 sentences describing how the brand sounds",\n'
        '  "target_audience": "specific demographic + psychographic description",\n'
        '  "content_pillars": ["pillar 1", "pillar 2", "pillar 3", "pillar 4"],\n'
        '  "tone_attributes": ["tone1", "tone2", "tone3"],\n'
        '  "key_offerings": ["product or service 1", "product or service 2"]\n'
        "}"
    )

    user_prompt = (
        f"URL: {url}\n"
        f"Title: {title}\n"
        f"og:title: {og_title}\n"
        f"og:site_name: {og_site_name}\n"
        f"og:description: {og_description}\n"
        f"meta description: {meta_description}\n"
        f"H1: {h1}\n\n"
        f"Page text (truncated):\n{body_excerpt}"
    )

    try:
        response = generate(
            prompt=user_prompt,
            system=system_prompt,
            temperature=0.4,
            max_tokens=1024,
            json_mode=True,
            user=request.user,
        )
        if not response.content:
            return JsonResponse({"error": "AI couldn't read that page."}, status=502)

        try:
            result = parse_llm_json(response.content)
        except json.JSONDecodeError:
            retry_resp = generate(
                prompt=user_prompt + "\n\nReturn ONLY valid JSON, no markdown fences or explanation.",
                system=system_prompt,
                temperature=0.3,
                max_tokens=1024,
                json_mode=True,
                user=request.user,
            )
            result = parse_llm_json(retry_resp.content) if retry_resp.content else json.loads("")

        # Validate industry against choices
        valid_industries = {v for v, _ in UserProfile.Industry.choices}
        if result.get("industry") not in valid_industries:
            result["industry"] = ""

        # Validate tone_attributes
        allowed_tones = {
            "confident", "approachable", "witty", "professional", "casual",
            "bold", "educational", "inspirational", "empathetic",
            "authoritative", "playful", "minimalist",
        }
        result["tone_attributes"] = [
            t for t in result.get("tone_attributes", []) if t in allowed_tones
        ]

        # Persist inferred voice/audience onto profile (empty fields only).
        profile = request.user.profile
        inference_payload = {
            "company_name": result.get("company_name", "") or "",
            "website_url": url,
            "industry": result.get("industry", "") or "",
            "brand_voice": result.get("brand_voice", "") or "",
            "target_audience": result.get("target_audience", "") or "",
            "content_pillars": result.get("content_pillars", []) or [],
            "tone_attributes": result.get("tone_attributes", []) or [],
            "key_offerings": result.get("key_offerings", []) or [],
        }
        apply_url_inference_to_profile(profile, inference_payload)

        # Funnel marker — counted in admin dashboard adoption metrics.
        try:
            request.user.profile.record_onboarding_step("url_inference_applied")
        except Exception:
            logger.exception("Failed to record url_inference_applied for %s", request.user.email)

        return JsonResponse({
            "company_name": result.get("company_name", "") or "",
            "industry": result.get("industry", "") or "",
            "brand_voice": result.get("brand_voice", "") or "",
            "target_audience": result.get("target_audience", "") or "",
            "content_pillars": result.get("content_pillars", []) or [],
            "tone_attributes": result.get("tone_attributes", []) or [],
            "key_offerings": result.get("key_offerings", []) or [],
            "website_url": url,
        })

    except PlanLimitExceeded as exc:
        return JsonResponse(
            {
                "error": exc.message,
                "error_type": "plan_limit",
                "limit_type": exc.limit_type,
                "suggested_plan": exc.suggested_plan,
                "upgrade_url": "/billing/pricing/",
            },
            status=402,
        )
    except json.JSONDecodeError:
        logger.warning("URL inference returned invalid JSON: %s", response.content[:200])
        return JsonResponse({"error": "AI returned an unexpected response. Try again."}, status=500)
    except Exception as exc:
        logger.error("URL inference failed (%s): %s", type(exc).__name__, exc, exc_info=True)
        return JsonResponse({"error": "AI error. Try again in a moment."}, status=500)


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
    from apps.accounts.setup_mission import (
        build_setup_mission,
        get_onboarding_intent,
        is_commerce_industry,
    )
    from apps.content.models import Post
    from apps.platforms.models import SocialAccount

    progress = get_onboarding_progress(request.user)
    today = timezone.now().date()
    brief = DailyBrief.objects.filter(user=request.user, date=today).first()
    profile = request.user.profile
    pending_posts = Post.objects.filter(
        user=request.user,
        status__in=[Post.Status.PENDING_APPROVAL, Post.Status.DRAFT],
    ).order_by("-created_at")
    posts_ready = pending_posts.count()
    preview_posts = list(pending_posts[:3])
    has_platforms = SocialAccount.objects.filter(
        user=request.user, is_active=True
    ).exists()
    setup_mission = build_setup_mission(request.user)
    progress_context = {
        "progress": progress,
        "brief": brief,
        "posts_ready": posts_ready,
        "preview_posts": preview_posts,
        "has_platforms": has_platforms,
        "is_commerce": is_commerce_industry(profile.industry),
        "onboarding_intent": get_onboarding_intent(profile),
        "setup_mission": setup_mission,
    }

    # If everything is done, redirect to the best first-value screen
    if progress["all_done"] and request.GET.get("completed"):
        from apps.accounts.onboarding_redirects import post_onboarding_redirect_url_name

        return redirect(post_onboarding_redirect_url_name(request.user))

    return render(request, "accounts/onboarding_complete.html", {
        **progress_context,
        "page_title": "Your AI Agency is Starting",
        **_onboarding_setup_context(complete=True),
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
    pending_posts = Post.objects.filter(
        user=request.user,
        status__in=[Post.Status.PENDING_APPROVAL, Post.Status.DRAFT],
    ).order_by("-created_at")
    posts_ready = pending_posts.count()
    preview_posts = list(pending_posts[:3])
    has_platforms = SocialAccount.objects.filter(
        user=request.user, is_active=True
    ).exists()
    from apps.accounts.setup_mission import build_setup_mission, is_commerce_industry, get_onboarding_intent

    profile = request.user.profile

    return render(request, "accounts/_onboarding_progress.html", {
        "progress": progress,
        "brief": brief,
        "posts_ready": posts_ready,
        "preview_posts": preview_posts,
        "has_platforms": has_platforms,
        "is_commerce": is_commerce_industry(profile.industry),
        "onboarding_intent": get_onboarding_intent(profile),
        "setup_mission": build_setup_mission(request.user),
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

    return redirect(request.META.get("HTTP_REFERER") or reverse("accounts:settings"))


# ── AI Learning — Adapt Agent v2 controls (W3 Commit 4) ────────────────────
#
# The settings page that lets a user see what Adapt v2 has learned about
# their business, revert individual mutations, pause the loop entirely,
# or wipe all mutations and start fresh.
#
# Reads AgentAction rows with agent_type="adapt" — the same audit trail
# that the dry-run / live cycle writes in apps/agents/adapt_agent.py.
# Reversal is just applying the inverse of output_data["before"/"after"]
# back to UserProfile, then marking the AgentAction as reverted.


@login_required
def ai_learning_view(request):
    """List recent Adapt Agent mutations with revert / pause / reset UI."""
    from apps.agents.models import AgentAction

    actions = list(
        AgentAction.objects.filter(
            user=request.user, agent_type="adapt",
        ).order_by("-created_at")[:50]
    )

    # Annotate each action with a human-readable description for the table
    annotated = []
    for a in actions:
        annotated.append({
            "obj": a,
            "title": _adapt_action_title(a),
            "evidence": _adapt_action_evidence(a),
            "is_reverted": "reverted" in (a.input_data or {}),
        })

    return render(request, "accounts/ai_learning.html", {
        "actions": annotated,
        "profile": request.user.profile,
        "page_title": "AI Learning",
    })


def _adapt_action_title(action):
    """Human-readable headline for an adapt AgentAction row."""
    t = action.action_type
    inp = action.input_data or {}
    out = action.output_data or {}
    if t == "promote_dna":
        combo = inp.get("combo") or out.get("after_appends", {}).get("combo", {})
        descriptor = ", ".join(f"{k}={v}" for k, v in combo.items() if v)
        return f"Promoted pattern: {descriptor}"
    if t == "retire_dna":
        combo = inp.get("combo") or out.get("after_appends", {}).get("combo", {})
        descriptor = ", ".join(f"{k}={v}" for k, v in combo.items() if v)
        return f"Retired pattern: {descriptor}"
    if t == "reweight_pillar":
        pillar = inp.get("pillar", "")
        before = out.get("before", 1.0)
        after = out.get("after", 1.0)
        return f"Pillar reweight: {pillar} ({before} → {after})"
    if t == "adjust_frequency":
        before = out.get("before")
        after = out.get("after")
        return f"Posting frequency: {before} → {after} posts/week"
    if t == "shift_schedule":
        plat = inp.get("platform", "")
        return f"Optimal posting hours updated for {plat}"
    return t.replace("_", " ").title()


def _adapt_action_evidence(action):
    """Short evidence string explaining why this mutation fired."""
    inp = action.input_data or {}
    ratio = inp.get("ratio")
    sample = inp.get("sample_size")
    bits = []
    if isinstance(ratio, (int, float)):
        bits.append(f"{ratio:.1f}× median engagement")
    if isinstance(sample, int):
        bits.append(f"{sample} post{'s' if sample != 1 else ''}")
    return " · ".join(bits) if bits else ""


@login_required
@require_POST
def ai_learning_revert(request, action_id):
    """Revert a single Adapt mutation.

    Inverts the output_data["before"]/["after"] for in-place fields, or
    removes the appended item for append-style fields (promote_dna,
    retire_dna).
    """
    from apps.agents.models import AgentAction
    from django.shortcuts import get_object_or_404

    action = get_object_or_404(
        AgentAction, pk=action_id, user=request.user, agent_type="adapt",
    )
    if "reverted" in (action.input_data or {}):
        messages.info(request, "Already reverted.")
        return redirect("accounts:ai_learning")

    profile = request.user.profile
    out = action.output_data or {}
    t = action.action_type

    try:
        if t == "promote_dna":
            # Remove the appended item from dna_preferences.promoted
            appended = out.get("after_appends") or {}
            prefs = profile.dna_preferences or {}
            promoted = prefs.get("promoted") or []
            prefs["promoted"] = [
                p for p in promoted
                if p.get("combo") != appended.get("combo")
            ]
            profile.dna_preferences = prefs
            profile.save(update_fields=["dna_preferences", "updated_at"])

        elif t == "retire_dna":
            appended = out.get("after_appends") or {}
            prefs = profile.dna_preferences or {}
            retired = prefs.get("retired") or []
            prefs["retired"] = [
                r for r in retired
                if r.get("combo") != appended.get("combo")
            ]
            profile.dna_preferences = prefs
            profile.save(update_fields=["dna_preferences", "updated_at"])

        elif t == "reweight_pillar":
            pillar = (action.input_data or {}).get("pillar")
            before = out.get("before")
            weights = dict(profile.pillar_weights or {})
            if pillar and before is not None:
                weights[pillar] = before
                profile.pillar_weights = weights
                profile.save(update_fields=["pillar_weights", "updated_at"])

        elif t == "adjust_frequency":
            before = out.get("before")
            if before is not None:
                profile.posting_frequency = before
                profile.save(update_fields=["posting_frequency", "updated_at"])

        elif t == "shift_schedule":
            plat = (action.input_data or {}).get("platform")
            before = out.get("before")
            if plat is not None:
                schedule = dict(profile.optimal_schedule or {})
                if before:
                    schedule[plat] = before
                else:
                    schedule.pop(plat, None)
                profile.optimal_schedule = schedule
                profile.save(update_fields=["optimal_schedule", "updated_at"])

        # Mark this action as reverted in its own input_data
        action.input_data = {
            **(action.input_data or {}),
            "reverted": True,
            "reverted_at": timezone.now().isoformat(),
        }
        action.save(update_fields=["input_data"])
        messages.success(request, "Reverted that change.")
    except Exception as exc:
        messages.error(request, f"Couldn't revert: {exc}")

    return redirect("accounts:ai_learning")


@login_required
@require_POST
def ai_learning_toggle_pause(request):
    """Flip adapt_paused on the user's profile. Pausing stops future
    cycles but keeps everything Adapt has already learned in place."""
    profile = request.user.profile
    profile.adapt_paused = not profile.adapt_paused
    profile.save(update_fields=["adapt_paused", "updated_at"])
    if profile.adapt_paused:
        messages.success(request, "⏸ AI Learning paused. Adapt won't change your settings until you resume.")
    else:
        messages.success(request, "▶ AI Learning resumed. Adapt will start learning again on the next 12h cycle.")
    return redirect("accounts:ai_learning")


@login_required
@require_POST
def ai_learning_reset(request):
    """Revert every non-reverted Adapt mutation in reverse chronological
    order. Returns the profile to its post-onboarding state for the
    fields Adapt manages."""
    from apps.agents.models import AgentAction

    pending = AgentAction.objects.filter(
        user=request.user, agent_type="adapt",
    ).order_by("-created_at")

    reverted_count = 0
    for action in pending:
        if "reverted" in (action.input_data or {}):
            continue
        # Re-use the single-revert logic by faking a request flow. To
        # keep this simple and predictable, inline a minimal revert:
        out = action.output_data or {}
        profile = request.user.profile
        try:
            t = action.action_type
            if t in ("promote_dna", "retire_dna"):
                appended = out.get("after_appends") or {}
                key = "promoted" if t == "promote_dna" else "retired"
                prefs = profile.dna_preferences or {}
                current = prefs.get(key) or []
                prefs[key] = [c for c in current if c.get("combo") != appended.get("combo")]
                profile.dna_preferences = prefs
                profile.save(update_fields=["dna_preferences", "updated_at"])
            elif t == "reweight_pillar":
                pillar = (action.input_data or {}).get("pillar")
                before = out.get("before")
                if pillar and before is not None:
                    weights = dict(profile.pillar_weights or {})
                    weights[pillar] = before
                    profile.pillar_weights = weights
                    profile.save(update_fields=["pillar_weights", "updated_at"])
            elif t == "adjust_frequency":
                before = out.get("before")
                if before is not None:
                    profile.posting_frequency = before
                    profile.save(update_fields=["posting_frequency", "updated_at"])
            elif t == "shift_schedule":
                plat = (action.input_data or {}).get("platform")
                before = out.get("before")
                if plat is not None:
                    schedule = dict(profile.optimal_schedule or {})
                    if before:
                        schedule[plat] = before
                    else:
                        schedule.pop(plat, None)
                    profile.optimal_schedule = schedule
                    profile.save(update_fields=["optimal_schedule", "updated_at"])
            action.input_data = {
                **(action.input_data or {}),
                "reverted": True,
                "reverted_at": timezone.now().isoformat(),
                "reverted_via": "global_reset",
            }
            action.save(update_fields=["input_data"])
            reverted_count += 1
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Adapt reset: failed to revert action %s for %s", action.pk, request.user.email,
            )

    if reverted_count:
        messages.success(request, f"Reset complete — reverted {reverted_count} change(s).")
    else:
        messages.info(request, "Nothing to reset — no active Adapt mutations.")
    return redirect("accounts:ai_learning")


@ratelimit(key="ip", rate="20/m", block=True)
def facebook_signup_connect(request):
    """
    Start Facebook OAuth with full publishing scopes for new sign-ups.

    Skips django-allauth's intermediate page; callback is /platforms/callback/facebook/.
    """
    return start_facebook_platform_oauth(request, mode="signup")


@ratelimit(key="ip", rate="20/m", block=True)
def facebook_login_connect(request):
    """Start Facebook OAuth for returning users (platform scopes + auto-connect)."""
    return start_facebook_platform_oauth(request, mode="login")

