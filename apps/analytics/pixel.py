"""
Kova Pixel — website tracking endpoint, settings page, and attribution engine.

Sprint T2A: Lets users embed a lightweight JS pixel on their website to track
page views, form submissions, purchases, and custom events. Events are attributed
back to social posts via UTM parameters, powering the revenue dashboard.
"""

import json
import logging
import secrets
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.accounts.models import UserProfile
from apps.analytics.models import (
    Conversion,
    ConversionJourney,
    ConversionTouchpoint,
    WebsiteEvent,
)
from apps.billing.models import get_user_plan_limits

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

MAX_METADATA_SIZE = 10_240  # 10 KB
VALID_EVENT_TYPES = {c[0] for c in WebsiteEvent.EventType.choices}
RATE_LIMIT_PER_MINUTE = 120  # per pixel_token


# ─── Public tracking endpoint ─────────────────────────────────────────────────


@csrf_exempt
@ratelimit(key="ip", rate="120/m", method="POST", block=True)
def pixel_track(request):
    """
    Public endpoint for Kova Pixel events.
    Authenticated by pixel_token (not session/cookie).
    Accepts POST (event data) and OPTIONS (CORS preflight).
    """
    # CORS headers for all responses
    cors_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Max-Age": "86400",
    }

    # Handle CORS preflight
    if request.method == "OPTIONS":
        response = JsonResponse({}, status=204)
        for k, v in cors_headers.items():
            response[k] = v
        return response

    if request.method != "POST":
        response = JsonResponse({"error": "Method not allowed"}, status=405)
        for k, v in cors_headers.items():
            response[k] = v
        return response

    # Parse JSON body (sendBeacon sends as text/plain with JSON body)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        response = JsonResponse({"error": "Invalid JSON"}, status=400)
        for k, v in cors_headers.items():
            response[k] = v
        return response

    # Validate token
    token = data.get("token")
    if not token or not isinstance(token, str) or len(token) > 64:
        response = JsonResponse({"error": "Invalid token"}, status=400)
        for k, v in cors_headers.items():
            response[k] = v
        return response

    # Rate limit per token
    rate_key = f"pixel_rate:{token[:32]}"
    hits = cache.get(rate_key, 0)
    if hits >= RATE_LIMIT_PER_MINUTE:
        response = JsonResponse({"error": "Rate limit exceeded"}, status=429)
        for k, v in cors_headers.items():
            response[k] = v
        return response
    cache.set(rate_key, hits + 1, timeout=60)

    # Look up user by token
    try:
        profile = UserProfile.objects.select_related("user").get(pixel_token=token)
    except UserProfile.DoesNotExist:
        response = JsonResponse({"error": "Invalid token"}, status=403)
        for k, v in cors_headers.items():
            response[k] = v
        return response

    # Check plan allows pixel (multi_touch_attribution = Pro+)
    limits = get_user_plan_limits(profile.user)
    if not limits.get("multi_touch_attribution"):
        response = JsonResponse({"error": "Pixel requires Pro or Agency plan"}, status=403)
        for k, v in cors_headers.items():
            response[k] = v
        return response

    user = profile.user

    # Validate event type
    event_type = data.get("event_type", "page_view")
    if event_type not in VALID_EVENT_TYPES:
        event_type = "custom"

    # Validate visitor_id
    visitor_id = str(data.get("visitor_id", ""))[:64]
    if not visitor_id:
        response = JsonResponse({"error": "Missing visitor_id"}, status=400)
        for k, v in cors_headers.items():
            response[k] = v
        return response

    # Parse revenue safely
    revenue = Decimal("0")
    raw_revenue = data.get("revenue")
    if raw_revenue:
        try:
            revenue = min(Decimal(str(raw_revenue)), Decimal("9999999.99"))
            if revenue < 0:
                revenue = Decimal("0")
        except (InvalidOperation, ValueError):
            revenue = Decimal("0")

    # Sanitize metadata size
    metadata = data.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    meta_str = json.dumps(metadata)
    if len(meta_str) > MAX_METADATA_SIZE:
        metadata = {"_truncated": True}

    # Deduplication: prevent duplicate events from beacon retry + XHR fallback
    dedup_key = f"pixel_dedup:{token[:16]}:{visitor_id}:{event_type}:{str(data.get('page_url', ''))[:80]}"
    if cache.get(dedup_key):
        response = JsonResponse({"ok": True, "deduplicated": True}, status=200)
        for k, v in cors_headers.items():
            response[k] = v
        return response
    cache.set(dedup_key, 1, timeout=5)  # 5-second dedup window

    # Create the event
    event = WebsiteEvent.objects.create(
        user=user,
        event_type=event_type,
        event_name=str(data.get("event_name", ""))[:100],
        page_url=str(data.get("page_url", ""))[:2048],
        page_title=str(data.get("page_title", ""))[:500],
        referrer=str(data.get("referrer", ""))[:2048],
        utm_source=str(data.get("utm_source", ""))[:255],
        utm_medium=str(data.get("utm_medium", ""))[:255],
        utm_campaign=str(data.get("utm_campaign", ""))[:255],
        utm_content=str(data.get("utm_content", ""))[:255],
        visitor_id=visitor_id,
        session_id=str(data.get("session_id", ""))[:64],
        device_type=_detect_device(data.get("screen_width")),
        revenue=revenue,
        currency=str(data.get("currency", "USD"))[:3],
        metadata=metadata,
    )

    # Attribution: link to post via UTM
    _attribute_to_post(event)

    # Update conversion journey
    _update_journey(user, event)

    # Auto-create lead from form submissions
    if event_type == "form_submit":
        _create_lead_from_form(user, event)

    response = JsonResponse({"ok": True}, status=201)
    for k, v in cors_headers.items():
        response[k] = v
    return response


