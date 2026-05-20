"""
Create Agent — Strategic Content Intelligence Engine.

Not just a copywriter. This agent thinks like a content strategist:
1. Analyzes the raw idea through multiple strategic lenses
2. Determines the best angle and framework for EACH platform independently
3. Engineers engagement hooks and CTAs per platform's unique psychology
4. Generates content that creates genuine VALUE — not filler

Architecture:
  ContentSeed → strategic_analysis → platform_strategy → content_generation → Post objects

The agent is called:
  1. Synchronously via Celery task when user submits a seed
  2. Daily by the Chief Strategist (Sprint 10) for queue generation
"""

import json
import logging
import re
from datetime import datetime, timedelta, timezone

from django.utils import timezone as dj_timezone

from apps.agents.llm import generate, get_model_for_task, LLMResponse, parse_llm_json
from apps.agents.models import AgentAction, AgentConfig
from apps.agents.schemas import PostDraft
from apps.content.models import ContentSeed, Post
from apps.platforms.models import SocialAccount

logger = logging.getLogger(__name__)


# ─── Smart Auto-Approval (Learning from User Patterns) ──────────────────────

def _should_auto_approve(user, post):
    """
    Decide if a post can be auto-approved based on learned patterns.
    Returns True only when confidence is high enough.

    Requirements to auto-approve:
    1. User has reviewed 15+ posts (enough training data)
    2. Approval rate >= 80% (user generally trusts the agent)
    3. Post content length is within the platform's approved range
    4. No recent rejections on this platform (last 5 posts)
    """
    from django.db.models import Q

    # Need enough history to learn from
    reviewed = Post.objects.filter(
        user=user,
        generated_by_agent="create",
        status__in=[
            Post.Status.APPROVED, Post.Status.SCHEDULED,
            Post.Status.PUBLISHED, Post.Status.REJECTED,
        ],
    )
    total = reviewed.count()
    if total < 15:
        return False

    rejected_count = reviewed.filter(status=Post.Status.REJECTED).count()
    approval_rate = (total - rejected_count) / total

    if approval_rate < 0.80:
        return False

    # Check platform-specific: no rejections in last 5 posts for this platform
    recent_platform = (
        Post.objects.filter(
            user=user,
            platform=post.platform,
            generated_by_agent="create",
            status__in=[
                Post.Status.APPROVED, Post.Status.SCHEDULED,
                Post.Status.PUBLISHED, Post.Status.REJECTED,
            ],
        )
        .order_by("-created_at")[:5]
        .values_list("status", flat=True)
    )
    if Post.Status.REJECTED in list(recent_platform):
        return False

    # Content length sanity: must be within range of approved posts for platform
    approved_lengths = list(
        Post.objects.filter(
            user=user,
            platform=post.platform,
            generated_by_agent="create",
            status__in=[
                Post.Status.APPROVED, Post.Status.SCHEDULED,
                Post.Status.PUBLISHED,
            ],
        )
        .exclude(content_text="")
        .values_list("content_text", flat=True)[:30]
    )
    if approved_lengths:
        lengths = [len(t) for t in approved_lengths]
        min_len = min(lengths) * 0.5
        max_len = max(lengths) * 1.5
        post_len = len(post.content_text or "")
        if post_len < min_len or post_len > max_len:
            return False

    logger.info(
        "Smart auto-approval: approved post %s (platform=%s, approval_rate=%.0f%%)",
        post.id, post.platform, approval_rate * 100,
    )
    return True


def _get_kova_page_url(user) -> str:
    """Return the absolute public URL of the user's first active Kova Link Page, or ''."""
    try:
        from django.conf import settings
        from apps.links.models import KovaPage
        page = KovaPage.objects.filter(user=user).first()
        if page:
            base = (getattr(settings, "SITE_URL", "") or "").rstrip("/")
            return f"{base}/k/{page.slug}/"
    except Exception:
        pass
    return ""


# ─── Performance Intelligence (Content DNA Feedback Loop) ────────────────────

def _get_performance_intelligence(user) -> str:
    """
    Query the Analyst Agent's historical findings and build an intelligence
    briefing for the Create Agent. This is the feedback loop — the system
    gets smarter with every post published.

    Returns a formatted string for injection into the system prompt.
    """
    from apps.agents.analyst_agent import get_content_dna_summary
    from apps.analytics.models import PostMetric

    parts = []

    # 1. Content DNA — what attributes correlate with high engagement
    try:
        dna = get_content_dna_summary(user, days=30)
        winning = dna.get("winning_attributes", [])
        if winning:
            parts.append("## PERFORMANCE INTELLIGENCE (from your last 30 days)")
            parts.append("The Analyst Agent identified these winning content patterns:\n")
            for attr in winning[:8]:
                parts.append(f"  - **{attr['attribute']}** → avg engagement: {attr['avg_engagement']}% ({attr['posts']} posts)")
            parts.append("")
            parts.append("INSTRUCTION: Bias your content toward these winning attributes when they fit naturally.")
            parts.append("Don't force it — but all else being equal, prefer formats, tones, and hooks that have proven to work.")

        # Algorithm signal rates — saves/shares as % of reach
        algo_signals = dna.get("algorithm_signals", {})
        if algo_signals:
            parts.append("\n## ALGORITHM SIGNAL RATES (what the algorithms reward)")
            for plat, sigs in algo_signals.items():
                parts.append(f"  **{plat}**: save rate {sigs['avg_save_rate']}% · share rate {sigs['avg_share_rate']}% · comment rate {sigs['avg_comment_rate']}% ({sigs['posts_analyzed']} posts)")
            parts.append("INSTRUCTION: Saves and shares matter 5-10x more than likes for algorithm distribution.")
            parts.append("Write content people want to SAVE (reference-worthy, actionable) or SHARE (relatable, surprising, useful to others).")
            parts.append("Ask yourself: 'Would someone screenshot this or send it to a friend?' If not, make it more save/share-worthy.\n")

        # Format mix — which content formats perform best per platform
        format_mix = dna.get("format_mix", {})
        if format_mix:
            parts.append("## FORMAT MIX INTELLIGENCE (which formats your audience prefers)")
            for plat, formats in format_mix.items():
                top = formats[:3]
                ranked = ", ".join(f"{f['format']} ({f['avg_engagement']}% eng, {f['posts']} posts)" for f in top)
                parts.append(f"  **{plat}**: {ranked}")
            parts.append("INSTRUCTION: Lean heavily toward the top-performing formats. If carousels outperform photos 3x, create more carousels.\n")
    except Exception as e:
        logger.debug("Performance intelligence (DNA) unavailable for %s: %s", user.email, e)

    # 2. Top-performing posts — learn from actual wins
    try:
        top_posts = (
            Post.objects.filter(
                user=user,
                status=Post.Status.PUBLISHED,
                published_at__gte=dj_timezone.now() - timedelta(days=30),
            )
            .select_related("social_account", "metrics")
            .order_by("-metrics__engagement_rate")[:5]
        )

        examples = []
        for post in top_posts:
            try:
                m = post.metrics
                if m.engagement_rate and m.engagement_rate > 0:
                    examples.append({
                        "platform": post.social_account.platform if post.social_account else "?",
                        "preview": post.content_text[:150],
                        "engagement_rate": round(m.engagement_rate, 2),
                        "angle": post.ai_angle,
                        "framework": post.ai_framework,
                    })
            except PostMetric.DoesNotExist:
                continue

        if examples:
            parts.append("## TOP-PERFORMING POSTS (study these — they worked)")
            for i, ex in enumerate(examples[:3], 1):
                parts.append(f"### Win #{i} ({ex['platform']}, {ex['engagement_rate']}% engagement)")
                parts.append(f"  Angle: {ex['angle'] or 'N/A'} | Framework: {ex['framework'] or 'N/A'}")
                parts.append(f"  Content: \"{ex['preview']}...\"")
            parts.append("\nLearn from these. What made them work? Apply those patterns to new content.\n")
    except Exception as e:
        logger.debug("Performance intelligence (top posts) unavailable for %s: %s", user.email, e)

    # 3. Recent topics — avoid repetition
    try:
        recent = (
            Post.objects.filter(
                user=user,
                created_at__gte=dj_timezone.now() - timedelta(days=7),
            )
            .values_list("ai_angle", flat=True)
        )
        recent_angles = [a for a in recent if a]
        if recent_angles:
            parts.append("## RECENTLY USED ANGLES (avoid repeating these)")
            for angle in recent_angles[:10]:
                parts.append(f"  - {angle}")
            parts.append("\nTake a FRESH angle. Don't repeat what was just posted.\n")
    except Exception as e:
        logger.debug("Performance intelligence (recent angles) unavailable for %s: %s", user.email, e)

    return "\n".join(parts)

# ─── Platform strategy guides (not just formatting — actual strategy) ────────

