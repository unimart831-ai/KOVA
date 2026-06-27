"""
Industry Playbooks — Pre-loaded intelligence for specific business verticals.

Solves the cold-start problem: new users get industry-specific Content DNA,
seed suggestions, posting strategies, and content calendars from day 1.

Each playbook includes:
  - content_dna_presets: Winning content attributes for the industry
  - seed_suggestions: Ready-to-use content ideas for the first week
  - content_calendar: Weekly content mix template
  - posting_strategy: Platform-specific advice
  - seasonal_events: Key dates and campaigns
  - competitor_benchmarks: What "good" looks like in this industry

Playbooks are loaded during onboarding when user selects their industry.
They feed into the Create Agent's system prompt via _get_industry_intelligence().
"""

import logging

logger = logging.getLogger(__name__)

PLAYBOOKS = {
    # ──────────────────────────────────────────────────────────────────────
    # Food & Restaurant
    # ──────────────────────────────────────────────────────────────────────
    "food_restaurant": {
        "name": "Food & Restaurant",
        "industries": ["food_restaurant"],
        "keywords": ["restaurant", "food", "cafe", "kitchen", "catering", "bakery", "chef"],
        "content_dna_presets": {
            "winning_formats": ["behind-the-scenes", "food-close-up", "customer-story", "process-video", "daily-special"],
            "winning_tones": ["mouth-watering", "casual-friendly", "local-pride", "storytelling"],
            "winning_hooks": [
                "This is what happens when...",
                "You haven't lived until you've tried...",
                "The secret behind our...",
                "Every morning at 5am, we...",
            ],
            "best_content_types": {
                "twitter": "Bold food opinions, quick polls, daily specials",
                "instagram": "Food close-ups, BTS kitchen shots, Reels of plating/cooking",
                "facebook": "Community posts, event announcements, customer stories",
                "linkedin": "Business growth story, supplier relationships, food industry insights",
                "tiktok": "Cooking process videos, taste tests, kitchen chaos, recipe reveals",
            },
        },
        "seed_suggestions": [
            "Show the story behind our signature dish — how we created it and why it's special",
            "A day in the life at our kitchen — the 5am starts, the prep, the first customer",
            "Customer spotlight — feature a regular who's been coming since day one",
            "The ingredients we source locally and why it matters for the taste",
            "Our team's favorite off-menu item that most customers don't know about",
            "What goes wrong in a restaurant kitchen (and how we handle it)",
            "Why we chose this location and what the neighborhood means to us",
        ],
        "content_calendar": {
            "monday": {"theme": "Behind the Scenes", "example": "Kitchen prep, team morning routine"},
            "tuesday": {"theme": "Tip Tuesday", "example": "Cooking tip, food pairing suggestion"},
            "wednesday": {"theme": "Customer Spotlight", "example": "Feature a regular, share their story"},
            "thursday": {"theme": "Throwback / Story", "example": "How we started, a milestone moment"},
            "friday": {"theme": "Weekend Special", "example": "Promote weekend offers, new dish"},
            "saturday": {"theme": "Live / Interactive", "example": "Poll, Q&A, weekend vibes"},
            "sunday": {"theme": "Community / Gratitude", "example": "Thank customers, share reviews"},
        },
        "posting_strategy": {
            "best_times": "11:30 AM (lunch decision), 5:30 PM (dinner decision), 8 PM (craving scroll)",
            "frequency": "5-7 posts per week across platforms",
            "platform_priority": ["instagram", "tiktok", "facebook", "twitter"],
            "key_insight": "Food content is visual-first. Invest in good photos. Close-ups with steam/texture outperform wide shots 3:1.",
        },
        "seasonal_events": [
            {"month": 1, "event": "New Year health/fresh start menus"},
            {"month": 2, "event": "Valentine's Day special menus/couples offers"},
            {"month": 4, "event": "Easter specials"},
            {"month": 6, "event": "Mid-year customer appreciation"},
            {"month": 8, "event": "Mashujaa Day (Oct 20) prep content"},
            {"month": 10, "event": "Mashujaa Day celebrations, year-end planning"},
            {"month": 12, "event": "Christmas/New Year menus, holiday catering"},
        ],
    },

    # ──────────────────────────────────────────────────────────────────────
    # Fashion & Beauty
    # ──────────────────────────────────────────────────────────────────────
    "creator_expert": {
        "name": "Creator & Expert Brand",
        "industries": ["creator"],
        "keywords": ["creator", "coach", "consultant", "speaker", "educator", "analyst", "newsletter"],
        "content_dna_presets": {
            "winning_formats": ["strong opinion", "personal lesson", "framework", "behind-the-scenes build", "case study"],
            "winning_tones": ["authoritative", "human", "practical", "thoughtful"],
            "winning_hooks": [
                "What nobody tells you about building a personal brand in Africa",
                "I used to believe X. I was wrong.",
                "The framework I keep coming back to when helping clients solve this",
                "If you're trying to grow on LinkedIn or X, start here",
            ],
            "best_content_types": {
                "twitter": "Strong opinions, short lessons, build-in-public updates, conversation starters",
                "linkedin": "Thought leadership, personal lessons, authority frameworks, client insights",
                "instagram": "Behind-the-scenes, story-led lessons, proof of work, quick explainers",
                "facebook": "Story posts, community takes, value-first explainers, event announcements",
                "tiktok": "Direct-to-camera explainers, myth busting, mini case studies",
            },
        },
        "seed_suggestions": [
            "Share a strong lesson from client work that changed how you think about your field",
            "Break down one framework or method you use repeatedly and why it works",
            "Tell the story behind a professional mistake that taught you something valuable",
            "Give your take on an industry belief most people repeat without questioning",
            "Show how you prepare, research, or work behind the scenes so people see the craft",
        ],
        "content_calendar": {
            "monday": {"theme": "Point of View", "example": "A strong opinion or market observation"},
            "tuesday": {"theme": "Framework", "example": "A practical model people can apply"},
            "wednesday": {"theme": "Proof", "example": "Client result, case study, or credibility builder"},
            "thursday": {"theme": "Behind the Work", "example": "How you think, prepare, or create"},
            "friday": {"theme": "Lesson Learned", "example": "A personal or professional lesson with a takeaway"},
            "saturday": {"theme": "Conversation", "example": "Ask a specific question that surfaces audience insight"},
            "sunday": {"theme": "Reset", "example": "A reflective post or plan for the coming week"},
        },
        "posting_strategy": {
            "best_times": "7 AM, 12 PM, and 6 PM in the audience's workday rhythm",
            "frequency": "4-6 posts per week with consistency over volume",
            "platform_priority": ["linkedin", "twitter", "instagram", "facebook"],
            "key_insight": "Creators and experts win by being memorable and useful. Strong point of view plus proof beats generic motivation.",
        },
        "seasonal_events": [
            {"month": 1, "event": "Year-ahead positioning, predictions, and planning frameworks"},
            {"month": 6, "event": "Mid-year lessons, audits, and reset content"},
            {"month": 12, "event": "Year in review, what changed, and what matters next"},
        ],
    },

    "fashion_beauty": {
        "name": "Fashion & Beauty",
        "industries": ["ecommerce", "fashion_beauty", "salon_beauty", "wholesale_retail"],
        "keywords": ["fashion", "clothing", "beauty", "salon", "makeup", "style", "boutique", "hair"],
        "content_dna_presets": {
            "winning_formats": ["outfit-of-the-day", "transformation", "styling-tips", "trend-alert", "customer-wearing"],
            "winning_tones": ["aspirational", "empowering", "trendy", "relatable"],
            "winning_hooks": [
                "This look is about to be everywhere...",
                "3 ways to style one piece",
                "Stop sleeping on this trend",
                "The outfit that gets me compliments every time",
            ],
            "best_content_types": {
                "twitter": "Trend commentary, bold fashion opinions, style debates",
                "instagram": "OOTD, flat lays, Reels transitions, carousel styling tips",
                "facebook": "New arrivals, sale announcements, customer transformations",
                "linkedin": "Fashion business insights, brand story, industry trends",
                "tiktok": "Get ready with me, outfit transformations, trend recreations",
            },
        },
        "seed_suggestions": [
            "3 ways to style our best-selling piece for different occasions",
            "The trend we're seeing everywhere right now — and how to wear it affordably",
            "Customer transformation spotlight — before and after styling session",
            "What's in our new collection and the inspiration behind it",
            "Honest take: which fashion trends are worth investing in vs. skipping",
            "Behind the scenes of a photoshoot or new collection prep",
            "Style tips for [season] that work for Kenyan weather",
        ],
        "content_calendar": {
            "monday": {"theme": "New Week, New Look", "example": "Outfit inspiration to start the week"},
            "tuesday": {"theme": "Trend Talk", "example": "Break down a current trend"},
            "wednesday": {"theme": "Style Tips", "example": "How-to content, pairing advice"},
            "thursday": {"theme": "Customer Feature", "example": "Repost customer photos, reviews"},
            "friday": {"theme": "Weekend Ready", "example": "Going out looks, weekend casual"},
            "saturday": {"theme": "Sale / Promo", "example": "Weekend offers, limited editions"},
            "sunday": {"theme": "Self-Care Sunday", "example": "Beauty routine, skincare, feel-good content"},
        },
        "posting_strategy": {
            "best_times": "8 AM (morning scroll), 12 PM (lunch break), 7 PM (evening planning)",
            "frequency": "7-10 posts per week (Instagram-heavy)",
            "platform_priority": ["instagram", "tiktok", "facebook", "twitter"],
            "key_insight": "User-generated content (customers wearing your products) drives 4x more trust than brand-shot content. Encourage and repost.",
        },
        "seasonal_events": [
            {"month": 2, "event": "Valentine's Day outfits/gift guides"},
            {"month": 3, "event": "Transition to warm weather styles"},
            {"month": 6, "event": "Mid-year clearance, new collection launches"},
            {"month": 10, "event": "Mashujaa Day, Kenyan fashion celebration"},
            {"month": 11, "event": "Black Friday/holiday shopping prep"},
            {"month": 12, "event": "Holiday party looks, New Year's Eve outfits, gift guides"},
        ],
    },

    # ──────────────────────────────────────────────────────────────────────
    # Real Estate
    # ──────────────────────────────────────────────────────────────────────
    "real_estate": {
        "name": "Real Estate",
        "industries": ["real_estate"],
        "keywords": ["real estate", "property", "realtor", "housing", "apartment", "rental", "land"],
        "content_dna_presets": {
            "winning_formats": ["property-tour", "market-update", "client-testimonial", "neighborhood-guide", "tips-for-buyers"],
            "winning_tones": ["authoritative", "helpful", "local-expert", "trustworthy"],
            "winning_hooks": [
                "This property just listed and it won't last...",
                "The one thing nobody tells you about buying property in Nairobi",
                "I've sold 50+ properties. Here's the #1 mistake buyers make",
                "This neighborhood is about to blow up. Here's why.",
            ],
            "best_content_types": {
                "twitter": "Market hot takes, listing teasers, quick tips",
                "instagram": "Property tours (Reels), aerial shots, before/after renovations",
                "facebook": "Listings with details, community posts, virtual open houses",
                "linkedin": "Market analysis, investment insights, industry commentary",
                "tiktok": "Property walkthrough tours, neighborhood vlogs, real estate myths busted",
            },
        },
        "seed_suggestions": [
            "Virtual tour of our newest listing — walk through every room",
            "Market update: what's happening with property prices in [area] this quarter",
            "Client success story — how we found the perfect home for [family type]",
            "5 things to check before buying any property in Kenya",
            "Neighborhood guide: why [area] is the best place to invest right now",
            "Common mistakes first-time property buyers make (and how to avoid them)",
            "The real cost of buying a home — beyond the asking price",
        ],
        "content_calendar": {
            "monday": {"theme": "Market Monday", "example": "Market stats, trends, price updates"},
            "tuesday": {"theme": "Property Tour", "example": "Video walkthrough of a listing"},
            "wednesday": {"theme": "Tips & Education", "example": "Buyer/seller tips, mortgage advice"},
            "thursday": {"theme": "Client Story", "example": "Testimonial, closing day celebration"},
            "friday": {"theme": "Featured Listing", "example": "Highlight a property with key details"},
            "saturday": {"theme": "Neighborhood Spotlight", "example": "Why this area, amenities, lifestyle"},
            "sunday": {"theme": "Dream Home Sunday", "example": "Aspirational content, investment vision"},
        },
        "posting_strategy": {
            "best_times": "7 AM (morning commute research), 1 PM (lunch break), 6 PM (evening browsing)",
            "frequency": "5-7 posts per week",
            "platform_priority": ["instagram", "facebook", "tiktok", "linkedin"],
            "key_insight": "Video tours get 5x more engagement than photo listings. Always show, don't tell. Drone/aerial shots signal professionalism.",
        },
        "seasonal_events": [
            {"month": 1, "event": "New year property goals, investment planning"},
            {"month": 3, "event": "First quarter market review"},
            {"month": 6, "event": "Mid-year investment opportunities"},
            {"month": 9, "event": "End of year rush, tax planning content"},
            {"month": 12, "event": "Year in review, market predictions for next year"},
        ],
    },

    # ──────────────────────────────────────────────────────────────────────
    # Tech & SaaS
    # ──────────────────────────────────────────────────────────────────────
    "tech_saas": {
        "name": "Tech & SaaS",
        "industries": ["saas"],
        "keywords": ["tech", "software", "saas", "startup", "app", "developer", "platform"],
        "content_dna_presets": {
            "winning_formats": ["product-update", "founder-story", "how-to-tutorial", "industry-take", "customer-case-study"],
            "winning_tones": ["thought-leadership", "transparent", "builder-energy", "data-driven"],
            "winning_hooks": [
                "We just shipped something our users have been asking for...",
                "Here's what building a startup in Nairobi actually looks like",
                "The conventional wisdom about [X] is wrong. Here's the data.",
                "We lost 30% of users last month. Here's what we learned.",
            ],
            "best_content_types": {
                "twitter": "Hot takes, build-in-public updates, industry debates, tweetstorms",
                "instagram": "Team photos, office life, product screenshots, founder stories",
                "facebook": "Product announcements, community building, event promotion",
                "linkedin": "Thought leadership, hiring posts, case studies, industry analysis",
                "tiktok": "Day-in-the-life of a founder, product demos, tech explainers",
            },
        },
        "seed_suggestions": [
            "What we shipped this week and why it matters for our users",
            "The biggest lesson from our last product launch — what went right and wrong",
            "How one of our customers used our product to solve [specific problem]",
            "Building a tech company in Kenya — the realities nobody talks about",
            "Our take on [industry trend] and what it means for [target audience]",
            "The tech stack behind our product — and why we chose each piece",
            "A mistake we made early on that cost us time/money — and the fix",
        ],
        "content_calendar": {
            "monday": {"theme": "Build Update", "example": "What we're working on this week"},
            "tuesday": {"theme": "Tutorial / How-To", "example": "Teach users something valuable"},
            "wednesday": {"theme": "Industry Take", "example": "Hot take on a trend or news"},
            "thursday": {"theme": "Customer Story", "example": "Case study or testimonial"},
            "friday": {"theme": "Founder Friday", "example": "Personal story, lessons learned"},
            "saturday": {"theme": "Community", "example": "Engage with replies, repost users"},
            "sunday": {"theme": "Week Ahead", "example": "Preview upcoming features/events"},
        },
        "posting_strategy": {
            "best_times": "8 AM (morning tech scroll), 12 PM (lunch learning), 5 PM (end of day catch-up)",
            "frequency": "5-7 posts per week (LinkedIn + Twitter heavy)",
            "platform_priority": ["twitter", "linkedin", "instagram", "tiktok"],
            "key_insight": "Transparency wins. 'Here's what we built' beats 'We're excited to announce' every time. Show the work, not just the result.",
        },
        "seasonal_events": [
            {"month": 1, "event": "Year kickoff, product roadmap teasers"},
            {"month": 3, "event": "Q1 review, user milestone celebrations"},
            {"month": 6, "event": "Mid-year product review, conference season"},
            {"month": 9, "event": "Planning season, pricing/plan updates"},
            {"month": 12, "event": "Year in review, wrapped-style user stats"},
        ],
    },

    # ──────────────────────────────────────────────────────────────────────
    # Professional Services & Consulting
    # ──────────────────────────────────────────────────────────────────────
    "professional_services": {
        "name": "Professional Services",
        "industries": ["consulting", "agency", "finance", "education", "health"],
        "keywords": ["consulting", "agency", "legal", "accounting", "coaching", "training", "advisory"],
        "content_dna_presets": {
            "winning_formats": ["expert-tip", "myth-busting", "case-study", "framework", "client-result"],
            "winning_tones": ["authoritative", "educational", "approachable-expert", "problem-solver"],
            "winning_hooks": [
                "Most businesses get this wrong about [topic]...",
                "I've consulted for 50+ companies. The #1 pattern I see is...",
                "Here's a framework I use with every client:",
                "Your [accountant/lawyer/advisor] should have told you this",
            ],
            "best_content_types": {
                "twitter": "Quick tips, industry hot takes, frameworks in thread form",
                "instagram": "Carousel infographics, quote cards, behind-the-scenes of consulting",
                "facebook": "Longer educational posts, event promotion, client success stories",
                "linkedin": "Thought leadership, frameworks, case studies, hiring/growth updates",
                "tiktok": "Quick explainers, myth-busting, day-in-the-life of a consultant",
            },
        },
        "seed_suggestions": [
            "The 3-step framework I use with every new client to identify their biggest bottleneck",
            "A common misconception in our industry — and the truth behind it",
            "Client case study: how we helped [type of business] achieve [specific result]",
            "5 questions every business should ask before hiring a [consultant/agency/advisor]",
            "What I've learned from working with 50+ businesses in Kenya",
            "The one piece of advice I wish I'd gotten when starting my practice",
            "Industry trends that will affect your business this year — and how to prepare",
        ],
        "content_calendar": {
            "monday": {"theme": "Expert Insight", "example": "Share a proven framework or methodology"},
            "tuesday": {"theme": "Myth Buster", "example": "Debunk a common industry misconception"},
            "wednesday": {"theme": "Case Study", "example": "Client result with specific numbers"},
            "thursday": {"theme": "Quick Tip", "example": "One actionable piece of advice"},
            "friday": {"theme": "Industry News", "example": "Commentary on a recent development"},
            "saturday": {"theme": "Personal Story", "example": "Your journey, lessons learned"},
            "sunday": {"theme": "Week Prep", "example": "Help audience prepare for the week"},
        },
        "posting_strategy": {
            "best_times": "7:30 AM (morning learning), 12:30 PM (lunch education), 6 PM (professional development)",
            "frequency": "4-6 posts per week (LinkedIn-heavy)",
            "platform_priority": ["linkedin", "twitter", "instagram", "facebook"],
            "key_insight": "Authority is built through specificity. 'I helped a client increase revenue 34%' beats 'We help businesses grow' every time. Use real numbers.",
        },
        "seasonal_events": [
            {"month": 1, "event": "New year business planning, goal-setting content"},
            {"month": 3, "event": "Tax season (if relevant), Q1 strategy check-in"},
            {"month": 6, "event": "Mid-year review, strategy adjustment content"},
            {"month": 9, "event": "Q4 planning, budget season preparation"},
            {"month": 12, "event": "Year wrap-up, planning for next year"},
        ],
    },
}


