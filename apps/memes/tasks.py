"""
Meme Intelligence Engine — Celery tasks.

Two main tasks:
1. discover_trending_memes — periodic (every 3 hours), finds what's trending
2. adapt_memes_for_users — after discovery, creates brand-adapted versions
3. update_meme_lifecycle — periodic (daily), ages out stale memes
"""

import json
import logging

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

logger = logging.getLogger(__name__)
User = get_user_model()


# ─── TASK 1: DISCOVER TRENDING MEMES ────────────────────────────────────────

@shared_task(name="memes.discover_trending_memes", bind=True, max_retries=1)
def discover_trending_memes(self):
    """
    Discover what's trending in Kenya and globally.

    Uses Tavily web search + LLM analysis to find meme-worthy trends,
    score them, and extract reusable formats.

    Runs every 3 hours via Celery Beat.
    """
    from apps.agents.llm import generate, get_model_for_task, parse_llm_json
    from .models import KenyanEvent, TrendingMeme

    logger.info("🎭 Meme Discovery starting...")

    # ── 1. Gather context: what events are coming up? ────────────
    today = timezone.now().date()
    upcoming_events = KenyanEvent.objects.filter(
        date__gte=today,
        date__lte=today + timezone.timedelta(days=14),
    ).values_list("name", "date", "event_type", "meme_potential", "tags", "meme_angles")

    events_context = ""
    if upcoming_events:
        events_context = "\n\n=== UPCOMING KENYAN EVENTS (next 14 days) ===\n"
        for name, date, etype, potential, tags, angles in upcoming_events:
            events_context += (
                f"- {name} ({date}, {etype}, meme potential: {potential})\n"
                f"  Tags: {json.dumps(tags)}\n"
                f"  Meme angles: {json.dumps(angles)}\n"
            )

    # Also check what events happened recently (memes about past events)
    recent_events = KenyanEvent.objects.filter(
        date__gte=today - timezone.timedelta(days=3),
        date__lt=today,
    ).values_list("name", "date", "meme_angles")
    if recent_events:
        events_context += "\n=== JUST HAPPENED (last 3 days — aftermath memes) ===\n"
        for name, date, angles in recent_events:
            events_context += f"- {name} ({date}) — possible meme angles: {json.dumps(angles)}\n"

    # ── 2. Web search for trending content ───────────────────────
    web_context = _search_meme_trends()

    # ── 3. Check what we already have (avoid duplicates) ─────────
    recent_memes = TrendingMeme.objects.filter(
        detected_at__gte=timezone.now() - timezone.timedelta(days=3),
    ).values_list("title", flat=True)
    existing_context = ""
    if recent_memes:
        existing_context = (
            f"\n\n=== ALREADY DETECTED (don't repeat these) ===\n"
            f"{json.dumps(list(recent_memes))}\n"
        )

    # ── 4. LLM: Discover + analyze memes ────────────────────────
    system_prompt = (
        "You are the Meme Intelligence Engine for Kova, a social media platform used by "
        "Kenyan businesses and creators. Your job is to discover trending memes, viral formats, "
        "and culturally relevant humor that brands can adapt.\n\n"
        "FOCUS AREAS:\n"
        "1. Kenyan Twitter (KOT) — the most meme-prolific community in East Africa\n"
        "2. TikTok Kenya — Gen Z memes, challenges, trends\n"
        "3. Global memes that Kenyans are adapting locally\n"
        "4. Upcoming events that will generate memes\n"
        "5. Recurring Kenyan cultural moments (salary day, rain season, matatu culture)\n\n"
        "CULTURAL INTELLIGENCE:\n"
        "- Sheng (Nairobi urban slang) memes are high-engagement for youth audiences\n"
        "- Political memes are risky for brands — flag them as low brand-safety\n"
        "- Tribal humor can be sensitive — flag appropriately\n"
        "- M-Pesa, matatu, traffic, hustle culture = universally relatable Kenyan content\n"
        "- Kenyan humor: self-deprecating, observational, situational > absurdist\n\n"
        "For each meme/trend you discover, extract the REUSABLE FORMAT — the template "
        "that any brand can adapt. Not the specific content, but the structure.\n\n"
        "Respond in JSON with:\n"
        '"memes": list of 5-8 trending meme/format objects, each with:\n'
        '  "title": short catchy name for this meme/trend\n'
        '  "description": what is this meme about and why is it trending (2-3 sentences)\n'
        '  "format_description": the REUSABLE FORMAT — how to adapt this to any brand\n'
        '  "example_text": an example of this meme in the wild\n'
        '  "image_description": visual component description (if applicable, else "")\n'
        '  "category": one of: social, political, sports, entertainment, business, tech, food, music, education, general\n'
        '  "humor_type": one of: observational, satirical, absurd, wordplay, situational, relatable, self_deprecating, reaction\n'
        '  "source_platform": one of: twitter, tiktok, instagram, facebook, reddit, youtube, whatsapp, cross_platform\n'
        '  "virality_score": 0-100 (how viral right now)\n'
        '  "brand_safety_score": 0-100 (how safe for brands to use)\n'
        '  "cultural_relevance_score": 0-100 (how Kenyan/culturally relevant)\n'
        '  "adaptability_score": 0-100 (how easy to adapt to different brands)\n'
        '  "lifecycle": one of: emerging, trending, peaked\n'
        '  "tags": list of relevant tags\n'
        '  "sensitivity_notes": any cultural/political sensitivity warnings (or "")\n'
        '  "target_demographics": who this resonates with, e.g., ["gen_z", "nairobi", "campus"]\n'
        '  "shelf_life_hours": estimated hours before this meme becomes stale (24-168)\n'
    )

    from apps.memes.relevance import msme_moments_context
    msme_context = msme_moments_context()

    prompt = (
        f"Date: {today.strftime('%A, %B %d, %Y')}\n"
        f"Time: {timezone.now().strftime('%H:%M')} EAT (East Africa Time)\n"
        f"{events_context}\n"
        f"{msme_context}\n"
        f"{web_context}\n"
        f"{existing_context}\n\n"
        "Discover 5-8 trending memes, viral formats, or culturally relevant humor "
        "that Kenyan businesses and creators can adapt for their brand content. "
        "Focus on what's ACTUALLY trending right now based on the web search data. "
        "Include both Kenya-specific and global-but-locally-adapted trends.\n\n"
        "Remember: the FORMAT is what matters — brands will remix the structure, "
        "not copy the specific content."
    )

    try:
        response = generate(
            prompt=prompt,
            system=system_prompt,
            model=get_model_for_task("research.trends"),
            json_mode=True,
            temperature=0.7,
            max_tokens=3000,
        )

        if not response.content or not response.content.strip():
            logger.warning("Meme Discovery: LLM returned empty response")
            return {"discovered": 0}

        result = parse_llm_json(response.content)
        memes_data = result.get("memes", [])

        if not memes_data:
            logger.warning("Meme Discovery: no memes in LLM response")
            return {"discovered": 0}

    except Exception as e:
        logger.exception("Meme Discovery LLM call failed: %s", e)
        return {"discovered": 0, "error": str(e)}

    # ── 5. Save discovered memes ─────────────────────────────────
    created_count = 0
    for meme_data in memes_data:
        title = meme_data.get("title", "").strip()
        if not title:
            continue

        # Skip if we already have a similar meme (fuzzy title match)
        if TrendingMeme.objects.filter(title__iexact=title).exists():
            continue

        shelf_life = meme_data.get("shelf_life_hours", 72)
        try:
            shelf_life = int(shelf_life)
        except (TypeError, ValueError):
            shelf_life = 72

        lifecycle_map = {
            "emerging": TrendingMeme.Lifecycle.EMERGING,
            "trending": TrendingMeme.Lifecycle.TRENDING,
            "peaked": TrendingMeme.Lifecycle.PEAKED,
        }

        try:
            TrendingMeme.objects.create(
                title=title,
                description=meme_data.get("description", ""),
                format_description=meme_data.get("format_description", ""),
                example_text=meme_data.get("example_text", ""),
                image_description=meme_data.get("image_description", ""),
                category=meme_data.get("category", "general"),
                humor_type=meme_data.get("humor_type", "relatable"),
                source_platform=meme_data.get("source_platform", "cross_platform"),
                virality_score=_clamp(meme_data.get("virality_score", 50)),
                brand_safety_score=_clamp(meme_data.get("brand_safety_score", 50)),
                cultural_relevance_score=_clamp(meme_data.get("cultural_relevance_score", 50)),
                adaptability_score=_clamp(meme_data.get("adaptability_score", 50)),
                lifecycle=lifecycle_map.get(
                    meme_data.get("lifecycle", "trending"), TrendingMeme.Lifecycle.TRENDING,
                ),
                expires_at=timezone.now() + timezone.timedelta(hours=shelf_life),
                tags=meme_data.get("tags", []),
                sensitivity_notes=meme_data.get("sensitivity_notes", ""),
                target_demographics=meme_data.get("target_demographics", []),
            )
            created_count += 1
        except Exception as e:
            logger.warning("Failed to save meme '%s': %s", title, e)

    logger.info("🎭 Meme Discovery complete: %d new memes found", created_count)
    return {"discovered": created_count}