# ─── Pixel settings page ─────────────────────────────────────────────────────


@login_required
def pixel_settings(request):
    """Pixel setup page: snippet, token, test status, recent stats."""
    profile = request.user.profile

    # Generate token on first visit
    if not profile.pixel_token:
        profile.pixel_token = secrets.token_hex(32)
        profile.save(update_fields=["pixel_token"])

    # Check plan eligibility
    limits = get_user_plan_limits(profile.user)
    pixel_enabled = limits.get("multi_touch_attribution", False)

    # Stats (last 24h / 7d / 30d)
    now = timezone.now()
    stats = {}
    if pixel_enabled:
        base_qs = WebsiteEvent.objects.filter(user=request.user)
        stats = {
            "events_24h": base_qs.filter(created_at__gte=now - timezone.timedelta(hours=24)).count(),
            "events_7d": base_qs.filter(created_at__gte=now - timezone.timedelta(days=7)).count(),
            "events_30d": base_qs.filter(created_at__gte=now - timezone.timedelta(days=30)).count(),
            "unique_visitors_7d": (
                base_qs.filter(created_at__gte=now - timezone.timedelta(days=7))
                .values("visitor_id").distinct().count()
            ),
            "top_pages": list(
                base_qs.filter(
                    created_at__gte=now - timezone.timedelta(days=7),
                    event_type="page_view",
                )
                .values("page_url")
                .annotate(count=Count("id"))
                .order_by("-count")[:5]
            ),
            "events_by_type": list(
                base_qs.filter(created_at__gte=now - timezone.timedelta(days=7))
                .values("event_type")
                .annotate(count=Count("id"))
                .order_by("-count")
            ),
            "revenue_7d": (
                base_qs.filter(
                    created_at__gte=now - timezone.timedelta(days=7),
                    event_type__in=["purchase", "add_to_cart"],
                ).aggregate(total=Sum("revenue"))["total"] or 0
            ),
        }

    # Build base URL for pixel script
    if hasattr(settings, "CUSTOM_DOMAIN") and settings.CUSTOM_DOMAIN:
        base_url = f"https://{settings.CUSTOM_DOMAIN}"
    elif hasattr(settings, "RAILWAY_PUBLIC_DOMAIN") and settings.RAILWAY_PUBLIC_DOMAIN:
        base_url = f"https://{settings.RAILWAY_PUBLIC_DOMAIN}"
    else:
        base_url = request.build_absolute_uri("/").rstrip("/")

    context = {
        "pixel_token": profile.pixel_token,
        "pixel_enabled": pixel_enabled,
        "base_url": base_url,
        "stats": stats,
        "plan": profile.get_plan_display(),
    }
    return render(request, "analytics/pixel_settings.html", context)


@login_required
@require_POST
def pixel_regenerate_token(request):
    """Regenerate the pixel token (invalidates old pixel installations)."""
    profile = request.user.profile
    profile.pixel_token = secrets.token_hex(32)
    profile.save(update_fields=["pixel_token"])
    return JsonResponse({"token": profile.pixel_token})


