"""
Send real-time WebSocket events from anywhere in the backend.

Usage:
    from apps.notifications.realtime import send_user_event

    # Notify a user about agent status change
    send_user_event(user_id, "agent_status", {
        "agent": "create",
        "status": "completed",
        "message": "3 posts generated",
    })

    # Notify about a new notification
    send_user_event(user_id, "notification", {
        "message": "Your post was published!",
        "count": 12,
    })
"""

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def send_user_event(user_id, event_type: str, data: dict | None = None):
    """Send a WebSocket event to a specific user's channel group.

    Safe to call from synchronous code (Celery tasks, views, signals).
    Silently logs errors if the channel layer is unavailable.
    """
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return

        group_name = f"user_{user_id}"
        message = {"type": event_type, **(data or {})}
        async_to_sync(channel_layer.group_send)(group_name, message)
    except Exception:
        logger.debug("WebSocket send failed for user %s event %s", user_id, event_type, exc_info=True)