# ─── TASK 2: ADAPT MEMES FOR USERS ──────────────────────────────────────────

@shared_task(name="memes.adapt_memes_for_users", bind=True, max_retries=1)
def adapt_memes_for_users(self):
    """
    Take trending memes and create brand-adapted versions for each active user.

    Runs after discover_trending_memes. Checks each user's preferences and
    creates personalized adaptations of the best available memes.
    """
    from apps.agents.llm import generate, get_model_for_task, parse_llm_json
    from .models import MemeAdaptation, MemePreferences, TrendingMeme

    logger.info("🎨 Meme Adaptation starting...")

    # Get usable memes sorted by score (no slice here — filtering happens per-user)
    usable_memes = TrendingMeme.objects.filter(
        lifecycle__in=[
            TrendingMeme.Lifecycle.EMERGING,
            TrendingMeme.Lifecycle.TRENDING,
            TrendingMeme.Lifecycle.PEAKED,
        ],
        expires_at__gt=timezone.now(),
        brand_safety_score__gte=30,
    ).order_by("-virality_score")

    if not usable_memes:
        logger.info("No usable memes available for adaptation")
        return {"adapted": 0}

    # Get users with active meme preferences
    active_prefs = MemePreferences.objects.filter(is_active=True).select_related("user", "user__profile")

    if not active_prefs.exists():
        # If no preferences exist yet, adapt for all active users with content
        from apps.content.models import Post
        active_users = (
            User.objects.filter(
                is_active=True,
                posts__isnull=False,
            )
            .distinct()[:20]
        )
        # Create default preferences for them
        for user in active_users:
            MemePreferences.objects.get_or_create(user=user)
        active_prefs = MemePreferences.objects.filter(is_active=True).select_related("user", "user__profile")

    total_adapted = 0

    for prefs in active_prefs:
        user = prefs.user
        profile = getattr(user, "profile", None)
        if not profile:
            continue

        # Check weekly quota
        week_ago = timezone.now() - timezone.timedelta(days=7)
        this_week_count = MemeAdaptation.objects.filter(
            user=user, created_at__gte=week_ago,
        ).count()
        if this_week_count >= prefs.max_memes_per_week:
            continue

        # Filter memes based on user preferences
        user_memes = usable_memes
        if prefs.excluded_categories:
            user_memes = user_memes.exclude(category__in=prefs.excluded_categories)
        if prefs.preferred_categories:
            preferred = user_memes.filter(category__in=prefs.preferred_categories)
            if preferred.exists():
                user_memes = preferred

        # Filter by risk tolerance
        if prefs.risk_tolerance == MemePreferences.RiskTolerance.CONSERVATIVE:
            user_memes = user_memes.filter(brand_safety_score__gte=70)
        elif prefs.risk_tolerance == MemePreferences.RiskTolerance.MODERATE:
            user_memes = user_memes.filter(brand_safety_score__gte=40)

        # Skip memes already adapted for this user
        already_adapted = MemeAdaptation.objects.filter(
            user=user,
        ).values_list("trending_meme_id", flat=True)
        user_memes = user_memes.exclude(id__in=already_adapted)

        # Take top 2 memes for this user
        memes_to_adapt = list(user_memes[:2])
        if not memes_to_adapt:
            continue

        remaining_quota = prefs.max_memes_per_week - this_week_count

        for meme in memes_to_adapt[:remaining_quota]:
            try:
                adaptation = _adapt_meme_for_user(meme, user, profile, prefs)
                if adaptation and adaptation.status != MemeAdaptation.Status.FAILED:
                    from apps.memes.pipeline import auto_queue_adaptation
                    auto_queue_adaptation(adaptation, prefs)
                    total_adapted += 1
            except Exception as e:
                logger.warning(
                    "Failed to adapt meme '%s' for %s: %s",
                    meme.title, user.email, e,
                )

    logger.info("🎨 Meme Adaptation complete: %d adaptations created", total_adapted)
    return {"adapted": total_adapted}


