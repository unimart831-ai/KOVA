"""Lead detection + escalation for engagement inbox."""

from __future__ import annotations

import re

from apps.engage.models import Interaction

LEAD_SIGNALS = re.compile(
    r"\b(price|cost|how much|buy|order|book|appointment|available|delivery|"
    r"whatsapp|call me|interested|quote)\b",
    re.I,
)


def detect_lead_intent(text: str) -> bool:
    return bool(LEAD_SIGNALS.search(text or ""))


def escalate_flagged_threads(user) -> int:
    """Flag negative sentiment and lead-intent interactions for priority review."""
    qs = Interaction.objects.filter(
        user=user,
        status=Interaction.Status.NEW,
    )
    updated = 0
    for item in qs[:50]:
        text = (item.content or "") + " " + (item.ai_suggested_reply or "")
        if item.sentiment == "negative" or detect_lead_intent(text):
            item.status = Interaction.Status.FLAGGED
            item.save(update_fields=["status"])
            updated += 1
    return updated
