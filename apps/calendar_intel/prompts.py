"""
Prompt templates for the holiday-draft generator.

Two prompts: a stable system prompt (good candidate for prompt caching) and
a per-call user prompt that injects context. Together they instruct the LLM
to return the JSON shape defined in schemas.HolidayDraftsOutput.

See KOVA_HOLIDAY_AWARENESS.md section 15.
"""
from __future__ import annotations

import json
from typing import Iterable


SYSTEM_PROMPT = """\
You are Kova's holiday content generator. You produce social media post
drafts for a small business owner around upcoming holidays, observances,
and personal moments. Your only output is a JSON object matching the
required schema. Never write commentary, markdown, or explanation outside
of the JSON.

You are NOT a generic copywriter. Every draft you write must:

1. Be in the user's brand voice (faithful to tone, vocabulary, energy).
2. Tie the moment to the user's real product / service / community —
   not generic platitudes.
3. Reference local context (city / country / market) when natural.
4. Match per-platform conventions (length, hashtag style, CTA placement).
5. Be safe to publish without further moderation.

Hard rules — failures here cause the draft to be rejected:

- Do not use these generic phrases: "Happy {holiday}", "Celebrate with us",
  "On this special day", "Show your special someone", "Thinking of you".
- Do not fabricate offers, discounts, percentages, statistics, testimonials,
  or client names. If you don't have a real number, don't invent one.
- For religious moments: be respectful, never proselytize, never wish a
  religion onto people who haven't opted in.
- For political / sensitive moments: stay neutral, never partisan, never
  invoke disputed events or figures.
- Each draft in your response must use a different angle from the
  suggested-angles list — repetition wastes the user's slots.
- Honor any explicit "avoid_phrases" the moment specifies.

Per-platform conventions to obey:

- Instagram: 1-2 sentences body + 3-5 hashtags + light emoji ok. <2200 chars.
- LinkedIn: 3-4 sentences, professional, NO hashtag spam, link in first
  comment not body. <3000 chars.
- Twitter/X: under 280 chars total. 1-2 hashtags max. Punchy.
- Facebook: 2-3 sentences, conversational. Link OK in body.

Output schema (return JSON exactly in this shape):

{
  "drafts": [
    {
      "angle_used": "<short label of the angle from the angles list>",
      "rationale": "<one sentence why this angle for this user>",
      "platform_versions": {
        "instagram": "<copy or null>",
        "linkedin":  "<copy or null>",
        "twitter":   "<copy or null>",
        "facebook":  "<copy or null>"
      },
      "suggested_publish_time": "<ISO 8601 datetime in user-local TZ or null>"
    }
  ]
}

Only include `platform_versions` keys for platforms the user has connected
(listed in the user prompt). Set the others to null. The `drafts` array
must contain between 1 and the requested count.
"""


def build_user_prompt(
    *,
    business_name: str,
    industry: str,
    brand_voice: str,
    location: str,
    currency: str,
    connected_platforms: list[str],
    products_summary: list[str],
    top_posts_summary: list[str],
    moment_name: str,
    moment_date: str,
    days_until: int,
    tone_hint: str,
    angles: list[str],
    avoid_phrases: list[str],
    requested_drafts: int,
) -> str:
    """Compose the per-call user prompt with all context the model needs."""

    def _bullet(items: Iterable[str]) -> str:
        items = [i for i in items if i]
        if not items:
            return "  (none provided)"
        return "\n".join(f"  - {i}" for i in items)

    parts = [
        "MOMENT TO WRITE FOR",
        "─" * 40,
        f"Name: {moment_name}",
        f"Date: {moment_date} (in {days_until} day{'s' if days_until != 1 else ''} from today)",
        f"Tone hint: {tone_hint or 'unspecified'}",
        "Suggested angles (use a different one for each draft):",
        _bullet(angles),
        "Phrases to AVOID (in addition to the global hard-rules):",
        _bullet(avoid_phrases),
        "",
        "USER / BUSINESS CONTEXT",
        "─" * 40,
        f"Business name: {business_name or '(unspecified)'}",
        f"Industry: {industry or '(unspecified)'}",
        f"Location: {location or '(unspecified)'}",
        f"Currency: {currency or 'USD'}",
        f"Brand voice: {brand_voice or '(no brand voice provided — keep tone neutral, warm, professional)'}",
        f"Connected platforms (only emit copy for these): {', '.join(connected_platforms) if connected_platforms else '(none)'}",
        "",
        "Products / services (tie content to one of these where natural):",
        _bullet(products_summary),
        "",
        "Recent post excerpts (for tone calibration only — DO NOT copy):",
        _bullet(top_posts_summary),
        "",
        "TASK",
        "─" * 40,
        f"Generate exactly {requested_drafts} distinct draft{'s' if requested_drafts != 1 else ''}, "
        "each using a different angle from the list above. For each draft, "
        "produce platform_versions copy ONLY for the user's connected platforms; "
        "leave the others as null. Return JSON only — no preamble, no markdown.",
    ]
    return "\n".join(parts)


def render_top_posts_summary(posts) -> list[str]:
    """Compress recent posts into short tone-calibration excerpts.
    `posts` is an iterable of objects with .content_text and optionally .ai_angle."""
    out = []
    for p in posts:
        text = (getattr(p, "content_text", "") or "").strip().replace("\n", " ")
        if not text:
            continue
        excerpt = (text[:140] + "...") if len(text) > 140 else text
        angle = getattr(p, "ai_angle", "") or ""
        if angle:
            out.append(f'"{excerpt}" (angle: {angle})')
        else:
            out.append(f'"{excerpt}"')
    return out[:3]


def render_products_summary(products) -> list[str]:
    """Compress product list into short prompt-friendly bullets."""
    out = []
    for p in products:
        name = (getattr(p, "name", "") or "").strip()
        if not name:
            continue
        desc = (getattr(p, "description", "") or "").strip()
        excerpt = (desc[:120] + "...") if len(desc) > 120 else desc
        if excerpt:
            out.append(f"{name} — {excerpt}")
        else:
            out.append(name)
    return out[:5]
