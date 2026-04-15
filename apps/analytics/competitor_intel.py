"""
Competitor Intelligence Engine — AI-Powered Competitive Analysis.

This is NOT a scraper. It uses LLM intelligence + user-provided context to:
  1. Analyze competitor social media strategy (what they do well, where they fail)
  2. Compare competitor vs user's own strategy (head-to-head SWOT)
  3. Generate actionable content ideas from competitive gaps
  4. Detect strategy shifts and emerging threats
  5. Surface insights in Daily Brief + Strategist recommendations

The key insight: competitors are free training data. Their successes teach you
what works WITHOUT spending your own time/money experimenting.

Architecture:
  User adds competitor (name + handles + notes) →
  AI analyzes their strategy (using LLM knowledge + user context) →
  Generates SWOT + actionable insights →
  Insights feed into: Strategist, Daily Brief, Content Studio suggestions
"""

import json
import logging
from datetime import timedelta

from django.utils import timezone

from apps.agents.llm import generate, get_model_for_task, parse_llm_json
from apps.agents.models import AgentAction
from apps.analytics.models import (
    Competitor,
    CompetitorAnalysis,
    CompetitorInsight,
)
from apps.content.models import Post

logger = logging.getLogger(__name__)


# ─── User Context Builder ────────────────────────────────────────────────────

def _build_user_context(user):
    """Build context about the user's brand for comparison."""
    profile = getattr(user, "profile", None)

    # Get Content DNA (what's working for the user)
    recent_posts = (
        Post.objects.filter(user=user, status=Post.Status.PUBLISHED)
        .order_by("-published_at")[:15]
    )

    content_dna = {}
    for post in recent_posts:
        dna = post.content_dna or {}
        for key, val in dna.items():
            if key not in content_dna:
                content_dna[key] = []
            if isinstance(val, list):
                content_dna[key].extend(val)
            else:
                content_dna[key].append(val)

    # Connected platforms
    platforms = list(
        user.social_accounts.filter(is_active=True)
        .values_list("platform", flat=True)
        .distinct()
    )

    return {
        "company": getattr(profile, "company_name", "") if profile else "",
        "industry": getattr(profile, "industry", "") if profile else "",
        "brand_voice": getattr(profile, "brand_voice", "") if profile else "",
        "target_audience": getattr(profile, "target_audience", "") if profile else "",
        "content_pillars": getattr(profile, "content_pillars", []) if profile else [],
        "goals": getattr(profile, "goals", []) if profile else [],
        "platforms": platforms,
        "content_dna_summary": {k: list(set(v))[:5] for k, v in content_dna.items()},
        "post_count_30d": Post.objects.filter(
            user=user, status=Post.Status.PUBLISHED,
            published_at__gte=timezone.now() - timedelta(days=30),
        ).count(),
    }


def _build_competitor_context(competitor):
    """Build context about a competitor for analysis."""
    return {
        "name": competitor.name,
        "website": competitor.website,
        "industry": competitor.industry,
        "notes": competitor.notes,
        "handles": competitor.handles,
        "platforms": competitor.platforms_tracked,
        "previous_strengths": competitor.strengths[:3] if competitor.strengths else [],
        "previous_weaknesses": competitor.weaknesses[:3] if competitor.weaknesses else [],
        "previous_patterns": competitor.content_patterns,
    }


def _extract_partial_competitor_result(raw_content: str) -> dict:
    """
    Best-effort extraction of competitor analysis fields from broken/truncated JSON.
    Tries to pull recognizable fields via regex so we don't lose the entire analysis.
    """
    import re

    result = {
        "summary": "",
        "content_strategy": {},
        "strengths": [],
        "weaknesses": [],
        "opportunities": [],
        "threats": [],
        "comparison": {},
        "actionable_insights": [],
        "threat_level": "medium",
    }

    def _extract_string(key):
        m = re.search(rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_content, re.DOTALL)
        return m.group(1).replace("\\n", "\n").replace('\\"', '"') if m else ""

    def _extract_list(key):
        m = re.search(rf'"{key}"\s*:\s*\[(.*?)\]', raw_content, re.DOTALL)
        if not m:
            return []
        items = re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1))
        return [i.replace("\\n", "\n").replace('\\"', '"') for i in items if i.strip()]

    result["summary"] = _extract_string("summary") or raw_content[:500]
    result["strengths"] = _extract_list("strengths")
    result["weaknesses"] = _extract_list("weaknesses")
    result["opportunities"] = _extract_list("opportunities")
    result["threats"] = _extract_list("threats")
    result["threat_level"] = _extract_string("threat_level") or "medium"

    return result


