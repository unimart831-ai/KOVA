"""Social media manager WhatsApp commands — POST, SCHEDULE, PLAN, RETRY, etc."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

PROMO_PRESETS: dict[str, dict] = {
    "launch": {
        "label": "Launch / new arrival",
        "idea": "New arrival launch — spotlight the product, urgency to order, shop link",
        "formats": ["reels", "carousels", "stories", "images"],
    },
    "sale": {
        "label": "Flash sale",
        "idea": "Limited-time sale — discount hook, deadline, M-Pesa / shop CTA",
        "formats": ["reels", "carousels", "stories", "text"],
    },
    "clearance": {
        "label": "Clearance",
        "idea": "Clearance / last pieces — scarcity, sizes left, shop now",
        "formats": ["carousels", "images", "stories"],
    },
    "testimonial": {
        "label": "Testimonial / social proof",
        "idea": "Customer testimonial or before-after — trust + book/buy CTA",
        "formats": ["carousels", "text", "images"],
    },
    "restock": {
        "label": "Back in stock",
        "idea": "Back in stock announcement — notify followers, link to shop",
        "formats": ["images", "stories", "text"],
    },
}


def dispatch_smm_command(user, text: str) -> tuple[str, str, bool, dict] | None:
    """Return handler result or None if not an SMM command."""
    normalized = re.sub(r"\s+", " ", text.strip().lower())

    if normalized.startswith("post "):
        return handle_post(user, text)
    if normalized.startswith("schedule"):
        return handle_schedule(user, text)
    if normalized.startswith("add "):
        return handle_add_product(user, text)
    if normalized in {"plan", "calendar", "content plan", "week plan"}:
        return handle_plan(user)
    if normalized in {"retry", "retry publish", "republish"} or normalized.startswith("retry "):
        return handle_retry(user, text)
    if normalized in {"weekly", "week", "scorecard", "report"}:
        return handle_weekly(user)
    if normalized in {"recycle", "post again", "repost"}:
        return handle_recycle(user)
    if normalized.startswith("sale "):
        return handle_promo_preset(user, text, preset="sale")
    if normalized.startswith("promo "):
        return handle_promo_preset(user, text, preset=None)
    if normalized in {"quiet", "quiet week", "slow week"}:
        return handle_quiet_week(user, enable=True)
    if normalized in {"busy week", "normal week", "full week"}:
        return handle_quiet_week(user, enable=False)

    return None


def handle_post(user, text: str) -> tuple[str, str, bool, dict]:
    """POST <caption> — draft text/image posts to connected platforms."""
    from apps.agents.adapt_agent import auto_schedule_post
    from apps.content.models import Post
    from apps.platforms.models import SocialAccount

    caption = text[5:].strip() if text.lower().startswith("post ") else text.strip()
    if len(caption) < 5:
        return (
            "Try: POST Weekend 20% off braids — book by Friday\n"
            "Creates draft posts on your connected platforms. Reply APPROVE when ready.",
            "post", False, {},
        )

    accounts = SocialAccount.objects.filter(user=user, is_active=True).exclude(platform="whatsapp")
    if not accounts.exists():
        return ("Connect Facebook or Instagram first: Settings → Platforms.", "post", False, {})

    created = 0
    for account in accounts:
        fmt = Post.PostFormat.TEXT
        media_urls: list = []
        if account.platform in Post.MEDIA_REQUIRED_PLATFORMS:
            fmt = Post.PostFormat.IMAGE
            from apps.products.models import Product

            product = Product.objects.filter(user=user, is_active=True).exclude(image="").first()
            if product and product.image:
                try:
                    media_urls = [product.image.url]
                except Exception:
                    pass
            if not media_urls:
                continue

        post = Post.objects.create(
            user=user,
            social_account=account,
            platform=account.platform,
            content_text=caption[:2200],
            content_type="original",
            status=Post.Status.PENDING_APPROVAL,
            post_format=fmt,
            visual_strategy="ai_photo" if media_urls else "text",
            media_urls=media_urls,
            media_status=Post.MediaStatus.GENERATED if media_urls else Post.MediaStatus.NONE,
            generated_by_agent="create",
            visual_metadata={"source": "whatsapp_post_command"},
        )
        try:
            auto_schedule_post(post)
        except Exception:
            pass
        created += 1

    if not created:
        return (
            "No posts created — Instagram/TikTok need a product photo. "
            "Snap a product first or connect Facebook.",
            "post", False, {},
        )
    return (
        f"Created {created} draft post(s) from your caption.\n"
        f"\"{caption[:100]}{'…' if len(caption) > 100 else ''}\"\n\n"
        "Reply POSTS · APPROVE · or edit in Studio.",
        "post", True, {"created": created},
    )


def handle_schedule(user, text: str) -> tuple[str, str, bool, dict]:
    """SCHEDULE <n> <when> — reschedule pending/failed post by queue index."""
    from apps.content.approval import get_pending_posts
    from apps.content.models import Post

    parts = re.sub(r"\s+", " ", text.strip().lower()).split()
    if len(parts) < 3:
        return (
            "Try: SCHEDULE 1 tomorrow 6pm\n"
            "Or: SCHEDULE 2 friday 10am\n"
            "Uses your approval queue numbering (POSTS).",
            "schedule", False, {},
        )

    try:
        index = int(parts[1])
    except ValueError:
        return ("Use a post number from POSTS, e.g. SCHEDULE 1 tomorrow 6pm", "schedule", False, {})

    when_text = " ".join(parts[2:])
    scheduled_at = _parse_schedule_when(when_text, user)
    if not scheduled_at:
        return (
            f"Couldn't parse \"{when_text}\". Try: tomorrow 6pm · friday 10am · 2026-07-15 18:00",
            "schedule", False, {},
        )

    pending = get_pending_posts(user, limit=20)
    failed = list(
        Post.objects.filter(user=user, status=Post.Status.FAILED).order_by("-updated_at")[:10]
    )
    combined = list(pending) + [p for p in failed if p not in pending]

    if index < 1 or index > len(combined):
        return (f"Post #{index} not found. Reply POSTS to see your queue.", "schedule", False, {})

    post = combined[index - 1]
    post.scheduled_at = scheduled_at
    post.status = Post.Status.SCHEDULED
    post.publish_error = ""
    post.save(update_fields=["scheduled_at", "status", "publish_error", "updated_at"])

    local = timezone.localtime(scheduled_at)
    return (
        f"Scheduled post #{index} for {local.strftime('%a %d %b, %I:%M %p').lstrip('0')}.\n"
        f"\"{(post.content_text or '')[:60]}…\"\n"
        "It will publish automatically unless you reject it.",
        "schedule", True, {"post_id": str(post.pk), "scheduled_at": scheduled_at.isoformat()},
    )


def handle_add_product(user, text: str) -> tuple[str, str, bool, dict]:
    """ADD <name> <price> — text-only product (no photo)."""
    from apps.products.models import Product

    body = text[4:].strip() if text.lower().startswith("add ") else text.strip()
    parts = body.rsplit(" ", 1)
    if len(parts) < 2:
        return (
            "Try: ADD Blue dress 2500\n"
            "Adds to your shop + catalog. Send a photo later to Snap polish.",
            "add", False, {},
        )

    name, price_token = parts[0].strip(), parts[1].strip()
    price = _parse_amount(price_token)
    if not name or price is None:
        return ("Try: ADD Blue dress 2500", "add", False, {})

    from apps.products.owner_snap_whatsapp import _product_limit_message

    limit_msg = _product_limit_message(user)
    if limit_msg:
        return limit_msg, "add", False, {}

    product = Product.objects.create(
        user=user,
        name=name[:200],
        price=price,
        currency=getattr(getattr(user, "profile", None), "currency", "KES") or "KES",
        source=Product.Source.MANUAL,
        is_active=True,
    )
    site = getattr(settings, "SITE_URL", "").rstrip("/")
    return (
        f"Added *{product.name}* — {product.currency} {price:,.0f}\n"
        f"Shop: {site}/shop/\n\n"
        "Send a photo to polish & create a campaign, or PRICE/STOCK to update.",
        "add", True, {"product_id": str(product.pk)},
    )


def handle_plan(user) -> tuple[str, str, bool, dict]:
    """7-day content plan summary."""
    from apps.briefs.calendar_hints import format_moments_whatsapp, upcoming_moments
    from apps.content.models import Post, WeeklyContentPlan

    today = timezone.localdate()
    week_end = today + timedelta(days=7)

    scheduled = Post.objects.filter(
        user=user,
        status__in=[Post.Status.APPROVED, Post.Status.SCHEDULED],
        scheduled_at__date__gte=today,
        scheduled_at__date__lte=week_end,
    ).count()
    pending = Post.objects.filter(user=user, status=Post.Status.PENDING_APPROVAL).count()
    failed = Post.objects.filter(user=user, status=Post.Status.FAILED).count()

    plan = WeeklyContentPlan.objects.filter(user=user).order_by("-week_start").first()
    plan_line = ""
    if plan and plan.theme:
        plan_line = f"\nTheme: {plan.theme[:120]}"

    profile = getattr(user, "profile", None)
    country = getattr(profile, "country", "KE") or "KE"
    moments = upcoming_moments(country=country, within_days=14)
    moments_txt = format_moments_whatsapp(moments)
    if moments_txt:
        moments_txt = "\n\n" + moments_txt

    quiet = _is_quiet_week(user)
    quiet_line = "\n🌙 Quiet week ON — lighter posting." if quiet else ""

    site = getattr(settings, "SITE_URL", "").rstrip("/")
    return (
        f"📋 *Your 7-day plan*\n"
        f"• Scheduled: {scheduled}\n"
        f"• Awaiting approval: {pending}\n"
        f"• Failed (fix with RETRY): {failed}"
        f"{plan_line}{quiet_line}{moments_txt}\n\n"
        f"PROMO LAUNCH · SALE 20% off · POST <caption> · Studio: {site}/content/studio/",
        "plan", True,
        {"scheduled": scheduled, "pending": pending, "failed": failed},
    )


def handle_retry(user, text: str) -> tuple[str, str, bool, dict]:
    """RETRY [n] — republish failed post."""
    from apps.content.approval import republish_post_for_user
    from apps.content.models import Post

    parts = re.sub(r"\s+", " ", text.strip().lower()).split()
    index = 1
    if len(parts) >= 2 and parts[1].isdigit():
        index = int(parts[1])

    failed = list(
        Post.objects.filter(user=user, status=Post.Status.FAILED)
        .select_related("social_account")
        .order_by("-updated_at")[:10]
    )
    if not failed:
        return ("No failed posts — you're clear! ✅", "retry", True, {})

    if index < 1 or index > len(failed):
        return (f"Failed post #{index} not found. {len(failed)} failed — try RETRY 1.", "retry", False, {})

    post = failed[index - 1]
    result = republish_post_for_user(user, post, schedule_intent="post_now")
    if not result.get("success"):
        return (result.get("message") or result.get("error") or "Could not retry publish.", "retry", False, result)

    plat = post.social_account.get_platform_display() if post.social_account else post.platform
    return (
        f"Retrying publish to {plat}…\n\"{(post.content_text or '')[:60]}…\"\n"
        "You'll get a WhatsApp ping when it's live or if it fails again.",
        f"retry_{index}", True, {"post_id": str(post.pk)},
    )


def handle_weekly(user) -> tuple[str, str, bool, dict]:
    from apps.briefs.weekly_report import format_weekly_smm_whatsapp

    return format_weekly_smm_whatsapp(user), "weekly", True, {}


def handle_recycle(user) -> tuple[str, str, bool, dict]:
    """Queue a recycle seed from top-performing old post."""
    from apps.analytics.models import PostMetric
    from apps.content.models import ContentSeed, Post
    from apps.content.tasks import generate_from_seed

    from apps.billing.enforcement import check_seed_limit

    allowed, msg = check_seed_limit(user)
    if not allowed:
        return msg, "recycle", False, {}

    cutoff = timezone.now() - timedelta(days=30)
    top = (
        Post.objects.filter(
            user=user,
            status=Post.Status.PUBLISHED,
            published_at__lte=cutoff,
            metrics__isnull=False,
        )
        .select_related("metrics")
        .order_by("-metrics__engagement_rate")
        .first()
    )
    if not top:
        return (
            "No posts old enough to recycle yet (need 30+ days of data). "
            "Keep publishing — POST AGAIN will unlock later.",
            "recycle", False, {},
        )

    rate = getattr(getattr(top, "metrics", None), "engagement_rate", 0) or 0
    seed = ContentSeed.objects.create(
        user=user,
        idea=f"[Recycle] {(top.content_text or 'Top post')[:80]}",
        notes=f"[Recycle] source_post={top.pk}",
        status=ContentSeed.SeedStatus.NEW,
    )
    from apps.utils import fire_task

    fire_task(generate_from_seed, str(seed.pk))

    site = getattr(settings, "SITE_URL", "").rstrip("/")
    return (
        f"♻️ Recycling your top post into a fresh campaign.\n"
        f"\"{(top.content_text or '')[:80]}…\"\n\n"
        f"Drafts land in Studio: {site}/content/studio/\nReply POSTS when ready.",
        "recycle", True, {"seed_id": str(seed.pk), "source_post_id": str(top.pk)},
    )


def handle_promo_preset(user, text: str, *, preset: str | None) -> tuple[str, str, bool, dict]:
    from apps.billing.enforcement import check_seed_limit
    from apps.briefs.actions import ensure_brief_idea_asset, proposals_url_for_asset

    parts = re.sub(r"\s+", " ", text.strip().lower()).split()
    key = preset
    extra = ""
    if not key:
        key = parts[1] if len(parts) > 1 else "launch"
        extra = " ".join(parts[2:]) if len(parts) > 2 else ""
    else:
        extra = " ".join(parts[1:]) if len(parts) > 1 else ""

    if key not in PROMO_PRESETS:
        opts = ", ".join(PROMO_PRESETS)
        return (f"Unknown preset. Try: PROMO launch · PROMO sale · PROMO clearance\nOptions: {opts}", "promo", False, {})

    spec = PROMO_PRESETS[key]
    idea = spec["idea"]
    if extra:
        idea = f"{idea} — {extra}"

    allowed, limit_msg = check_seed_limit(user)
    if not allowed:
        return limit_msg, "promo", False, {}

    asset = ensure_brief_idea_asset(
        user,
        idea,
        context=f"Preset: {spec['label']}. Formats: {', '.join(spec['formats'])}.",
        platform_hint="",
        source="whatsapp_promo",
    )
    meta = dict(asset.metadata or {})
    meta["selected_content_types"] = {f: True for f in spec["formats"]}
    meta["promo_preset"] = key
    asset.metadata = meta
    asset.save(update_fields=["metadata", "updated_at"])

    url = proposals_url_for_asset(asset)
    return (
        f"🎯 *{spec['label']}* campaign queued.\n"
        f"{idea[:160]}\n\n"
        f"Pick your angle: {url}\nReply CAMPAIGNS when drafts are ready.",
        f"promo_{key}", True, {"asset_id": str(asset.pk), "preset": key},
    )


def handle_quiet_week(user, *, enable: bool) -> tuple[str, str, bool, dict]:
    profile = getattr(user, "profile", None)
    if not profile:
        return ("Profile not found.", "quiet", False, {})

    prefs = dict(profile.dna_preferences or {})
    if enable:
        prefs["quiet_week_until"] = (timezone.localdate() + timedelta(days=7)).isoformat()
        profile.posting_frequency = max(2, min(getattr(profile, "posting_frequency", 7) or 7, 3))
        msg = (
            "🌙 *Quiet week enabled* — Kova will aim for ~2–3 posts this week.\n"
            "Reply BUSY WEEK to return to normal."
        )
    else:
        prefs.pop("quiet_week_until", None)
        profile.posting_frequency = max(getattr(profile, "posting_frequency", 7) or 7, 7)
        msg = "☀️ *Full week* — normal posting frequency restored."

    profile.dna_preferences = prefs
    profile.save(update_fields=["dna_preferences", "posting_frequency", "updated_at"])
    return msg, "quiet_week" if enable else "full_week", True, {"quiet_week": enable}


def _is_quiet_week(user) -> bool:
    profile = getattr(user, "profile", None)
    if not profile:
        return False
    until = (profile.dna_preferences or {}).get("quiet_week_until")
    if not until:
        return False
    try:
        return timezone.localdate() <= datetime.fromisoformat(until).date()
    except ValueError:
        return False


def _parse_amount(token: str) -> Decimal | None:
    cleaned = token.lower().replace(",", "")
    for prefix in ("ksh", "kes", "sh"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
            break
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    return value if value >= 0 else None


def _parse_schedule_when(when_text: str, user) -> datetime | None:
    """Parse natural-ish schedule strings in user timezone."""
    import zoneinfo

    when_text = when_text.strip().lower()
    tz_name = getattr(getattr(user, "profile", None), "timezone", None) or "Africa/Nairobi"
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        tz = zoneinfo.ZoneInfo("Africa/Nairobi")

    now = timezone.now().astimezone(tz)
    base = now.replace(hour=18, minute=0, second=0, microsecond=0)

    if when_text.startswith("tomorrow"):
        base = (now + timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
        when_text = when_text.replace("tomorrow", "").strip()
    elif when_text.startswith("today"):
        base = now.replace(hour=18, minute=0, second=0, microsecond=0)
        when_text = when_text.replace("today", "").strip()

    weekdays = {
        "monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1,
        "wednesday": 2, "wed": 2, "thursday": 3, "thu": 3, "thur": 3,
        "friday": 4, "fri": 4, "saturday": 5, "sat": 5, "sunday": 6, "sun": 6,
    }
    for name, wd in weekdays.items():
        if when_text.startswith(name):
            days_ahead = (wd - now.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            base = (now + timedelta(days=days_ahead)).replace(hour=18, minute=0, second=0, microsecond=0)
            when_text = when_text[len(name):].strip()
            break

    time_match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", when_text)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or 0)
        ampm = time_match.group(3)
        if ampm == "pm" and hour < 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        if not ampm and hour <= 7:
            hour += 12
        base = base.replace(hour=hour, minute=minute)

    iso_try = re.match(r"(\d{4}-\d{2}-\d{2})(?:[ T](\d{1,2}):(\d{2}))?", when_text)
    if iso_try:
        y, m, d = map(int, iso_try.group(1).split("-"))
        hour, minute = int(iso_try.group(2) or 18), int(iso_try.group(3) or 0)
        base = datetime(y, m, d, hour, minute, tzinfo=tz)

    if base <= now:
        base += timedelta(days=1)
    return base.astimezone(timezone.utc)


def handle_owner_voice_note(user, msg_data: dict) -> tuple[str, str, bool, dict]:
    """Transcribe owner voice note → campaign idea asset."""
    from django.conf import settings as django_settings

    audio_info = msg_data.get("audio") or {}
    media_id = audio_info.get("id")
    mime = audio_info.get("mime_type") or "audio/ogg"
    if not media_id:
        return ("Couldn't read that voice note. Try again or type your idea.", "voice", False, {})

    token = getattr(django_settings, "WHATSAPP_ACCESS_TOKEN", "") or ""
    phone_id = getattr(django_settings, "WHATSAPP_PHONE_NUMBER_ID", "") or ""
    if not (token and phone_id):
        return ("Voice notes need WhatsApp configured. Type your idea instead.", "voice", False, {})

    try:
        from apps.platforms.providers.whatsapp import WhatsAppProvider
        from apps.content.voice import transcribe_audio
        from io import BytesIO

        provider = WhatsAppProvider()
        media_bytes, fetched_mime = provider.download_media_bytes(token, media_id)
        if not media_bytes:
            return ("Couldn't download voice note. Try again.", "voice", False, {})

        bio = BytesIO(media_bytes)
        bio.name = "voice.ogg"
        bio.content_type = fetched_mime or mime
        result = transcribe_audio(bio, mime)
        if result.get("error"):
            return (f"Transcription failed: {result['error'][:120]}", "voice", False, {})
        text = (result.get("text") or "").strip()
        if len(text) < 5:
            return ("Voice note was too short. Try again with your campaign idea.", "voice", False, {})
    except Exception:
        logger.exception("Owner voice note transcription failed")
        return ("Couldn't transcribe voice note. Type your idea instead.", "voice", False, {})

    from apps.billing.enforcement import check_seed_limit
    from apps.briefs.actions import ensure_brief_idea_asset, proposals_url_for_asset

    allowed, limit_msg = check_seed_limit(user)
    if not allowed:
        return limit_msg, "voice", False, {}

    asset = ensure_brief_idea_asset(
        user,
        text[:400],
        context="From WhatsApp voice note",
        source="whatsapp_voice",
    )
    url = proposals_url_for_asset(asset)
    return (
        f"🎙️ Got it:\n\"{text[:200]}{'…' if len(text) > 200 else ''}\"\n\n"
        f"Pick your angle: {url}\nReply CAMPAIGNS when drafts are ready.",
        "voice", True, {"asset_id": str(asset.pk), "transcript_len": len(text)},
    )