def get_playbook_for_industry(industry: str, company_name: str = "", brand_voice: str = "") -> dict | None:
    """
    Match a user's industry to the best playbook.
    Checks exact industry code match first, then falls back to keyword matching
    against company_name and brand_voice.
    """
    # Direct industry code match
    for key, playbook in PLAYBOOKS.items():
        if industry in playbook["industries"]:
            return playbook

    # Keyword matching on company name / brand voice
    search_text = f"{company_name} {brand_voice}".lower()
    for key, playbook in PLAYBOOKS.items():
        for keyword in playbook.get("keywords", []):
            if keyword in search_text:
                return playbook

    return None


def get_playbook_intelligence(user) -> str:
    """
    Generate a formatted intelligence briefing from the user's industry playbook.
    Injected into the Create Agent's system prompt for new users who don't yet
    have Content DNA from published posts.

    Returns empty string if no matching playbook or user has enough real data.
    """
    from apps.content.models import Post

    # Skip if user already has sufficient real performance data
    published_count = Post.objects.filter(
        user=user,
        status=Post.Status.PUBLISHED,
    ).count()
    if published_count >= 15:
        # After 15 published posts, real Content DNA takes over
        return ""

    try:
        profile = user.profile
    except Exception:
        return ""

    playbook = get_playbook_for_industry(
        industry=profile.industry,
        company_name=profile.company_name,
        brand_voice=profile.brand_voice,
    )
    if not playbook:
        return ""

    dna = playbook["content_dna_presets"]
    strategy = playbook["posting_strategy"]
    calendar = playbook["content_calendar"]

    parts = [
        f"## INDUSTRY PLAYBOOK: {playbook['name']}",
        f"(Pre-loaded intelligence — will be replaced by real Content DNA after ~15 posts)\n",
    ]

    # Winning formats
    parts.append("### What works in this industry:")
    for fmt in dna["winning_formats"]:
        parts.append(f"  - Format: **{fmt}**")
    parts.append("")

    # Winning tones
    parts.append("### Tones that resonate:")
    for tone in dna["winning_tones"]:
        parts.append(f"  - {tone}")
    parts.append("")

    # Platform-specific advice
    parts.append("### Platform-specific content strategy:")
    for platform, advice in dna.get("best_content_types", {}).items():
        parts.append(f"  - **{platform}**: {advice}")
    parts.append("")

    # Hooks
    parts.append("### Proven hook patterns (adapt, don't copy):")
    for hook in dna["winning_hooks"]:
        parts.append(f"  - \"{hook}\"")
    parts.append("")

    # Weekly rhythm
    parts.append("### Recommended content calendar:")
    for day, info in calendar.items():
        parts.append(f"  - **{day.capitalize()}**: {info['theme']} — {info['example']}")
    parts.append("")

    # Key insight
    parts.append(f"### Key insight: {strategy['key_insight']}")
    parts.append(f"### Recommended posting: {strategy['frequency']}")
    parts.append(f"### Best times: {strategy['best_times']}")

    # How many more posts until real DNA kicks in
    remaining = max(0, 15 - published_count)
    parts.append(f"\n*{remaining} more published posts until real performance data replaces these presets.*")

    return "\n".join(parts)


