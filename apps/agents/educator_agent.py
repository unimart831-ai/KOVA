"""
Educator Agent — Platform-level content author for Kova.

Distinct from the six per-tenant agents (Research, Create, Adapt, Engage,
Analyst, Strategist), this agent acts on behalf of Kova itself:

  • Writes educational articles (tips, how-tos, best practices) that serve
    both in-product /help/ users and public /blog/ prospects.
  • Compiles the weekly "Kova This Week" digest (changelog + featured
    articles + platform stats) that ships inside the existing per-user
    weekly report email.

Every output is created in a DRAFT / APPROVED workflow. Nothing is
published or sent without founder review.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from html import escape

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.agents.llm import generate, get_model_for_task, parse_llm_json
from apps.help.models import (
    Article,
    ArticleTopic,
    ChangelogEntry,
    WeeklyDigest,
)
from apps.utils.html_sanitize import sanitize_html

logger = logging.getLogger(__name__)


AUTHOR_AGENT = "educator"


def _estimate_reading_minutes(html: str) -> int:
    text = re.sub(r"<[^>]+>", " ", html)
    words = len(text.split())
    return max(1, round(words / 220))


def _unique_slug(base: str) -> str:
    slug = slugify(base)[:110] or "article"
    candidate = slug
    n = 2
    while Article.objects.filter(slug=candidate).exists():
        candidate = f"{slug}-{n}"
        n += 1
    return candidate


# ────────────────────────────────────────────────────────────────────────
# Article drafting
# ────────────────────────────────────────────────────────────────────────


_ARTICLE_SYSTEM = """You are the Educator, an in-house content author for Kova Agent — an autonomous social media platform for African MSMEs.

You write practical, confident, specific articles that teach small business owners how to use Kova Agent and succeed on social media. No filler, no SEO mush, no generic advice.

Voice: clear, direct, warm but not chatty. Short sentences. Concrete examples.

Output ONLY a JSON object with these keys:
- "title": string, under 70 characters.
- "excerpt": string, under 180 characters, a plain-text summary used on cards.
- "meta_title": string, under 65 characters, SEO title.
- "meta_description": string, under 155 characters, SEO description.
- "body_html": string, the article body as HTML. Only these tags are allowed: p, h2, h3, h4, ul, ol, li, strong, em, a, blockquote, code, pre, br, hr. Do NOT include <h1> — the title is rendered by the page. Open with a p paragraph. 400-900 words typical.
- "tags": array of 3-6 short lowercase strings.

Do not include any prose outside the JSON."""


@dataclass
class DraftResult:
    article: Article
    topic: ArticleTopic | None
    llm_tokens: int


def draft_article(
    topic: ArticleTopic | str,
    audience: str = Article.Audience.USER,
    category: str = Article.Category.TIPS,
) -> DraftResult:
    """Draft an Article from a topic. Returns a DraftResult.

    `topic` may be an ArticleTopic row (preferred — audience/category are
    read from it) or a raw title string (used for ad-hoc drafts).
    """
    topic_obj: ArticleTopic | None = None
    if isinstance(topic, ArticleTopic):
        topic_obj = topic
        title_seed = topic.title
        rationale = topic.rationale
        audience = topic.audience
        category = topic.suggested_category
    else:
        title_seed = str(topic)
        rationale = ""

    prompt_lines = [
        f"Topic: {title_seed}",
        f"Intended audience: {audience} (user = inside the product help centre; prospect = public SEO blog; both = writes for either).",
        f"Category: {category}.",
    ]
    if rationale:
        prompt_lines.append(f"Why this matters: {rationale}")
    prompt = "\n".join(prompt_lines)

    model = get_model_for_task("educator.draft_article")
    logger.info("Educator drafting article: topic=%r model=%s", title_seed, model)
    resp = generate(
        prompt=prompt,
        system=_ARTICLE_SYSTEM,
        model=model,
        temperature=0.6,
        max_tokens=2500,
        json_mode=True,
    )

    try:
        data = parse_llm_json(resp.content)
    except json.JSONDecodeError as e:
        logger.error("Educator: LLM returned invalid JSON: %s", e)
        raise

    title = (data.get("title") or title_seed).strip()[:200]
    body_html = sanitize_html(data.get("body_html") or "")
    if not body_html.strip():
        raise ValueError("Educator produced an empty article body.")

    with transaction.atomic():
        article = Article.objects.create(
            slug=_unique_slug(title),
            title=title,
            excerpt=(data.get("excerpt") or "").strip()[:300],
            body_md="",  # agent emits HTML directly; markdown source is forward-compat
            body_html=body_html,
            category=category,
            audience=audience,
            status=Article.Status.DRAFT,
            meta_title=(data.get("meta_title") or "").strip()[:70],
            meta_description=(data.get("meta_description") or "").strip()[:160],
            tags=list(data.get("tags") or [])[:10],
            reading_minutes=_estimate_reading_minutes(body_html),
            author_agent=AUTHOR_AGENT,
        )
        if topic_obj is not None:
            topic_obj.status = ArticleTopic.Status.DRAFTED
            topic_obj.drafted_article = article
            topic_obj.drafted_at = timezone.now()
            topic_obj.save(update_fields=["status", "drafted_article", "drafted_at"])

    logger.info(
        "Educator created Article id=%s slug=%s tokens=%d",
        article.id, article.slug, resp.total_tokens,
    )
    return DraftResult(article=article, topic=topic_obj, llm_tokens=resp.total_tokens)


# ────────────────────────────────────────────────────────────────────────
# Topic ideation — the agent proposes its own backlog
# ────────────────────────────────────────────────────────────────────────


_TOPIC_SYSTEM = """You are the Educator for Kova Agent, an AI-powered social media platform serving African MSMEs (small businesses).

