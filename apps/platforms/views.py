import logging
import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.accounts.facebook_oauth import (
    FacebookOAuthError,
    log_facebook_oauth_callback,
    login_user_from_facebook_oauth,
    peek_facebook_oauth_mode,
    persist_facebook_platform_account,
    redirect_facebook_oauth_failure,
    resolve_user_from_facebook_result,
    validate_facebook_callback_state,
)
from apps.platforms.models import SocialAccount
from apps.platforms.providers.registry import get_provider

logger = logging.getLogger(__name__)

# Platforms active for new connections. Providers, model choices, and DB records
# for other platforms are preserved — they are simply not exposed in the UI yet.
# Add a platform here when its OAuth app is approved and tested end-to-end.
# Kova supports Facebook, Instagram, TikTok, LinkedIn + WhatsApp to close.
ACTIVE_PLATFORMS = [
    {
        "key": "whatsapp",
        "label": "WhatsApp",
        "icon": '<svg class="w-7 h-7" viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>',
        "color": "text-[#25D366]",
        "description": "Close deals — inbox, templates, M-Pesa in chat",
    },
    {
        "key": "facebook",
        "label": "Facebook",
        "icon": '<svg class="w-7 h-7" viewBox="0 0 24 24" fill="currentColor"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>',
        "color": "text-[#1877F2]",
        "description": "Pages, organic posts, comments & leads",
    },
    {
        "key": "instagram",
        "label": "Instagram",
        "icon": '<svg class="w-7 h-7" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C8.74 0 8.333.015 7.053.072 5.775.132 4.905.333 4.14.63c-.789.306-1.459.717-2.126 1.384S.935 3.35.63 4.14C.333 4.905.131 5.775.072 7.053.012 8.333 0 8.74 0 12s.015 3.667.072 4.947c.06 1.277.261 2.148.558 2.913.306.788.717 1.459 1.384 2.126.667.666 1.336 1.079 2.126 1.384.766.296 1.636.499 2.913.558C8.333 23.988 8.74 24 12 24s3.667-.015 4.947-.072c1.277-.06 2.148-.262 2.913-.558.788-.306 1.459-.718 2.126-1.384.666-.667 1.079-1.335 1.384-2.126.296-.765.499-1.636.558-2.913.06-1.28.072-1.687.072-4.947s-.015-3.667-.072-4.947c-.06-1.277-.262-2.149-.558-2.913-.306-.789-.718-1.459-1.384-2.126C21.319 1.347 20.651.935 19.86.63c-.765-.297-1.636-.499-2.913-.558C15.667.012 15.26 0 12 0zm0 2.16c3.203 0 3.585.016 4.85.071 1.17.055 1.805.249 2.227.415.562.217.96.477 1.382.896.419.42.679.819.896 1.381.164.422.36 1.057.413 2.227.057 1.266.07 1.646.07 4.85s-.015 3.585-.074 4.85c-.061 1.17-.256 1.805-.421 2.227-.224.562-.479.96-.899 1.382-.419.419-.824.679-1.38.896-.42.164-1.065.36-2.235.413-1.274.057-1.649.07-4.859.07-3.211 0-3.586-.015-4.859-.074-1.171-.061-1.816-.256-2.236-.421-.569-.224-.96-.479-1.379-.899-.421-.419-.69-.824-.9-1.38-.165-.42-.359-1.065-.42-2.235-.045-1.26-.061-1.649-.061-4.844 0-3.196.016-3.586.061-4.861.061-1.17.255-1.814.42-2.234.21-.57.479-.96.9-1.381.419-.419.81-.689 1.379-.898.42-.166 1.051-.361 2.221-.421 1.275-.045 1.65-.06 4.859-.06l.045.03zm0 3.678a6.162 6.162 0 100 12.324 6.162 6.162 0 100-12.324zM12 16c-2.21 0-4-1.79-4-4s1.79-4 4-4 4 1.79 4 4-1.79 4-4 4zm7.846-10.405a1.441 1.441 0 11-2.88 0 1.441 1.441 0 012.88 0z"/></svg>',
        "color": "text-[#E4405F]",
        "description": "Reels, carousels, stories & DMs",
    },
    {
        "key": "tiktok",
        "label": "TikTok",
        "icon": '<svg class="w-7 h-7" viewBox="0 0 24 24" fill="currentColor"><path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z"/></svg>',
        "color": "text-gray-900 dark:text-white",
        "description": "Short-form video, trending sounds & comments",
    },
    {
        "key": "linkedin",
        "label": "LinkedIn",
        "icon": '<svg class="w-7 h-7" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>',
        "color": "text-[#0A66C2]",
        "description": "B2B content, thought leadership & company pages",
    },
]

