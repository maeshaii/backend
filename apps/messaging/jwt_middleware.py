import typing
from urllib.parse import parse_qs

from channels.auth import AuthMiddlewareStack
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.utils.functional import LazyObject

from rest_framework_simplejwt.authentication import JWTAuthentication


class _LazyUser(LazyObject):
    def _setup(self):
        self._wrapped = AnonymousUser()


class JWTAuthMiddleware:
    """Populate scope['user'] from a JWT passed via querystring or headers.

    - Accepts `?token=<JWT>` in the websocket URL
    - Or `Authorization: Bearer <JWT>` header (if clients can set it)
    - Falls back to whatever user is already present on the scope
    """

    def __init__(self, inner):
        self.inner = inner
        self.jwt_auth = JWTAuthentication()

    async def __call__(self, scope, receive, send):
        # Ensure we have a user on scope by default
        scope.setdefault('user', _LazyUser())

        token = self._extract_token_from_scope(scope)
        if token:
            user = await self._authenticate_token(token)
            if user is not None:
                scope['user'] = user

        return await self.inner(scope, receive, send)

    def _extract_token_from_scope(self, scope) -> typing.Optional[str]:
        # Query string first: ws://.../path?token=JWT
        try:
            raw_qs = scope.get('query_string', b'').decode('utf-8')
            params = parse_qs(raw_qs)
            if 'token' in params and params['token']:
                return params['token'][0]
        except Exception:
            pass

        # Headers: Authorization: Bearer <JWT>
        try:
            headers = dict(scope.get('headers') or [])
            auth_header = headers.get(b'authorization')
            if auth_header:
                parts = auth_header.decode('utf-8').split()
                if len(parts) == 2 and parts[0].lower() == 'bearer':
                    return parts[1]
        except Exception:
            pass

        return None

    @database_sync_to_async
    def _authenticate_token(self, token):
        try:
            validated = self.jwt_auth.get_validated_token(token)
            user = self.jwt_auth.get_user(validated)
            return user
        except Exception:
            return None


def JWTAuthMiddlewareStack(inner):
    """Compose JWT auth first, then Django session auth for fallbacks."""
    return JWTAuthMiddleware(AuthMiddlewareStack(inner))