# ─── Full Analysis ───────────────────────────────────────────────────────────

def analyze_competitor(user, competitor):
    """
    Run a full AI analysis of a competitor's social media strategy.

    The LLM synthesizes:
    - What it knows about this brand/business publicly
    - The social handles provided (it can reason about platform usage)
    - User-provided notes and context
    - Comparison with the user's own strategy

    Returns a CompetitorAnalysis object.
    """
    action = AgentAction.objects.create(
        user=user,
        agent_type="research",
        action_type="competitor_analysis",
        description=f"Analyzing competitor: {competitor.name}",
        input_data={"competitor_id": str(competitor.id), "name": competitor.name},
    )

    try:
        user_ctx = _build_user_context(user)
        comp_ctx = _build_competitor_context(competitor)

        system_prompt = (
            "You are an elite competitive intelligence analyst specializing in social media "
            "and digital marketing strategy for African and global markets.\n"
            "You're analyzing a competitor for a business. Think like a war-room strategist:\n\n"
            "1. WHAT are they doing? (content themes, formats, frequency, tone, platforms)\n"
            "2. What's WORKING for them? (identify strengths from their strategy)\n"
            "3. What are they MISSING? (gaps, weaknesses, blind spots)\n"
            "4. How does the USER compare? (where is the user winning vs losing)\n"
            "5. What can the user STEAL/ADAPT? (actionable opportunities)\n"
            "6. PRICING & POSITIONING — how do they price/position vs the user?\n"
            "7. AUDIENCE ENGAGEMENT — quality of their community, not just size\n"
            "8. PROMOTIONAL PATTERNS — how/when do they run campaigns, discounts, launches?\n"
            "9. PLATFORM-SPECIFIC TACTICS — what do they do differently on each platform?\n"
            "10. REPUTATION & SENTIMENT — how do customers talk about them publicly?\n\n"
            "Be SPECIFIC and ACTIONABLE. Not 'they post good content' — instead:\n"
            "'They post behind-the-scenes kitchen Reels 3x/week which likely drives high saves. "
            "You're not doing any BTS content — this is a gap you can fill.'\n\n"
            "INDUSTRY CONTEXT: Analyze through the lens of their specific industry.\n"
            "For e-commerce (Jumia, Jiji, Kilimall): compare product range, delivery, pricing, "
            "promotional frequency, flash sales, payment options, customer service channels.\n"
            "For restaurants/food: compare menu variety, delivery platforms, review responses, "
            "food photography quality, influencer partnerships.\n"
            "For tech/SaaS: compare feature marketing, case studies, thought leadership, "
            "comparison pages, onboarding content, developer relations.\n\n"
            "Use what you know about the brand. If you don't know them specifically, "
            "analyze based on their industry, platform presence, and the user's notes.\n\n"
            "Respond in JSON:\n"
            '{\n'
            '  "summary": "2-3 sentence executive summary of their overall strategy and market positioning",\n'
            '  "content_strategy": {\n'
            '    "primary_themes": ["list of main content themes"],\n'
            '    "content_formats": ["formats they likely use most: reels, carousels, stories, etc."],\n'
            '    "posting_frequency": "estimated posts per week per platform",\n'
            '    "tone": "their brand voice/tone description",\n'
            '    "best_platforms": ["their strongest platforms ranked"],\n'
            '    "target_audience": "who they seem to target",\n'
            '    "engagement_quality": "how well their audience engages — comments quality, shares, saves",\n'
            '    "promotional_patterns": "how often they run promos, flash sales, campaigns",\n'
            '    "platform_tactics": {"instagram": "what they do specifically on IG", "twitter": "...", "etc": "..."}\n'
            '  },\n'
            '  "strengths": ["3-5 specific things they do well — be concrete, not vague"],\n'
            '  "weaknesses": ["3-5 specific gaps or weaknesses — things they neglect, do poorly, or miss entirely"],\n'
            '  "opportunities": ["3-5 things YOU can do that THEY miss — content angles, platforms, audiences they ignore"],\n'
            '  "threats": ["2-3 things they do that directly threaten your positioning"],\n'
            '  "comparison": {\n'
            '    "you_win": ["specific areas where the user is stronger"],\n'
            '    "they_win": ["specific areas where the competitor is stronger"],\n'
            '    "neutral": ["areas roughly equal or incomparable"]\n'
            '  },\n'
            '  "pricing_positioning": {\n'
            '    "pricing_approach": "premium/mid-range/budget/freemium — how they position on price",\n'
            '    "value_proposition": "what they promise vs the user",\n'
            '    "differentiation": "how they differentiate from competitors like the user"\n'
            '  },\n'
            '  "actionable_insights": [\n'
            '    {\n'
            '      "type": "content_gap|trend_ahead|weakness|strategy_shift|opportunity",\n'
            '      "priority": "high|medium|low",\n'
            '      "title": "short insight title — specific, not generic",\n'
            '      "description": "what you noticed in 2-3 sentences with evidence",\n'
            '      "suggested_action": "what the user should do about it — specific step",\n'
            '      "content_idea": "a specific content seed inspired by this insight"\n'
            '    }\n'
            '  ],\n'
            '  "threat_level": "low|medium|high"\n'
            '}\n'
        )

        prompt = (
            f"=== YOUR BRAND ===\n"
            f"Company: {user_ctx['company'] or 'Not specified'}\n"
            f"Industry: {user_ctx['industry'] or 'General'}\n"
            f"Brand voice: {user_ctx['brand_voice'][:200] if user_ctx['brand_voice'] else 'Not specified'}\n"
            f"Target audience: {user_ctx['target_audience'][:200] if user_ctx['target_audience'] else 'Not specified'}\n"
            f"Content pillars: {json.dumps(user_ctx['content_pillars'])}\n"
            f"Goals: {json.dumps(user_ctx['goals'])}\n"
            f"Active platforms: {', '.join(user_ctx['platforms'])}\n"
            f"Posts last 30 days: {user_ctx['post_count_30d']}\n"
            f"Your Content DNA: {json.dumps(user_ctx['content_dna_summary'], default=str)}\n\n"
            f"=== COMPETITOR TO ANALYZE ===\n"
            f"Name: {comp_ctx['name']}\n"
            f"Website: {comp_ctx['website'] or 'Not provided'}\n"
            f"Industry: {comp_ctx['industry'] or 'Same as user'}\n"
            f"Notes from user: {comp_ctx['notes'] or 'None'}\n"
            f"Social handles:\n"
        )

        for platform, handle in comp_ctx["handles"].items():
            prompt += f"  - {platform}: @{handle}\n"

        if not comp_ctx["handles"]:
            prompt += "  (No specific handles provided — analyze based on name + industry)\n"

        if comp_ctx["previous_patterns"]:
            prompt += (
                f"\nPrevious analysis patterns (COMPARE to detect CHANGES/SHIFTS):\n"
                f"{json.dumps(comp_ctx['previous_patterns'], default=str)[:500]}\n"
                f"Previous strengths: {json.dumps(comp_ctx['previous_strengths'], default=str)}\n"
                f"Previous weaknesses: {json.dumps(comp_ctx['previous_weaknesses'], default=str)}\n"
                f"If you detect any SHIFTS from the previous analysis, create a "
                f"'strategy_shift' insight highlighting what changed and what it means.\n"
            )

        # Product context — so analysis considers product/service overlap
        try:
            from apps.products.models import Product
            user_products = Product.objects.filter(user=user, is_active=True)
            if user_products.exists():
                product_names = list(user_products.values_list("name", flat=True)[:15])
                featured = list(
                    user_products.filter(is_featured=True).values_list("name", flat=True)[:5]
                )
                categories = list(
                    user_products.exclude(category=None)
                    .values_list("category__name", flat=True).distinct()[:5]
                )
                prompt += (
                    f"\n=== YOUR PRODUCT CATALOG ===\n"
                    f"Products/services: {', '.join(product_names)}\n"
                )
                if categories:
                    prompt += f"Categories: {', '.join(categories)}\n"
                if featured:
                    prompt += f"Featured products: {', '.join(featured)}\n"
                prompt += (
                    "Compare how the competitor likely approaches these same product "
                    "categories. Do they promote similar products differently? "
                    "Are there product categories they focus on that the user ignores, "
                    "or vice versa? Include product-related insights.\n"
                )
        except Exception:
            pass  # Product data is optional enrichment

        prompt += (
            "\nAnalyze this competitor's social media strategy. "
            "Be specific, actionable, and focused on what the user can LEARN and DO differently. "
            "Think about what would make the user say 'Now I know exactly what to do about them.'"
        )

        response = generate(
            prompt=prompt,
            system=system_prompt,
            model=get_model_for_task("research.trends", user=user),
            json_mode=True,
            temperature=0.5,
            max_tokens=4500,
        )

        try:
            result = parse_llm_json(response.content)
        except (json.JSONDecodeError, ValueError):
            logger.warning("Competitor analysis LLM returned non-JSON for %s", competitor.name)
            # Try to extract individual fields from partial/broken JSON
            result = _extract_partial_competitor_result(response.content)

        # Save the analysis
        analysis = CompetitorAnalysis.objects.create(
            competitor=competitor,
            user=user,
            analysis_type=CompetitorAnalysis.AnalysisType.FULL,
            summary=result.get("summary", ""),
            content_strategy=result.get("content_strategy", {}),
            strengths=result.get("strengths", []),
            weaknesses=result.get("weaknesses", []),
            opportunities=result.get("opportunities", []),
            threats=result.get("threats", []),
            comparison_to_user=result.get("comparison", {}),
            actionable_insights=result.get("actionable_insights", []),
            tokens_used=response.total_tokens,
        )

        # Update the competitor's cached intelligence
        content_strategy = result.get("content_strategy", {})
        # Merge pricing_positioning into content_patterns for storage
        pricing = result.get("pricing_positioning", {})
        if pricing:
            content_strategy["pricing_positioning"] = pricing

        competitor.strengths = result.get("strengths", [])
        competitor.weaknesses = result.get("weaknesses", [])
        competitor.content_patterns = content_strategy
        competitor.threat_level = result.get("threat_level", "medium")
        competitor.last_analyzed_at = timezone.now()
        competitor.save(update_fields=[
            "strengths", "weaknesses", "content_patterns",
            "threat_level", "last_analyzed_at",
        ])

        # Create individual insight records
        _create_insights_from_analysis(user, competitor, analysis, result)

        action.status = AgentAction.ActionStatus.COMPLETED
        action.output_data = {"analysis_id": str(analysis.id), "insights_count": len(result.get("actionable_insights", []))}
        action.tokens_used = response.total_tokens
        action.completed_at = timezone.now()
        action.save(update_fields=["status", "output_data", "tokens_used", "completed_at"])

        logger.info(
            "Competitor analysis complete: %s — %d insights for %s",
            competitor.name, len(result.get("actionable_insights", [])), user.email,
        )
        return analysis

    except Exception as e:
        logger.exception("Competitor analysis failed for %s: %s", competitor.name, e)
        action.status = AgentAction.ActionStatus.FAILED
        action.error_message = str(e)
        action.save(update_fields=["status", "error_message"])
        return None


