"""
ASGI config for backend project.

It exposes the ASGI callable as a module-level variable named ``application``.
<<<<<<< HEAD
"""

import os
import django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter

# Configure Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

# Ensure Django apps are loaded before importing things that use models
django.setup()

# Now it's safe to import things that rely on Django models
from apps.messaging.jwt_middleware import JWTAuthMiddlewareStack
from apps.messaging.routing import websocket_urlpatterns

# Create ASGI application
application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": JWTAuthMiddlewareStack(
        URLRouter(
            websocket_urlpatterns
        )
    ),
})
=======

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

application = get_asgi_application()
>>>>>>> 746e601016fd6b6113a8116f65f35a08788c789a
