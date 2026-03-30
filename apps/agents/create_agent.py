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
from datetime import datetime, timedelta, timezone

from django.utils import timezone as dj_timezone

from apps.agents.llm import generate, LLMResponse
from apps.agents.models import AgentAction, AgentConfig
from apps.content.models import ContentSeed, Post
from apps.platforms.models import SocialAccount

logger = logging.getLogger(__name__)


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
    except Exception:
        pass

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
    except Exception:
        pass

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
    except Exception:
        pass

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
        "psychology": "Professional credibility + vulnerability. People engage with frameworks they can steal and stories they relate to. The best posts teach something specific or share a hard-won lesson.",
        "winning_patterns": [
            "Personal story → universal business lesson (the 'I failed at X and learned Y' format)",
            "Numbered framework/list with actionable steps",
            "Contrarian industry take backed by experience",
            "Behind-the-scenes of a decision/process with real numbers",
            "Hook line → line break → line break → story → lesson → question to audience",
        ],
        "avoid": "Humble-bragging, 'Agree?' as a CTA, fake stories, emoji walls, 'I'm thrilled to share' openings",
        "cta_style": "End with a genuine question that invites people to share their experience. Make it specific, not generic.",
        "formats": ["text post", "article-style post", "carousel outline"],
    },
    "instagram": {
        "name": "Instagram",
        "max_chars": 2200,
        "psychology": "Aspiration + education. Save-worthy content wins the algorithm. Carousels get 3x engagement. People save posts that teach them something they can reference later.",
        "winning_patterns": [
            "Carousel-style: '5 things I wish I knew about X' (write as numbered list)",
            "Micro-lesson: one specific tip explained in depth",
            "Before/after transformation stories",
            "Quote-style caption with deep context below",
            "Behind-the-scenes with authentic storytelling",
        ],
        "avoid": "Stock photo language, over-polished corporate tone, irrelevant hashtags, being preachy",
        "cta_style": "Save this for later / Share with someone who needs this / Drop a 🔥 if you agree",
        "formats": ["photo caption", "carousel caption", "reel script"],
    },
    "facebook": {
        "name": "Facebook",
        "max_chars": 63206,
        "psychology": "Community + conversation. Facebook rewards posts that generate long comment threads. Storytelling and relatable content get shared. People share content that makes them look thoughtful or helpful.",
        "winning_patterns": [
            "Story format: setup → tension → resolution → lesson",
            "Opinion piece that invites debate (not controversy, but perspective)",
            "Helpful resource or tip framed as 'Something I just learned'",
            "Question that taps into shared experience",
            "Longer-form storytelling with emotional hooks",
        ],
        "avoid": "Clickbait, engagement bait ('Tag 3 friends'), overly promotional, link-only posts",
        "cta_style": "Ask a genuine question. 'What's been your experience with X?' works better than 'Like if you agree'.",
        "formats": ["text post", "link post with commentary", "photo post"],
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

    # Company context
    context_lines = []
    if profile.company_name:
        context_lines.append(f"**Company**: {profile.company_name}")
    if profile.industry:
        context_lines.append(f"**Industry**: {profile.get_industry_display()}")
    if profile.website_url:
        context_lines.append(f"**Website**: {profile.website_url}")
    if context_lines:
        parts.append("## BRAND CONTEXT\n" + "\n".join(context_lines))

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

    # Performance intelligence — the feedback loop
    intel = _get_performance_intelligence(user)
    if intel:
        parts.append(intel)

    return "\n".join(parts)


def build_generation_prompt(seed: ContentSeed, platforms: list[dict]) -> str:
    """Build the user prompt with strategic platform targeting."""
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
- **Avoid**: {guide.get('avoid', 'Generic content')}
- **CTA approach**: {guide.get('cta_style', 'Adapt to context')}
- **Format options**: {', '.join(guide.get('formats', ['text post']))}
"""

    prompt = f"""## YOUR TASK

Transform this raw idea into high-performing, platform-native content.

### THE IDEA
{seed.idea}
{f"### ADDITIONAL CONTEXT FROM USER" + chr(10) + seed.notes if seed.notes else ""}

### STRATEGIC THINKING (do this before writing)
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
      "platform": "twitter",
      "username": "@handle",
      "content_text": "The full post text, ready to publish. Include line breaks, formatting, hashtags as native to the platform.",
      "content_type": "original",
      "format": "single tweet",
      "framework_used": "Hook → Value → CTA",
      "angle": "Brief description of the specific angle chosen for this platform",
      "reasoning": "Why this angle, framework, and format will perform well here. What engagement pattern it targets.",
      "predicted_score": 72
    }}
  ]
}}