def _create_insights_from_analysis(user, competitor, analysis, result):
    """Create CompetitorInsight records from analysis results."""
    type_map = {
        "content_gap": CompetitorInsight.InsightType.CONTENT_GAP,
        "trend_ahead": CompetitorInsight.InsightType.TREND_AHEAD,
        "weakness": CompetitorInsight.InsightType.WEAKNESS,
        "strategy_shift": CompetitorInsight.InsightType.STRATEGY_SHIFT,
        "viral_content": CompetitorInsight.InsightType.VIRAL_CONTENT,
        "opportunity": CompetitorInsight.InsightType.OPPORTUNITY,
    }

    priority_map = {
        "high": CompetitorInsight.Priority.HIGH,
        "medium": CompetitorInsight.Priority.MEDIUM,
        "low": CompetitorInsight.Priority.LOW,
    }

    for item in result.get("actionable_insights", []):
        insight_type = type_map.get(
            item.get("type", "opportunity"),
            CompetitorInsight.InsightType.OPPORTUNITY,
        )
        priority = priority_map.get(
            item.get("priority", "medium"),
            CompetitorInsight.Priority.MEDIUM,
        )

        CompetitorInsight.objects.create(
            user=user,
            competitor=competitor,
            analysis=analysis,
            insight_type=insight_type,
            priority=priority,
            title=item.get("title", "Untitled insight"),
            description=item.get("description", ""),
            suggested_action=item.get("suggested_action", ""),
            suggested_content_idea=item.get("content_idea", ""),
        )