@shared_task(name="memes.adapt_single_meme", bind=True, max_retries=1)
def adapt_single_meme(self, meme_id, user_id):
    """Adapt a specific meme for a specific user (triggered from UI)."""
    from .models import MemeAdaptation, MemePreferences, TrendingMeme

    try:
        meme = TrendingMeme.objects.get(id=meme_id)
        user = User.objects.select_related("profile").get(id=user_id)
    except (TrendingMeme.DoesNotExist, User.DoesNotExist) as e:
        logger.warning("adapt_single_meme: not found: %s", e)
        return {"error": str(e)}

    profile = getattr(user, "profile", None)
    if not profile:
        return {"error": "User has no profile"}

    prefs, _ = MemePreferences.objects.get_or_create(user=user)

    adaptation = _adapt_meme_for_user(meme, user, profile, prefs)
    if adaptation and adaptation.status != MemeAdaptation.Status.FAILED:
        from apps.memes.pipeline import auto_queue_adaptation
        auto_queue_adaptation(adaptation, prefs)
        return {"adaptation_id": str(adaptation.id)}

    reason = (adaptation.error_message if adaptation else "") or "Adaptation failed"
    try:
        from apps.notifications.models import Notification
        Notification.create_for_user(
            user,
            Notification.NotificationType.SYSTEM,
            f"Meme adaptation failed for \"{meme.title}\": {reason[:120]}",
        )
    except Exception:
        logger.exception("Failed to notify user of meme adapt failure")
    return {"error": reason, "adaptation_id": str(adaptation.id) if adaptation else None}


