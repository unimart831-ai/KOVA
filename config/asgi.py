"""
ASGI config for Kova Agent.
Supports HTTP + WebSocket via Django Channels.
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        # WebSocket routes will be added here when we build real-time features
        # "websocket": AuthMiddlewareStack(
        #     URLRouter([])
        # ),
    }
)