PLATFORM_GUIDES = {
    "twitter": {
        "name": "X (Twitter)",
        "max_chars": 280,
        "psychology": "Speed, wit, boldness. People scroll fast — you have 0.5 seconds to stop them. Hot takes, contrarian views, and surprising data points win. Retweets come from 'I wish I said that' moments.",
        "winning_patterns": [
            "Bold opening statement that challenges conventional wisdom",
            "Specific numbers/data that make people stop scrolling",
            "Relatable observation + unexpected twist",
            "'Most people think X. They're wrong. Here's why:' format",
            "Thread hooks: 'I spent X hours/days studying Y. Here's what nobody talks about:'",
        ],
        "avoid": "Generic motivational quotes, excessive hashtags, corporate-speak, 'Excited to announce' openings",
        "cta_style": "Implicit (provoke replies via strong opinions or questions) rather than explicit asks",
        "formats": ["single tweet", "thread (3-7 tweets)"],
    },
    "linkedin": {
        "name": "LinkedIn",
        "max_chars": 3000,
        "psychology": "Professional credibility + vulnerability. People engage with frameworks they can steal and stories they relate to. The best posts teach something specific or share a hard-won lesson. LinkedIn's algorithm rewards dwell time — comments that expand text, saves, and shares from outside your network. The feed is slower-moving than Twitter; quality beats volume.",
        "winning_patterns": [
            "Personal story → universal business lesson (the 'I failed at X and learned Y' format)",
            "Numbered framework/list with actionable steps (e.g. '5 things I wish I knew before...')",
            "Contrarian industry take backed by real experience (opens debate, drives comments)",
            "Behind-the-scenes of a decision/process with real numbers — vague claims get ignored",
            "Hook line → single line break → punchy follow-up → develop the story",
            "The '1-3-1' structure: 1 bold hook, 3 proof/insight lines, 1 closing question",
            "'What nobody tells you about X' — promises insider knowledge, earns the click-through",
        ],
        "avoid": "Humble-bragging, 'Agree?' as a CTA, fake or obviously embellished stories, emoji walls, 'I'm thrilled to share' openings, excessive blank lines in the opening hook, URLs or links in the post body (reduces reach ~50% — use 'link in first comment ↓' instead), generic motivational fluff with no specific insight",
        "cta_style": "End with a genuine specific question that invites people to share their own experience. Never 'Agree?' or 'Thoughts?'. If referencing a resource or product, write 'link in first comment ↓' — NEVER paste a URL in the post body.",
        "formats": ["text post", "article-style post", "carousel outline (numbered slides)"],
        "hashtag_strategy": "3-5 hashtags max, placed at the very end after a blank line. Mix: 1 broad (#Marketing), 1 niche (#B2BSaaS), 1 topic (#ContentStrategy). Never embed hashtags mid-sentence — it looks spammy and breaks the reading flow.",
        "link_strategy": "NEVER include URLs in the post body. LinkedIn's algorithm actively penalises external links in body by ~50% reach reduction. Use the phrase 'link in first comment ↓' — the publishing system posts the actual URL as the first comment automatically.",
        "optimal_length": "Under 1300 chars often outperforms longer posts as it fits above the fold without 'see more'. Aim 800-1800 chars for thought leadership. Never pad to hit a length target — every sentence must earn its place.",
        "formatting_rules": "CRITICAL: LinkedIn hides content behind 'see more' after ~5 visible lines. Blank lines count as visible lines. Front-load value in the first 5 lines — use SINGLE line breaks (not double) for the opening hook and first 2-3 sentences. Save double line breaks for structure AFTER the fold. The reader must see enough substance in those first 5 lines to WANT to click 'see more'. Never waste above-the-fold space on a title line followed by a blank line.",
    },
    "instagram": {
        "name": "Instagram",
        "max_chars": 2200,
        "psychology": "Visual-first + save-worthy education. DM shares are the #1 algorithm signal — content sent to friends gets massive Explore distribution. Saves are #2 — people save what they want to reference later. Comments and watch time (for Reels) round out the signals. Likes barely move distribution. The algorithm tests content with a small audience for 15-30 minutes: if saves + shares spike, it pushes to Explore. REELS get 3-5x the organic reach of feed posts — they're Instagram's growth engine and reach non-followers. Carousels get ~2-3x the reach of single photos because the swipe action is itself an engagement signal.",
        "winning_patterns": [
            "Carousel: numbered tip list ('5 mistakes that are killing your X') — highly saveable, drives swipes",
            "Carousel: step-by-step framework people will screenshot and reference — put the payoff on slide 7-8 to maximise swipe-through",
            "Reel hook + value bomb: 3-second text hook on screen, then rapid-fire useful info, then CTA to save",
            "Before/after with the real numbers — relatable struggle → satisfying outcome, invites DM shares",
            "Micro-lesson: one specific insight explained in depth — 'Here is the one thing that changed everything about X'",
            "Behind-the-scenes with emotional honesty — the messy reality, not the polished highlight reel",
            "Conversation-starting opinion: a bold take that makes people DM it to a friend going through the same thing",
        ],
        "avoid": "Stock photo language, corporate polish, more than 5 hashtags (looks spammy, harms reach), irrelevant hashtags, URLs in captions (not clickable — always use 'link in bio' language instead), walls of text with no line breaks, starting with a hashtag or @mention, preachy or lecture-y tone",
        "cta_style": "End with ONE strong CTA from: '💾 Save this before you forget' / '📤 Send this to someone who needs it' / '📌 Tap link in bio for [specific thing]' / 'Drop a 🔥 in the comments if this hit'. Never combine multiple CTAs — pick one and commit. For product/website links: ALWAYS say 'link in bio' — NEVER paste a URL in the caption (URLs in captions are not clickable and signal low-quality content to the algorithm).",
        "formats": ["single photo caption", "carousel caption (write as numbered points, each point = one slide concept)", "reel script with visual cues"],
        "formatting_rules": "CRITICAL CAPTION STRUCTURE: Instagram shows ~125 characters before 'more' — the first line is your entire hook. It must create an irresistible curiosity gap or bold claim. Use EMPTY LINES between paragraphs (press Enter twice) — this is essential for readability; wall-of-text captions lose readers immediately. Ideal structure: Hook line → empty line → 3-5 short punchy paragraphs → empty line → CTA → empty line → Hashtags (3-5 max, niche-specific, at the very end). HASHTAG STRATEGY: Use 3-5 highly specific hashtags over broad ones (#marketingstrategy beats #marketing). Broad hashtags (#love, #instagood) are saturated and send zero new traffic. REEL CAPTIONS: Keep short (50-150 chars) — Reel captions appear below the video and are often not read; the hook lives in the first 3 seconds of the video, not the caption. LINK RULE: NEVER include a URL in the caption — it won't be clickable and signals low quality. Use 'link in bio 👆' or 'tap the link in my bio' language instead.",
    },
    "facebook": {
        "name": "Facebook",
        "max_chars": 63206,
        "psychology": "Community + conversation. Facebook rewards posts that spark long comment threads and shares. Stories, relatable moments, and genuinely helpful content get shared — people share what makes them look thoughtful or helpful to their network. SHARES are the #1 algorithmic signal. Long comment threads with back-and-forth replies are #2. Reactions are #3. The algorithm tests your post with a small sample audience in the first 30-60 minutes — if they engage heavily, the algorithm pushes it wider. If not, it dies in the feed. Native content (uploaded directly) always outperforms shared links.",
        "winning_patterns": [
            "Story arc: setup → tension → resolution → lesson — invites readers to comment their own version of the story",
            "Opinion piece that opens a genuine perspective: 'Here's what I think about X — what's your take?' (debate, not controversy)",
            "Helpful tip or resource framed as personal discovery: 'Something I just learned that changed how I...'",
            "Open question tapping into shared experience: 'Has this ever happened to you?' or 'What would you do in this situation?'",
            "Behind-the-scenes with emotional honesty — the real story with real numbers, not the polished version",
            "Educational content in scannable short paragraphs: one idea per 2-3 lines, blank line between sections",
        ],
        "avoid": "Clickbait headlines, engagement bait ('Tag 3 friends!', 'Like if you agree!', 'Comment YES if...'), overly promotional tone, ANY URLs or links in the post body (Facebook algorithmically reduces organic reach 50-70% for posts with outbound links — the system handles this automatically), walls of unbroken text, cross-posting identical Instagram captions, excessive hashtags (max 5)",
        "cta_style": "End with a genuine open question that invites personal experience. 'What's been your experience with this?' outperforms 'Click the link below' by 4-5x. NEVER include URLs in the post body — if a product/website link is needed, it is posted automatically as the first comment after publishing, which preserves full organic reach.",
        "formats": ["text story post", "photo post with storytelling caption", "native video or Reel (highest organic reach)", "carousel album (strong engagement, 2-10 images)"],
        "formatting_rules": "Facebook shows ~400 characters before 'See more'. The first 2-3 lines MUST hook the reader — compelling enough that NOT clicking 'See more' feels like missing out. Use short paragraphs (2-3 lines max), one blank line between sections. Place 3-5 highly relevant hashtags at the very end only. CRITICAL: Do NOT include any URLs, product links, or website addresses in content_text. Facebook penalises outbound links in post body with 50-70% organic reach reduction. Any link to share must be omitted from content_text — the publishing system automatically posts it as the first comment immediately after the post goes live, which is the correct strategy for maximum reach.",
    },
    "tiktok": {
        "name": "TikTok",
        "max_chars": 4000,
        "psychology": "Authenticity + entertainment + education. The 'I just learned something' reaction drives shares. Hook in first 2 seconds or they scroll. Raw > polished.",
        "winning_patterns": [
            "Hook: 'Nobody talks about this but...' + genuinely useful info",
            "Quick tips list: 'Three things that changed my [topic]'",
            "Storytime format: 'So this happened...' with a lesson",
            "Myth-busting: 'Stop doing X. Here's what works instead'",
            "POV/scenario format that audience relates to",
        ],
        "avoid": "Over-produced scripts, corporate language, trying too hard to be trendy, long intros",
        "cta_style": "Follow for more [specific topic] / Save this before it gets buried / Part 2?",
        "formats": ["video script with visual cues", "caption + hook"],
    },
    "youtube": {
        "name": "YouTube",
        "max_chars": 5000,
        "psychology": "Depth + authority. YouTube viewers want to LEARN something or be ENTERTAINED for longer. The title and first 30 seconds decide if they stay. SEO matters — people search YouTube like Google.",
        "winning_patterns": [
            "Title formula: Number + Result + Timeframe ('How I Got 10K Subs in 90 Days')",
            "Hook in first 15 seconds: State the problem, tease the solution, show proof",
            "Value stacking: 'I'll show you X, then Y, and finally the thing nobody talks about'",
            "Structured chapters with timestamps for audience retention",
            "End screen CTA: 'Watch this next' → link to related video",
        ],
        "avoid": "Long intros, 'Hey guys welcome back', no clear value proposition, clickbait without payoff",
        "cta_style": "Subscribe + bell for [specific benefit]. Like if [specific moment resonated]. Comment your [specific question related to content].",
        "formats": ["video description + title", "short script outline"],
    },
    "pinterest": {
        "name": "Pinterest",
        "max_chars": 500,
        "psychology": "Discovery + aspiration + planning. Pinterest is a visual search engine, not a social feed. People save content for future reference. Evergreen content > trending content. SEO-rich descriptions drive traffic for months.",
        "winning_patterns": [
            "Keyword-rich title: Include what people would SEARCH for",
            "Descriptive, helpful pin descriptions with natural keywords",
            "List-style: '10 Ways to...' / '5 Ideas for...' — highly saveable",
            "Seasonal content 45 days early (Valentines content in January)",
            "How-to content with clear visual: 'Step-by-step guide to...'",
        ],
        "avoid": "Hashtag-heavy descriptions, vague titles, time-sensitive content without evergreen value, selfie-style images",
        "cta_style": "Save this pin for later / Click through for the full guide / Visit the link for more details",
        "formats": ["pin title + description", "board description"],
    },
    "threads": {
        "name": "Threads",
        "max_chars": 500,
        "psychology": "Casual conversation + real-time commentary. Think Twitter but warmer, less culture-war. Text-first but images boost engagement. Threads rewards frequent posting and genuine interaction.",
        "winning_patterns": [
            "Conversational opener: 'Hot take:' or 'Unpopular opinion:' (but actually insightful)",
            "Micro-thread: 3-5 connected posts telling a story or building an argument",
            "Real-time commentary on industry news or trends",
            "Relatable observations: 'The moment when...' + twist",
            "Ask-the-audience: Genuine questions that invite personal experience",
        ],
        "avoid": "Cross-posting identical Twitter content, overly formal tone, hashtag spam, link-only posts",
        "cta_style": "What do you think? / Reply with your experience / Drop your take below",
        "formats": ["single post", "micro-thread (3-5 posts)"],
    },
    "bluesky": {
        "name": "Bluesky",
        "max_chars": 300,
        "psychology": "Twitter-like but with a stronger community ethos. Early-adopter tech/media crowd. Values substance, wit, and authentic voice over clout-chasing. Anti-algorithm sentiment — people engage with what they genuinely enjoy.",
        "winning_patterns": [
            "Sharp observations about tech, culture, or industry — brevity is king at 300 chars",
            "Genuine hot takes with reasoning, not just provocation",
            "Thread format for deeper thoughts (skeet + replies to self)",
            "Community building: engage with others' posts, quote-post with added value",
            "Behind-the-scenes authenticity: 'Working on X, here's what I'm learning'",
        ],
        "avoid": "Engagement bait, 'Like if you agree', corporate-speak, content that only makes sense with context from another platform",
        "cta_style": "Implicit — strong opinions and genuine questions naturally drive replies. No explicit follow/like asks.",
        "formats": ["single skeet (post)", "thread"],
    },
}