@login_required
def pixel_events(request):
    """User-facing event browser — browse pixel events with filters."""
    from django.core.paginator import Paginator

    profile = request.user.profile
    limits = get_user_plan_limits(profile.user)
    if not limits.get("multi_touch_attribution"):
        return render(request, "analytics/pixel_events.html", {"pixel_enabled": False})

    qs = WebsiteEvent.objects.filter(user=request.user).select_related("post")

    # Filters
    event_type = request.GET.get("type", "")
    if event_type and event_type in VALID_EVENT_TYPES:
        qs = qs.filter(event_type=event_type)

    visitor = request.GET.get("visitor", "").strip()
    if visitor:
        qs = qs.filter(visitor_id=visitor)

    has_revenue = request.GET.get("revenue", "")
    if has_revenue == "yes":
        qs = qs.filter(revenue__gt=0)

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get("page", 1))

    # Visitor journeys summary (top 10 active)
    journeys = (
        ConversionJourney.objects.filter(user=request.user)
        .order_by("-last_touch_at")[:10]
    )

    context = {
        "pixel_enabled": True,
        "events": page,
        "paginator": paginator,
        "event_types": WebsiteEvent.EventType.choices,
        "current_type": event_type,
        "current_visitor": visitor,
        "current_revenue": has_revenue,
        "journeys": journeys,
    }
    return render(request, "analytics/pixel_events.html", context)


@login_required
def pixel_test(request):
    """Check if pixel has fired recently — returns JSON for HTMX polling."""
    now = timezone.now()
    recent = WebsiteEvent.objects.filter(
        user=request.user,
        created_at__gte=now - timezone.timedelta(minutes=5),
    ).order_by("-created_at").first()

    if recent:
        return JsonResponse({
            "detected": True,
            "event_type": recent.get_event_type_display(),
            "page_url": recent.page_url[:80],
            "time": recent.created_at.isoformat(),
        })
    return JsonResponse({"detected": False})


# ─── Attribution engine ───────────────────────────────────────────────────────


def _detect_device(screen_width):
    """Infer device type from screen width sent by pixel."""
    if not screen_width:
        return ""
    try:
        w = int(screen_width)
    except (ValueError, TypeError):
        return ""
    if w < 768:
        return "mobile"
    elif w < 1024:
        return "tablet"
    return "desktop"


def _attribute_to_post(event):
    """
    Link a WebsiteEvent to its originating Post via UTM parameters.
    Kova posts use utm_content=<post_uuid_prefix> for tracking.
    """
    from apps.content.models import Post

    # Try utm_content first (most specific — contains post ID prefix)
    if event.utm_content:
        # Use a range filter on UUID which is indexable, instead of id__startswith
        prefix = event.utm_content.strip()
        try:
            # Pad prefix to form valid UUID range bounds
            lower = prefix.ljust(32, "0")
            upper = prefix.ljust(32, "f")
            # Insert hyphens for UUID format
            lower_uuid = f"{lower[:8]}-{lower[8:12]}-{lower[12:16]}-{lower[16:20]}-{lower[20:32]}"
            upper_uuid = f"{upper[:8]}-{upper[8:12]}-{upper[12:16]}-{upper[16:20]}-{upper[20:32]}"
            post = (
                Post.objects.filter(
                    user=event.user,
                    id__gte=lower_uuid,
                    id__lte=upper_uuid,
                ).first()
            )
        except (ValueError, Exception):
            post = None
        if post:
            event.post = post
            event.save(update_fields=["post"])
            return

    # Fallback: match by campaign name
    if event.utm_campaign:
        post = (
            Post.objects.filter(
                user=event.user,
                utm_campaign=event.utm_campaign,
                status="published",
            )
            .order_by("-published_at")
            .first()
        )
        if post:
            event.post = post
            event.save(update_fields=["post"])


