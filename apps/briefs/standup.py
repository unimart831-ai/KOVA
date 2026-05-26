"""Morning Standup — structured daily digest for web + WhatsApp."""

from __future__ import annotations

from django.conf import settings
from django.urls import reverse

from apps.briefs.delivery import extract_your_move


def guess_decision_url(decision) -> str | None:
    """Map a decision item to the most relevant in-app destination."""
    if not isinstance(decision, dict):
        return None
    text = " ".join([
        decision.get("item", ""),
        decision.get("recommended_action", ""),
        decision.get("context", ""),
    ]).lower()
    if any(w in text for w in ("whatsapp", "wa chat", "status")):
        return reverse("whatsapp:status_studio")
    if any(w in text for w in ("comment", "reply", "inbox", "message", "dm", "mention")):
        return reverse("engage:inbox")
    if any(w in text for w in ("lead", "pricing", "prospect", "inquiry")):
        return reverse("leads:list")
    if any(w in text for w in ("booking", "appointment", "schedule")):
        return reverse("bookings:list")
    if any(w in text for w in ("fail", "queue", "publish error")):
        return reverse("content:queue")
    if any(w in text for w in ("approv", "draft", "post", "content", "studio")):
        return reverse("content:studio")
    if any(w in text for w in ("platform", "connect", "account", "profile health")):
        return reverse("platforms:list")
    if any(w in text for w in ("holiday", "moment", "calendar")):
        return reverse("brief:home")
    if any(w in text for w in ("revenue", "sale", "money", "pixel")):
        return reverse("analytics:revenue")
    if any(w in text for w in ("competitor", "intel")):
        return reverse("analytics:competitors")
    return None


def enrich_decisions(decisions):
    enriched = []
    for decision in decisions or []:
        item = dict(decision) if isinstance(decision, dict) else {"item": str(decision)}
        url = guess_decision_url(item)
        if url:
            item["action_url"] = url
        enriched.append(item)
    return enriched


def get_top_decision(brief) -> dict | None:
    """Pick the single highest-priority decision for standup."""
    if not brief:
        return None
    decisions = enrich_decisions((brief.performance_summary or {}).get("decisions_needed", []))
    if not decisions:
        return None
    for d in decisions:
        if isinstance(d, dict) and d.get("urgency") == "now":
            return d
    return decisions[0]


def build_standup_context(user, brief) -> dict:
    """Web + WhatsApp standup payload."""
    from apps.briefs.delivery import build_mobile_digest

    site = getattr(settings, "SITE_URL", "").rstrip("/")
    digest = build_mobile_digest(brief) if brief else {}
    top = get_top_decision(brief)
    decision_url = top.get("action_url") if top else None
    if decision_url and site and decision_url.startswith("/"):
        decision_url = f"{site}{decision_url}"

    overnight = ""
    if brief and brief.overnight_work:
        ow = brief.overnight_work
        if isinstance(ow, dict):
            overnight = ow.get("summary") or ow.get("headline") or ""
        elif isinstance(ow, str):
            overnight = ow

    posts_pending = brief.posts_pending if brief else 0
    score = brief.kova_score if brief else 0
    delta = brief.kova_score_delta if brief else 0

    return {
        "headline": digest.get("headline") or "Your Morning Standup",
        "your_move": extract_your_move(brief.summary if brief else "") or digest.get("your_move") or "",
        "kova_score": score,
        "kova_score_delta": delta,
        "posts_pending": posts_pending,
        "top_decision": top,
        "decision_url": decision_url,
        "overnight_summary": (overnight or "")[:280],
        "brief_url": f"{site}/brief/" if site else reverse("brief:home"),
        "studio_url": f"{site}/content/studio/" if site else reverse("content:studio"),
        "whatsapp_hint": "Reply STANDUP on WhatsApp for this digest anytime.",
    }


def format_standup_whatsapp_message(user, brief) -> str:
    """Compact standup message for WhatsApp STANDUP command."""
    ctx = build_standup_context(user, brief)
    lines = ["☀️ Morning Standup", ""]

    if brief:
        delta = ctx["kova_score_delta"] or 0
        delta_txt = f" ({'+' if delta > 0 else ''}{delta})" if delta else ""
        lines.append(f"Score: {ctx['kova_score']}/100{delta_txt} · {ctx['posts_pending']} post(s) to approve")
    else:
        lines.append("Your brief isn't ready yet — check back after your brief time.")

    if ctx["your_move"]:
        lines.append(f"\nYour move: {ctx['your_move'][:200]}")

    if ctx["overnight_summary"]:
        lines.append(f"\nOvernight: {ctx['overnight_summary'][:160]}")

    top = ctx["top_decision"]
    if top:
        item = top.get("item") or top.get("title") or "Decision needed"
        action = top.get("recommended_action") or "Open the app to decide"
        lines.append(f"\n⚡ Only you: {item[:120]}")
        lines.append(f"→ {action[:120]}")
        if ctx["decision_url"]:
            lines.append(f"\n{ctx['decision_url']}")

    if ctx["posts_pending"] > 0:
        lines.append(f"\nReply APPROVE ALL to schedule {ctx['posts_pending']} post(s).")
    elif not top:
        lines.append(f"\nFull brief: {ctx['brief_url']}")

    return "\n".join(lines)[:4090]


def mark_standup_engaged(brief) -> None:
    if brief and not brief.is_read:
        brief.is_read = True
        brief.save(update_fields=["is_read"])
