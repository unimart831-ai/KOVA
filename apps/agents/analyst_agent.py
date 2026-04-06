"""
Analyst Agent — Performance Intelligence Engine.

Responsibilities:
  1. Analyze post performance and identify what's working
  2. Extract Content DNA from posts (attribute tagging)
  3. Score engagement prediction for new posts
  4. Generate performance summaries for Daily Briefs
"""

import json
import logging
from datetime import timedelta

from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone

from apps.agents.llm import generate, get_model_for_task, parse_llm_json
from apps.agents.models import AgentAction, AgentConfig
from apps.analytics.models import PostMetric
from apps.content.models import Post

logger = logging.getLogger(__name__)


def _get_recent_published_posts(user, days=7):
    """Get published posts with metrics from the last N days."""
    cutoff = timezone.now() - timedelta(days=days)
    return (
        Post.objects.filter(
            user=user,
            status=Post.Status.PUBLISHED,
            published_at__gte=cutoff,
        )
        .select_related("social_account", "metrics")
        .order_by("-published_at")
    )


def _build_performance_data(posts):
    """Build a structured performance summary from posts + metrics."""
    platform_stats = {}
    top_posts = []
    total_engagement = 0
    total_impressions = 0

    for post in posts:
        platform = post.social_account.platform if post.social_account else "unknown"

        if platform not in platform_stats:
            platform_stats[platform] = {
                "posts": 0,
                "total_likes": 0,
                "total_comments": 0,
                "total_shares": 0,
                "total_impressions": 0,
                "total_clicks": 0,
            }

        platform_stats[platform]["posts"] += 1

        try:
            m = post.metrics
            platform_stats[platform]["total_likes"] += m.likes
            platform_stats[platform]["total_comments"] += m.comments
            platform_stats[platform]["total_shares"] += m.shares
            platform_stats[platform]["total_impressions"] += m.impressions
            platform_stats[platform]["total_clicks"] += m.clicks

            engagement = m.likes + m.comments + m.shares
            total_engagement += engagement
            total_impressions += m.impressions

            top_posts.append({
                "content": post.content_text[:120],
                "platform": platform,
                "likes": m.likes,
                "comments": m.comments,
                "shares": m.shares,
                "impressions": m.impressions,
                "engagement_rate": m.engagement_rate or 0,
                "angle": post.ai_angle,
                "framework": post.ai_framework,
                "dna": post.content_dna,
            })
        except PostMetric.DoesNotExist:
            pass

    # Sort top posts by engagement
    top_posts.sort(key=lambda p: p["likes"] + p["comments"] + p["shares"], reverse=True)

    return {
        "platform_stats": platform_stats,
        "top_posts": top_posts[:5],
        "total_posts": len(posts),
        "total_engagement": total_engagement,
        "total_impressions": total_impressions,
        "avg_engagement_rate": (
            round(total_engagement / total_impressions * 100, 2)
            if total_impressions > 0 else 0
        ),
    }