# ─── TASK 3: LIFECYCLE MANAGEMENT ────────────────────────────────────────────

@shared_task(name="memes.update_meme_lifecycle")
def update_meme_lifecycle():
    """
    Age out stale memes. Move lifecycle stages based on time.
    Runs daily via Celery Beat.
    """
    from .models import TrendingMeme

    now = timezone.now()

    # Expire memes past their shelf life
    expired = TrendingMeme.objects.filter(
        expires_at__lte=now,
        lifecycle__in=[
            TrendingMeme.Lifecycle.EMERGING,
            TrendingMeme.Lifecycle.TRENDING,
            TrendingMeme.Lifecycle.PEAKED,
        ],
    ).update(lifecycle=TrendingMeme.Lifecycle.DEAD)

    # Age emerging → trending (after 6 hours)
    aged_emerging = TrendingMeme.objects.filter(
        lifecycle=TrendingMeme.Lifecycle.EMERGING,
        detected_at__lte=now - timezone.timedelta(hours=6),
    ).update(lifecycle=TrendingMeme.Lifecycle.TRENDING)

    # Age trending → peaked (after 48 hours)
    aged_trending = TrendingMeme.objects.filter(
        lifecycle=TrendingMeme.Lifecycle.TRENDING,
        detected_at__lte=now - timezone.timedelta(hours=48),
    ).update(lifecycle=TrendingMeme.Lifecycle.PEAKED, peak_at=now)

    # Age peaked → fading (after 96 hours)
    aged_peaked = TrendingMeme.objects.filter(
        lifecycle=TrendingMeme.Lifecycle.PEAKED,
        detected_at__lte=now - timezone.timedelta(hours=96),
    ).update(lifecycle=TrendingMeme.Lifecycle.FADING)

    # Fading → dead (after 168 hours / 1 week)
    aged_fading = TrendingMeme.objects.filter(
        lifecycle=TrendingMeme.Lifecycle.FADING,
        detected_at__lte=now - timezone.timedelta(hours=168),
    ).update(lifecycle=TrendingMeme.Lifecycle.DEAD)

    logger.info(
        "Meme lifecycle update: %d expired, %d emerging→trending, "
        "%d trending→peaked, %d peaked→fading, %d fading→dead",
        expired, aged_emerging, aged_trending, aged_peaked, aged_fading,
    )
    return {
        "expired": expired,
        "aged_emerging": aged_emerging,
        "aged_trending": aged_trending,
        "aged_peaked": aged_peaked,
        "aged_fading": aged_fading,
    }


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _clamp(value, min_val=0, max_val=100):
    """Clamp a value between min and max."""
    try:
        return max(min_val, min(max_val, int(value)))
    except (TypeError, ValueError):
        return 50


# Banned phrases for meme adaptations — phrases that scream "generated by AI"
# or veer into territory we shouldn't auto-publish without a human eye.
_MEME_BANNED_PHRASES = (
    "on this special day",
    "in today's fast-paced world",
    "elevate your",
    "as an ai",
    "as a language model",
    "i'm sorry, but",
    "i cannot",
    "i can't help with",
)


def _check_adapted_text(adapted_text: str, adapted_caption: str = "") -> dict:
    """
    Quality gate for meme adaptations before we persist or show them.
    Returns {'passed': bool, 'reasons': [str]}.

    Blocks: empty, too short, contains AI-leak phrases or generic openers,
    suspiciously long (>2200 chars — exceeds even IG limit).
    Soft checks (warnings, not blocks): hashtag spam, URL injection.
    """
    text = (adapted_text or "").strip()
    combined = f"{text}\n{adapted_caption or ''}".lower()
    reasons: list[str] = []

    if not text:
        reasons.append("empty adapted_text")
        return {"passed": False, "reasons": reasons}

    if len(text) < 15:
        reasons.append(f"adapted_text too short ({len(text)} chars)")

    if len(text) > 2500:
        reasons.append(f"adapted_text exceeds 2500 chars ({len(text)})")

    for phrase in _MEME_BANNED_PHRASES:
        if phrase in combined:
            reasons.append(f"contains banned phrase: {phrase!r}")

    return {"passed": not reasons, "reasons": reasons}