# Kova supports 5 channels: WhatsApp, Facebook, Instagram, TikTok, LinkedIn.
COMING_SOON_PLATFORMS = []

# Flat set used for filtering throughout the app (Create Agent, content forms, etc.)
ACTIVE_PLATFORM_KEYS = {p["key"] for p in ACTIVE_PLATFORMS}

# Keep backward-compat name — code that imports AVAILABLE_PLATFORMS still works
AVAILABLE_PLATFORMS = ACTIVE_PLATFORMS

# Wedge GTM priority: WhatsApp → Instagram → Facebook first on connect page
WEDGE_PLATFORM_ORDER = ("whatsapp", "instagram", "facebook")

PLATFORM_ORDER_BY_MODEL = {
    "product": ("whatsapp", "instagram", "facebook", "tiktok", "linkedin"),
    "service": ("whatsapp", "instagram", "facebook", "linkedin", "tiktok"),
    "professional": ("linkedin", "instagram", "facebook", "whatsapp", "tiktok"),
}

RECOMMENDED_BY_MODEL = {
    "product": frozenset({"whatsapp", "instagram", "facebook"}),
    "service": frozenset({"whatsapp", "instagram", "facebook"}),
    "professional": frozenset({"linkedin", "instagram"}),
}


def _sort_platforms_wedge_first(platforms: list[dict]) -> list[dict]:
    order = {key: idx for idx, key in enumerate(WEDGE_PLATFORM_ORDER)}
    return sorted(
        platforms,
        key=lambda p: (order.get(p["key"], 99), p["label"]),
    )


def _sort_platforms_for_model(platforms: list[dict], business_model: str) -> list[dict]:
    order = PLATFORM_ORDER_BY_MODEL.get(business_model, PLATFORM_ORDER_BY_MODEL["product"])
    order_map = {key: idx for idx, key in enumerate(order)}
    recommended = RECOMMENDED_BY_MODEL.get(business_model, RECOMMENDED_BY_MODEL["product"])
    enriched = []
    for p in platforms:
        enriched.append({**p, "recommended": p["key"] in recommended})
    return sorted(enriched, key=lambda p: (order_map.get(p["key"], 99), p["label"]))