def analyze_performance(user, days=7):
    """
    Analyst Agent: Analyze recent post performance and return insights.
    Returns a dict with performance summary + LLM-generated insights.
    """
    action = AgentAction.objects.create(
        user=user,
        agent_type="analyst",
        action_type="performance_analysis",
        description=f"Analyzing post performance for the last {days} days",
    )

    try:
        posts = _get_recent_published_posts(user, days)
        perf_data = _build_performance_data(posts)

        if perf_data["total_posts"] == 0:
            action.status = AgentAction.ActionStatus.COMPLETED
            action.output_data = {"message": "No published posts to analyze"}
            action.save(update_fields=["status", "output_data"])
            return {
                "summary": "No posts published in the last week. Start creating content to get insights!",
                "top_posts": [],
                "platform_stats": {},
                "content_dna_insights": [],
            }

        # Ask LLM to analyze the data
        system_prompt = (
            "You are the Analyst Agent for a social media management platform. "
            "Analyze the performance data and provide actionable insights. "
            "Be specific about what content attributes drive engagement. "
            "Respond in JSON format with these keys:\n"
            '- "summary": 2-3 sentence performance overview\n'
            '- "top_insight": the single most important finding\n'
            '- "content_dna_insights": list of 3-5 specific findings about what content attributes work best '
            '(e.g. "Question-format posts get 2.4x more comments")\n'
            '- "recommendations": list of 2-3 specific action items\n'
            '- "platform_breakdown": brief analysis per platform\n'
        )

        prompt = (
            f"Here is the post performance data for the last {days} days:\n\n"
            f"Total posts: {perf_data['total_posts']}\n"
            f"Total engagement (likes+comments+shares): {perf_data['total_engagement']}\n"
            f"Total impressions: {perf_data['total_impressions']}\n"
            f"Average engagement rate: {perf_data['avg_engagement_rate']}%\n\n"
            f"Platform breakdown:\n{json.dumps(perf_data['platform_stats'], indent=2)}\n\n"
            f"Top performing posts:\n{json.dumps(perf_data['top_posts'], indent=2)}\n\n"
        )

        # Intelligence: inject prediction accuracy so analyst knows its track record
        from apps.agents.memory import get_prediction_accuracy
        accuracy = get_prediction_accuracy(user, days=30)
        if accuracy.get("validated_count", 0) > 0:
            prompt += (
                f"\n=== YOUR PREDICTION ACCURACY (last 30 days) ===\n"
                f"Predictions validated: {accuracy['validated_count']}\n"
                f"Avg predicted score: {accuracy['avg_predicted']}\n"
                f"Avg actual score: {accuracy['avg_actual']}\n"
                f"Avg error: {accuracy['avg_error']} (positive = underestimate)\n"
                f"Accurate within ±10: {accuracy['accuracy_rate']}%\n"
                f"Overestimates: {accuracy['overestimates']}, Underestimates: {accuracy['underestimates']}\n"
                f"LEARN FROM THIS: Adjust your predictions based on your track record.\n\n"
            )

        prompt += "Analyze this data and provide insights in the specified JSON format."

        response = generate(prompt=prompt, system=system_prompt, model=get_model_for_task("analyst.performance", user=user), json_mode=True, temperature=0.3)

        try:
            insights = parse_llm_json(response.content)
        except (json.JSONDecodeError, ValueError):
            insights = {
                "summary": response.content,
                "top_insight": "",
                "content_dna_insights": [],
                "recommendations": [],
                "platform_breakdown": "",
            }

        result = {
            **insights,
            "performance_data": perf_data,
        }

        action.status = AgentAction.ActionStatus.COMPLETED
        action.output_data = result
        action.tokens_used = response.total_tokens
        action.input_tokens = response.input_tokens
        action.output_tokens = response.output_tokens
        action.model_used = response.model
        action.completed_at = timezone.now()
        action.save(update_fields=["status", "output_data", "tokens_used", "input_tokens", "output_tokens", "model_used", "completed_at"])

        return result

    except Exception as e:
        logger.exception("Analyst Agent failed: %s", e)
        action.status = AgentAction.ActionStatus.FAILED
        action.error_message = str(e)
        action.save(update_fields=["status", "error_message"])
        return {
            "summary": "Analysis temporarily unavailable.",
            "top_posts": [],
            "platform_stats": {},
            "content_dna_insights": [],
        }


def extract_content_dna(post):
    """
    Extract Content DNA attributes from a post using LLM.
    Tags the post with structured attributes for correlation analysis.
    """
    system_prompt = (
        "You are a content analyst. Extract structured attributes from this social media post. "
        "Respond in JSON with these keys:\n"
        '- "format": one of [question, statement, story, list, thread, how_to, hot_take, announcement, behind_scenes]\n'
        '- "tone": one of [inspirational, educational, humorous, provocative, professional, casual, urgent, empathetic]\n'
        '- "topic": brief topic label (2-3 words)\n'
        '- "has_cta": boolean — does it include a call to action?\n'
        '- "has_stats": boolean — does it include numbers/statistics?\n'
        '- "has_question": boolean — does it ask a question?\n'
        '- "has_emoji": boolean — does it use emoji?\n'
        '- "has_hashtags": boolean — does it include hashtags?\n'
        '- "length": one of [short, medium, long] based on character count relative to platform\n'
        '- "hook_type": one of [statistic, question, bold_claim, story_opener, curiosity_gap, none]\n'
        '- "has_image": boolean — does this post have a visual attached?\n'
        '- "image_source": one of [ai_generated, uploaded, none] — where the visual came from\n'
        '- "image_type": one of [photo, illustration, graphic, meme, infographic, carousel, none] — what kind of visual\n'
    )

    # Determine visual context for the LLM
    has_image = bool(post.media_urls) or post.attachments.exists()
    image_source = "none"
    if has_image:
        image_source = "ai_generated" if post.media_status == "generated" else "uploaded"

    prompt = (
        f"Platform: {post.social_account.platform if post.social_account else 'unknown'}\n"
        f"Content:\n{post.content_text}\n"
        f"Has image: {has_image}\n"
        f"Image source: {image_source}\n\n"
        "Extract the Content DNA attributes."
    )

    for attempt in range(2):
        try:
            response = generate(prompt=prompt, system=system_prompt, model=get_model_for_task("analyst.content_dna", user=post.user), json_mode=True, temperature=0.1, max_tokens=500)
            dna = parse_llm_json(response.content)
            post.content_dna = dna
            post.save(update_fields=["content_dna"])
            return dna
        except Exception as e:
            if attempt == 0:
                logger.info("Content DNA extraction attempt 1 failed for post %s, retrying: %s", post.id, e)
                continue
            logger.warning("Content DNA extraction failed for post %s after 2 attempts: %s", post.id, e)
            return {}


