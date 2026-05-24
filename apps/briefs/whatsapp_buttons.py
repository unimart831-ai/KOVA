"""WhatsApp button definitions for daily brief delivery + reply-to-act."""

from __future__ import annotations

from django.conf import settings

# Template quick-reply labels (must match Meta-approved template exactly)
TEMPLATE_QUICK_REPLY_LABELS = ("Approve", "Score", "Help")

# Session interactive button IDs → command text for whatsapp_commands
BUTTON_ID_TO_COMMAND = {
    "brief_approve": "approve",
    "brief_score": "score",
    "brief_help": "help",
    "brief_brief": "brief",
    "brief_posts": "posts",
    "brief_idea_1": "idea 1",
    "brief_idea_2": "idea 2",
}

# Title fallbacks (case-insensitive match)
TITLE_TO_COMMAND = {
    "approve": "approve",
    "score": "score",
    "help": "help",
    "brief": "brief",
    "posts": "posts",
    "open brief": "brief",
}


def map_button_inbound(button_id: str = "", title: str = "") -> str:
    """Map interactive button id/title to a command string."""
    if button_id and button_id in BUTTON_ID_TO_COMMAND:
        return BUTTON_ID_TO_COMMAND[button_id]
    normalized = (title or "").strip().lower()
    if normalized in TITLE_TO_COMMAND:
        return TITLE_TO_COMMAND[normalized]
    return (title or button_id or "").strip()


def build_daily_brief_template_components(
    first_name: str,
    summary_snippet: str,
    score_line: str,
) -> list[dict]:
    """Build Meta template components for the daily brief ping.

    Template layout (register in Meta Business Suite):
      Body: 3 variables (name, summary, score)
      Button 0: URL  — "Open brief" → https://YOUR_DOMAIN/brief/{{1}}
      Button 1: Quick reply — "Approve"
      Button 2: Quick reply — "Score"

    If URL is fully static (no {{1}}), set KOVA_DAILY_BRIEF_URL_SUFFIX="" in env.
    """
    components: list[dict] = [{
        "type": "body",
        "parameters": [
            {"type": "text", "text": first_name},
            {"type": "text", "text": summary_snippet},
            {"type": "text", "text": score_line},
        ],
    }]

    url_suffix = getattr(settings, "KOVA_DAILY_BRIEF_URL_SUFFIX", "?utm_source=whatsapp")
    if url_suffix:
        components.append({
            "type": "button",
            "sub_type": "url",
            "index": "0",
            "parameters": [{"type": "text", "text": url_suffix.lstrip("?") if url_suffix.startswith("?") else url_suffix}],
        })

    return components


def action_buttons_for_user(user, *, posts_pending: int = 0) -> list[dict]:
    """Up to 3 session buttons shown after each command reply (24h window)."""
    if posts_pending > 0:
        return [
            {"id": "brief_approve", "title": "Approve"},
            {"id": "brief_posts", "title": "Posts"},
            {"id": "brief_score", "title": "Score"},
        ]
    return [
        {"id": "brief_brief", "title": "Brief"},
        {"id": "brief_score", "title": "Score"},
        {"id": "brief_help", "title": "Help"},
    ]