@login_required
def platform_list(request):
    """Show connected platforms and connect buttons."""
    accounts = (
        request.user.social_accounts
        .defer("access_token", "refresh_token", "token_scope")
        .all()
    )
    connected_platforms = set(
        accounts.filter(is_active=True).values_list("platform", flat=True)
    )

    platforms = []
    for p in AVAILABLE_PLATFORMS:
        platforms.append({
            **p,
            "connected": p["key"] in connected_platforms,
            "provider_available": get_provider(p["key"]) is not None,
        })

    for acc in accounts:
        acc.profile_audit = None
        acc.profile_audit_gap_count = 0

    from apps.platforms.outage import get_outages
    platform_outages = {p: v for p, v in get_outages().items() if v}

    profile = request.user.profile
    business_model = getattr(profile, "business_model", "") or "product"
    active_count = accounts.filter(is_active=True).count()
    plan_limits = getattr(request, "plan_limits", None) or {}
    max_accounts = plan_limits.get("max_social_accounts")
    needs_reauth = sum(
        1 for acc in accounts
        if not acc.is_active or getattr(acc, "needs_reauth", False)
    )

    from apps.accounts.segments import build_surface_experience

    connected_list = list(connected_platforms)
    segment_surface = build_surface_experience(
        profile=profile,
        connected_platforms=connected_list,
    )

    sorted_platforms = _sort_platforms_for_model(platforms, business_model)

    return render(request, "platforms/list.html", {
        "accounts": accounts,
        "platforms": sorted_platforms,
        "coming_soon_platforms": COMING_SOON_PLATFORMS,
        "platform_outages": platform_outages,
        "page_title": "Platforms",
        "business_model": business_model,
        "segment_surface": segment_surface,
        "connected_count": active_count,
        "connected_platform_count": active_count,
        "accounts_limit": max_accounts,
        "at_account_limit": bool(max_accounts and active_count >= max_accounts),
        "needs_reauth_count": needs_reauth,
    })


@login_required
@ratelimit(key="user", rate="10/m", block=True)
def connect_platform(request, platform):
    """Start OAuth flow for a platform."""
    if platform not in ACTIVE_PLATFORM_KEYS:
        messages.error(request, f"{platform.title()} is not available yet. Stay tuned!")
        return redirect("platforms:list")

    provider = get_provider(platform)
    if not provider:
        messages.error(request, f"Platform '{platform}' is not available.")
        return redirect("platforms:list")

    # TikTok — require acknowledgment before OAuth (posts may be private until app audit)
    if platform == "tiktok" and request.GET.get("ack") != "1":
        return render(request, "platforms/tiktok_connect_notice.html", {
            "page_title": "Connect TikTok",
            "connect_url": (
                reverse("platforms:connect", kwargs={"platform": "tiktok"}) + "?ack=1"
            ),
        })

    # WhatsApp — Embedded Signup (primary) or manual token (fallback)
    if platform == "whatsapp":
        if request.method == "POST":
            access_token = request.POST.get("access_token", "").strip()
            phone_number_id = request.POST.get("phone_number_id", "").strip()
            waba_id = request.POST.get("waba_id", "").strip()
            if not access_token or not phone_number_id:
                messages.error(request, "Access token and Phone Number ID are required.")
                return redirect("platforms:list")
            try:
                result = provider.handle_callback(
                    code=access_token,
                    redirect_uri="",
                    phone_number_id=phone_number_id,
                    waba_id=waba_id,
                )
                SocialAccount.objects.update_or_create(
                    user=request.user,
                    platform="whatsapp",
                    platform_user_id=result.platform_user_id,
                    defaults={
                        "username": result.username,
                        "display_name": result.display_name,
                        "access_token": result.access_token,
                        "is_active": True,
                        "last_error": "",
                        "metadata": result.metadata,
                    },
                )
                messages.success(request, f"Connected WhatsApp — {result.display_name}")
            except Exception as exc:
                logger.error("WhatsApp connect failed: %s", exc, exc_info=True)
                messages.error(request, f"Failed to connect WhatsApp: {exc}")
            return redirect("platforms:list")
        return render(request, "platforms/whatsapp_connect.html", {
            "page_title": "Connect WhatsApp",
            "facebook_app_id": getattr(settings, "FACEBOOK_APP_ID", ""),
            "fb_wa_config_id": getattr(settings, "FB_WA_CONFIG_ID", ""),
            "embedded_signup_available": bool(
                getattr(settings, "FACEBOOK_APP_ID", "")
                and getattr(settings, "FACEBOOK_APP_SECRET", "")
                and getattr(settings, "FB_WA_CONFIG_ID", "")
            ),
        })

    # Generate and store a CSRF-like state token
    state = secrets.token_urlsafe(32)
    request.session[f"oauth_state_{platform}"] = state
    request.session[f"oauth_platform"] = platform

    redirect_uri = request.build_absolute_uri(
        reverse("platforms:oauth_callback", kwargs={"platform": platform})
    )
    auth_url = provider.get_auth_url(state=state, redirect_uri=redirect_uri)

    # Persist PKCE code_verifier in the session for providers that use it
    # (e.g. Twitter/X). The verifier is stashed on the provider instance by
    # get_auth_url() and must travel server-side, never in the URL.
    code_verifier = getattr(provider, "_pending_code_verifier", None)
    if code_verifier:
        request.session[f"oauth_code_verifier_{platform}"] = code_verifier
        provider._pending_code_verifier = None

    return redirect(auth_url)