# ─── Content strategy frameworks ─────────────────────────────────────────────

CONTENT_FRAMEWORKS = """
## CONTENT STRATEGY FRAMEWORKS (choose the best one for each post)

1. **Hook → Value → CTA**: Strong opening → deliver genuine insight → drive action
2. **PAS (Problem → Agitate → Solve)**: Name the pain → make it feel urgent → present the answer
3. **Story → Lesson → Application**: Personal/relatable story → extract the principle → show how to apply
4. **Observation → Insight → Implication**: Point out something everyone sees → reveal what it means → explain why it matters
5. **Myth → Truth → Proof**: Common misconception → the real answer → evidence/experience
6. **Before → After → Bridge**: Where audience is now → where they want to be → how to get there

Choose the framework that creates MAXIMUM IMPACT for the specific platform and idea.
"""

ENGAGEMENT_ENGINEERING = """
## ENGAGEMENT ENGINEERING RULES

1. **Specificity beats generality**: "We grew from 0 to 10K followers in 90 days" beats "We grew our audience"
2. **Pattern interrupts**: Start with something unexpected. The brain engages with surprise.
3. **Curiosity gaps**: Open a loop in the reader's mind that they NEED to close by reading more.
4. **Social proof signals**: Reference real numbers, timeframes, or outcomes when relevant.
5. **Emotional resonance**: Connect to feelings your audience experiences daily (frustration, aspiration, pride).
6. **Actionability**: Every post should leave the reader with something they can DO, THINK, or FEEL differently.
7. **Conversation starters**: End with questions people WANT to answer (about their experience, not yes/no).

## ALGORITHM OPTIMIZATION (how platforms decide to show your content to MORE people)

The first 30-60 minutes after posting decide everything. Platforms show your post to a small test audience first.
If THEY engage, the algorithm pushes it wider. If they don't — it dies.

**Engagement value ranking (most to least valuable for distribution):**
  1. DM shares / Sends — someone actively shared your content with a friend (STRONGEST signal)
  2. Saves / Bookmarks — they want to come back to it (HIGH value)
  3. Long comments (5+ words) — they invested time responding
  4. Shares / Reposts — public endorsement
  5. Watch time / Dwell time — they stopped scrolling and consumed
  6. "See more" clicks — they expanded to read the full text
  7. Likes — weakest signal, still counts but barely moves distribution

**HOOK RULES (first line is EVERYTHING):**
- The first line must create an IRRESISTIBLE reason to keep reading.
- Test: would YOU stop scrolling for this first line? If not, rewrite it.
- For platforms with "See more" (LinkedIn, Instagram, Facebook): the visible preview (first 2-3 lines)
  must be so compelling that NOT clicking "See more" feels like a loss.
- Strong hooks: bold claim, surprising stat, curiosity gap, direct "you" address, contrarian take.
- Weak hooks: greetings ("Hey everyone!"), announcements ("Excited to share"), questions with obvious answers.

**SAVE/SHARE OPTIMIZATION:**
- "Save-worthy" = reference material (tips, steps, frameworks, templates, checklists)
- "Share-worthy" = relatable truth, useful to others, makes the sharer look smart/helpful
- Explicitly prompt when natural: "Save this for when you need it" or "Send this to someone who..."
- Don't beg — engineer content so good that saving/sharing is the natural response.
"""


def build_system_prompt(user) -> str:
    """Build the system prompt with user's brand context and strategic intelligence."""
    profile = user.profile

    parts = [
        "You are Kova — a Strategic Content Intelligence Agent.",
        "",
        "You don't just write posts. You think like a content strategist, audience psychologist,",
        "and platform-native creator combined. Every post you generate must:",
        "  → Deliver genuine VALUE (teach, provoke thought, or inspire action)",
        "  → Feel NATIVE to the platform (not cross-posted or reformatted)",
        "  → Engineer ENGAGEMENT (hooks, curiosity gaps, conversation starters)",
        "  → Serve a STRATEGIC PURPOSE (build authority, grow audience, drive conversions)",
        "",
        "CRITICAL RULES:",
        "- NEVER write generic, filler content. If a sentence doesn't add value, cut it.",
        "- Each platform post must take a DIFFERENT ANGLE on the same idea.",
        "  Twitter gets the bold take. LinkedIn gets the framework. Instagram gets the visual lesson.",
        "  Do NOT just reformat the same text for different character limits.",
        "- Use real specificity: numbers, timeframes, concrete examples > vague claims.",
        "- Match the brand voice EXACTLY. Adapt frameworks to their tone, not the other way around.",
        "- Write content people would SAVE, SHARE, or SCREENSHOT — not just scroll past.",
        "",
        CONTENT_FRAMEWORKS,
        ENGAGEMENT_ENGINEERING,
    ]

    # Brand voice
    if profile.brand_voice:
        parts.append(f"## BRAND VOICE\n{profile.brand_voice}")
    else:
        parts.append("## BRAND VOICE\nProfessional yet approachable. Confident but not arrogant. Clear, direct, value-driven.")
    if profile.brand_voice_examples:
        parts.append("### Voice Examples (match this style):")
        for i, ex in enumerate(profile.brand_voice_examples[:3], 1):
            parts.append(f"  {i}. {ex}")

    # Tone attributes — structured voice descriptors
    if getattr(profile, "tone_attributes", None):
        parts.append(f"### Tone Attributes: {', '.join(profile.tone_attributes)}")
        parts.append("Combine these tone qualities in every post. They define HOW the brand speaks.")

    # Company context
    context_lines = []
    if profile.company_name:
        context_lines.append(f"**Company**: {profile.company_name}")
    if profile.industry:
        context_lines.append(f"**Industry**: {profile.get_industry_display()}")
    if profile.website_url:
        context_lines.append(f"**Website**: {profile.website_url}")
    if getattr(profile, "key_offerings", None):
        context_lines.append(f"**Products/Services**: {', '.join(profile.key_offerings)}")
    if context_lines:
        parts.append("## BRAND CONTEXT\n" + "\n".join(context_lines))

    # Content language preference
    if getattr(profile, "content_language", "en") != "en":
        lang_display = profile.get_content_language_display()
        parts.append(f"## CONTENT LANGUAGE\nGenerate all content in **{lang_display}**.")
        parts.append("Use natural, native language patterns — not translated-from-English phrasing.")

    # Audience intelligence
    if profile.target_audience:
        parts.append(f"## TARGET AUDIENCE\n{profile.target_audience}")
        parts.append("Think about: What keeps this audience up at night? What do they aspire to? What frustrates them about the status quo?")

    # Content pillars
    if profile.content_pillars:
        parts.append(f"## CONTENT PILLARS\n{', '.join(profile.content_pillars)}")
        parts.append("Stay within these themes. Every post should map to at least one pillar.")

    # Goals
    if profile.goals:
        parts.append(f"## STRATEGIC GOALS\n{', '.join(profile.goals)}")
        parts.append("Bias content toward these objectives. Each post should serve at least one goal.")

    # Brand restrictions / guardrails
    if getattr(profile, "brand_restrictions", ""):
        parts.append(f"## BRAND GUARDRAILS (MUST FOLLOW)\n{profile.brand_restrictions}")
        parts.append("These are non-negotiable rules. Violating any guardrail is a critical failure.")

    # Visual brand identity — guides AI image generation
    visual_parts = []
    if getattr(profile, "brand_colors", None):
        visual_parts.append(f"**Brand Colors**: {', '.join(profile.brand_colors)}")
    if getattr(profile, "visual_style", "auto") != "auto":
        visual_parts.append(f"**Visual Style**: {profile.get_visual_style_display()}")
    if visual_parts:
        parts.append("## VISUAL BRAND IDENTITY\n" + "\n".join(visual_parts))
        parts.append(
            "When writing image_prompt descriptions, incorporate these brand visuals. "
            "Images should feel like they belong to THIS brand, not generic stock photos."
        )

    # Product catalog — stock-aware content generation
    from apps.products.utils import get_product_context
    product_ctx = get_product_context(user)
    if product_ctx:
        parts.append(product_ctx)

    # Performance intelligence — the feedback loop
    intel = _get_performance_intelligence(user)
    if intel:
        parts.append(intel)

    # Agent memory — learn from past actions and user corrections
    from apps.agents.memory import get_agent_learning_context, get_user_edit_patterns
    learning = get_agent_learning_context(user, "create", action_type="generate_from_seed")
    if learning:
        parts.append(learning)
    edit_patterns = get_user_edit_patterns(user)
    if edit_patterns:
        parts.append(edit_patterns)

    # Industry Playbook — cold-start intelligence for new users
    from apps.agents.playbooks import get_playbook_intelligence
    playbook_intel = get_playbook_intelligence(user)
    if playbook_intel:
        parts.append(playbook_intel)

    # Adapt Agent v2 learnings — bias toward proven winners, exclude
    # retired losers. The Adapt cycle writes these every 12h based on
    # the user's last 30 days of performance.
    adapt_intel = _adapt_preferences_for_prompt(profile)
    if adapt_intel:
        parts.append(adapt_intel)

    return "\n".join(parts)


