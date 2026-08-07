"""
WebSocket consumer for real-time notifications and live updates.

Replaces HTMX polling for: agent status, seed generation progress,
post publishing status, new notifications, and engage inbox updates.

Clients connect to: ws://<host>/ws/updates/
Messages are JSON with a "type" field for routing on the client side.
"""

import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

logger = logging.getLogger(__name__)


class UpdatesConsumer(AsyncJsonWebsocketConsumer):
    """Per-user WebSocket channel for real-time updates.

    Group name: user_<user_id>
    Server pushes events like:
      {"type": "notification", "message": "...", "count": 5}
      {"type": "agent_status", "agent": "create", "status": "running"}
      {"type": "seed_progress", "seed_id": "...", "status": "completed", "post_count": 3}
      {"type": "post_status", "post_id": "...", "status": "published"}
      {"type": "engage_new", "interaction_id": "...", "platform": "instagram"}
    """

    async def connect(self):
        user = self.scope.get("user")
        if not user or user.is_anonymous:
            await self.close()
            return

        self.user_id = str(user.pk)
        self.group_name = f"user_{self.user_id}"

        try:
            await self.channel_layer.group_add(self.group_name, self.channel_name)
        except Exception as exc:
            # Redis/channel layer unavailable — close cleanly; client JS reconnects.
            logger.warning(
                "WebSocket channel layer unavailable for user %s: %s",
                self.user_id,
                exc,
            )
            await self.close()
            return

        await self.accept()

        count = await self._unread_notification_count()
        await self.send_json({"type": "connected", "unread_count": count})

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            try:
                await self.channel_layer.group_discard(self.group_name, self.channel_name)
            except Exception as exc:
                logger.debug(
                    "WebSocket group_discard failed for user %s: %s",
                    getattr(self, "user_id", "?"),
                    exc,
                )

    async def receive_json(self, content, **kwargs):
        msg_type = content.get("type", "")
        if msg_type == "ping":
            await self.send_json({"type": "pong"})
        elif msg_type == "mark_read":
            await self._mark_notifications_read()
            await self.send_json({"type": "unread_count", "count": 0})

    async def notification(self, event):
        await self.send_json(event)

    async def agent_status(self, event):
        await self.send_json(event)

    async def seed_progress(self, event):
        await self.send_json(event)

    async def post_status(self, event):
        await self.send_json(event)

    async def engage_new(self, event):
        await self.send_json(event)

    async def token_warning(self, event):
        await self.send_json(event)

    async def brief_ready(self, event):
        await self.send_json(event)

    @database_sync_to_async
    def _unread_notification_count(self):
        from apps.messaging.notifications.models import Notification
        return Notification.objects.filter(user_id=self.user_id, is_read=False).count()

    @database_sync_to_async
    def _mark_notifications_read(self):
        from apps.messaging.notifications.models import Notification
        Notification.objects.filter(user_id=self.user_id, is_read=False).update(is_read=True)