def predict_engagement(post):
    """
    Predict engagement score for a post before publishing.
    Uses historical performance + content attributes to estimate.
    Returns a float 0-100.
    """
    user = post.user

    # Get historical averages
    recent_metrics = PostMetric.objects.filter(
        post__user=user,
        post__status=Post.Status.PUBLISHED,
        post__social_account__platform=(
            post.social_account.platform if post.social_account else ""
        ),
    ).aggregate(
        avg_likes=Avg("likes"),
        avg_comments=Avg("comments"),
        avg_shares=Avg("shares"),
        avg_engagement=Avg("engagement_rate"),
        post_count=Count("id"),
    )

    if not recent_metrics["post_count"] or recent_metrics["post_count"] < 3:
        # Not enough data — return AI's original prediction or 50
        return post.predicted_engagement_score or 50.0

    # Get top-performing content DNA patterns
    top_posts = (
        Post.objects.filter(
            user=user,
            status=Post.Status.PUBLISHED,
            social_account__platform=(
                post.social_account.platform if post.social_account else ""
            ),
        )
        .exclude(content_dna={})
        .select_related("metrics")
        .order_by("-metrics__engagement_rate")[:10]
    )

    system_prompt = (
        "You are an engagement prediction model. Based on historical performance data "
        "and the content attributes of a new post, predict its engagement score (0-100). "
        "Respond with ONLY a JSON object: {\"score\": <number>, \"reasoning\": \"<brief explanation>\"}"
    )

    top_dna = [{"dna": p.content_dna, "engagement_rate": p.metrics.engagement_rate}
               for p in top_posts if hasattr(p, "metrics") and p.metrics]

    prompt = (
        f"Platform: {post.social_account.platform if post.social_account else 'unknown'}\n"
        f"Historical averages: {json.dumps(recent_metrics, default=str)}\n"
        f"Top performing content DNA patterns: {json.dumps(top_dna[:5], default=str)}\n\n"
        f"New post content:\n{post.content_text[:300]}\n\n"
        f"New post DNA: {json.dumps(post.content_dna, default=str)}\n\n"
        "Predict the engagement score (0-100)."
    )

    try:
        response = generate(prompt=prompt, system=system_prompt, model=get_model_for_task("analyst.predict", user=post.user), json_mode=True, temperature=0.2, max_tokens=200)
        result = parse_llm_json(response.content)
        score = float(result.get("score", 50))
        score = max(0, min(100, score))
        post.predicted_engagement_score = score
        post.ai_reasoning = result.get("reasoning", post.ai_reasoning)
        post.save(update_fields=["predicted_engagement_score", "ai_reasoning"])
        return score
    except Exception as e:
        logger.warning("Engagement prediction failed for post %s: %s", post.id, e)
        return post.predicted_engagement_score or 50.0


# ── Batched variants (reduce N calls → 1 call for multi-post operations) ─────