@ratelimit(key="ip", rate="30/m", block=True)
def oauth_callback(request, platform):
    """Handle OAuth callback from a platform."""
    received_state = request.GET.get("state", "")
    facebook_auth_mode = request.session.get("oauth_facebook_mode")
    if not facebook_auth_mode and platform == "facebook":
        facebook_auth_mode = peek_facebook_oauth_mode(received_state)
    if not request.user.is_authenticated and not facebook_auth_mode:
        return redirect("account_login")

    provider = get_provider(platform)
    if not provider:
        messages.error(request, "Invalid platform.")
        return redirect("platforms:list" if request.user.is_authenticated else "account_login")

    # Verify state to prevent CSRF
    if platform == "facebook":
        facebook_auth_mode, state_error = validate_facebook_callback_state(
            request, received_state,
        )
        if state_error:
            log_facebook_oauth_callback(
                mode=facebook_auth_mode,
                success=False,
                error=state_error,
            )
            messages.error(request, state_error)
            return redirect_facebook_oauth_failure(
                request, facebook_auth_mode or peek_facebook_oauth_mode(received_state),
            )
    else:
        expected_state = request.session.pop(f"oauth_state_{platform}", None)
        if not expected_state or expected_state != received_state:
            messages.error(request, "Invalid OAuth state. Please try again.")
            return redirect("platforms:list")

    error = request.GET.get("error")
    if error:
        err_desc = request.GET.get("error_description", error)
        log_facebook_oauth_callback(
            mode=facebook_auth_mode,
            success=False,
            error=f"authorization_denied:{err_desc}",
        )
        messages.error(request, f"Authorization denied: {err_desc}")
        if facebook_auth_mode:
            return redirect_facebook_oauth_failure(request, facebook_auth_mode)
        return redirect("platforms:list")

    code = request.GET.get("code", "")
    if not code:
        log_facebook_oauth_callback(
            mode=facebook_auth_mode,
            success=False,
            error="missing_code",
        )
        messages.error(request, "No authorization code received.")
        if facebook_auth_mode:
            return redirect_facebook_oauth_failure(request, facebook_auth_mode)
        return redirect("platforms:list")

    redirect_uri = request.build_absolute_uri(
        reverse("platforms:oauth_callback", kwargs={"platform": platform})
    )

    try:
        result = provider.handle_callback(
            code=code,
            redirect_uri=redirect_uri,
            code_verifier=request.session.pop(f"oauth_code_verifier_{platform}", ""),
        )

        if facebook_auth_mode and platform == "facebook":
            email_present = bool((result.metadata.get("email") or "").strip())
            try:
                user, _created = resolve_user_from_facebook_result(result, facebook_auth_mode)
            except FacebookOAuthError as exc:
                log_facebook_oauth_callback(
                    mode=facebook_auth_mode,
                    success=False,
                    email_present=email_present,
                    error=str(exc),
                )
                messages.error(request, str(exc))
                return redirect_facebook_oauth_failure(request, facebook_auth_mode)

            login_user_from_facebook_oauth(request, user)
            account, created = persist_facebook_platform_account(
                user, result, auto_connected=True,
            )
            accounts_connected = SocialAccount.objects.filter(
                user=user, platform__in=("facebook", "instagram"), is_active=True,
            ).count()
            log_facebook_oauth_callback(
                mode=facebook_auth_mode,
                success=True,
                user_id=user.pk,
                email_present=email_present,
                accounts_connected=accounts_connected,
            )
            action = "connected" if created else "reconnected"
            messages.success(
                request,
                f"Successfully {action} {account.get_platform_display()} — @{account.username}",
            )

            pages = result.metadata.get("pages", [])
            if not pages:
                messages.warning(
                    request,
                    "Facebook connected, but no Pages were found on your account. "
                    "Kova publishes to Facebook Pages, not personal profiles. "
                    "Make sure you are an admin of at least one Facebook Page, "
                    "then reconnect and grant the 'Manage your Pages' permission."
                )
            elif len(pages) > 1:
                page_names = ", ".join(p["name"] for p in pages[:3])
                messages.info(
                    request,
                    f"Found {len(pages)} Facebook Pages ({page_names}). "
                    f"Kova is publishing to '{pages[0]['name']}' by default. "
                    "Contact support if you need to switch to a different Page."
                )

            if not user.onboarding_completed:
                if not (getattr(user, "phone_number", "") or "").strip():
                    return redirect("accounts:collect_phone")
                return redirect("accounts:onboarding_choose_path")
            return redirect("brief:home")

        # Create or update the SocialAccount
        # Determine account_type based on platform and metadata
        account_type = result.metadata.get("account_type", "personal")
        if platform == "facebook":
            account_type = "page"
        elif platform == "instagram":
            account_type = result.metadata.get("account_type", "business")
        elif platform == "linkedin":
            account_type = result.metadata.get("account_type", "personal")

        account, created = SocialAccount.objects.update_or_create(
            user=request.user,
            platform=platform,
            platform_user_id=result.platform_user_id,
            defaults={
                "username": result.username,
                "display_name": result.display_name,
                "avatar_url": result.avatar_url,
                "access_token": result.access_token,
                "refresh_token": result.refresh_token,
                "token_expires_at": result.token_expires_at,
                "token_scope": result.token_scope,
                "is_active": True,
                "last_error": "",
                "metadata": result.metadata,
                "account_type": account_type,
            },
        )
        action = "connected" if created else "reconnected"
        messages.success(request, f"Successfully {action} {account.get_platform_display()} — @{account.username}")

        if platform == "tiktok":
            try:
                snap = provider.audit_profile(result.access_token)
                meta = dict(account.metadata or {})
                if "privacy_level" in (snap.fields_thin or []):
                    meta["tiktok_self_only"] = True
                    account.metadata = meta
                    account.save(update_fields=["metadata", "updated_at"])
                    messages.warning(
                        request,
                        "TikTok connected. Until TikTok approves our app for public posting, "
                        "your videos publish as private (visible only to you). "
                        "Instagram and Facebook are recommended for public reach today.",
                    )
                else:
                    meta["tiktok_self_only"] = False
                    account.metadata = meta
                    account.save(update_fields=["metadata", "updated_at"])
            except Exception as exc:
                logger.warning("TikTok creator audit failed: %s", exc)

        # Facebook: preserve the user's previously selected Page across reconnects.
        # update_or_create overwrites metadata on every reconnect, which would
        # silently reset their page choice. We restore it here if the page
        # still exists in the new metadata.
        if platform == "facebook" and not created:
            prev_metadata = SocialAccount.objects.filter(
                user=request.user, platform="facebook",
                platform_user_id=result.platform_user_id,
            ).values_list("metadata", flat=True).first()
            if prev_metadata:
                prev_selected = (prev_metadata or {}).get("selected_page_id")
                new_pages = result.metadata.get("pages", [])
                if prev_selected and any(p["id"] == prev_selected for p in new_pages):
                    account.metadata["selected_page_id"] = prev_selected
                    account.save(update_fields=["metadata", "updated_at"])

        # Facebook: validate that at least one Page was fetched. Without a
        # Page, Kova cannot publish — surface a clear, actionable warning
        # immediately so the user knows what to do before their first post.
        if platform == "facebook":
            pages = result.metadata.get("pages", [])
            if not pages:
                messages.warning(
                    request,
                    "Facebook connected, but no Pages were found on your account. "
                    "Kova publishes to Facebook Pages, not personal profiles. "
                    "Make sure you are an admin of at least one Facebook Page, "
                    "then reconnect and grant the 'Manage your Pages' permission."
                )
            elif len(pages) > 1:
                page_names = ", ".join(p["name"] for p in pages[:3])
                messages.info(
                    request,
                    f"Found {len(pages)} Facebook Pages ({page_names}). "
                    f"Kova is publishing to '{pages[0]['name']}' by default. "
                    "Contact support if you need to switch to a different Page."
                )

        # If this was a LinkedIn org flow, redirect to page selection
        if platform == "linkedin" and request.session.pop("linkedin_org_flow", False):
            return redirect("platforms:linkedin_select_page")

    except Exception as exc:
        logger.error("OAuth callback failed for %s: %s", platform, exc, exc_info=True)
        log_facebook_oauth_callback(
            mode=facebook_auth_mode if platform == "facebook" else None,
            success=False,
            error=str(exc),
        )
        messages.error(request, f"Failed to connect: {exc}")
        if facebook_auth_mode and platform == "facebook":
            return redirect_facebook_oauth_failure(request, facebook_auth_mode)

    # If user is still in onboarding, return to brand confirm (express step 2).
    if not request.user.onboarding_completed:
        return redirect("/accounts/onboarding/?step=2")
    return redirect("platforms:list")