def _update_journey(user, event):
    """
    Update or create a ConversionJourney for this visitor.
    Adds a touchpoint to track the multi-touch attribution path.
    """
    # Find or create journey for this visitor
    journey, created = ConversionJourney.objects.get_or_create(
        user=user,
        visitor_id=event.visitor_id,
        is_converted=False,
        defaults={
            "first_touch_at": timezone.now(),
            "last_touch_at": timezone.now(),
            "touchpoint_count": 0,
        },
    )

    # Map pixel event types to touchpoint types
    touch_type_map = {
        "page_view": ConversionTouchpoint.TouchType.PAGE_VIEW,
        "form_submit": ConversionTouchpoint.TouchType.FORM_SUBMIT,
        "button_click": ConversionTouchpoint.TouchType.LINK_CLICK,
        "purchase": ConversionTouchpoint.TouchType.LINK_CLICK,
        "add_to_cart": ConversionTouchpoint.TouchType.LINK_CLICK,
        "sign_up": ConversionTouchpoint.TouchType.FORM_SUBMIT,
        "custom": ConversionTouchpoint.TouchType.DIRECT,
    }

    # Create touchpoint
    ConversionTouchpoint.objects.create(
        journey=journey,
        post=event.post,
        touch_type=touch_type_map.get(
            event.event_type, ConversionTouchpoint.TouchType.PAGE_VIEW
        ),
        utm_source=event.utm_source,
        utm_medium=event.utm_medium,
        utm_campaign=event.utm_campaign,
        utm_content=event.utm_content,
        referrer=event.referrer,
        landing_page=event.page_url,
        device_type=event.device_type,
    )

    # Update journey counters
    journey.touchpoint_count += 1
    journey.last_touch_at = timezone.now()
    update_fields = ["touchpoint_count", "last_touch_at"]

    # Mark as converted for purchase events
    if event.event_type == "purchase" and event.revenue > 0:
        journey.is_converted = True
        journey.converted_at = timezone.now()
        journey.total_revenue = event.revenue
        update_fields += ["is_converted", "converted_at", "total_revenue"]

        # Bridge: create a Conversion record so revenue appears in the dashboard
        from apps.content.campaign_attribution import create_attributed_conversion, resolve_marketing_campaign

        campaign = resolve_marketing_campaign(
            user,
            utm_campaign=event.utm_campaign,
            post=event.post,
        )
        conversion = create_attributed_conversion(
            user,
            Conversion.ConversionType.SALE,
            post=event.post,
            campaign=campaign,
            revenue=event.revenue,
            event_name=event.event_name or "pixel_purchase",
            utm_source=event.utm_source,
            utm_medium=event.utm_medium,
            utm_campaign=event.utm_campaign,
            utm_content=event.utm_content,
            metadata={
                "source": "kova_pixel",
                "page_url": event.page_url,
                "visitor_id": event.visitor_id,
                "currency": event.currency,
            },
        )
        journey.conversion = conversion
        update_fields.append("conversion")

    elif event.event_type == "sign_up":
        # Also record sign-ups as lead conversions
        from apps.content.campaign_attribution import create_attributed_conversion, resolve_marketing_campaign

        campaign = resolve_marketing_campaign(
            user,
            utm_campaign=event.utm_campaign,
            post=event.post,
        )
        create_attributed_conversion(
            user,
            Conversion.ConversionType.LEAD,
            post=event.post,
            campaign=campaign,
            event_name=event.event_name or "pixel_signup",
            utm_source=event.utm_source,
            utm_medium=event.utm_medium,
            utm_campaign=event.utm_campaign,
            utm_content=event.utm_content,
            metadata={
                "source": "kova_pixel",
                "page_url": event.page_url,
                "visitor_id": event.visitor_id,
            },
        )

    journey.save(update_fields=update_fields)

    # Link event to journey
    event.journey = journey
    event.save(update_fields=["journey"])


def _create_lead_from_form(user, event):
    """Auto-create a Lead when a form_submit event contains an email."""
    from apps.leads.models import Lead

    metadata = event.metadata or {}
    # Look for email in form data
    email = metadata.get("email", "") or metadata.get("Email", "")
    if not email or "@" not in email:
        return

    name = metadata.get("name", "") or metadata.get("Name", "")

    lead, created = Lead.objects.get_or_create(
        user=user,
        email=email.lower().strip()[:254],
        defaults={
            "name": name[:255] if name else "",
            "source_type": "form_submission",
            "source_platform": "website",
            "source_post": event.post,
            "metadata": {
                "form_data": {
                    k: v for k, v in metadata.items()
                    if k.lower() not in ("password", "pass", "pwd", "credit_card", "cc", "ssn")
                },
                "page_url": event.page_url,
                "utm_source": event.utm_source,
                "utm_campaign": event.utm_campaign,
            },
            "first_seen_at": timezone.now(),
        },
    )

    if not created:
        # Update last activity
        lead.last_activity_at = timezone.now()
        lead.save(update_fields=["last_activity_at"])

    # Create lead activity
    try:
        from apps.leads.models import LeadActivity
        LeadActivity.objects.create(
            lead=lead,
            activity_type="form_submitted",
            metadata={
                "page_url": event.page_url,
                "form_name": event.event_name,
                "source": "kova_pixel",
            },
        )
    except Exception:
        logger.warning("Failed to create lead activity for pixel form event", exc_info=True)