def batch_extract_content_dna(posts):
    """
    Extract Content DNA for multiple posts in a single LLM call.
    Falls back to per-post extraction if batch parse fails.
    """
    if not posts:
        return []
    if len(posts) == 1:
        return [extract_content_dna(posts[0])]

    system_prompt = (
        "You are a content analyst. Extract structured attributes from each post below. "
        "Respond with a JSON array — one object per post, in the same order. "
        "Each object must have these keys:\n"
        '- "format": one of [question, statement, story, list, thread, how_to, hot_take, announcement, behind_scenes]\n'
        '- "tone": one of [inspirational, educational, humorous, provocative, professional, casual, urgent, empathetic]\n'
        '- "topic": brief topic label (2-3 words)\n'
        '- "has_cta": boolean\n- "has_stats": boolean\n- "has_question": boolean\n'
        '- "has_emoji": boolean\n- "has_hashtags": boolean\n'
        '- "length": one of [short, medium, long]\n'
        '- "hook_type": one of [statistic, question, bold_claim, story_opener, curiosity_gap, none]\n'
        '- "has_image": boolean\n- "image_source": one of [ai_generated, uploaded, none]\n'
        '- "image_type": one of [photo, illustration, graphic, meme, infographic, carousel, none]\n'
    )

    post_descriptions = []
    for i, post in enumerate(posts):
        has_image = bool(post.media_urls) or post.attachments.exists()
        image_source = "none"
        if has_image:
            image_source = "ai_generated" if post.media_status == "generated" else "uploaded"
        post_descriptions.append(
            f"--- Post {i + 1} ---\n"
            f"Platform: {post.social_account.platform if post.social_account else 'unknown'}\n"
            f"Content:\n{post.content_text}\n"
            f"Has image: {has_image}\nImage source: {image_source}"
        )

    prompt = "\n\n".join(post_descriptions) + "\n\nExtract Content DNA for all posts. Return a JSON array."

    for attempt in range(2):
        try:
            response = generate(
                prompt=prompt, system=system_prompt,
                model=get_model_for_task("analyst.content_dna", user=posts[0].user),
                json_mode=True, temperature=0.1,
                max_tokens=300 * len(posts),
            )
            results = parse_llm_json(response.content)

            if isinstance(results, list) and len(results) == len(posts):
                for post, dna in zip(posts, results):
                    if isinstance(dna, dict):
                        post.content_dna = dna
                        post.save(update_fields=["content_dna"])
                return results

            # Length mismatch — fall through to per-post fallback
            logger.warning("Batch DNA returned %d results for %d posts, falling back", len(results) if isinstance(results, list) else 0, len(posts))
            break
        except Exception as e:
            if attempt == 0:
                logger.info("Batch DNA attempt 1 failed, retrying: %s", e)
                continue
            logger.warning("Batch DNA failed after 2 attempts: %s", e)
            break

    # Fallback: per-post extraction
    return [extract_content_dna(p) for p in posts]


def batch_predict_engagement(posts):
    """
    Predict engagement scores for multiple posts in a single LLM call.
    Falls back to per-post prediction if batch parse fails.
    """
    if not posts:
        return []
    if len(posts) == 1:
        return [predict_engagement(posts[0])]

    user = posts[0].user

    # Get historical averages (shared across all posts from same user)
    recent_metrics = PostMetric.objects.filter(
        post__user=user,
        post__status=Post.Status.PUBLISHED,
    ).aggregate(
        avg_likes=Avg("likes"),
        avg_comments=Avg("comments"),
        avg_shares=Avg("shares"),
        avg_engagement=Avg("engagement_rate"),
        post_count=Count("id"),
    )

    if not recent_metrics["post_count"] or recent_metrics["post_count"] < 3:
        for post in posts:
            score = post.predicted_engagement_score or 50.0
            post.predicted_engagement_score = score
        return [p.predicted_engagement_score for p in posts]

    top_posts = (
        Post.objects.filter(user=user, status=Post.Status.PUBLISHED)
        .exclude(content_dna={})
        .select_related("metrics")
        .order_by("-metrics__engagement_rate")[:10]
    )
    top_dna = [{"dna": p.content_dna, "engagement_rate": p.metrics.engagement_rate}
               for p in top_posts if hasattr(p, "metrics") and p.metrics]

    system_prompt = (
        "You are an engagement prediction model. Predict scores (0-100) for multiple posts. "
        "Respond with a JSON array of objects, one per post in order: "
        '[{"score": <number>, "reasoning": "<brief>"}, ...]'
    )

    post_descriptions = []
    for i, post in enumerate(posts):
        platform = post.social_account.platform if post.social_account else "unknown"
        post_descriptions.append(
            f"--- Post {i + 1} ---\n"
            f"Platform: {platform}\n"
            f"Content: {post.content_text[:200]}\n"
            f"DNA: {json.dumps(post.content_dna, default=str)}"
        )

    prompt = (
        f"Historical averages: {json.dumps(recent_metrics, default=str)}\n"
        f"Top DNA patterns: {json.dumps(top_dna[:5], default=str)}\n\n"
        + "\n\n".join(post_descriptions)
        + "\n\nPredict engagement scores for all posts."
    )

    try:
        response = generate(
            prompt=prompt, system=system_prompt,
            model=get_model_for_task("analyst.predict", user=posts[0].user),
            json_mode=True, temperature=0.2,
            max_tokens=150 * len(posts),
        )
        results = parse_llm_json(response.content)

        if isinstance(results, list) and len(results) == len(posts):
            scores = []
            for post, pred in zip(posts, results):
                if isinstance(pred, dict):
                    score = max(0, min(100, float(pred.get("score", 50))))
                    post.predicted_engagement_score = score
                    post.ai_reasoning = pred.get("reasoning", post.ai_reasoning)
                    post.save(update_fields=["predicted_engagement_score", "ai_reasoning"])
                    scores.append(score)
                else:
                    scores.append(post.predicted_engagement_score or 50.0)
            return scores

        logger.warning("Batch predict returned %d results for %d posts, falling back",
                       len(results) if isinstance(results, list) else 0, len(posts))
    except Exception as e:
        logger.warning("Batch engagement prediction failed: %s", e)

    # Fallback: per-post prediction
    return [predict_engagement(p) for p in posts]