@login_required
def disconnect_platform(request, pk):
    """Disconnect a social account — soft-deactivate to preserve linked content."""
    if request.method != "POST":
        return redirect("platforms:list")

    account = get_object_or_404(SocialAccount, pk=pk, user=request.user)
    platform_display = account.get_platform_display()
    username = account.username

    # Soft-deactivate: clear tokens but keep the record so Posts/Interactions survive
    account.access_token = ""
    account.refresh_token = ""
    account.is_active = False
    account.last_error = "Disconnected by user"
    account.save(update_fields=["access_token", "refresh_token", "is_active", "last_error", "updated_at"])

    messages.success(request, f"Disconnected {platform_display} — @{username}")
    return redirect("platforms:list")


@login_required
@ratelimit(key="user", rate="10/m", block=True)
@require_POST
def whatsapp_embedded_callback(request):
    """
    Handle WhatsApp Embedded Signup callback.

    Receives authorization code + session info from Facebook JS SDK,
    exchanges for access token, and stores the connection.
    """
    code = request.POST.get("code", "").strip()
    phone_number_id = request.POST.get("phone_number_id", "").strip()
    waba_id = request.POST.get("waba_id", "").strip()

    if not code:
        messages.error(request, "No authorization code received from WhatsApp signup.")
        return redirect("platforms:list")

    try:
        provider = get_provider("whatsapp")
        result = provider.handle_embedded_signup(
            code=code,
            phone_number_id=phone_number_id,
            waba_id=waba_id,
        )

        SocialAccount.objects.update_or_create(
            user=request.user,
            platform="whatsapp",
            platform_user_id=result.platform_user_id,
            defaults={
                "username": result.username,
                "display_name": result.display_name,
                "access_token": result.access_token,
                "is_active": True,
                "last_error": "",
                "metadata": result.metadata,
            },
        )
        messages.success(request, f"Connected WhatsApp — {result.display_name}")
    except Exception as exc:
        logger.error("WhatsApp Embedded Signup failed: %s", exc, exc_info=True)
        messages.error(request, f"Failed to connect WhatsApp: {exc}")

    if not request.user.onboarding_completed:
        return redirect("/accounts/onboarding/?step=2")
    return redirect("platforms:list")