Your job: propose fresh, specific article topics that would actually help a Kova user or attract a new prospect through search.

Two audiences to serve:
- "user" = someone already using Kova; they want tactical tips for getting more out of the platform.
- "prospect" = a small business owner reading the public blog; they want playbooks and growth tactics.
- "both" = evergreen guidance that serves either reader.

Output rules:
- Respond with ONLY a JSON object of the form: {"topics": [ ... ]}.
- Each topic has these keys:
    "title" (under 70 chars, specific and actionable — never generic like "How to use social media"),
    "audience" (one of: user, prospect, both),
    "category" (one of: tips, getting-started, content, agents, analytics, account, product-updates),
    "rationale" (one sentence, plain text, on why this topic helps the audience),
    "priority" (integer 0-100, higher = more valuable).
- Do not repeat any title already present in the corpus or backlog (lists provided).
- Favor categories under-represented in the published corpus.
- Write titles a small business owner in Lagos, Nairobi, Kigali or Accra would actually click."""


def suggest_topics(n: int = 5) -> list[ArticleTopic]:
    """Generate up to n novel ArticleTopic rows, grounded in existing corpus
    and changelog. Returns the topics it actually created (duplicates and
    invalid items are silently skipped). Never raises — failures return []."""
    from django.db.models import Count

    existing_article_titles = list(
        Article.objects.order_by("-published_at").values_list("title", flat=True)[:80]
    )
    existing_topic_titles = list(
        ArticleTopic.objects
        .filter(status__in=[ArticleTopic.Status.PENDING, ArticleTopic.Status.DRAFTED])
        .values_list("title", flat=True)[:50]
    )
    cat_counts = dict(
        Article.objects.filter(status=Article.Status.PUBLISHED)
        .values("category").annotate(c=Count("id")).values_list("category", "c")
    )
    recent_changelog = list(
        ChangelogEntry.objects.filter(is_public=True)
        .order_by("-shipped_at")[:5]
        .values_list("title", flat=True)
    )

    context = [f"Please propose {n} novel article topics.", ""]
    context.append("Existing published articles (DO NOT duplicate):")
    for t in existing_article_titles:
        context.append(f"- {t}")
    if existing_topic_titles:
        context.append("")
        context.append("Already in the backlog (DO NOT duplicate):")
        for t in existing_topic_titles:
            context.append(f"- {t}")
    context.append("")
    context.append("Category coverage across published articles:")
    for cat_value, cat_label in Article.Category.choices:
        context.append(f"- {cat_value}: {cat_counts.get(cat_value, 0)} article(s)")
    if recent_changelog:
        context.append("")
        context.append("Things shipped on Kova recently (good seeds for product-updates or how-to tips):")
        for t in recent_changelog:
            context.append(f"- {t}")

    try:
        model = get_model_for_task("educator.suggest_topics")
        resp = generate(
            prompt="\n".join(context),
            system=_TOPIC_SYSTEM,
            model=model,
            temperature=0.8,
            max_tokens=1500,
            json_mode=True,
        )
    except Exception:
        logger.exception("Educator suggest_topics LLM call failed")
        return []

    try:
        data = parse_llm_json(resp.content)
    except json.JSONDecodeError:
        logger.error(
            "Educator suggest_topics returned invalid JSON: %s", (resp.content or "")[:500],
        )
        return []

    raw_topics = data.get("topics") or []
    if not isinstance(raw_topics, list):
        return []

    valid_categories = {c for c, _ in Article.Category.choices}
    valid_audiences = {a for a, _ in Article.Audience.choices}
    seen_lower = {t.lower() for t in existing_article_titles + existing_topic_titles}

    created: list[ArticleTopic] = []
    for item in raw_topics[:n]:
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or "").strip()[:200]
        if not title or title.lower() in seen_lower:
            continue

        category = item.get("category") or Article.Category.TIPS
        if category not in valid_categories:
            category = Article.Category.TIPS

        audience = item.get("audience") or Article.Audience.USER
        if audience not in valid_audiences:
            audience = Article.Audience.USER

        try:
            priority = int(item.get("priority", 50))
        except (ValueError, TypeError):
            priority = 50
        priority = max(0, min(100, priority))

        topic, was_created = ArticleTopic.objects.get_or_create(
            title=title,
            defaults={
                "rationale": (item.get("rationale") or "").strip()[:500],
                "suggested_category": category,
                "audience": audience,
                "priority": priority,
                "source": ArticleTopic.Source.GAP,  # agent-generated from gap analysis
            },
        )
        if was_created:
            created.append(topic)
            seen_lower.add(title.lower())

    logger.info(
        "Educator suggested %d new topics (requested %d, LLM returned %d)",
        len(created), n, len(raw_topics),
    )
    return created


def draft_next_topic(min_backlog: int = 1, suggest_batch: int = 5) -> DraftResult | None:
    """Draft the highest-priority pending topic.

    If the backlog has fewer than ``min_backlog`` pending topics when this
    runs, the agent first calls ``suggest_topics`` to refill it. This keeps
    the weekly drafting loop fully autonomous — the founder never has to
    seed topics manually.

    Returns ``None`` only if the backlog is empty AND topic generation
    produced no usable candidates."""
    pending_count = ArticleTopic.objects.filter(
        status=ArticleTopic.Status.PENDING,
    ).count()
    if pending_count < min_backlog:
        logger.info(
            "Educator backlog=%d < min_backlog=%d; asking agent to suggest topics.",
            pending_count, min_backlog,
        )
        suggest_topics(n=suggest_batch)

    topic = (
        ArticleTopic.objects
        .filter(status=ArticleTopic.Status.PENDING)
        .order_by("-priority", "created_at")
        .first()
    )
    if not topic:
        logger.warning("Educator: backlog empty and topic suggestion produced nothing.")
        return None
    return draft_article(topic)


# ────────────────────────────────────────────────────────────────────────
# Weekly digest
# ────────────────────────────────────────────────────────────────────────


def _week_bounds(week_end: date | None = None) -> tuple[date, date]:
    """Return (week_start, week_end) where week_end is the upcoming Sunday
    (inclusive) and week_start is Monday of the same week."""
    today = timezone.localdate() if week_end is None else week_end
    # days_ahead from today to Sunday (weekday 6)
    days_ahead = (6 - today.weekday()) % 7
    end = today + timedelta(days=days_ahead)
    start = end - timedelta(days=6)
    return start, end


def _render_changelog_html(entries: list[ChangelogEntry]) -> str:
    if not entries:
        return ""
    items = []
    for e in entries:
        label = escape(e.get_category_display())
        title = escape(e.title)
        body = escape(e.body_md).replace("\n", "<br>") if e.body_md else ""
        items.append(
            f'<li style="margin-bottom:10px;">'
            f'<span style="display:inline-block;font-size:10px;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:0.05em;color:#0066FF;background:#E6F0FF;padding:2px 8px;border-radius:4px;'
            f'margin-right:8px;">{label}</span>'
            f'<strong style="color:#111827;">{title}</strong>'
            + (f'<div style="font-size:13px;color:#4b5563;margin-top:4px;">{body}</div>' if body else "")
            + "</li>"
        )
    return (
        '<h3 style="margin:24px 0 8px;font-size:15px;color:#111827;">✨ What shipped this week</h3>'
        '<ul style="list-style:none;padding:0;margin:0;">'
        + "".join(items) + "</ul>"
    )


def _render_articles_html(articles: list[Article], site_url: str = "") -> str:
    if not articles:
        return ""
    base = site_url.rstrip("/")
    items = []
    for a in articles:
        title = escape(a.title)
        excerpt = escape(a.excerpt or "")
        href = f"{base}/learn/{a.slug}/" if base else f"/learn/{a.slug}/"
        items.append(
            f'<tr><td style="padding:12px 0;border-bottom:1px solid #e5e7eb;">'
            f'<a href="{href}" style="text-decoration:none;color:#111827;font-weight:600;font-size:14px;">{title}</a>'
            f'<div style="font-size:12px;color:#6b7280;margin-top:2px;">{excerpt}</div>'
            f'</td></tr>'
        )
    return (
        '<h3 style="margin:24px 0 8px;font-size:15px;color:#111827;">📚 New reading</h3>'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0">'
        + "".join(items) + "</table>"
    )


_DIGEST_INTRO_SYSTEM = """You are the Educator, writing a warm one-paragraph intro for Kova Agent's weekly newsletter section.

