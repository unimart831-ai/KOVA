"""
One-time script to fix existing DailyBrief and CompetitorAnalysis records
that have raw JSON stored in their text summary fields.

Run: python manage.py shell < scripts/fix_raw_json_records.py
"""

import json

from apps.agents.llm import parse_llm_json
from apps.analytics.models import CompetitorAnalysis
from apps.briefs.models import DailyBrief

# ── Fix Daily Briefs with raw JSON in summary ──────────────────────────────

broken_briefs = DailyBrief.objects.filter(summary__startswith="{")
print(f"Found {broken_briefs.count()} daily briefs with raw JSON summary")

for brief in broken_briefs:
    try:
        data = parse_llm_json(brief.summary)
    except (json.JSONDecodeError, ValueError):
        try:
            data = json.loads(brief.summary)
        except json.JSONDecodeError:
            print(f"  SKIP brief {brief.date} — can't parse")
            continue

    updated = []
    if isinstance(data.get("summary"), str):
        brief.summary = data["summary"]
        updated.append("summary")

    if data.get("trending_topics") and not brief.trending_topics:
        brief.trending_topics = data["trending_topics"]
        updated.append("trending_topics")

    if data.get("suggested_posts") and not brief.suggested_posts:
        brief.suggested_posts = data["suggested_posts"]
        updated.append("suggested_posts")

    if data.get("performance_highlight") and not brief.performance_summary.get("highlight"):
        brief.performance_summary = {
            **brief.performance_summary,
            "highlight": data["performance_highlight"],
        }
        updated.append("performance_summary")

    if updated:
        brief.save(update_fields=updated)
        print(f"  FIXED brief {brief.date}: {', '.join(updated)}")


# ── Fix Competitor Analyses with raw JSON in summary ────────────────────────

broken_analyses = CompetitorAnalysis.objects.filter(summary__startswith="{")
print(f"\nFound {broken_analyses.count()} competitor analyses with raw JSON summary")

for analysis in broken_analyses:
    try:
        data = parse_llm_json(analysis.summary)
    except (json.JSONDecodeError, ValueError):
        try:
            data = json.loads(analysis.summary)
        except json.JSONDecodeError:
            print(f"  SKIP analysis {analysis.pk} — can't parse")
            continue

    updated = []
    if isinstance(data.get("summary"), str):
        analysis.summary = data["summary"]
        updated.append("summary")

    for field in ["strengths", "weaknesses", "opportunities", "threats"]:
        if data.get(field) and not getattr(analysis, field):
            setattr(analysis, field, data[field])
            updated.append(field)

    if data.get("content_strategy") and not analysis.content_strategy:
        analysis.content_strategy = data["content_strategy"]
        updated.append("content_strategy")

    if data.get("comparison") and not analysis.comparison_to_user:
        analysis.comparison_to_user = data["comparison"]
        updated.append("comparison_to_user")

    if data.get("actionable_insights") and not analysis.actionable_insights:
        analysis.actionable_insights = data["actionable_insights"]
        updated.append("actionable_insights")

    if updated:
        analysis.save(update_fields=updated)
        print(f"  FIXED analysis {analysis.pk}: {', '.join(updated)}")

        # Also update the parent Competitor's cached fields
        if analysis.competitor:
            comp = analysis.competitor
            if data.get("strengths"):
                comp.strengths = data["strengths"]
            if data.get("weaknesses"):
                comp.weaknesses = data["weaknesses"]
            if data.get("content_strategy"):
                comp.content_patterns = data["content_strategy"]
            if data.get("threat_level"):
                comp.threat_level = data["threat_level"]
            comp.save(update_fields=["strengths", "weaknesses", "content_patterns", "threat_level"])

print("\nDone!")