@login_required
def linkedin_connect_page(request):
    """Start OAuth flow for LinkedIn with organization scopes to connect a Company Page."""
    provider = get_provider("linkedin")
    if not provider:
        messages.error(request, "LinkedIn provider is not available.")
        return redirect("platforms:list")

    state = secrets.token_urlsafe(32)
    request.session["oauth_state_linkedin"] = state
    request.session["oauth_platform"] = "linkedin"
    request.session["linkedin_org_flow"] = True  # Flag to route to page selection after callback

    redirect_uri = request.build_absolute_uri(
        reverse("platforms:oauth_callback", kwargs={"platform": "linkedin"})
    )
    auth_url = provider.get_auth_url(state=state, redirect_uri=redirect_uri, include_org_scopes=True)
    return redirect(auth_url)


@login_required
def linkedin_select_page(request):
    """Show available LinkedIn Company Pages to connect, or create the account if one is selected."""
    # Find the user's LinkedIn personal account (needed for the access token)
    li_account = request.user.social_accounts.filter(
        platform="linkedin", is_active=True
    ).first()

    if not li_account:
        messages.error(request, "Please connect your LinkedIn personal account first.")
        return redirect("platforms:list")

    provider = get_provider("linkedin")
    if not provider:
        messages.error(request, "LinkedIn provider is not available.")
        return redirect("platforms:list")

    if request.method == "POST":
        org_id = request.POST.get("org_id", "").strip()
        org_name = request.POST.get("org_name", "").strip()
        org_vanity = request.POST.get("org_vanity", "").strip()
        org_logo = request.POST.get("org_logo", "").strip()

        if not org_id:
            messages.error(request, "No organization selected.")
            return redirect("platforms:linkedin_select_page")

        # Create a separate SocialAccount for the Company Page
        account, created = SocialAccount.objects.update_or_create(
            user=request.user,
            platform="linkedin",
            platform_user_id=f"org_{org_id}",
            defaults={
                "username": org_vanity or org_name.lower().replace(" ", ""),
                "display_name": org_name,
                "avatar_url": org_logo,
                "access_token": li_account.access_token,
                "refresh_token": li_account.refresh_token,
                "token_expires_at": li_account.token_expires_at,
                "token_scope": li_account.token_scope,
                "is_active": True,
                "last_error": "",
                "account_type": "organization",
                "metadata": {
                    "linkedin_sub": li_account.metadata.get("linkedin_sub", ""),
                    "organization_id": org_id,
                    "organization_name": org_name,
                    "account_type": "organization",
                },
            },
        )
        action = "connected" if created else "reconnected"
        messages.success(request, f"Successfully {action} LinkedIn Company Page — {org_name}")
        return redirect("platforms:list")

    # GET — fetch available organizations and show selection form
    organizations = provider.get_organizations(li_account.access_token)
    if not organizations:
        messages.warning(
            request,
            "No LinkedIn Company Pages found. You must be an administrator of a Company Page to connect it."
        )
        return redirect("platforms:list")

    return render(request, "platforms/linkedin_select_page.html", {
        "organizations": organizations,
        "page_title": "Connect LinkedIn Company Page",
    })


@login_required
@require_POST
def facebook_select_page(request, pk):
    """Set which Facebook Page Kova publishes to (multi-Page accounts)."""
    from apps.platforms.models import SocialAccount

    account = get_object_or_404(
        SocialAccount, pk=pk, user=request.user, platform="facebook", is_active=True,
    )
    page_id = request.POST.get("page_id", "").strip()
    pages = (account.metadata or {}).get("pages", [])
    selected = next((p for p in pages if p.get("id") == page_id), None)
    if not selected:
        messages.error(request, "That Page is not connected to your Facebook account.")
        return redirect("platforms:list")

    metadata = dict(account.metadata or {})
    metadata["selected_page_id"] = page_id
    account.metadata = metadata
    account.save(update_fields=["metadata", "updated_at"])
    messages.success(request, f"Active Facebook Page set to {selected.get('name', 'Page')}.")
    return redirect("platforms:list")
