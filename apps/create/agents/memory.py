"""
Agent Memory — The Intelligence Layer.

This module transforms agents from stateless LLM callers into learning systems.
Every agent can now:
  1. Read its own past actions and outcomes before making decisions
  2. Track which predictions were accurate vs. wrong
  3. Learn from user corrections (edits, rejections)
  4. Build compounding intelligence over time

Architecture:
  [Agent runs] → memory.get_agent_history() → injects lessons into LLM prompt
  [Post published] → memory.measure_outcomes() → scores past actions
  [User edits post] → memory.record_edit_feedback() → captures correction signal
  [Metrics arrive] → memory.validate_predictions() → compares predicted vs actual
"""

import logging
from datetime import timedelta
from difflib import SequenceMatcher

from django.db.models import Avg, Count, F, Q
from django.utils import timezone

from apps.create.agents.models import AgentAction
from apps.insight.analytics.models import PostMetric
from apps.create.content.models import Post

logger = logging.getLogger(__name__)


# ─── Edit Tracking (Close the user-correction feedback loop) ─────────────────

def record_edit_feedback(post):
    """
    Called when a user saves edits to a post. Compares current content_text
    against ai_original_text to measure how much the user changed.

    Sets: post.user_edited, post.edit_distance_ratio
    """
    if not post.ai_original_text:
        return

    original = post.ai_original_text
    current = post.content_text

    if original == current:
        post.user_edited = False
        post.edit_distance_ratio = 0.0
    else:
        post.user_edited = True
        ratio = SequenceMatcher(None, original, current).ratio()
        post.edit_distance_ratio = round(1.0 - ratio, 3)

    post.save(update_fields=["user_edited", "edit_distance_ratio"])


# ─── Prediction Validation (Close the prediction feedback loop) ──────────────

def validate_prediction(post):
    """
    Compare a post's predicted_engagement_score against actual performance.
    Called after metrics are fetched (typically 24-48h after publish).

    Updates: PostMetric.predicted_score, actual_score, prediction_error
    """
    try:
        metric = post.metrics
    except PostMetric.DoesNotExist:
        return None

    if not post.predicted_engagement_score:
        return None

    if metric.prediction_validated_at:
        return metric.prediction_error  # Already validated

    # Calculate actual score (normalized 0-100)
    # Use same scale as prediction: engagement quality metric
    if metric.impressions > 0:
        raw_rate = ((metric.likes + metric.comments + metric.shares) / metric.impressions) * 100
        # Normalize: typical engagement rates are 1-10%, map to 0-100
        actual_score = min(100, raw_rate * 10)
    elif metric.likes + metric.comments + metric.shares > 0:
        actual_score = min(100, (metric.likes + metric.comments + metric.shares) * 2)
    else:
        actual_score = 0.0

    metric.predicted_score = post.predicted_engagement_score
    metric.actual_score = round(actual_score, 2)
    metric.prediction_error = round(actual_score - post.predicted_engagement_score, 2)
    metric.prediction_validated_at = timezone.now()
    metric.save(update_fields=[
        "predicted_score", "actual_score", "prediction_error", "prediction_validated_at",
    ])

    return metric.prediction_error


def get_prediction_accuracy(user, days=30):
    """
    Get prediction accuracy stats for a user over the last N days.
    Returns dict with avg error, overestimate/underestimate counts, and accuracy trend.
    """
    cutoff = timezone.now() - timedelta(days=days)
    validated = PostMetric.objects.filter(
        post__user=user,
        prediction_validated_at__gte=cutoff,
        prediction_error__isnull=False,
    )

    count = validated.count()
    if count == 0:
        return {"validated_count": 0, "message": "No validated predictions yet."}

    stats = validated.aggregate(
        avg_error=Avg("prediction_error"),
        avg_abs_error=Avg(F("prediction_error") * F("prediction_error")),  # MSE proxy
        avg_predicted=Avg("predicted_score"),
        avg_actual=Avg("actual_score"),
    )

    overestimates = validated.filter(prediction_error__lt=-10).count()
    underestimates = validated.filter(prediction_error__gt=10).count()
    accurate = validated.filter(prediction_error__gte=-10, prediction_error__lte=10).count()

    return {
        "validated_count": count,
        "avg_error": round(stats["avg_error"] or 0, 2),
        "avg_predicted": round(stats["avg_predicted"] or 0, 2),
        "avg_actual": round(stats["avg_actual"] or 0, 2),
        "overestimates": overestimates,
        "underestimates": underestimates,
        "accurate_within_10": accurate,
        "accuracy_rate": round((accurate / count) * 100, 1) if count > 0 else 0,
    }


