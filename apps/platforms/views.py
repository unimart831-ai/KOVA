import logging
import secrets

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.platforms.models import SocialAccount
from apps.platforms.providers.registry import get_provider

logger = logging.getLogger(__name__)

AVAILABLE_PLATFORMS = [
    {"key": "twitter", "label": "X (Twitter)", "icon": "🐦"},
    {"key": "linkedin", "label": "LinkedIn", "icon": "💼"},
    {"key": "instagram", "label": "Instagram", "icon": "📷"},
    {"key": "facebook", "label": "Facebook", "icon": "📘"},
    {"key": "tiktok", "label": "TikTok", "icon": "🎵"},
]


@login_required
def platform_list(request):
    """Show connected platforms and connect buttons."""
    accounts = request.user.social_accounts.all()
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

    return render(request, "platforms/list.html", {
        "accounts": accounts,
        "platforms": platforms,
        "page_title": "Connected Platforms",
    })


@login_required
def connect_platform(request, platform):
    """Start OAuth flow for a platform."""
    provider = get_provider(platform)
    if not provider:
        messages.error(request, f"Platform '{platform}' is not available.")
        return redirect("platforms:list")

    # Generate and store a CSRF-like state token
    state = secrets.token_urlsafe(32)
    request.session[f"oauth_state_{platform}"] = state
    request.session[f"oauth_platform"] = platform

    redirect_uri = request.build_absolute_uri(
        reverse("platforms:oauth_callback", kwargs={"platform": platform})
    )
    auth_url = provider.get_auth_url(state=state, redirect_uri=redirect_uri)
    return redirect(auth_url)


@login_required
def oauth_callback(request, platform):
    """Handle OAuth callback from a platform."""
    provider = get_provider(platform)
    if not provider:
        messages.error(request, "Invalid platform.")
        return redirect("platforms:list")

    # Verify state to prevent CSRF
    expected_state = request.session.pop(f"oauth_state_{platform}", None)
    received_state = request.GET.get("state", "")
    if not expected_state or expected_state != received_state:
        messages.error(request, "Invalid OAuth state. Please try again.")
        return redirect("platforms:list")

    error = request.GET.get("error")
    if error:
        messages.error(request, f"Authorization denied: {request.GET.get('error_description', error)}")
        return redirect("platforms:list")

    code = request.GET.get("code", "")
    if not code:
        messages.error(request, "No authorization code received.")
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

        # Create or update the SocialAccount
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
            },
        )
        action = "connected" if created else "reconnected"
        messages.success(request, f"Successfully {action} {account.get_platform_display()} — @{account.username}")

    except Exception as exc:
        logger.error("OAuth callback failed for %s: %s", platform, exc, exc_info=True)
        messages.error(request, f"Failed to connect: {exc}")

    return redirect("platforms:list")


@login_required
def disconnect_platform(request, pk):
    """Disconnect and remove a social account."""
    if request.method != "POST":
        return redirect("platforms:list")

    account = get_object_or_404(SocialAccount, pk=pk, user=request.user)
    platform_display = account.get_platform_display()
    username = account.username

    account.delete()

    messages.success(request, f"Disconnected {platform_display} — @{username}")
    return redirect("platforms:list")