def _adapt_preferences_for_prompt(profile) -> str:
    """Render the Adapt Agent v2's promoted / retired DNA patterns as a
    prompt section. Returns "" if no preferences set yet (warming up).

    Spec: docs/specs/ADAPT_AGENT_V2_SPEC.md — Decision 1 + Decision 2.
    """
    prefs = profile.dna_preferences or {}
    promoted = prefs.get("promoted", []) or []
    retired = prefs.get("retired", []) or []

    if not promoted and not retired:
        return ""

    lines = ["## AI-LEARNED PATTERNS (from your post performance)"]

    if promoted:
        lines.append("**Patterns that work for this brand — bias toward these:**")
        for p in promoted[-5:]:  # latest 5 to keep prompt tight
            combo = p.get("combo", {})
            descriptor = ", ".join(
                f"{k}={v}" for k, v in combo.items() if v is not None
            )
            lines.append(f"  - {descriptor}")

    if retired:
        lines.append("**Patterns that under-performed — AVOID these:**")
        for r in retired[-5:]:
            combo = r.get("combo", {})
            descriptor = ", ".join(
                f"{k}={v}" for k, v in combo.items() if v is not None
            )
            lines.append(f"  - {descriptor}")

    lines.append(
        "These were learned automatically from your last 30 days of posts. "
        "When generating, lean into the working patterns and steer clear of "
        "the retired ones unless the seed explicitly calls for them."
    )
    return "\n".join(lines)


def build_generation_prompt(seed: ContentSeed, platforms: list[dict]) -> str:
    """Build the user prompt with strategic platform targeting."""
    platform_section = ""
    for p in platforms:
        guide = PLATFORM_GUIDES.get(p["platform"], {})
        winning = "\n".join(f"    - {w}" for w in guide.get("winning_patterns", []))
        formatting = guide.get("formatting_rules", "")
        formatting_line = f"\n- **Formatting**: {formatting}" if formatting else ""
        platform_section += f"""
### {guide.get('name', p['platform'].title())} (@{p['username']})
- **Character limit**: {guide.get('max_chars', 'N/A')}
- **Platform psychology**: {guide.get('psychology', 'Adapt to platform norms')}
- **What wins here**:
{winning}
- **Avoid**: {guide.get('avoid', 'Generic content')}
- **CTA approach**: {guide.get('cta_style', 'Adapt to context')}
- **Format options**: {', '.join(guide.get('formats', ['text post']))}{formatting_line}
"""

    prompt = f"""## YOUR TASK

Transform this raw idea into high-performing, platform-native content.

### THE IDEA
{seed.idea}
{f"### ADDITIONAL CONTEXT FROM USER" + chr(10) + seed.notes if seed.notes else ""}
"""

    # Inject product-specific context when seed is linked to a product
    if seed.product_id:
        p = seed.product
        product_lines = [f"### PRODUCT BEING PROMOTED"]
        product_lines.append(f"- **Name**: {p.name}")
        if p.display_price:
            product_lines.append(f"- **Price**: {p.display_price}")
        if p.description:
            product_lines.append(f"- **Description**: {p.description}")
        if p.product_url:
            product_lines.append(f"- **Purchase URL**: {p.product_url}")
            product_lines.append("→ Use this URL for 'Shop Now' / 'Buy Now' / 'Get Yours' CTAs.")
        if p.tags:
            product_lines.append(f"- **Tags**: {', '.join(p.tags)}")
        if p.stock_status == "low_stock":
            product_lines.append(f"- **⚠️ LOW STOCK** — Create urgency! Only {p.quantity or 'few'} left.")
        prompt += "\n".join(product_lines) + "\n\n"

    prompt += f"""### STRATEGIC THINKING (do this before writing)
For each platform, consider:
1. What's the most compelling ANGLE for THIS audience on THIS platform?
2. Which content framework creates the most impact?
3. What hook will stop the scroll in the first line?
4. What's the takeaway that makes this worth sharing/saving?

### TARGET PLATFORMS
{platform_section}

### OUTPUT FORMAT
Respond with a JSON object. No markdown code fences. Structure:
{{
  "batch_strategy": "One sentence explaining the overall content strategy for this idea.",
  "posts": [
    {{
      "platform": "instagram",
      "username": "@handle",
      "content_text": "The full post caption / text, ready to publish. Include line breaks, emojis, hashtags as native to the platform.",
      "content_type": "original",
      "post_format": "One of: text | image | carousel | story | reel — the CONTENT FORMAT for this specific post. Choose based on the platform and content type: Instagram feed → image or carousel; Instagram Stories → story; Reels → reel; Facebook feed → text or image; LinkedIn → text or image (carousel for multi-point posts); TikTok → reel.",
      "carousel_slides": "ONLY when post_format is 'carousel' — an array of slide objects: [{{\\"heading\\": \\"Slide title (max 60 chars)\\", \\"body\\": \\"Slide body text (max 150 chars, punchy)\\", \\"image_prompt\\": \\"Vivid prompt for AI image generation for THIS slide. Describe scene, mood, colors, lighting. Under 150 words. NO text in the image.\\", \\"image_url\\": \\"\\"}}, ...]. For all other formats: empty array [].",
      "framework_used": "Hook → Value → CTA",
      "angle": "Brief description of the specific angle chosen for this platform",
      "reasoning": "Why this angle, framework, and format will perform well here. What engagement pattern it targets.",
      "content_intent": "One of: problem_awareness | solution | proof | offer | authority — what this post is designed to achieve in the customer journey",
      "predicted_score": 72,
      "image_prompt": "For post_format 'image': A vivid, specific description for AI image generation. Describe: subject, composition, style/mood, colors (use brand colors if provided), and lighting. Make it platform-appropriate (square for Instagram feed, vertical 9:16 for story/reel). Under 200 words. NEVER include text/words in the image. For post_format 'story' or 'reel': provide a 9:16 vertical image prompt. For post_format 'text' or 'carousel': leave as EMPTY STRING.",
      "visual_strategy": {{
        "strategy": "One of: ai_photo | quote_card | tip_graphic | stat_highlight | cta_banner | carousel | story_graphic | none. Match to post_format: image→ai_photo/quote_card/etc, carousel→carousel, story→story_graphic, reel→ai_photo, text→none.",
        "text": "For quote_card: the quote text. For tip_graphic: the title.",
        "attribution": "For quote_card: who said it (optional).",
        "tips": ["For tip_graphic: array of tip strings."],
        "stat_number": "For stat_highlight: the big number (e.g. '87%', '10,000+').",
        "stat_label": "For stat_highlight: what the number means.",
        "headline": "For cta_banner / story_graphic: the main headline.",
        "subtext": "For cta_banner / story_graphic: supporting text.",
        "cta_text": "For cta_banner / story_graphic: button/CTA text."
      }}
    }}
  ]
}}

POST FORMAT GUIDE — choose the best format for each platform:
- **Instagram feed post**: use post_format="image" (single striking image) or post_format="carousel" (3-7 slides for educational/list content — carousels get 3× more reach on Instagram)
- **Instagram Story**: use post_format="story" (vertical 9:16, short punchy text, high-energy, casual tone)
- **Instagram Reel**: use post_format="reel" (vertical 9:16, hook in first 2 seconds, trend-aware)
- **Facebook post**: use post_format="text" (text-only performs well) or post_format="image" if visual adds value
- **LinkedIn post**: use post_format="text" for thought leadership; post_format="carousel" for step-by-step guides or frameworks (LinkedIn carousels = document posts, great for authority building)
- **TikTok**: use post_format="reel" (always video-first, vertical 9:16)
- **WhatsApp**: use post_format="text" or post_format="image"

CAROUSEL SLIDE GUIDE (when post_format="carousel"):
- 3-7 slides is optimal (Instagram penalises >10 slides)
- Slide 1: HOOK — bold claim or question that stops the scroll. The cover image matters most.
- Slides 2-N: VALUE — one idea per slide. Short. Punchy. Each slide should make people swipe.
- Last slide: CTA — "Save this", "Follow for more", or a clear next step.
- Each slide MUST have: heading (title), body (body text), image_prompt (for AI image)
- image_prompt per slide: describe a visual that reinforces THAT slide's specific message

STORY FORMAT GUIDE (when post_format="story"):
- Very short text (max 10 words as a headline, 1-2 sentences body)
- High energy, casual, conversational — Stories disappear in 24h so urgency is native
- Emojis are essential — they replace facial expressions in text
- Always include a CTA sticker hint in the content_text (e.g., "Tap the link in bio 👆")
- image_prompt: describe a vibrant, eye-catching 9:16 vertical scene

IMPORTANT:
- Generate ONE post per platform
- Each post MUST take a DIFFERENT angle on the idea — do NOT rewrite the same content
- predicted_score is your honest assessment (0-100) of performance potential
- Content must be READY TO PUBLISH — no placeholders, no [insert X here]
"""

    # Facebook-specific link rule: enforce at prompt level so the AI never
    # includes outbound URLs in the post body. Links are posted as a first
    # comment by the publishing system after the post goes live, which
    # protects organic reach (FB penalises links in body by 50-70%).
    if any(p["platform"] == "facebook" for p in platforms):
        prompt += """
⚠️  FACEBOOK LINK RULE — NON-NEGOTIABLE:
Facebook's algorithm reduces organic reach by 50-70% for any post that contains
an outbound URL or link in the post body. For every Facebook post:
  • Write content_text with NO URLs, product links, or website addresses
  • Tell the story / share the tip / make the offer — all WITHOUT a link
  • The publishing system automatically posts the product/CTA URL as the
    first comment immediately after the post goes live (correct strategy)
  • A Facebook post with no link in the body + a link in the first comment
    gets FULL organic reach AND the link is visible to engaged readers
Violating this rule is a critical failure — it destroys the reach of the post.
"""

    # Instagram-specific link rule: URLs in captions are NOT clickable.
    # The only working link on Instagram is the bio link. Using "link in bio"
    # language is the platform-native and algorithm-friendly approach.
    if any(p["platform"] == "instagram" for p in platforms):
        prompt += """
⚠️  INSTAGRAM LINK RULE — NON-NEGOTIABLE:
Instagram does NOT make URLs in captions clickable. Pasting a URL in a caption:
  • Doesn't work (user can't tap it)
  • Signals low-quality, spammy content to the algorithm
  • Looks unprofessional to the audience
For every Instagram post that references a product, website, or resource:
  • NEVER paste a URL in content_text
  • Use the platform-native language: "link in bio 👆", "tap the link in my bio",
    or "full details at the link in my bio"
  • The actual URL is stored in the profile bio and updated by the system
Violating this rule produces content that literally doesn't work on the platform.
"""

    # LinkedIn-specific link rule: outbound URLs in post body suppress reach ~50%.
    # LinkedIn's algorithm detects links and reduces distribution to keep users on-platform.
    # The correct strategy is to write the full post body WITHOUT any URLs, then add the
    # link as the first comment immediately after publishing (done automatically by Kova).
    if any(p["platform"] == "linkedin" for p in platforms):
        prompt += """
⚠️  LINKEDIN LINK RULE — NON-NEGOTIABLE:
LinkedIn's algorithm suppresses organic reach by ~50% for any post containing
an outbound URL in the post body. This is well-documented and consistent.
For every LinkedIn post:
  • Write content_text with NO URLs, no "click here", no raw links
  • End the post body with a CTA that hints at the link below, e.g.:
      "I've put together a full guide — link in the first comment ↓"
      "Full breakdown in the comments 👇"
      "The resource is in the first comment below"
  • Kova automatically posts the product/CTA URL as the first comment
    immediately after the post goes live (this is the correct LinkedIn strategy)
  • A LinkedIn post with no link in body + link in first comment gets
    FULL organic reach AND the link is visible to engaged readers
Violating this rule cuts the post's reach in half before anyone sees it.
"""

    return prompt