# ─── Agent History (Each agent reads its own past to learn) ──────────────────

def get_agent_learning_context(user, agent_type, action_type=None, limit=10):
    """
    Build a learning context string for an agent by reading its own past actions
    and their outcomes. This is injected into the agent's system prompt.

    Returns a formatted string summarizing what worked, what didn't, and patterns.
    """
    query = AgentAction.objects.filter(
        user=user,
        agent_type=agent_type,
        status=AgentAction.ActionStatus.COMPLETED,
    )
    if action_type:
        query = query.filter(action_type=action_type)

    # Get actions with measured outcomes
    actions_with_outcomes = query.filter(
        outcome_score__isnull=False,
    ).order_by("-created_at")[:limit]

    if not actions_with_outcomes.exists():
        return ""

    parts = ["## LEARNING FROM PAST ACTIONS (your own history)"]
    parts.append(f"Based on {actions_with_outcomes.count()} recent measured outcomes:\n")

    # Summarize top wins and losses
    wins = []
    losses = []
    for action in actions_with_outcomes:
        summary = {
            "date": action.created_at.strftime("%b %d"),
            "score": action.outcome_score,
            "data": action.outcome_data,
        }
        if action.outcome_score >= 60:
            wins.append(summary)
        elif action.outcome_score < 40:
            losses.append(summary)

    if wins:
        parts.append("### What WORKED well:")
        for w in wins[:3]:
            outcome_summary = w["data"].get("summary", "") if isinstance(w["data"], dict) else ""
            parts.append(f"  - [{w['date']}] Score: {w['score']}/100. {outcome_summary}")

    if losses:
        parts.append("\n### What DIDN'T work:")
        for l in losses[:3]:
            outcome_summary = l["data"].get("summary", "") if isinstance(l["data"], dict) else ""
            parts.append(f"  - [{l['date']}] Score: {l['score']}/100. {outcome_summary}")

    # Aggregate stats
    all_scores = [a.outcome_score for a in actions_with_outcomes]
    avg_score = sum(all_scores) / len(all_scores)
    parts.append(f"\nAverage outcome score: {avg_score:.1f}/100")
    parts.append("INSTRUCTION: Learn from these outcomes. Repeat what worked. Avoid what failed.\n")

    return "\n".join(parts)


def get_user_edit_patterns(user, days=30):
    """
    Analyze how the user edits AI content — what patterns they correct.
    Returns insights for agents to learn from.
    """
    cutoff = timezone.now() - timedelta(days=days)
    edited_posts = Post.objects.filter(
        user=user,
        user_edited=True,
        ai_original_text__gt="",
        created_at__gte=cutoff,
    ).select_related("social_account").order_by("-edit_distance_ratio")

    if not edited_posts.exists():
        return ""

    total_posts = Post.objects.filter(
        user=user,
        ai_original_text__gt="",
        created_at__gte=cutoff,
    ).count()
    edit_count = edited_posts.count()
    edit_rate = round((edit_count / total_posts) * 100, 1) if total_posts > 0 else 0

    avg_distance = edited_posts.aggregate(
        avg=Avg("edit_distance_ratio"),
    )["avg"] or 0

    parts = ["## USER EDIT PATTERNS (learn from their corrections)"]
    parts.append(f"User edits {edit_rate}% of AI-generated posts (avg change: {avg_distance:.0%})")

    # Show heavily edited examples so LLM can learn the pattern
    heavy_edits = edited_posts.filter(edit_distance_ratio__gte=0.3)[:3]
    if heavy_edits:
        parts.append("\n### Posts the user significantly rewrote:")
        for p in heavy_edits:
            platform = p.social_account.platform if p.social_account else "?"
            parts.append(f"  Platform: {platform} | Change: {p.edit_distance_ratio:.0%}")
            parts.append(f"  AI wrote: \"{p.ai_original_text[:120]}...\"")
            parts.append(f"  User changed to: \"{p.content_text[:120]}...\"")
            parts.append("")

    # Show posts user approved without changes (these are what we should aim for)
    accepted = Post.objects.filter(
        user=user,
        user_edited=False,
        ai_original_text__gt="",
        status__in=[Post.Status.APPROVED, Post.Status.PUBLISHED],
        created_at__gte=cutoff,
    ).select_related("social_account")[:3]

    if accepted:
        parts.append("### Posts the user APPROVED without changes (aim for this):")
        for p in accepted:
            platform = p.social_account.platform if p.social_account else "?"
            parts.append(f"  Platform: {platform}")
            parts.append(f"  Content: \"{p.content_text[:120]}...\"")

    parts.append("\nINSTRUCTION: Match the user's voice. Study what they keep vs. what they change.\n")
    return "\n".join(parts)