IMPORTANT:
- Generate ONE post per platform
- Each post MUST take a DIFFERENT angle on the idea — do NOT rewrite the same content
- predicted_score is your honest assessment (0-100) of performance potential
- Content must be READY TO PUBLISH — no placeholders, no [insert X here]
"""
    return prompt


def parse_posts(llm_content: str) -> tuple[str, list[dict]]:
    """
    Parse the LLM JSON response into post dicts. Resilient to markdown fences.
    Returns (batch_strategy, list_of_post_dicts).
    """
    text = llm_content.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```) and last line (```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    data = json.loads(text)
    batch_strategy = data.get("batch_strategy", "")
    return batch_strategy, data.get("posts", [])


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

        # Call LLM
        llm_response: LLMResponse = generate(
            prompt=prompt,
            system=system,
            json_mode=True,
            temperature=0.7,
            max_tokens=4096,
        )

        # Parse response
        batch_strategy, post_dicts = parse_posts(llm_response.content)

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

        # Determine initial status based on auto-approve setting
        auto_approve = getattr(user.profile, "auto_approve_posts", False)
        initial_status = Post.Status.APPROVED if auto_approve else Post.Status.PENDING_APPROVAL

        for pd in post_dicts:
            raw_platform = pd.get("platform", "")
            platform = platform_aliases.get(raw_platform.lower().strip(), raw_platform.lower().strip())
            account = account_map.get(platform)
            if not account:
                logger.warning("LLM generated for platform '%s' but no account connected", platform)
                continue

            post = Post.objects.create(
                user=user,
                seed=seed,
                social_account=account,
                content_text=pd.get("content_text", ""),
                content_type=pd.get("content_type", "original"),
                status=initial_status,
                generated_by_agent="create",
                predicted_engagement_score=pd.get("predicted_score"),
                ai_reasoning=pd.get("reasoning", ""),
                ai_angle=pd.get("angle", ""),
                ai_framework=pd.get("framework_used", ""),
            )
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
            json_mode=True,
            temperature=0.8,  # Slightly higher for creative diversity
            max_tokens=2048,
        )

        text = llm_response.content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)

        data = json.loads(text)

        post.content_text = data.get("content_text", post.content_text)
        post.ai_angle = data.get("angle", "")
        post.ai_framework = data.get("framework_used", "")
        post.ai_reasoning = data.get("reasoning", "")
        post.predicted_engagement_score = data.get("predicted_score")
        post.save(update_fields=[
            "content_text", "ai_angle", "ai_framework", "ai_reasoning",
            "predicted_engagement_score", "updated_at",
        ])

        action.status = AgentAction.ActionStatus.COMPLETED
        action.output_data = {"post_id": str(post.id), "platform": platform}
        action.tokens_used = llm_response.total_tokens
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
            json_mode=True,
            temperature=0.7,
            max_tokens=4096,
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

            post = Post.objects.create(
                user=user,
                seed=source_post.seed,
                social_account=account,
                content_text=pd.get("content_text", ""),
                content_type="repurposed",
                status=Post.Status.PENDING_APPROVAL,
                generated_by_agent="create",
                predicted_engagement_score=pd.get("predicted_score"),
                ai_reasoning=pd.get("reasoning", ""),
                ai_angle=pd.get("angle", ""),
                ai_framework=pd.get("framework_used", ""),
            )
            created_posts.append(post)

        action.status = AgentAction.ActionStatus.COMPLETED
        action.output_data = {
            "posts_created": len(created_posts),
            "post_ids": [str(p.id) for p in created_posts],
            "source_post_id": str(source_post.id),
        }
        action.tokens_used = llm_response.total_tokens
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
