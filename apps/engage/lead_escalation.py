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
    )[:50]
    flag_ids = []
    for item in qs:
        text = (item.content or "") + " " + (item.ai_suggested_reply or "")
        if item.sentiment == "negative" or detect_lead_intent(text):
            flag_ids.append(item.pk)
    if not flag_ids:
        return 0
    return Interaction.objects.filter(pk__in=flag_ids).update(status=Interaction.Status.FLAGGED)