def parse_posts(llm_content: str) -> tuple[str, list[dict]]:
    """
    Parse the LLM JSON response into post dicts.
    Uses shared parse_llm_json for resilient parsing.
    Returns (batch_strategy, list_of_post_dicts).
    """
    data = parse_llm_json(llm_content)
    batch_strategy = data.get("batch_strategy", "")
    return batch_strategy, data.get("posts", [])


# ─── Per-Platform Regeneration (Truncation Recovery) ─────────────────────────

# Minimum content length (chars) per platform to accept as valid.
# Anything below this is likely truncated from a multi-platform batch.
_MIN_CONTENT_LENGTH = {
    "linkedin": 600,   # typical LI post is 700-2000 chars; 200 missed most truncations
    "facebook": 300,
    "youtube": 150,
    "tiktok": 100,
    "instagram": 80,
    "twitter": 30,
    "threads": 30,
    "bluesky": 30,
    "pinterest": 30,
}


def _regenerate_single_platform(user, seed, platform_info, system_prompt):
    """
    Generate content for a SINGLE platform. Called as fallback when
    multi-platform generation produces truncated content.

    Returns a post dict or None on failure.
    """
    guide = PLATFORM_GUIDES.get(platform_info["platform"], {})
    winning = "\n".join(f"    - {w}" for w in guide.get("winning_patterns", []))
    formatting = guide.get("formatting_rules", "")
    formatting_line = f"\n- **Formatting**: {formatting}" if formatting else ""

    prompt = f"""## YOUR TASK

Transform this idea into ONE high-performing post for {guide.get('name', platform_info['platform'].title())}.

### THE IDEA
{seed.idea}
{f"### ADDITIONAL CONTEXT" + chr(10) + seed.notes if seed.notes else ""}

### PLATFORM: {guide.get('name', platform_info['platform'].title())} (@{platform_info['username']})
- **Character limit**: {guide.get('max_chars', 'N/A')}
- **Psychology**: {guide.get('psychology', 'Adapt to norms')}
- **What wins**:
{winning}{formatting_line}
- **CTA**: {guide.get('cta_style', 'Adapt to context')}

### OUTPUT FORMAT
Respond with a JSON object:
{{
  "platform": "{platform_info['platform']}",
  "username": "@{platform_info['username']}",
  "content_text": "The COMPLETE post text, ready to publish. Write the FULL post — do NOT cut it short.",
  "content_type": "original",
  "format": "text post",
  "framework_used": "Hook → Value → CTA",
  "angle": "Brief description of the angle",
  "reasoning": "Why this will perform well (1 sentence)",
  "predicted_score": 72,
  "image_prompt": ""
}}

CRITICAL:
- Write the COMPLETE post. Do not stop early or summarize.
- Content must be READY TO PUBLISH — no placeholders.
- For LinkedIn/Facebook: aim for 800-2000 characters of substantive content.
"""

    try:
        response = generate(
            prompt=prompt,
            system=system_prompt,
            model=get_model_for_task("create.generate", user=user),
            json_mode=True,
            temperature=0.7,
            max_tokens=4096,
        )

        if not response.content or not response.content.strip():
            return None

        data = parse_llm_json(response.content)

        # Handle both single object and wrapped {"posts": [...]} format
        if "posts" in data and isinstance(data["posts"], list):
            post_dict = data["posts"][0] if data["posts"] else None
        elif "content_text" in data:
            post_dict = data
        else:
            return None

        if post_dict:
            content = post_dict.get("content_text", "")
            logger.info(
                "Single-platform regen for %s: %d chars (finish=%s, tokens=%d/%d)",
                platform_info["platform"], len(content),
                response.finish_reason, response.input_tokens, response.output_tokens,
            )
        return post_dict

    except Exception as e:
        logger.error(
            "Single-platform regen failed for %s: %s",
            platform_info["platform"], e,
        )
        return None