def get_seed_suggestions(user) -> list[dict]:
    """
    Return dynamic content suggestions from AI agents, competitor insights,
    and AI-generated business-goal-aware ideas (cached).

    Each suggestion is a dict: {"text": str, "source": "trend"|"competitor"|"ai"}
    """
    suggestions = []

    try:
        profile = user.profile
    except Exception:
        return []

    # 1. Research Agent — latest trend discoveries
    try:
        from apps.agents.models import AgentAction

        latest_research = (
            AgentAction.objects.filter(
                user=user,
                agent_type="research",
                action_type="discover_trends",
                status="completed",
            )
            .order_by("-created_at")
            .values_list("output_data", flat=True)
            .first()
        )

        if latest_research and isinstance(latest_research, dict):
            for topic in latest_research.get("trending_topics", [])[:4]:
                angle = topic.get("suggested_angle", "")
                if angle:
                    suggestions.append({"text": angle, "source": "trend"})

            for brief in latest_research.get("opportunity_briefs", [])[:2]:
                title = brief.get("title", "")
                if title:
                    suggestions.append({"text": title, "source": "trend"})
    except Exception:
        logger.exception("playbooks: research-trend suggestions failed for user=%s", user.pk)

    # 2. Competitor insights — unacted content gap ideas
    try:
        from apps.analytics.models import CompetitorInsight

        gap_ideas = (
            CompetitorInsight.objects.filter(
                user=user,
                is_acted_on=False,
                is_dismissed=False,
                suggested_content_idea__isnull=False,
            )
            .exclude(suggested_content_idea="")
            .order_by("-created_at")
            .values_list("suggested_content_idea", flat=True)[:3]
        )

        for idea in gap_ideas:
            suggestions.append({"text": idea, "source": "competitor"})
    except Exception:
        logger.exception("playbooks: competitor-gap suggestions failed for user=%s", user.pk)

    # 3. AI-generated suggestions from business goals, products & context (cached)
    if len(suggestions) < 6:
        remaining = 8 - len(suggestions)
        ai_ideas = _get_ai_generated_suggestions(user, profile, max_count=remaining)
        suggestions.extend(ai_ideas)

    return suggestions