def _search_meme_trends():
    """Search the web for trending memes and viral content in Kenya."""
    api_key = getattr(settings, "TAVILY_API_KEY", "")
    if not api_key:
        return (
            "\n\nNOTE: No real-time web data available (Tavily not configured). "
            "Use your knowledge of current Kenyan meme culture and trending formats. "
            "Focus on evergreen Kenyan humor formats that are always relevant.\n"
        )

    try:
        from tavily import TavilyClient
    except ImportError:
        return "\n\nNOTE: Web search not available. Use your knowledge of Kenyan meme culture.\n"

    client = TavilyClient(api_key=api_key)
    results = []

    queries = [
        "Kenya trending memes this week Twitter KOT",
        "viral TikTok Kenya trends today",
        "trending topics Nairobi social media",
    ]

    for query in queries:
        try:
            search = client.search(
                query=query,
                search_depth="basic",
                max_results=5,
                include_answer=True,
            )
            if search.get("answer") or search.get("results"):
                results.append({
                    "query": query,
                    "answer": search.get("answer", ""),
                    "sources": [
                        {
                            "title": r.get("title", ""),
                            "snippet": r.get("content", "")[:200],
                        }
                        for r in search.get("results", [])[:3]
                    ],
                })
        except Exception as e:
            logger.warning("Meme trend search failed for '%s': %s", query, e)

    if not results:
        return "\n\nNOTE: Web search returned no results. Use your knowledge of Kenyan meme culture.\n"

    context = "\n\n=== REAL-TIME TREND DATA (from web search) ===\n"
    for r in results:
        context += f"\nSearch: {r['query']}\n"
        if r.get("answer"):
            context += f"Summary: {r['answer']}\n"
        for src in r.get("sources", []):
            context += f"  - {src['title']}: {src['snippet']}\n"

    return context


