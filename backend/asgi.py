"""
ASGI config for backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from apps.messaging.routing import websocket_urlpatterns
from apps.messaging.jwt_middleware import JWTAuthMiddlewareStack

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    # Prefer JWT auth if provided, then fall back to session auth
    "websocket": JWTAuthMiddlewareStack(
        URLRouter(
            websocket_urlpatterns
        )
    ),
})