# ─── Landscape Overview ─────────────────────────────────────────────────────

def generate_landscape_report(user):
    """
    Generate a competitive landscape overview across ALL tracked competitors.

    This is the big-picture view: where does the user stand relative to
    the competitive field? Called on-demand from the dashboard.
    """
    competitors = Competitor.objects.filter(user=user, is_active=True)
    if not competitors.exists():
        return None

    user_ctx = _build_user_context(user)

    # Gather latest analysis for each competitor
    competitor_summaries = []
    for comp in competitors:
        latest = comp.analyses.first()
        competitor_summaries.append({
            "name": comp.name,
            "platforms": comp.platforms_tracked,
            "threat_level": comp.threat_level,
            "strengths": comp.strengths[:3],
            "weaknesses": comp.weaknesses[:3],
            "summary": latest.summary if latest else "Not yet analyzed",
        })

    system_prompt = (
        "You are a competitive strategy analyst. Given a user's brand context and "
        "summaries of multiple competitors, create a LANDSCAPE REPORT.\n\n"
        "Think like a war room strategist:\n"
        "- Where is the user's STRONGEST position vs the field?\n"
        "- Where is the user most VULNERABLE?\n"
        "- What GAPS exist that NO competitor is filling?\n"
        "- What's the user's UNIQUE ANGLE that competitors can't easily copy?\n"
        "- What are the TOP 3 MOVES the user should make this week?\n\n"
        "Respond in JSON:\n"
        '{\n'
        '  "landscape_summary": "3-4 sentence overview of the competitive field",\n'
        '  "user_position": "strong|competitive|behind|differentiated",\n'
        '  "strongest_advantages": ["2-3 areas where user beats everyone"],\n'
        '  "biggest_vulnerabilities": ["2-3 areas where user is weakest"],\n'
        '  "market_gaps": ["2-3 opportunities no one is exploiting"],\n'
        '  "top_moves": [\n'
        '    {"move": "what to do", "why": "reasoning", "urgency": "now|this_week|this_month"}\n'
        '  ],\n'
        '  "threat_summary": "1-2 sentences about biggest competitive threats"\n'
        '}\n'
    )

    prompt = (
        f"=== YOUR BRAND ===\n"
        f"Company: {user_ctx['company'] or 'Not specified'}\n"
        f"Industry: {user_ctx['industry']}\n"
        f"Platforms: {', '.join(user_ctx['platforms'])}\n"
        f"Posts last 30d: {user_ctx['post_count_30d']}\n"
        f"Goals: {json.dumps(user_ctx['goals'])}\n\n"
        f"=== COMPETITORS ({len(competitor_summaries)}) ===\n"
        f"{json.dumps(competitor_summaries, indent=2, default=str)}\n\n"
        "Generate a competitive landscape report."
    )

    response = generate(
        prompt=prompt,
        system=system_prompt,
        model=get_model_for_task("analyst.performance", user=user),
        json_mode=True,
        temperature=0.4,
        max_tokens=2000,
    )

    try:
        return parse_llm_json(response.content)
    except (json.JSONDecodeError, ValueError):
        return {"landscape_summary": response.content[:500], "top_moves": []}