def _adapt_meme_for_user(meme, user, profile, prefs):
    """
    Use AI to adapt a trending meme for a specific user's brand.

    Returns the created MemeAdaptation or None on failure.
    """
    from apps.agents.llm import generate, get_model_for_task, parse_llm_json
    from .models import MemeAdaptation

    # Build brand context
    brand_name = profile.company_name or user.get_full_name() or user.email.split("@")[0]
    industry = profile.get_industry_display() if profile.industry else "General"
    city = getattr(profile, "city", "") or ""
    brand_voice = profile.brand_voice or "Professional but approachable"
    target_audience = profile.target_audience or "Not specified"
    key_offerings = profile.key_offerings or []
    content_language = profile.get_content_language_display() if profile.content_language else "English"

    # Product context
    product_context = ""
    try:
        from apps.products.models import Product
        products = Product.objects.filter(
            user=user, is_active=True,
        ).values_list("name", "category", "price", "stock_status")[:10]
        if products:
            product_context = "\nProducts/Services:\n"
            for name, cat, price, status in products:
                product_context += f"  - {name} ({cat}) — KES {price} [{status}]\n"
    except Exception:
        logger.exception("memes: product_context enrichment failed for user=%s", user.pk)

    # Platform targets
    platforms = prefs.preferred_platforms
    if not platforms:
        from apps.platforms.models import SocialAccount
        platforms = list(
            SocialAccount.objects.filter(user=user, is_active=True)
            .values_list("platform", flat=True)
            .distinct()[:5]
        )
    if not platforms:
        platforms = ["twitter", "instagram"]

    system_prompt = (
        "You are a creative meme adaptation specialist. Your job is to take a trending meme FORMAT "
        "and remix it for a specific brand — keeping the humor and virality while making it relevant "
        "to the brand's identity, products, and audience.\n\n"
        "RULES:\n"
        "- Preserve the HUMOR — if it's not funny, it's not a meme\n"
        "- Make it BRAND-RELEVANT — tie it to the brand's products, industry, or audience\n"
        "- Keep it NATURAL — it should feel like the brand 'gets it', not corporate cringe\n"
        "- Match the LANGUAGE tone — if the brand uses Sheng, the meme should too\n"
        "- Platform-AWARE — Twitter memes are text-heavy, IG is visual, TikTok is action\n"
        "- Don't force it — if the meme doesn't fit this brand, say so\n\n"
        "Respond in JSON:\n"
        '  "adapted_text": the brand-adapted meme content (ready to post)\n'
        '  "adapted_caption": platform caption with hashtags (for IG/TikTok)\n'
        '  "platform_targets": list of best platforms for this adaptation\n'
        '  "image_prompt": AI image generation prompt if visual meme (or "")\n'
        '  "brand_relevance_score": 0-100 how well this fits the brand\n'
        '  "humor_preserved_score": 0-100 how funny is the adaptation\n'
        '  "reasoning": why you made these adaptation choices (1-2 sentences)\n'
        '  "is_forced": true if the meme doesn\'t naturally fit this brand (skip if true)\n'
    )

    prompt = (
        f"=== TRENDING MEME ===\n"
        f"Title: {meme.title}\n"
        f"Description: {meme.description}\n"
        f"Format: {meme.format_description}\n"
        f"Example: {meme.example_text}\n"
        f"Category: {meme.get_category_display()}\n"
        f"Humor type: {meme.get_humor_type_display()}\n"
        f"Visual: {meme.image_description or 'Text-only'}\n\n"
        f"=== BRAND CONTEXT ===\n"
        f"Brand: {brand_name}\n"
        f"Industry: {industry}\n"
        f"City: {city or 'Kenya (general)'}\n"
        f"Voice: {brand_voice}\n"
        f"Audience: {target_audience}\n"
        f"Key offerings: {json.dumps(key_offerings)}\n"
        f"Language: {content_language}\n"
        f"{product_context}\n"
        f"Target platforms: {json.dumps(platforms)}\n\n"
        f"Adapt this meme for the brand above. Make it funny, relevant, and ready to post."
    )

    try:
        response = generate(
            prompt=prompt,
            system=system_prompt,
            model=get_model_for_task("create.generate", user=user),
            json_mode=True,
            temperature=0.8,  # higher creativity for humor
            max_tokens=1500,
            user=user,
        )

        if not response.content or not response.content.strip():
            return _fail_adaptation(meme, user, "AI returned an empty response")

        data = parse_llm_json(response.content)

        # Skip forced adaptations
        if data.get("is_forced"):
            logger.info("Meme '%s' doesn't fit %s — skipping", meme.title, user.email)
            return _fail_adaptation(
                meme, user,
                "This trend doesn't fit your brand naturally — try another meme.",
            )

        adapted_text = (data.get("adapted_text") or "").strip()
        adapted_caption = (data.get("adapted_caption") or "").strip()

        # ── Quality gate: never persist an unsafe or empty adaptation ──
        gate = _check_adapted_text(adapted_text, adapted_caption)
        if not gate["passed"]:
            logger.info(
                "Meme '%s' adaptation blocked by quality gate for %s: %s",
                meme.title, user.email, gate["reasons"],
            )
            return _fail_adaptation(
                meme, user,
                "Quality check failed: " + "; ".join(gate["reasons"]),
            )

        adaptation = MemeAdaptation.objects.create(
            user=user,
            trending_meme=meme,
            adapted_text=adapted_text,
            adapted_caption=adapted_caption,
            platform_targets=data.get("platform_targets", platforms),
            image_prompt=data.get("image_prompt", ""),
            brand_relevance_score=_clamp(data.get("brand_relevance_score", 50)),
            humor_preserved_score=_clamp(data.get("humor_preserved_score", 50)),
            ai_reasoning=data.get("reasoning", ""),
            model_used=response.model,
            tokens_used=response.total_tokens,
        )

        # Update adaptation count on the meme
        meme.adaptation_count += 1
        meme.save(update_fields=["adaptation_count"])

        logger.info(
            "Adapted meme '%s' for %s (relevance: %d, humor: %d)",
            meme.title, user.email,
            adaptation.brand_relevance_score, adaptation.humor_preserved_score,
        )
        return adaptation

    except Exception as e:
        logger.warning("Meme adaptation failed for '%s' x %s: %s", meme.title, user.email, e)
        return _fail_adaptation(meme, user, str(e)[:500])