def run_create_agent(seed: ContentSeed) -> list[Post]:
    """
    Main entry point: take a ContentSeed and produce Post drafts.

    Returns list of created Post objects.
    """
    user = seed.user

    # Check if agent is enabled
    agent_config = AgentConfig.objects.filter(user=user, agent_type="create").first()
    if agent_config and not agent_config.is_active:
        seed.status = ContentSeed.SeedStatus.FAILED
        seed.error_message = "Create Agent is disabled. Enable it in Agent Control Center."
        seed.save(update_fields=["status", "error_message", "updated_at"])
        return []

    # Determine target platforms
    connected = SocialAccount.objects.filter(user=user, is_active=True)
    if seed.target_platforms:
        connected = connected.filter(platform__in=seed.target_platforms)

    if not connected.exists():
        seed.status = ContentSeed.SeedStatus.FAILED
        seed.error_message = "No connected platforms found. Connect at least one platform first."
        seed.save(update_fields=["status", "error_message", "updated_at"])
        return []

    platforms = [{"platform": a.platform, "username": a.username, "account_id": str(a.id)} for a in connected]

    # Mark processing
    seed.status = ContentSeed.SeedStatus.PROCESSING
    seed.save(update_fields=["status", "updated_at"])

    # Log agent action
    action = AgentAction.objects.create(
        user=user,
        agent_type="create",
        action_type="generate_from_seed",
        description=f"Generating posts from seed: {seed.idea[:100]}",
        status=AgentAction.ActionStatus.STARTED,
        input_data={"seed_id": str(seed.id), "idea": seed.idea, "platforms": [p["platform"] for p in platforms]},
    )

    try:
        # Build prompts
        system = build_system_prompt(user)
        prompt = build_generation_prompt(seed, platforms)

        # Call LLM (with two retries on parse failure)
        batch_strategy = ""
        post_dicts = []
        last_error = None
        was_truncated_at_all = False

        for attempt in range(3):
            llm_response: LLMResponse = generate(
                prompt=prompt,
                system=system,
                model=get_model_for_task("create.generate", user=user),
                json_mode=True,
                temperature=0.7 if attempt == 0 else 0.3,  # lower temp on retries for cleaner JSON
                max_tokens=16384,
            )

            # Diagnostic logging for truncation investigation
            logger.info(
                "Create Agent attempt %d: finish=%s, tokens=%d/%d, content_len=%d",
                attempt + 1, llm_response.finish_reason,
                llm_response.input_tokens, llm_response.output_tokens,
                len(llm_response.content or ""),
            )

            # Detect token-limit truncation — LLM ran out of space mid-JSON
            if llm_response.was_truncated:
                was_truncated_at_all = True
                logger.warning(
                    "Create Agent: LLM response truncated (finish_reason=length, "
                    "output_tokens=%d). Will use per-platform fallback.",
                    llm_response.output_tokens,
                )

            # Guard against empty LLM response
            if not llm_response.content or not llm_response.content.strip():
                last_error = "LLM returned an empty response — the AI model may be overloaded."
                logger.warning("Create Agent: Empty response on attempt %d", attempt + 1)
                continue

            try:
                batch_strategy, post_dicts = parse_posts(llm_response.content)
                last_error = None
                break  # Success
            except json.JSONDecodeError as parse_err:
                last_error = str(parse_err)
                logger.warning(
                    "Create Agent: JSON parse failed on attempt %d: %s",
                    attempt + 1, parse_err,
                )
                # On retry, add a stricter instruction to the prompt
                prompt = (
                    prompt
                    + "\n\nCRITICAL: Your previous response had invalid JSON. "
                    "Return ONLY a valid JSON object. No markdown fences. "
                    "No trailing commas. Escape all special characters in strings. "
                    "Double-check every quote and bracket."
                )

        if last_error:
            raise json.JSONDecodeError(last_error, doc="", pos=0)

        # ── Content-length validation & per-platform regeneration ─────────
        # When the multi-platform batch was truncated the LLM may have
        # produced short / cut-off content for some platforms. Detect those
        # and regenerate individually so every platform gets a full post.
        platform_map = {p["platform"]: p for p in platforms}
        truncated_platforms = []

        for pd in post_dicts:
            plat = pd.get("platform", "").lower().strip()
            content = pd.get("content_text", "")
            min_len = _MIN_CONTENT_LENGTH.get(plat, 30)
            if len(content) < min_len:
                truncated_platforms.append(plat)
                logger.warning(
                    "Create Agent: %s content too short (%d chars, min %d) — "
                    "queuing for single-platform regen",
                    plat, len(content), min_len,
                )
            else:
                logger.info(
                    "Create Agent: %s content OK (%d chars)",
                    plat, len(content),
                )

        # When the LLM was token-limited, ANY platform's content could be
        # incomplete — not just the last one. Apply a 3× min-length bar to
        # every platform that wasn't already flagged by the normal check.
        if was_truncated_at_all and post_dicts:
            for pd in post_dicts:
                plat = pd.get("platform", "").lower().strip()
                if plat not in truncated_platforms:
                    content = pd.get("content_text", "")
                    min_len = _MIN_CONTENT_LENGTH.get(plat, 30)
                    if len(content) < min_len * 3:
                        truncated_platforms.append(plat)
                        logger.warning(
                            "Create Agent: %s likely truncated (%d chars, "
                            "was_truncated=True) — queuing for regen",
                            plat, len(content),
                        )

        # Check for platforms that are completely missing from the response
        parsed_platforms = {pd.get("platform", "").lower().strip() for pd in post_dicts}
        for p in platforms:
            if p["platform"] not in parsed_platforms:
                truncated_platforms.append(p["platform"])
                logger.warning(
                    "Create Agent: %s completely missing from LLM response — "
                    "queuing for single-platform regen",
                    p["platform"],
                )

        # Regenerate truncated / missing platforms one at a time
        if truncated_platforms:
            logger.info(
                "Create Agent: Regenerating %d truncated platforms: %s",
                len(truncated_platforms), truncated_platforms,
            )
            for plat in truncated_platforms:
                pinfo = platform_map.get(plat)
                if not pinfo:
                    continue
                new_pd = _regenerate_single_platform(user, seed, pinfo, system)
                if not new_pd:
                    continue
                # Replace the truncated post dict or append the missing one
                replaced = False
                for i, existing in enumerate(post_dicts):
                    if existing.get("platform", "").lower().strip() == plat:
                        post_dicts[i] = new_pd
                        replaced = True
                        break
                if not replaced:
                    post_dicts.append(new_pd)

        # Save batch strategy on the seed
        seed.batch_strategy = batch_strategy
        seed.save(update_fields=["batch_strategy", "updated_at"])

        # Create Post objects
        created_posts = []
        account_map = {a.platform: a for a in connected}

        # Normalize LLM platform names to our internal keys
        platform_aliases = {
            "twitter": "twitter", "x": "twitter", "x (twitter)": "twitter",
            "linkedin": "linkedin",
            "instagram": "instagram",
            "facebook": "facebook",
            "tiktok": "tiktok", "tik tok": "tiktok",
        }

        # Respect user's auto_approve_posts preference:
        # ON  → APPROVED (Adapt Agent will auto-schedule)
        # OFF → Smart auto-approval checks learned patterns first
        profile = getattr(user, "profile", None)
        if profile and profile.auto_approve_posts:
            initial_status = Post.Status.APPROVED
        else:
            initial_status = Post.Status.PENDING_APPROVAL

        for pd in post_dicts:
            raw_platform = pd.get("platform", "")
            platform = platform_aliases.get(raw_platform.lower().strip(), raw_platform.lower().strip())
            account = account_map.get(platform)
            if not account:
                logger.warning("LLM generated for platform '%s' but no account connected", platform)
                continue

            draft = PostDraft.from_llm_dict(pd)
            # Strip invisible Unicode characters (zero-width spaces, BOM markers,
            # soft hyphens) that Claude/GPT occasionally emit and that cause
            # LinkedIn / Facebook APIs to silently truncate the published post.
            from apps.content.tasks import sanitize_content
            content_text = sanitize_content(draft.content_text)
            if content_text != draft.content_text:
                logger.warning(
                    "Create Agent: stripped %d invisible char(s) from %s content before save.",
                    len(draft.content_text) - len(content_text), platform,
                )

            # Diagnostic: warn if content seems suspiciously short
            # (may indicate LLM token-limit truncation salvaged by JSON repair)
            if content_text and len(content_text) < 200 and platform in ("linkedin", "facebook"):
                logger.warning(
                    "Create Agent: %s content_text is only %d chars "
                    "(may be truncated). First 100: %s",
                    platform, len(content_text), repr(content_text[:100]),
                )

            _kwargs = draft.to_post_kwargs()
            post = Post.objects.create(
                user=user,
                seed=seed,
                product=seed.product if seed else None,
                social_account=account,
                platform=account.platform,
                content_text=content_text,
                content_type=draft.content_type or "original",
                content_intent=_kwargs.get("content_intent", ""),
                post_format=_kwargs.get("post_format", "text"),
                carousel_slides=_kwargs.get("carousel_slides", []),
                aspect_ratio=_kwargs.get("aspect_ratio", "square"),
                status=initial_status,
                generated_by_agent="create",
                predicted_engagement_score=draft.predicted_score,
                ai_reasoning=draft.reasoning,
                ai_angle=draft.angle,
                ai_framework=draft.framework_used,
                ai_original_text=content_text,
            )

            # Smart auto-approval: learn from user's history
            if post.status == Post.Status.PENDING_APPROVAL:
                if _should_auto_approve(user, post):
                    post.status = Post.Status.APPROVED
                    post.save(update_fields=["status", "updated_at"])

            # Auto-populate UTM fields for revenue attribution
            post.populate_utm()

            # ── Attach product image if available (Snap to Sell) ─────
            # If the seed's product has photos, use them directly instead
            # of generating AI images — real photos are better.
            # With multiple images, distribute them across posts (round-robin)
            # so each post gets a different angle/photo.
            product_image_attached = False
            if seed and seed.product and seed.product.image:
                try:
                    from apps.content.models import MediaAttachment

                    product = seed.product
                    all_urls = product.all_image_urls  # primary + additional

                    # Round-robin: pick a different image for each post
                    post_index = len(created_posts)  # 0-based index of this post
                    img_index = post_index % len(all_urls)
                    chosen_url = all_urls[img_index]

                    # Create MediaAttachment — use the actual file for primary,
                    # or the URL reference for additional images
                    if img_index == 0 and product.image:
                        attachment = MediaAttachment.objects.create(
                            post=post,
                            file=product.image,
                            file_type="image",
                            alt_text=product.name[:500],
                            order=0,
                        )
                    else:
                        # Additional images are stored via default_storage
                        from django.core.files.storage import default_storage
                        from django.core.files.base import ContentFile
                        # Try to read the file from storage path
                        storage_path = chosen_url.replace("/media/", "", 1) if chosen_url.startswith("/media/") else chosen_url.lstrip("/")
                        try:
                            with default_storage.open(storage_path) as f:
                                file_data = f.read()
                            ext = storage_path.rsplit(".", 1)[-1].lower()
                            filename = f"post_media/{post.pk}_{img_index}.{ext}"
                            attachment = MediaAttachment.objects.create(
                                post=post,
                                file_type="image",
                                alt_text=product.name[:500],
                                order=0,
                            )
                            attachment.file.save(filename, ContentFile(file_data), save=True)
                        except Exception:
                            # Fallback: just use the URL without a file attachment
                            attachment = None

                    # Set media_urls so the publishing pipeline picks it up
                    post.media_urls = [chosen_url]
                    post.media_status = Post.MediaStatus.UPLOADED
                    post.save(update_fields=["media_urls", "media_status", "updated_at"])
                    product_image_attached = True
                    logger.info(
                        "Attached product image %d/%d to post %s: %s",
                        img_index + 1, len(all_urls), post.id, chosen_url,
                    )
                except Exception as img_exc:
                    logger.warning("Failed to attach product image to post %s: %s", post.id, img_exc)

            # ── Resolve the user's Kova Link Page URL once for all platforms ──
            kova_page_url = _get_kova_page_url(user)

            # ── Facebook first-comment: populate link to be posted after publish ──
            # Facebook reduces organic reach 50-70% for posts with outbound links
            # in the body. We store the CTA link in first_comment so the
            # publishing task can post it as a comment immediately after going live.
            if platform == "facebook":
                from apps.utils.first_comments import compose_first_comment
                fc_text = compose_first_comment(
                    platform="facebook",
                    post=post,
                    product=getattr(seed, "product", None) if seed else None,
                    profile=profile,
                    kova_page_url=kova_page_url,
                )
                if fc_text:
                    post.first_comment = fc_text
                    post.save(update_fields=["first_comment", "updated_at"])

            # ── Instagram first-comment: save/link-in-bio CTA ────────────────
            # Links in IG captions are not clickable — the only click path is
            # the bio link. The first comment reinforces the CTA and prompts
            # saves (top algorithm signal). Keep it brief and action-oriented.
            if platform == "instagram":
                ig_fc = ""
                if seed and seed.product and getattr(seed.product, "product_url", ""):
                    name = seed.product.name or "this"
                    ig_fc = f"💾 Save this! 🛍️ Shop {name} — link in bio 👆"
                elif kova_page_url:
                    ig_fc = "💾 Save this post for later! 🔗 Everything's at the link in bio 👆"
                elif profile and getattr(profile, "website_url", ""):
                    ig_fc = "💾 Save this post for later! 🔗 More at the link in bio 👆"
                else:
                    ig_fc = "💾 Save this for later!"
                post.first_comment = ig_fc
                post.save(update_fields=["first_comment", "updated_at"])

            # ── LinkedIn first-comment: populate link to be posted after publish ──
            # LinkedIn suppresses organic reach ~50% for posts with outbound links
            # in the body. We store the CTA link in first_comment so the
            # publishing task posts it as a comment immediately after going live.
            if platform == "linkedin" and not (post.first_comment or "").strip():
                from apps.utils.first_comments import compose_first_comment
                li_fc = compose_first_comment(
                    platform="linkedin",
                    post=post,
                    product=getattr(seed, "product", None) if seed else None,
                    profile=profile,
                    kova_page_url=kova_page_url,
                )
                if li_fc:
                    post.first_comment = li_fc
                    post.save(update_fields=["first_comment", "updated_at"])

            # Store visual strategy on the Post for analytics tracking
            image_prompt = pd.get("image_prompt", "")
            visual_strategy_data = pd.get("visual_strategy", {})
            strategy_name = visual_strategy_data.get("strategy", "none") if visual_strategy_data else "none"
            post.visual_strategy = strategy_name if strategy_name else "none"
            post.visual_metadata = {
                k: v for k, v in {
                    "image_prompt": image_prompt,
                    "strategy_data": visual_strategy_data,
                }.items() if v
            }
            post.save(update_fields=[
                "utm_source", "utm_medium", "utm_campaign", "utm_content",
                "visual_strategy", "visual_metadata",
            ])

            # Generate visual for the post (plan-gated with monthly limit)
            # Images are auto-generated for platforms that REQUIRE them
            # (Instagram, TikTok, Pinterest). For text-first platforms
            # (Facebook, LinkedIn, etc.), images are generated only if the
            # user opted-in via the "Generate AI images" checkbox on the seed.
            has_visual_request = image_prompt or visual_strategy_data.get("strategy", "none") != "none"

            # Determine if this platform requires media
            post_platform = post.social_account.platform if post.social_account else ""
            platform_requires_media = post_platform in Post.MEDIA_REQUIRED_PLATFORMS
            user_opted_in_images = getattr(seed, "generate_images", False)

            if has_visual_request and (platform_requires_media or user_opted_in_images) and not product_image_attached:
                from apps.billing.models import get_plan_limits
                user_plan = getattr(getattr(seed.user, "profile", None), "plan", "starter")
                plan_limits = get_plan_limits(user_plan)
                if plan_limits.get("ai_image_generation", False):
                    # Enforce monthly image limit
                    from django.utils import timezone as tz
                    monthly_limit = plan_limits.get("ai_images_per_month", 5)
                    month_start = tz.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    images_this_month = Post.objects.filter(
                        user=seed.user,
                        media_status="generated",
                        created_at__gte=month_start,
                    ).count()
                    if images_this_month < monthly_limit:
                        # Dispatch image generation as async Celery task
                        # so the user sees posts immediately without waiting.
                        # Route by post_format: story/reel use generate_post_images
                        # (handles 9:16 aspect ratio); image format uses async_generate_image.
                        post.media_status = Post.MediaStatus.PENDING
                        post.media_prompt = image_prompt
                        post.save(update_fields=["media_status", "media_prompt", "updated_at"])
                        try:
                            from apps.utils import fire_task
                            if post.post_format in ("story", "reel"):
                                from apps.content.tasks import generate_post_images
                                fire_task(generate_post_images, str(post.id))
                            else:
                                from apps.content.tasks import async_generate_image
                                fire_task(
                                    async_generate_image,
                                    str(post.id),
                                    image_prompt,
                                    visual_strategy_data if visual_strategy_data.get("strategy") else None,
                                )
                        except Exception as img_exc:
                            logger.warning("Failed to queue image gen for post %s: %s", post.id, img_exc)
                    else:
                        logger.info(
                            "Image limit reached for %s (%d/%d this month)",
                            seed.user, images_this_month, monthly_limit,
                        )
                        post.media_status = "none"
                        post.save(update_fields=["media_status", "updated_at"])
                else:
                    logger.info("Skipping visual gen for %s (plan: %s)", seed.user, user_plan)

            created_posts.append(post)

        # Update seed status
        seed.status = ContentSeed.SeedStatus.COMPLETED
        seed.save(update_fields=["status", "updated_at"])

        # Complete action log
        action.status = AgentAction.ActionStatus.COMPLETED
        action.output_data = {
            "posts_created": len(created_posts),
            "post_ids": [str(p.id) for p in created_posts],
            "platforms": [p.social_account.platform for p in created_posts],
        }
        action.tokens_used = llm_response.total_tokens
        action.input_tokens = llm_response.input_tokens
        action.output_tokens = llm_response.output_tokens
        action.model_used = llm_response.model
        action.duration_ms = llm_response.duration_ms
        action.completed_at = dj_timezone.now()
        action.save()

        logger.info(
            "Create Agent: Generated %d posts from seed '%s' (%d tokens)",
            len(created_posts), seed.idea[:50], llm_response.total_tokens,
        )
        return created_posts

    except json.JSONDecodeError as exc:
        seed.status = ContentSeed.SeedStatus.FAILED
        seed.error_message = f"Failed to parse AI response: {exc}"
        seed.save(update_fields=["status", "error_message", "updated_at"])
        action.status = AgentAction.ActionStatus.FAILED
        action.error_message = str(exc)
        action.completed_at = dj_timezone.now()
        action.save()
        logger.error("Create Agent JSON parse error: %s", exc)
        return []

    except Exception as exc:
        seed.status = ContentSeed.SeedStatus.FAILED
        seed.error_message = f"Agent error: {exc}"
        seed.save(update_fields=["status", "error_message", "updated_at"])
        action.status = AgentAction.ActionStatus.FAILED
        action.error_message = str(exc)
        action.completed_at = dj_timezone.now()
        action.save()
        logger.error("Create Agent error: %s", exc, exc_info=True)
        return []