# ─── Competitor Intel for Other Agents ───────────────────────────────────────

def get_competitor_context_for_strategist(user):
    """
    Build a compact competitor intelligence summary for the Strategist Agent.
    Called during strategy cycles to inform content decisions.
    """
    competitors = Competitor.objects.filter(user=user, is_active=True)
    if not competitors.exists():
        return {}

    # Recent unacted insights
    recent_insights = CompetitorInsight.objects.filter(
        user=user,
        is_acted_on=False,
        is_dismissed=False,
        created_at__gte=timezone.now() - timedelta(days=7),
    ).order_by("-created_at")[:5]

    # High-threat competitors
    high_threats = competitors.filter(threat_level="high")

    return {
        "competitor_count": competitors.count(),
        "high_threat_competitors": [
            {"name": c.name, "strengths": c.strengths[:2]}
            for c in high_threats
        ],
        "recent_insights": [
            {
                "competitor": i.competitor.name,
                "type": i.insight_type,
                "title": i.title,
                "action": i.suggested_action,
                "content_idea": i.suggested_content_idea,
            }
            for i in recent_insights
        ],
        "content_gaps": list(
            CompetitorInsight.objects.filter(
                user=user,
                insight_type=CompetitorInsight.InsightType.CONTENT_GAP,
                is_acted_on=False,
                is_dismissed=False,
            ).values_list("title", flat=True)[:3]
        ),
    }


def get_competitor_context_for_brief(user):
    """
    Build competitor intelligence summary for the Daily Brief.
    """
    recent_insights = CompetitorInsight.objects.filter(
        user=user,
        is_acted_on=False,
        is_dismissed=False,
        created_at__gte=timezone.now() - timedelta(days=3),
    ).select_related("competitor").order_by("-created_at")[:5]

    recent_analyses = CompetitorAnalysis.objects.filter(
        user=user,
        created_at__gte=timezone.now() - timedelta(days=7),
    ).select_related("competitor")[:3]

    return {
        "has_data": recent_insights.exists() or recent_analyses.exists(),
        "insights": [
            {
                "competitor": i.competitor.name,
                "type": i.get_insight_type_display(),
                "priority": i.priority,
                "title": i.title,
                "action": i.suggested_action,
            }
            for i in recent_insights
        ],
        "recent_analyses": [
            {
                "competitor": a.competitor.name,
                "summary": a.summary[:150],
                "date": a.created_at.strftime("%b %d"),
            }
            for a in recent_analyses
        ],
    }