def _get_ai_generated_suggestions(user, profile, max_count=6) -> list[dict]:
    """
    Generate personalised content suggestions using the LLM, grounded in
    the user's business goals, products, audience, recent performance,
    and the current date (seasonality).  Results are cached per-user for
    6 hours so the Studio page loads instantly.
    """
    import json
    import logging

    from django.core.cache import cache

    logger = logging.getLogger(__name__)

    cache_key = f"ai_seed_suggestions:{user.pk}"
    cached = cache.get(cache_key)
    if cached:
        return cached[:max_count]

    # ── Gather business context ──────────────────────────────────────
    try:
        from django.utils import timezone

        from apps.content.models import ContentSeed, Post
        from apps.products.models import Product

        goals = getattr(profile, "goals", []) or []
        pillars = getattr(profile, "content_pillars", []) or []
        offerings = getattr(profile, "key_offerings", []) or []
        audience = getattr(profile, "target_audience", "") or ""
        voice = getattr(profile, "brand_voice", "") or ""
        industry = getattr(profile, "industry", "") or ""
        company = getattr(profile, "company_name", "") or ""
        language = getattr(profile, "content_language", "en") or "en"

        # Products — featured first, then recent
        products_qs = Product.objects.filter(user=user, is_active=True)
        featured = list(
            products_qs.filter(is_featured=True)
            .values_list("name", flat=True)[:5]
        )
        other_products = list(
            products_qs.exclude(is_featured=True)
            .order_by("-created_at")
            .values_list("name", flat=True)[:5]
        )

        # Recent seeds — avoid repetition
        recent_ideas = list(
            ContentSeed.objects.filter(user=user)
            .order_by("-created_at")
            .values_list("idea", flat=True)[:8]
        )

        # Top-performing published posts (by engagement rate)
        top_posts = list(
            Post.objects.filter(user=user, status=Post.Status.PUBLISHED)
            .select_related("metrics")
            .order_by("-metrics__engagement_rate")
            .values_list("content_text", flat=True)[:5]
        )

        # Connected platforms
        platforms = list(
            user.social_accounts.filter(is_active=True)
            .values_list("platform", flat=True)
            .distinct()
        )

        today = timezone.now().date()
    except Exception:
        logger.exception("AI suggestions: failed to gather context for %s", user.pk)
        return _static_playbook_fallback(profile, max_count)

    # ── Build LLM prompt ─────────────────────────────────────────────
    prompt = (
        f"Date: {today.strftime('%A, %B %d, %Y')}\n\n"
        f"Business: {company}\n"
        f"Industry: {industry}\n"
        f"Brand voice: {voice}\n"
        f"Target audience: {audience}\n"
        f"Business goals: {json.dumps(goals)}\n"
        f"Content pillars: {json.dumps(pillars)}\n"
        f"Key offerings: {json.dumps(offerings)}\n"
        f"Featured products: {json.dumps(featured)}\n"
        f"Other products: {json.dumps(other_products)}\n"
        f"Connected platforms: {json.dumps(platforms)}\n"
        f"Content language: {language}\n\n"
        f"Recent content ideas (AVOID repeating these):\n"
        f"{json.dumps([i[:120] for i in recent_ideas])}\n\n"
        f"Top-performing post themes (lean into what works):\n"
        f"{json.dumps([t[:120] for t in top_posts])}\n\n"
        "Generate 8 fresh, specific, and actionable content ideas for this "
        "business. Each idea should be a single sentence that could be dropped "
        "straight into a content creation tool.\n\n"
        "Rules:\n"
        "- At least 2 ideas must directly promote specific products/services listed above\n"
        "- At least 2 ideas must advance the stated business goals\n"
        "- At least 1 idea should ride a current trend or seasonal hook for the date above\n"
        "- Mix content formats: posts, carousels, reels, stories, threads\n"
        "- Be SPECIFIC to this business — no generic 'share a tip' ideas\n"
        "- Match the brand voice described above\n"
        "- Do NOT repeat the recent content ideas listed above\n\n"
        'Respond ONLY with valid JSON: {"suggestions": ["idea 1", "idea 2", ...]}'
    )

    system = (
        "You are a world-class social media strategist. Generate content ideas "
        "that are specific, creative, and directly tied to this business's goals, "
        "products, and audience. Every idea should feel tailor-made, not templated."
    )

    # ── Call LLM ─────────────────────────────────────────────────────
    try:
        from apps.agents.llm import generate, get_model_for_task, parse_llm_json

        response = generate(
            prompt=prompt,
            system=system,
            model=get_model_for_task("research.suggestions", user=user),
            json_mode=True,
            temperature=0.8,
            max_tokens=1200,
        )

        result = parse_llm_json(response.content)
        raw_suggestions = result.get("suggestions", [])
        if not isinstance(raw_suggestions, list) or not raw_suggestions:
            raise ValueError("Empty or invalid suggestions list")

        ai_suggestions = [
            {"text": str(s).strip(), "source": "ai"}
            for s in raw_suggestions
            if isinstance(s, str) and s.strip()
        ][:8]

        # Cache for 6 hours
        cache.set(cache_key, ai_suggestions, timeout=6 * 60 * 60)
        logger.info(
            "AI suggestions: generated %d ideas for %s", len(ai_suggestions), user.pk
        )
        return ai_suggestions[:max_count]

    except Exception:
        logger.exception("AI suggestions: LLM call failed for %s", user.pk)
        return _static_playbook_fallback(profile, max_count)


def _static_playbook_fallback(profile, max_count=6) -> list[dict]:
    """Last-resort fallback to static industry playbook suggestions."""
    playbook = get_playbook_for_industry(
        industry=getattr(profile, "industry", ""),
        company_name=getattr(profile, "company_name", ""),
        brand_voice=getattr(profile, "brand_voice", ""),
    )
    if not playbook:
        return []
    return [
        {"text": s, "source": "playbook"}
        for s in playbook.get("seed_suggestions", [])[:max_count]
    ]