# ─── Outcome Measurement (Score past agent actions based on results) ─────────

def measure_create_agent_outcomes(user, days=7):
    """
    Measure outcomes for Create Agent actions: did the generated posts
    get good engagement? Were they heavily edited?

    Called periodically (e.g., daily) to retroactively score past actions.
    """
    cutoff = timezone.now() - timedelta(days=days)
    actions = AgentAction.objects.filter(
        user=user,
        agent_type="create",
        action_type="generate_content",
        status=AgentAction.ActionStatus.COMPLETED,
        outcome_score__isnull=True,
        created_at__gte=cutoff,
    )

    scored = 0
    for action in actions:
        seed_id = action.input_data.get("seed_id")
        if not seed_id:
            continue

        # Find posts generated from this action's seed
        posts = Post.objects.filter(
            seed_id=seed_id,
            user=user,
        ).select_related("metrics")

        if not posts.exists():
            continue

        published = posts.filter(status=Post.Status.PUBLISHED)
        if not published.exists():
            # Posts exist but aren't published yet — check if rejected
            rejected = posts.filter(status=Post.Status.REJECTED).count()
            if rejected > 0:
                action.outcome_score = max(0, 30 - (rejected * 10))
                action.outcome_data = {
                    "summary": f"{rejected} posts rejected by user",
                    "total_posts": posts.count(),
                    "rejected": rejected,
                }
                action.outcome_measured_at = timezone.now()
                action.save(update_fields=["outcome_score", "outcome_data", "outcome_measured_at"])
                scored += 1
            continue

        # Calculate outcome score from published posts
        total_engagement = 0
        total_edit_distance = 0
        posts_with_metrics = 0
        edit_count = 0

        for post in published:
            if post.user_edited:
                edit_count += 1
                total_edit_distance += post.edit_distance_ratio or 0

            try:
                m = post.metrics
                if m.engagement_rate:
                    total_engagement += m.engagement_rate
                    posts_with_metrics += 1
            except PostMetric.DoesNotExist:
                continue

        avg_engagement = total_engagement / posts_with_metrics if posts_with_metrics else 0
        avg_edit = total_edit_distance / edit_count if edit_count else 0
        acceptance_rate = published.count() / posts.count() if posts.count() else 0

        # Score: 40% engagement + 30% acceptance + 30% low edit distance
        engagement_score = min(100, avg_engagement * 10)  # normalize
        acceptance_score = acceptance_rate * 100
        edit_score = (1 - avg_edit) * 100  # less editing = better

        outcome = round(engagement_score * 0.4 + acceptance_score * 0.3 + edit_score * 0.3, 1)

        action.outcome_score = outcome
        action.outcome_data = {
            "summary": f"Avg engagement: {avg_engagement:.1f}%, "
                       f"Acceptance: {acceptance_rate:.0%}, "
                       f"Avg edit: {avg_edit:.0%}",
            "total_posts": posts.count(),
            "published": published.count(),
            "avg_engagement_rate": round(avg_engagement, 2),
            "acceptance_rate": round(acceptance_rate, 2),
            "avg_edit_distance": round(avg_edit, 3),
            "user_edits": edit_count,
        }
        action.outcome_measured_at = timezone.now()
        action.save(update_fields=["outcome_score", "outcome_data", "outcome_measured_at"])
        scored += 1

    return scored


