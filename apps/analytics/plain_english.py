"""Plain-English insights generator (Phase 4 P4.4).

Instead of charts and aggregate numbers the Performance dashboard
shows full sentences the owner can act on: "Your video posts get 3.2×
more engagement than image posts" and "Tuesday afternoon is your
strongest time slot."

Pure-python aggregation over PostMetric. No LLM, no chart libs.
Returns a list[dict] of {headline, detail, kind} the template renders
as a stack of cards.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import List, Dict

from django.db.models import Avg, Count, Sum, Q
from django.utils import timezone


def get_plain_english_insights(user, days: int = 30) -> List[Dict[str, str]]:
    """Return a small list of fully-formed sentences describing what
    has been working (and what hasn't) for this account."""
    from apps.analytics.models import PostMetric

    cutoff = timezone.now() - timedelta(days=days)
    metrics = (
        PostMetric.objects
        .filter(post__user=user, post__status="published", created_at__gte=cutoff)
        .select_related("post__social_account")
    )

    insights: list[dict] = []
    if not metrics.exists():
        return [{
            "kind": "empty",
            "headline": "No published posts yet in the last "
                        f"{days} days.",
            "detail": "Publish a few posts and insights will land here automatically.",
        }]

    # ── Best-performing platform ───────────────────────────────────
    by_platform = (
        metrics
        .values("post__social_account__platform")
        .annotate(
            avg_eng=Avg("engagement_rate"),
            n=Count("id"),
            total_impr=Sum("impressions"),
        )
        .filter(n__gte=2)
        .order_by("-avg_eng")
    )
    plats = list(by_platform)
    if len(plats) >= 2:
        best = plats[0]
        worst = plats[-1]
        best_rate = (best["avg_eng"] or 0)
        worst_rate = (worst["avg_eng"] or 0)
        if worst_rate > 0 and best_rate / worst_rate >= 1.5:
            ratio = best_rate / worst_rate
            insights.append({
                "kind": "platform",
                "headline": (
                    f"{(best['post__social_account__platform'] or '').title()} "
                    f"is your strongest channel — {ratio:.1f}× the engagement "
                    f"of {(worst['post__social_account__platform'] or '').title()}."
                ),
                "detail": (
                    f"Across {best['n']} {best['post__social_account__platform']} "
                    f"posts you averaged {best_rate*100:.1f}% engagement, vs "
                    f"{worst_rate*100:.1f}% on {worst['post__social_account__platform']}. "
                    "Consider shifting effort to the stronger channel."
                ),
            })

    # ── Best day of week ───────────────────────────────────────────
    by_dow = defaultdict(lambda: [0, 0])  # weekday → [sum_eng, count]
    for m in metrics:
        if m.post and m.post.published_at:
            dow = m.post.published_at.weekday()
            er = m.engagement_rate or 0
            by_dow[dow][0] += er
            by_dow[dow][1] += 1
    dow_avgs = {
        dow: (s / n) for dow, (s, n) in by_dow.items() if n >= 2
    }
    if len(dow_avgs) >= 3:
        names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        best_dow = max(dow_avgs, key=dow_avgs.get)
        worst_dow = min(dow_avgs, key=dow_avgs.get)
        if dow_avgs[best_dow] > 0 and dow_avgs[worst_dow] > 0:
            ratio = dow_avgs[best_dow] / max(dow_avgs[worst_dow], 1e-9)
            if ratio >= 1.3:
                insights.append({
                    "kind": "day",
                    "headline": (
                        f"{names[best_dow]} is your strongest day "
                        f"({dow_avgs[best_dow]*100:.1f}% avg engagement)."
                    ),
                    "detail": (
                        f"{names[worst_dow]} comes in lowest at "
                        f"{dow_avgs[worst_dow]*100:.1f}%. Lean more of your "
                        f"effort into {names[best_dow]} posts."
                    ),
                })

    # ── Content-type comparison ────────────────────────────────────
    by_type = (
        metrics
        .filter(post__content_type__isnull=False)
        .values("post__content_type")
        .annotate(avg_eng=Avg("engagement_rate"), n=Count("id"))
        .filter(n__gte=3)
        .order_by("-avg_eng")
    )
    types = list(by_type)
    if len(types) >= 2:
        top, bottom = types[0], types[-1]
        top_rate = top["avg_eng"] or 0
        bot_rate = bottom["avg_eng"] or 0
        if bot_rate > 0 and top_rate / bot_rate >= 1.5:
            ratio = top_rate / bot_rate
            insights.append({
                "kind": "content_type",
                "headline": (
                    f"Your {top['post__content_type']} posts outperform "
                    f"{bottom['post__content_type']} posts by {ratio:.1f}×."
                ),
                "detail": (
                    f"{top['n']} {top['post__content_type']} posts averaged "
                    f"{top_rate*100:.1f}% engagement. The {bottom['post__content_type']} "
                    f"format averaged {bot_rate*100:.1f}%. Do more of the winner."
                ),
            })

    # ── Save-rate signal ────────────────────────────────────────────
    save_totals = metrics.aggregate(
        saves=Sum("saves"), impr=Sum("impressions"),
    )
    if (save_totals["saves"] or 0) >= 10 and (save_totals["impr"] or 0) > 0:
        save_rate = save_totals["saves"] / save_totals["impr"]
        if save_rate >= 0.005:
            insights.append({
                "kind": "saves",
                "headline": (
                    f"You drove {save_totals['saves']} saves "
                    f"({save_rate*100:.2f}% save rate) — that's strong intent."
                ),
                "detail": (
                    "Saves mean people want to come back. Look at which posts "
                    "drove them and make more like that."
                ),
            })

    # ── Volume / consistency ────────────────────────────────────────
    n_posts = metrics.count()
    if n_posts < 8:
        insights.append({
            "kind": "volume",
            "headline": (
                f"Only {n_posts} published posts in the last {days} days — "
                "consistency matters more than perfection."
            ),
            "detail": (
                "Aim for 3-5 posts per week so the data has enough signal "
                "to learn from. The Adapt agent needs volume to spot patterns."
            ),
        })

    if not insights:
        insights.append({
            "kind": "fallback",
            "headline": (
                f"You published {n_posts} posts in the last {days} days "
                "with steady engagement."
            ),
            "detail": (
                "No standout pattern yet — keep posting and the AI will "
                "surface what's working in a few more cycles."
            ),
        })

    return insights[:5]
