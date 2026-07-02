"""Opportunity cards — proactive, one-tap growth suggestions for the owner.

Instead of dashboards, Kova surfaces "here's a move worth making" cards the owner
can act on with a single WhatsApp reply. Each card is grounded in real signals we
already have — returning-customer interest (Business Memory), low stock on wanted
products, and leads that have gone quiet — so the suggestion is always concrete.

Every rule is defensive: a missing model never breaks the card list.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)


def build_opportunity_cards(user, *, limit: int = 4) -> list[dict]:
    """Return up to `limit` opportunity cards, highest priority first.

    Card shape: {id, priority, title, detail, command}
    `command` is a ready-to-send WhatsApp reply (reuses the IDEA command).
    """
    cards: list[dict] = []
    cards += _returning_interest_cards(user)
    cards += _low_stock_cards(user)
    cards += _dormant_lead_cards(user)

    order = {"high": 0, "medium": 1, "low": 2}
    cards.sort(key=lambda c: order.get(c.get("priority", "low"), 3))
    return cards[:limit]


def _returning_interest_cards(user) -> list[dict]:
    """Customers who came back asking about the same product = warm demand."""
    try:
        from apps.whatsapp.models import CustomerMemory

        memories = CustomerMemory.objects.filter(user=user, interaction_count__gte=2).exclude(interests=[])[:200]
    except Exception:
        return []

    counter: Counter = Counter()
    for mem in memories:
        for interest in (mem.interests or [])[:3]:
            counter[str(interest)] += 1

    cards = []
    for interest, count in counter.most_common(2):
        cards.append(
            {
                "id": f"returning_interest:{interest}",
                "priority": "high" if count >= 2 else "medium",
                "title": f"🔥 Customers keep asking about {interest}",
                "detail": f"{count} returning customer{'s' if count != 1 else ''} mentioned {interest}.",
                "command": f"IDEA Promote {interest} to interested customers",
            }
        )
    return cards


def _low_stock_cards(user) -> list[dict]:
    """A wanted product running low is a restock/urgency opportunity."""
    try:
        from apps.products.models import Product

        low = list(
            Product.objects.filter(
                user=user,
                is_active=True,
                stock_status=Product.StockStatus.LOW_STOCK,
            ).order_by("-is_featured")[:2]
        )
    except Exception:
        return []

    cards = []
    for p in low:
        cards.append(
            {
                "id": f"low_stock:{p.pk}",
                "priority": "medium",
                "title": f"📉 {p.name} is running low",
                "detail": "Create urgency before it sells out — or restock.",
                "command": f"IDEA Low-stock urgency post for {p.name}",
            }
        )
    return cards


def _dormant_lead_cards(user) -> list[dict]:
    """Leads that have gone quiet are win-back opportunities."""
    try:
        from apps.leads.models import Lead

        cutoff_old = timezone.now() - timedelta(days=7)
        cutoff_recent = timezone.now() - timedelta(days=90)
        quiet = Lead.objects.filter(
            user=user,
            last_activity_at__lt=cutoff_old,
            last_activity_at__gte=cutoff_recent,
        ).count()
    except Exception:
        return []

    if quiet < 3:
        return []
    return [
        {
            "id": "dormant_leads",
            "priority": "low",
            "title": f"👋 {quiet} leads have gone quiet",
            "detail": "A win-back offer could bring them back.",
            "command": "IDEA Win-back offer for quiet customers",
        }
    ]


def format_opportunity_cards_message(user) -> str:
    """WhatsApp-friendly rendering of the opportunity cards."""
    cards = build_opportunity_cards(user)
    if not cards:
        return "No new opportunities right now — Kova will flag them as they come up."
    lines = ["💡 Opportunities Kova spotted:\n"]
    for i, c in enumerate(cards, 1):
        lines.append(f"{i}. {c['title']}\n   {c['detail']}\n   Reply: {c['command']}")
    return "\n\n".join(lines)
