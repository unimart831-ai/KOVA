"""
Platform-native rewrite layer — end copy-paste publishing.

Campaign copy → per-platform native rewrites via Create Agent LLM.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

PLATFORM_REWRITE_GUIDES = {
    "instagram": {
        "focus": "Storytelling, visual appeal, save/share hooks, emoji-light engagement",
        "tone": "Warm, aspirational, scroll-stopping first line",
        "max_chars": 2200,
    },
    "facebook": {
        "focus": "Community, conversation starters, shareable framing",
        "tone": "Friendly, inclusive, question or poll energy",
        "max_chars": 5000,
    },
    "tiktok": {
        "focus": "Hook strength in first 3 words, curiosity gap, trend-aware casual voice",
        "tone": "Casual, punchy, pattern interrupt",
        "max_chars": 2200,
    },
    "linkedin": {
        "focus": "Professional insights, authority, business value, line breaks for skim",
        "tone": "Thought leadership, specific takeaway, no hype",
        "max_chars": 3000,
    },
}


def _needs_rewrite(post_dict: dict, all_posts: list[dict]) -> bool:
    """Detect copy-paste: same caption body used on multiple platforms."""
    text = (post_dict.get("content_text") or "").strip()
    if len(text) < 40:
        return True
    plat = (post_dict.get("platform") or "").lower()
    if plat not in PLATFORM_REWRITE_GUIDES:
        return False
    for other in all_posts:
        if other is post_dict:
            continue
        other_text = (other.get("content_text") or "").strip()
        if other_text and text == other_text:
            return True
        # Near-duplicate (>85% overlap on short captions)
        if other_text and len(text) > 60 and text[:60] == other_text[:60]:
            return True
    return False


def rewrite_post_for_platform(
    post_dict: dict,
    *,
    seed,
    user,
    source_text: str = "",
) -> dict:
    """LLM rewrite single platform post — native tone, not truncated copy."""
    from apps.create.agents.llm import generate, get_model_for_task, parse_llm_json

    platform = (post_dict.get("platform") or "").lower()
    guide = PLATFORM_REWRITE_GUIDES.get(platform)
    if not guide:
        return post_dict

    base = (post_dict.get("content_text") or source_text or "").strip()
    if not base:
        return post_dict

    idea = (getattr(seed, "idea", None) or "")[:500]
    prompt = f"""Rewrite this social post for {platform.upper()} — native to the platform, NOT a copy-paste.

ORIGINAL:
{base}

CAMPAIGN IDEA:
{idea}

PLATFORM RULES:
- Focus: {guide['focus']}
- Tone: {guide['tone']}
- Max length: {guide['max_chars']} characters

Return JSON only: {{"content_text": "...", "angle": "one-line strategy note"}}
"""

    try:
        response = generate(
            prompt=prompt,
            system="You are a platform-native social copywriter. Never reuse the same opening line across platforms.",
            model=get_model_for_task("create.rewrite", user=user),
            json_mode=True,
            temperature=0.6,
            max_tokens=1200,
        )
        result = parse_llm_json(response.content)
        if result.get("content_text"):
            post_dict = dict(post_dict)
            post_dict["content_text"] = result["content_text"][: guide["max_chars"]]
            if result.get("angle"):
                post_dict["ai_angle"] = result["angle"]
            post_dict["platform_rewritten"] = True
    except Exception as exc:
        logger.warning("Platform rewrite failed for %s: %s", platform, exc)

    return post_dict


def apply_platform_rewrites(seed, post_dicts: list[dict], *, user=None) -> list[dict]:
    """
    Rewrite posts that share duplicate copy across platforms.
    Called after initial LLM batch, before Post.objects.create.
    """
    user = user or seed.user
    if not post_dicts or len(post_dicts) < 2:
        return post_dicts

    source = (post_dicts[0].get("content_text") or "").strip()
    out: list[dict] = []
    for pd in post_dicts:
        plat = (pd.get("platform") or "").lower()
        if plat in PLATFORM_REWRITE_GUIDES and _needs_rewrite(pd, post_dicts):
            pd = rewrite_post_for_platform(pd, seed=seed, user=user, source_text=source)
        out.append(pd)
    return out