def get_content_dna_summary(user, days=30):
    """
    Aggregate Content DNA across all published posts to find winning patterns.
    Returns top-performing attributes for the Daily Brief.
    """
    cutoff = timezone.now() - timedelta(days=days)
    posts = (
        Post.objects.filter(
            user=user,
            status=Post.Status.PUBLISHED,
            published_at__gte=cutoff,
        )
        .exclude(content_dna={})
        .select_related("metrics")
    )

    if not posts.exists():
        return {"winning_attributes": [], "total_analyzed": 0}

    # Tally attributes by engagement
    attribute_scores = {}

    for post in posts:
        try:
            engagement = post.metrics.engagement_rate or 0
        except PostMetric.DoesNotExist:
            continue

        # Recency weighting: recent posts count more (exponential decay)
        days_old = (timezone.now() - post.published_at).days if post.published_at else days
        recency_weight = 0.95 ** days_old  # ~60% weight at 10 days, ~36% at 20 days

        dna = post.content_dna
        for key, value in dna.items():
            if isinstance(value, bool):
                attr_key = f"{key}={value}"
            else:
                attr_key = f"{key}={value}"

            if attr_key not in attribute_scores:
                attribute_scores[attr_key] = {"total_engagement": 0, "weighted_total": 0, "count": 0}
            attribute_scores[attr_key]["total_engagement"] += engagement
            attribute_scores[attr_key]["weighted_total"] += engagement * recency_weight
            attribute_scores[attr_key]["count"] += 1

    # Calculate average engagement per attribute — with statistical minimum
    MIN_SAMPLE_SIZE = 5  # Don't trust patterns with fewer than 5 posts
    winning = []
    for attr, data in attribute_scores.items():
        if data["count"] >= MIN_SAMPLE_SIZE:
            avg = data["weighted_total"] / data["count"]
            raw_avg = data["total_engagement"] / data["count"]
            winning.append({
                "attribute": attr,
                "avg_engagement": round(avg, 2),
                "raw_avg_engagement": round(raw_avg, 2),
                "posts": data["count"],
                "confidence": "high" if data["count"] >= 10 else "moderate",
            })
        elif data["count"] >= 2:
            # Include with low confidence for visibility, but flag it
            avg = data["total_engagement"] / data["count"]
            winning.append({
                "attribute": attr,
                "avg_engagement": round(avg, 2),
                "raw_avg_engagement": round(avg, 2),
                "posts": data["count"],
                "confidence": "low",
            })

    winning.sort(key=lambda x: x["avg_engagement"], reverse=True)

    return {
        "winning_attributes": winning[:10],
        "total_analyzed": posts.count(),
    }


# ─── A/B Test Evaluation ─────────────────────────────────────────────────────