def regenerate_single_post(post: Post) -> Post:
    """
    Regenerate content for a single post on its original platform.

    Uses the seed idea (or the existing content if no seed) and generates
    a fresh take — different angle, different framework. Returns the
    updated Post object, or raises on failure.
    """
    user = post.user
    account = post.social_account
    platform = account.platform if account else "twitter"

    guide = PLATFORM_GUIDES.get(platform, {})
    winning = "\n".join(f"  - {w}" for w in guide.get("winning_patterns", []))

    # Source idea — prefer seed, fall back to existing content
    if post.seed:
        idea = post.seed.idea
        notes = post.seed.notes or ""
    else:
        idea = post.content_text[:500]
        notes = ""

    system = build_system_prompt(user)

    prompt = f"""## REGENERATE — SINGLE PLATFORM POST

You previously generated a post for {guide.get('name', platform.title())} that the user wants refreshed.
Generate a COMPLETELY NEW VERSION with a different angle, framework, and hook.

### THE IDEA
{idea}
{f"### ADDITIONAL CONTEXT" + chr(10) + notes if notes else ""}

### PREVIOUS VERSION (do NOT repeat this — take a fresh approach)
{post.content_text}
{f"Previous angle: {post.ai_angle}" if post.ai_angle else ""}
{f"Previous framework: {post.ai_framework}" if post.ai_framework else ""}

### PLATFORM: {guide.get('name', platform.title())} (@{account.username if account else 'user'})
- **Character limit**: {guide.get('max_chars', 'N/A')}
- **Platform psychology**: {guide.get('psychology', 'Adapt to platform norms')}
- **What wins here**:
{winning}
- **Avoid**: {guide.get('avoid', 'Generic content')}
- **CTA approach**: {guide.get('cta_style', 'Adapt to context')}

{CONTENT_FRAMEWORKS}
{ENGAGEMENT_ENGINEERING}

### OUTPUT FORMAT
Respond with a JSON object. No markdown code fences.
{{
  "content_text": "The full refreshed post text, ready to publish.",
  "framework_used": "Name of the framework you chose",
  "angle": "Brief description of the new angle",
  "reasoning": "Why this new version will perform better",
  "predicted_score": 75
}}
"""

    action = AgentAction.objects.create(
        user=user,
        agent_type="create",
        action_type="regenerate_post",
        description=f"Regenerating {platform} post: {idea[:80]}",
        status=AgentAction.ActionStatus.STARTED,
        input_data={"post_id": str(post.id), "platform": platform},
    )

    try:
        llm_response: LLMResponse = generate(
            prompt=prompt,
            system=system,
            model=get_model_for_task("create.regenerate", user=user),
            json_mode=True,
            temperature=0.8,  # Slightly higher for creative diversity
            max_tokens=2048,
        )

        data = parse_llm_json(llm_response.content)
        draft = PostDraft.from_llm_dict(data)

        # Keep existing content_text if the LLM returned nothing usable
        post.content_text = draft.content_text or post.content_text
        post.ai_angle = draft.angle
        post.ai_framework = draft.framework_used
        post.ai_reasoning = draft.reasoning
        post.predicted_engagement_score = draft.predicted_score
        post.save(update_fields=[
            "content_text", "ai_angle", "ai_framework", "ai_reasoning",
            "predicted_engagement_score", "updated_at",
        ])

        action.status = AgentAction.ActionStatus.COMPLETED
        action.output_data = {"post_id": str(post.id), "platform": platform}
        action.tokens_used = llm_response.total_tokens
        action.input_tokens = llm_response.input_tokens
        action.output_tokens = llm_response.output_tokens
        action.model_used = llm_response.model
        action.duration_ms = llm_response.duration_ms
        action.completed_at = dj_timezone.now()
        action.save()

        logger.info("Regenerated %s post %s (%d tokens)", platform, post.id, llm_response.total_tokens)
        return post

    except Exception as exc:
        action.status = AgentAction.ActionStatus.FAILED
        action.error_message = str(exc)
        action.completed_at = dj_timezone.now()
        action.save()
        logger.error("Regenerate post error: %s", exc, exc_info=True)
        raise