Given the list of things that shipped this week and the headline articles, write 2-3 sentences that feel like a human founder update — confident, practical, no hype words. Plain text only, no HTML. Under 60 words. Do not greet by name."""


def _generate_intro(changelog: list[ChangelogEntry], articles: list[Article]) -> str:
    if not changelog and not articles:
        return ""
    parts = []
    if changelog:
        parts.append("Shipped: " + "; ".join(e.title for e in changelog[:5]))
    if articles:
        parts.append("Articles: " + "; ".join(a.title for a in articles[:3]))
    try:
        model = get_model_for_task("educator.compile_digest")
        resp = generate(
            prompt="\n".join(parts),
            system=_DIGEST_INTRO_SYSTEM,
            model=model,
            temperature=0.5,
            max_tokens=200,
        )
        text = (resp.content or "").strip().strip('"').strip()
        return f'<p style="margin:0 0 12px;font-size:14px;line-height:1.6;color:#374151;">{escape(text)}</p>'
    except Exception as e:
        logger.warning("Educator intro generation failed, falling back to static intro: %s", e)
        return (
            '<p style="margin:0 0 12px;font-size:14px;line-height:1.6;color:#374151;">'
            "Here's what shipped on Kova this week, and a few things worth reading."
            "</p>"
        )


def compile_weekly_digest(week_end: date | None = None, force: bool = False) -> WeeklyDigest:
    """Assemble (or refresh) the WeeklyDigest for the given week. Idempotent:
    running twice for the same week updates the existing draft unless it has
    already been approved/sent (in which case it is returned unchanged unless
    force=True)."""
    from django.conf import settings

    start, end = _week_bounds(week_end)
    digest, _created = WeeklyDigest.objects.get_or_create(
        week_end=end,
        defaults={"status": WeeklyDigest.Status.DRAFT},
    )
    if digest.status in (WeeklyDigest.Status.APPROVED, WeeklyDigest.Status.SENT) and not force:
        return digest

    changelog = list(
        ChangelogEntry.objects.filter(
            is_public=True,
            shipped_at__date__gte=start,
            shipped_at__date__lte=end,
        ).order_by("-shipped_at")
    )
    articles = list(
        Article.objects.filter(
            status=Article.Status.PUBLISHED,
            audience__in=[Article.Audience.USER, Article.Audience.BOTH],
            published_at__date__gte=start - timedelta(days=14),  # last ~3 weeks
        ).order_by("-published_at")[:3]
    )

    site_url = getattr(settings, "SITE_URL", "")
    digest.intro_html = _generate_intro(changelog, articles)
    digest.changelog_html = _render_changelog_html(changelog)
    digest.articles_html = _render_articles_html(articles, site_url=site_url)
    digest.stats_html = ""  # analyst integration is a follow-up
    digest.raw_content = {
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "changelog_ids": [str(e.id) for e in changelog],
        "article_ids": [str(a.id) for a in articles],
        "compiled_at": timezone.now().isoformat(),
    }
    digest.save()
    logger.info(
        "Educator compiled digest week_end=%s changelog=%d articles=%d",
        end, len(changelog), len(articles),
    )
    return digest


def get_latest_sendable_digest() -> WeeklyDigest | None:
    """Return the most recently approved (but not yet sent) digest, if any.
    Used by send_weekly_reports_all to append the Kova section."""
    return (
        WeeklyDigest.objects
        .filter(status=WeeklyDigest.Status.APPROVED)
        .order_by("-week_end")
        .first()
    )