def evaluate_ab_test(ab_test):
    """
    Evaluate an A/B test by comparing variant metrics.

    Compares all published variants' engagement data via the LLM and
    declares a winner. Updates the ABTest with the result.

    Returns a dict with winner info and analysis summary.
    """
    from apps.content.models import ABTest

    user = ab_test.user
    variants = (
        ab_test.variants.filter(status=Post.Status.PUBLISHED)
        .select_related("social_account")
        .prefetch_related("metrics")
    )

    if variants.count() < 2:
        return {"error": "Need at least 2 published variants to evaluate."}

    action = AgentAction.objects.create(
        user=user,
        agent_type="analyst",
        action_type="ab_test_evaluation",
        description=f"Evaluating A/B test: {ab_test.name[:80]}",
        status=AgentAction.ActionStatus.STARTED,
        input_data={"ab_test_id": str(ab_test.id)},
    )

    try:
        # Build comparison data
        variant_data = []
        for v in variants:
            entry = {
                "label": v.variant_label,
                "post_id": str(v.id),
                "content_preview": v.content_text[:200],
                "angle": v.ai_angle,
                "framework": v.ai_framework,
                "content_dna": v.content_dna,
            }
            try:
                m = v.metrics
                entry["metrics"] = {
                    "impressions": m.impressions,
                    "reach": m.reach,
                    "likes": m.likes,
                    "comments": m.comments,
                    "shares": m.shares,
                    "saves": m.saves,
                    "clicks": m.clicks,
                    "engagement_rate": m.engagement_rate,
                }
            except PostMetric.DoesNotExist:
                entry["metrics"] = None
            variant_data.append(entry)

        # Determine winner by engagement rate (hard metric)
        scored = [
            v for v in variant_data
            if v["metrics"] and v["metrics"]["engagement_rate"] is not None
        ]

        if not scored:
            # No metrics yet — can't determine winner
            action.status = AgentAction.ActionStatus.COMPLETED
            action.output_data = {"message": "No engagement metrics available yet."}
            action.save(update_fields=["status", "output_data"])
            return {"error": "No engagement metrics collected yet. Wait for more data."}

        # Pick winner by engagement rate
        winner_data = max(scored, key=lambda v: v["metrics"]["engagement_rate"])

        # Ask LLM to explain WHY the winner won
        system_prompt = (
            "You are the Analyst Agent evaluating an A/B content test. "
            "Compare the variants and explain why the winner performed best. "
            "Respond in JSON with keys:\n"
            '- "winner_label": the winning variant label\n'
            '- "summary": 2-3 sentence executive summary of results\n'
            '- "why_winner_won": specific analysis of what made the winning content perform better\n'
            '- "learnings": list of 2-3 actionable content insights from this test\n'
            '- "confidence": "high", "medium", or "low" based on data quality\n'
        )

        prompt = (
            f"A/B Test: {ab_test.name}\n"
            f"Platform: {ab_test.social_account.platform}\n"
            f"Test duration: {ab_test.test_duration_hours} hours\n\n"
            f"Variants:\n{json.dumps(variant_data, indent=2, default=str)}\n\n"
            f"Winner by engagement rate: Variant {winner_data['label']} "
            f"({winner_data['metrics']['engagement_rate']:.2f}%)\n\n"
            "Explain these results. What content lessons can we learn?"
        )

        response = generate(
            prompt=prompt,
            system=system_prompt,
            model=get_model_for_task("analyst.performance", user=ab_test.user),
            json_mode=True,
            temperature=0.3,
        )

        try:
            analysis = parse_llm_json(response.content)
        except (json.JSONDecodeError, ValueError):
            analysis = {
                "winner_label": winner_data["label"],
                "summary": response.content[:500],
                "why_winner_won": "",
                "learnings": [],
                "confidence": "low",
            }

        # Update ABTest with winner
        winner_post = variants.get(variant_label=winner_data["label"])
        ab_test.winner = winner_post
        ab_test.status = ABTest.Status.CONCLUDED
        ab_test.concluded_at = timezone.now()
        ab_test.conclusion_summary = analysis.get("summary", "")
        ab_test.save(update_fields=[
            "winner", "status", "concluded_at", "conclusion_summary", "updated_at",
        ])

        result = {
            "winner_label": winner_data["label"],
            "winner_post_id": str(winner_post.id),
            "analysis": analysis,
            "variant_data": variant_data,
        }

        action.status = AgentAction.ActionStatus.COMPLETED
        action.output_data = result
        action.tokens_used = response.total_tokens
        action.input_tokens = response.input_tokens
        action.output_tokens = response.output_tokens
        action.model_used = response.model
        action.completed_at = timezone.now()
        action.save()

        logger.info("A/B Test %s concluded — winner: Variant %s", ab_test.id, winner_data["label"])
        return result

    except Exception as e:
        logger.exception("A/B test evaluation failed: %s", e)
        action.status = AgentAction.ActionStatus.FAILED
        action.error_message = str(e)
        action.save(update_fields=["status", "error_message"])
        return {"error": str(e)}