def measure_strategist_outcomes(user, days=7):
    """
    Measure outcomes for Strategist actions: did the proactive seeds it created
    result in published, high-performing content?
    """
    cutoff = timezone.now() - timedelta(days=days)
    actions = AgentAction.objects.filter(
        user=user,
        agent_type="strategist",
        action_type="strategy_cycle",
        status=AgentAction.ActionStatus.COMPLETED,
        outcome_score__isnull=True,
        created_at__gte=cutoff,
    )

    scored = 0
    for action in actions:
        seeds_created = action.output_data.get("seeds_created", 0)
        recommendations = action.output_data.get("recommendations", [])

        if seeds_created == 0 and not recommendations:
            continue

        # Find posts created from seeds within 24h after this strategy cycle
        cycle_end = action.created_at + timedelta(hours=24)
        posts = Post.objects.filter(
            user=user,
            seed__notes__contains="[Strategist Agent]",
            created_at__range=(action.created_at, cycle_end),
        ).select_related("metrics")

        published = posts.filter(status=Post.Status.PUBLISHED)
        total_engagement = 0
        posts_with_metrics = 0

        for post in published:
            try:
                m = post.metrics
                if m.engagement_rate:
                    total_engagement += m.engagement_rate
                    posts_with_metrics += 1
            except PostMetric.DoesNotExist:
                continue

        avg_engagement = total_engagement / posts_with_metrics if posts_with_metrics else 0
        acceptance_rate = published.count() / posts.count() if posts.count() > 0 else 0

        # Score: 50% engagement + 30% acceptance + 20% execution (seeds created)
        engagement_score = min(100, avg_engagement * 10)
        acceptance_score = acceptance_rate * 100
        execution_score = min(100, seeds_created * 25)

        outcome = round(engagement_score * 0.5 + acceptance_score * 0.3 + execution_score * 0.2, 1)

        action.outcome_score = outcome
        action.outcome_data = {
            "summary": f"Seeds: {seeds_created}, Published: {published.count()}, "
                       f"Avg engagement: {avg_engagement:.1f}%",
            "seeds_created": seeds_created,
            "posts_generated": posts.count(),
            "posts_published": published.count(),
            "avg_engagement_rate": round(avg_engagement, 2),
            "acceptance_rate": round(acceptance_rate, 2),
        }
        action.outcome_measured_at = timezone.now()
        action.save(update_fields=["outcome_score", "outcome_data", "outcome_measured_at"])
        scored += 1

    return scored


def get_strategy_history(user, limit=5):
    """
    Get the Strategist's recent cycle outcomes for injection into its next cycle.
    This is how the Strategist learns from its own past decisions.
    """
    recent = AgentAction.objects.filter(
        user=user,
        agent_type="strategist",
        action_type="strategy_cycle",
        status=AgentAction.ActionStatus.COMPLETED,
        outcome_score__isnull=False,
    ).order_by("-created_at")[:limit]

    if not recent.exists():
        return ""

    parts = ["## YOUR PAST STRATEGY OUTCOMES (learn from these)"]
    for action in recent:
        data = action.outcome_data or {}
        parts.append(
            f"  - [{action.created_at.strftime('%b %d')}] "
            f"Score: {action.outcome_score}/100 — {data.get('summary', 'No summary')}"
        )

    avg_score = sum(a.outcome_score for a in recent) / recent.count()
    parts.append(f"\nYour average strategy score: {avg_score:.0f}/100")

    if avg_score < 50:
        parts.append("⚠️ Recent strategies underperformed. Try different approaches.")
    elif avg_score >= 70:
        parts.append("✅ Recent strategies working well. Continue this direction.")

    parts.append("INSTRUCTION: Study what worked and what didn't. Adjust your approach accordingly.\n")
    return "\n".join(parts)