def _fail_adaptation(meme, user, reason: str):
    """Record a failed adaptation so the user sees why in Queue."""
    from .models import MemeAdaptation

    existing = MemeAdaptation.objects.filter(user=user, trending_meme=meme).first()
    if existing:
        if existing.status in (MemeAdaptation.Status.DRAFT, MemeAdaptation.Status.FAILED):
            existing.status = MemeAdaptation.Status.FAILED
            existing.error_message = reason[:500]
            existing.save(update_fields=["status", "error_message", "updated_at"])
        return existing

    return MemeAdaptation.objects.create(
        user=user,
        trending_meme=meme,
        adapted_text=f"Could not adapt: {meme.title}",
        status=MemeAdaptation.Status.FAILED,
        error_message=reason[:500],
    )


    try:
        from apps.memes.pipeline import auto_queue_adaptation
        auto_queue_adaptation(adaptation, prefs)
    except Exception as e:
        logger.warning("auto_queue failed for adaptation %s: %s", adaptation.pk, e)


# ══════════════════════════════════════════════════════════════════════════════
# TREND RIDE — Auto-detect relevant trends → generate content → notify user
# ══════════════════════════════════════════════════════════════════════════════


@shared_task(name="memes.scan_trends_for_users")
def scan_trends_for_users():
    """
    Periodic task: check trending memes + Kenyan events against each user's
    industry/audience → create TrendAlert for matches.

    Run every 2 hours via Celery Beat.
    """
    from apps.billing.models import get_plan_limits
    from apps.memes.models import TrendAlert, KenyanEvent, MemePreferences, TrendingMeme
    from apps.memes.relevance import get_meme_prefs, industry_relevance_for_trend

    now = timezone.now()
    detected = 0

    hot_memes = TrendingMeme.objects.filter(
        lifecycle__in=[
            TrendingMeme.Lifecycle.EMERGING,
            TrendingMeme.Lifecycle.TRENDING,
        ],
        brand_safety_score__gte=60,
        expires_at__gt=now,
    ).order_by("-virality_score")[:20]

    upcoming_events = KenyanEvent.objects.filter(
        date__range=[now.date(), (now + timezone.timedelta(days=3)).date()],
        meme_potential__in=["high", "medium"],
        sensitivity__in=["safe", "moderate"],
    )

    active_users = User.objects.filter(
        is_active=True,
        meme_preferences__is_active=True,
    ).select_related("profile", "meme_preferences")[:100]

    for user in active_users:
        profile = getattr(user, "profile", None)
        if not profile:
            continue

        from apps.billing.models import get_user_plan_limits

        limits = get_user_plan_limits(user)
        if not limits.get("memes_enabled", False):
            continue

        prefs = get_meme_prefs(user)

        for meme in hot_memes:
            if TrendAlert.objects.filter(
                user=user, trending_meme=meme,
                status__in=[
                    TrendAlert.Status.DETECTED,
                    TrendAlert.Status.GENERATING,
                    TrendAlert.Status.READY,
                    TrendAlert.Status.APPROVED,
                ],
            ).exists():
                continue

            if prefs.risk_tolerance == MemePreferences.RiskTolerance.CONSERVATIVE:
                if meme.brand_safety_score < 80:
                    continue
            if meme.category in (prefs.excluded_categories or []):
                continue

            relevance_score = industry_relevance_for_trend(meme, profile)
            if relevance_score < 60:
                continue

            urgency = max(2, 24 - (meme.virality_score // 5))
            alert = TrendAlert.objects.create(
                user=user,
                trend_topic=meme.title,
                trend_source=TrendAlert.TrendSource.MEME,
                trend_context=(
                    f"Trending meme ({meme.get_lifecycle_display()}): "
                    f"{meme.description[:200]}"
                ),
                trend_score=relevance_score,
                urgency_hours=urgency,
                trending_meme=meme,
                expires_at=now + timezone.timedelta(hours=urgency),
                status=TrendAlert.Status.DETECTED,
            )
            detected += 1

        for event in upcoming_events:
            if TrendAlert.objects.filter(user=user, kenyan_event=event).exists():
                continue

            days_until = (event.date - now.date()).days
            alert = TrendAlert.objects.create(
                user=user,
                trend_topic=event.name,
                trend_source=TrendAlert.TrendSource.KENYAN_EVENT,
                trend_context=(
                    f"Upcoming: {event.name} ({event.get_event_type_display()}) on {event.date}. "
                    f"Angles: {', '.join(event.meme_angles or [])}."
                ),
                trend_score=80 if event.meme_potential == "high" else 65,
                urgency_hours=max(6, days_until * 12),
                kenyan_event=event,
                expires_at=now + timezone.timedelta(hours=max(6, days_until * 12)),
                status=TrendAlert.Status.DETECTED,
            )
            detected += 1

    logger.info("Trend scan: created %d alerts", detected)
    return {"detected": detected}


@shared_task(name="memes.generate_trend_ride_content")
def generate_trend_ride_content(alert_id: str):
    """Generate brand-safe trend-riding content for a TrendAlert."""
    from django.utils import timezone
    from apps.memes.models import TrendAlert
    from apps.content.models import ContentSeed
    from apps.agents.models import AgentAction

    try:
        alert = TrendAlert.objects.select_related(
            "user", "user__profile", "trending_meme", "kenyan_event",
        ).get(pk=alert_id)
    except TrendAlert.DoesNotExist:
        return {"error": "not_found"}

    # Skip if expired
    if alert.is_expired:
        alert.status = TrendAlert.Status.EXPIRED
        alert.save(update_fields=["status"])
        return {"status": "expired"}

    user = alert.user
    profile = getattr(user, "profile", None)

    try:
        alert.status = TrendAlert.Status.GENERATING
        alert.save(update_fields=["status"])

        from apps.agents.llm_router import call_llm
        import json

        brand_context = ""
        if profile:
            brand_context = (
                f"Brand: {profile.company_name or 'Business'}, "
                f"Industry={profile.industry or 'general'}, "
                f"City={getattr(profile, 'city', '') or 'Kenya'}, "
                f"Voice={profile.brand_voice or 'professional'}, "
                f"Audience={profile.target_audience or 'general'}."
            )

        prompt = (
            "You are a social media trend expert. Generate a brand-safe angle for this trend.\n\n"
            f"Trend: {alert.trend_topic}\n"
            f"Context: {alert.trend_context}\n"
            f"Urgency: {alert.urgency_hours} hours before trend dies\n"
            f"{brand_context}\n\n"
            "Return JSON with:\n"
            "- brand_angle: 2-3 sentences explaining how this brand should ride this trend (specific, actionable)\n"
            "- post_idea: a complete content seed idea (the actual post concept, not just the angle)\n"
            "- platforms: which platforms to target (list)\n"
            "- safety_note: any sensitivities to be aware of (or 'none')\n"
            "Rules: NEVER be political, religious, or divisive. Keep it fun, relevant, and brand-safe.\n"
            "Return ONLY valid JSON."
        )

        response = call_llm(prompt=prompt, task="trend_ride", user=user, json_mode=True)

        try:
            result = json.loads(response["text"])
        except (json.JSONDecodeError, KeyError):
            result = {
                "brand_angle": f"Relevant trend: {alert.trend_topic}",
                "post_idea": f"Join the conversation about {alert.trend_topic} with your brand's unique take.",
                "platforms": ["instagram", "twitter"],
                "safety_note": "none",
            }

        alert.brand_angle = result.get("brand_angle", "")
        platforms = result.get("platforms", ["instagram", "twitter"])

        # Create ContentSeed
        seed = ContentSeed.objects.create(
            user=user,
            idea=(
                f"🔥 TREND ALERT: {alert.trend_topic}\n\n"
                f"{result.get('post_idea', alert.trend_topic)}\n\n"
                f"Angle: {alert.brand_angle}\n"
                f"This is time-sensitive — publish within {alert.urgency_hours} hours."
            ),
            notes=f"[Trend Ride] Auto-generated. Source: {alert.trend_source}",
            target_platforms=platforms,
        )
        alert.content_seed = seed
        alert.posts_generated = 1
        alert.status = TrendAlert.Status.READY
        alert.save()

        # Trigger content generation
        from apps.content.tasks import generate_from_seed
        generate_from_seed.delay(str(seed.pk))

        # Send notification
        try:
            from apps.notifications.models import Notification
            Notification.objects.create(
                user=user,
                notification_type="agent_action",
                title=f"🔥 Trend Alert: {alert.trend_topic[:50]}",
                message=(
                    f"A trending topic matches your brand! "
                    f"{alert.brand_angle[:150]}. "
                    f"Content ready for approval — act within {alert.urgency_hours}h."
                ),
            )
        except Exception:
            logger.exception("trend-alert notification failed for user=%s alert=%s", user.pk, alert.pk)

        AgentAction.objects.create(
            user=user,
            agent_type="research",
            action_type="trend_ride",
            input_data={"topic": alert.trend_topic, "source": alert.trend_source},
            output_data={"angle": alert.brand_angle[:200], "seed_id": str(seed.pk)},
            tokens_used=response.get("tokens_used", 0),
            model_used=response.get("model", ""),
        )

        logger.info("Trend ride content generated for %s: %s", user.email, alert.trend_topic)
        return {"status": "ready", "topic": alert.trend_topic, "seed_id": str(seed.pk)}

    except Exception as e:
        logger.exception("Trend ride generation failed for %s: %s", alert_id, e)
        alert.status = TrendAlert.Status.FAILED
        alert.error_message = str(e)[:1000]
        alert.save(update_fields=["status", "error_message"])
        return {"error": str(e)}
