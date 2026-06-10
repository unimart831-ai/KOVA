"""WebSocket push when new Engage interactions arrive."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def notify_engage_new(interaction) -> None:
    """Notify connected clients — Engage inbox can refresh without polling."""
    try:
        from apps.notifications.realtime import send_user_event

        platform = ""
        if interaction.social_account_id:
            platform = interaction.social_account.platform
        send_user_event(
            interaction.user_id,
            "engage_new",
            {
                "interaction_id": str(interaction.pk),
                "platform": platform,
            },
        )
    except Exception:
        logger.debug("engage_new WS notify failed", exc_info=True)