def repurpose_post(source_post: Post, target_platforms: list[str] = None) -> list[Post]:
    """
    Take a top-performing post and repurpose it for other platforms.

    The AI doesn't just reformat — it reconceives the idea for each
    platform's psychology and audience behavior. A LinkedIn framework post
    becomes a Twitter hot take, an Instagram save-worthy carousel, etc.

    Args:
        source_post: The published Post to repurpose.
        target_platforms: List of platform keys to repurpose for.
                         If None, uses all connected platforms except the source.

    Returns list of new Post objects (pending approval).
    """
    user = source_post.user
    source_platform = source_post.social_account.platform if source_post.social_account else "unknown"

    # Find target accounts
    connected = SocialAccount.objects.filter(user=user, is_active=True)
    if target_platforms:
        connected = connected.filter(platform__in=target_platforms)
    else:
        connected = connected.exclude(platform=source_platform)

    if not connected.exists():
        return []

    platforms = [{"platform": a.platform, "username": a.username, "account_id": str(a.id)} for a in connected]

    # Build performance context for the source post
    source_engagement = ""
    try:
        m = source_post.metrics
        source_engagement = (
            f"Engagement: {m.likes} likes, {m.comments} comments, {m.shares} shares, "
            f"{m.impressions} impressions, {m.engagement_rate or 0:.1f}% rate"
        )
    except Exception:
        source_engagement = "Performance data not yet available"

    action = AgentAction.objects.create(
        user=user,
        agent_type="create",
        action_type="repurpose_post",
        description=f"Repurposing {source_platform} post to {len(platforms)} platforms",
        status=AgentAction.ActionStatus.STARTED,
        input_data={
            "source_post_id": str(source_post.id),
            "source_platform": source_platform,
            "target_platforms": [p["platform"] for p in platforms],
        },
    )

    try:
        system = build_system_prompt(user)

        platform_section = ""
        for p in platforms:
            guide = PLATFORM_GUIDES.get(p["platform"], {})
            winning = "\n".join(f"    - {w}" for w in guide.get("winning_patterns", []))
            platform_section += f"""
### {guide.get('name', p['platform'].title())} (@{p['username']})
- **Character limit**: {guide.get('max_chars', 'N/A')}
- **Platform psychology**: {guide.get('psychology', 'Adapt to platform norms')}
- **What wins here**:
{winning}
- **CTA approach**: {guide.get('cta_style', 'Adapt to context')}
"""

        prompt = f"""## REPURPOSE — TRANSFORM A WINNER FOR NEW PLATFORMS

This post performed well on {PLATFORM_GUIDES.get(source_platform, {}).get('name', source_platform.title())}.
Your job: extract the CORE INSIGHT and reconceive it natively for each target platform.

DO NOT just reformat or shorten the original. Each platform version must:
- Take an angle that's NATIVE to that platform's culture
- Use hooks that work specifically on that platform
- Feel like it was written FOR that platform, not cross-posted

### SOURCE POST ({PLATFORM_GUIDES.get(source_platform, {}).get('name', source_platform.title())})
{source_post.content_text}

### SOURCE PERFORMANCE
{source_engagement}
{f"Angle: {source_post.ai_angle}" if source_post.ai_angle else ""}
{f"Framework: {source_post.ai_framework}" if source_post.ai_framework else ""}

### WHY IT WORKED
Analyze what made this content perform. Then translate THOSE QUALITIES
(not the exact words) into each platform's native language.

### TARGET PLATFORMS
{platform_section}

### OUTPUT FORMAT
Respond with a JSON object. No markdown code fences.
{{
  "repurpose_strategy": "One sentence: what's the core insight being repurposed and how the angle shifts per platform.",
  "posts": [
    {{
      "platform": "twitter",
      "username": "@handle",
      "content_text": "Full post text, ready to publish.",
      "content_type": "repurposed",
      "format": "single tweet",
      "framework_used": "Hook → Value → CTA",
      "angle": "How this platform's version differs from the original",
      "reasoning": "Why this adaptation works for this platform's audience",
      "predicted_score": 75
    }}
  ]
}}
"""

        llm_response: LLMResponse = generate(
            prompt=prompt,
            system=system,
            model=get_model_for_task("create.repurpose", user=user),
            json_mode=True,
            temperature=0.7,
            max_tokens=16384,
        )

        _, post_dicts = parse_posts(llm_response.content)

        created_posts = []
        account_map = {a.platform: a for a in connected}
        platform_aliases = {
            "twitter": "twitter", "x": "twitter", "x (twitter)": "twitter",
            "linkedin": "linkedin", "instagram": "instagram",
            "facebook": "facebook", "tiktok": "tiktok",
        }

        for pd in post_dicts:
            raw_platform = pd.get("platform", "")
            platform = platform_aliases.get(raw_platform.lower().strip(), raw_platform.lower().strip())
            account = account_map.get(platform)
            if not account:
                continue

            # Respect user's auto_approve_posts preference
            _profile = getattr(user, "profile", None)
            _status = (
                Post.Status.APPROVED
                if _profile and _profile.auto_approve_posts
                else Post.Status.PENDING_APPROVAL
            )
            draft = PostDraft.from_llm_dict(pd)
            _rp_kwargs = draft.to_post_kwargs()
            post = Post.objects.create(
                user=user,
                seed=source_post.seed,
                product=source_post.product,
                social_account=account,
                platform=account.platform,
                content_text=draft.content_text,
                content_type="repurposed",
                content_intent=_rp_kwargs.get("content_intent", ""),
                post_format=_rp_kwargs.get("post_format", "text"),
                carousel_slides=_rp_kwargs.get("carousel_slides", []),
                aspect_ratio=_rp_kwargs.get("aspect_ratio", "square"),
                status=_status,
                generated_by_agent="create",
                predicted_engagement_score=draft.predicted_score,
                ai_reasoning=draft.reasoning,
                ai_angle=draft.angle,
                ai_framework=draft.framework_used,
            )
            # Auto-populate UTM fields for revenue attribution
            post.populate_utm()
            post.save(update_fields=["utm_source", "utm_medium", "utm_campaign", "utm_content"])
            created_posts.append(post)

        action.status = AgentAction.ActionStatus.COMPLETED
        action.output_data = {
            "posts_created": len(created_posts),
            "post_ids": [str(p.id) for p in created_posts],
            "source_post_id": str(source_post.id),
        }
        action.tokens_used = llm_response.total_tokens
        action.input_tokens = llm_response.input_tokens
        action.output_tokens = llm_response.output_tokens
        action.model_used = llm_response.model
        action.completed_at = dj_timezone.now()
        action.save()

        logger.info(
            "Repurposed %s post → %d new posts (%d tokens)",
            source_platform, len(created_posts), llm_response.total_tokens,
        )
        return created_posts

    except Exception as exc:
        action.status = AgentAction.ActionStatus.FAILED
        action.error_message = str(exc)
        action.completed_at = dj_timezone.now()
        action.save()
        logger.error("Repurpose error: %s", exc, exc_info=True)
        return []


# ─── A/B Testing — Multi-variant generation ──────────────────────────────────

VARIANT_LABELS = "ABCDEFGHIJ"


def generate_ab_variants(ab_test) -> list[Post]:
    """
    Generate multiple content variants for an A/B test.

    Each variant gets a different strategic angle/framework/hook so the user
    can publish them and let real engagement data determine the winner.

    Args:
        ab_test: ABTest instance with seed, social_account, variant_count set.

    Returns list of created Post objects (one per variant).
    """
    from apps.content.models import ABTest

    user = ab_test.user
    account = ab_test.social_account
    platform = account.platform
    seed = ab_test.seed
    n = ab_test.variant_count

    guide = PLATFORM_GUIDES.get(platform, {})
    winning = "\n".join(f"    - {w}" for w in guide.get("winning_patterns", []))

    idea = seed.idea if seed else ab_test.name
    notes = seed.notes if seed else ""

    action = AgentAction.objects.create(
        user=user,
        agent_type="create",
        action_type="ab_variant_generation",
        description=f"Generating {n} A/B variants for: {idea[:80]}",
        status=AgentAction.ActionStatus.STARTED,
        input_data={
            "ab_test_id": str(ab_test.id),
            "platform": platform,
            "variant_count": n,
        },
    )

    try:
        system = build_system_prompt(user)

        prompt = f"""## A/B TEST — GENERATE {n} DISTINCT CONTENT VARIANTS

Your goal: create {n} meaningfully different versions of the same idea.
Each variant MUST differ in at least TWO of these dimensions:
  - **Angle**: The perspective or spin on the topic
  - **Hook**: How the first line grabs attention
  - **Framework**: Content structure (Hook→Value→CTA, PAS, Story→Lesson, etc.)
  - **Tone**: Emotional register (bold, educational, humorous, provocative, etc.)
  - **Format**: Length, structure, use of questions/stats/emojis

The purpose is A/B testing — we'll publish these variants and measure which
one the real audience engages with most. So maximize GENUINE diversity.

### THE IDEA
{idea}
{f"### ADDITIONAL CONTEXT" + chr(10) + notes if notes else ""}

### PLATFORM: {guide.get('name', platform.title())} (@{account.username})
- **Character limit**: {guide.get('max_chars', 'N/A')}
- **Platform psychology**: {guide.get('psychology', 'Adapt to platform norms')}
- **What wins here**:
{winning}
- **Avoid**: {guide.get('avoid', 'Generic content')}
- **CTA approach**: {guide.get('cta_style', 'Adapt to context')}

{CONTENT_FRAMEWORKS}
{ENGAGEMENT_ENGINEERING}

### OUTPUT FORMAT
Respond with a JSON object. No markdown code fences.
{{
  "variants": [
    {{
      "label": "A",
      "content_text": "Full post text, ready to publish.",
      "framework_used": "Hook → Value → CTA",
      "angle": "Specific angle taken",
      "reasoning": "Why this variant might win — what engagement pattern it targets.",
      "predicted_score": 72,
      "differentiation": "How this variant differs from the others"
    }}
  ]
}}

Generate exactly {n} variants labeled {', '.join(VARIANT_LABELS[:n])}.
"""

        llm_response: LLMResponse = generate(
            prompt=prompt,
            system=system,
            model=get_model_for_task("create.generate", user=user),
            json_mode=True,
            temperature=0.85,  # Higher for maximum diversity
            max_tokens=16384,
        )

        data = parse_llm_json(llm_response.content)
        variant_dicts = data.get("variants", [])

        if not variant_dicts:
            raise ValueError("LLM returned no variants")

        created_posts = []
        # Respect user's auto_approve_posts preference
        _profile = getattr(user, "profile", None)
        initial_status = (
            Post.Status.APPROVED
            if _profile and _profile.auto_approve_posts
            else Post.Status.PENDING_APPROVAL
        )

        for i, vd in enumerate(variant_dicts[:n]):
            label = vd.get("label", VARIANT_LABELS[i] if i < len(VARIANT_LABELS) else str(i + 1))
            draft = PostDraft.from_llm_dict(vd)
            _ab_kwargs = draft.to_post_kwargs()
            post = Post.objects.create(
                user=user,
                seed=seed,
                product=seed.product if seed else None,
                social_account=account,
                platform=account.platform,
                ab_test=ab_test,
                variant_label=label,
                content_text=draft.content_text,
                content_type="original",
                content_intent=_ab_kwargs.get("content_intent", ""),
                post_format=_ab_kwargs.get("post_format", "text"),
                carousel_slides=_ab_kwargs.get("carousel_slides", []),
                aspect_ratio=_ab_kwargs.get("aspect_ratio", "square"),
                status=initial_status,
                generated_by_agent="create",
                predicted_engagement_score=draft.predicted_score,
                ai_reasoning=draft.reasoning,
                ai_angle=draft.angle,
                ai_framework=draft.framework_used,
            )
            # Auto-populate UTM fields for revenue attribution
            post.populate_utm()
            post.save(update_fields=["utm_source", "utm_medium", "utm_campaign", "utm_content"])
            created_posts.append(post)

        # Update test status
        ab_test.status = ABTest.Status.DRAFT
        ab_test.save(update_fields=["status", "updated_at"])

        # Mark seed as completed if present
        if seed and seed.status != "completed":
            from apps.content.models import ContentSeed
            seed.status = ContentSeed.SeedStatus.COMPLETED
            seed.save(update_fields=["status", "updated_at"])

        action.status = AgentAction.ActionStatus.COMPLETED
        action.output_data = {
            "posts_created": len(created_posts),
            "post_ids": [str(p.id) for p in created_posts],
            "labels": [p.variant_label for p in created_posts],
        }
        action.tokens_used = llm_response.total_tokens
        action.input_tokens = llm_response.input_tokens
        action.output_tokens = llm_response.output_tokens
        action.model_used = llm_response.model
        action.completed_at = dj_timezone.now()
        action.save()

        logger.info(
            "A/B Test: Generated %d variants for '%s' (%d tokens)",
            len(created_posts), idea[:50], llm_response.total_tokens,
        )
        return created_posts

    except Exception as exc:
        ab_test.status = ABTest.Status.CANCELLED
        ab_test.save(update_fields=["status", "updated_at"])
        action.status = AgentAction.ActionStatus.FAILED
        action.error_message = str(exc)
        action.completed_at = dj_timezone.now()
        action.save()
        logger.error("A/B variant generation error: %s", exc, exc_info=True)
        return []
