import logging
import typing
from urllib.parse import parse_qs

from channels.auth import AuthMiddlewareStack
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.utils.functional import LazyObject

from rest_framework_simplejwt.authentication import JWTAuthentication

logger = logging.getLogger(__name__)


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

        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"JWT Middleware: Processing WebSocket connection for scope: {scope.get('path', 'unknown')}")

        # Try JWT token authentication first
        token = self._extract_token_from_scope(scope)
        logger.info(f"JWT Middleware: Extracted token: {token is not None}")
        
        if token:
            user = await self._authenticate_token(token)
            logger.info(f"JWT Middleware: JWT authentication result: {user is not None}")
            if user is not None:
                logger.info(f"JWT Middleware: Authenticated user: {user.user_id}")
                scope['user'] = user
        else:
            # Fallback to session-based authentication
            user = await self._authenticate_session(scope)
            logger.info(f"JWT Middleware: Session authentication result: {user is not None}")
            if user is not None:
                logger.info(f"JWT Middleware: Authenticated user: {user.user_id}")
                scope['user'] = user

        return await self.inner(scope, receive, send)

    def _extract_token_from_scope(self, scope) -> typing.Optional[str]:
        # Prioritize headers over URL for security
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

        # Fallback to query string (less secure, but for backward compatibility)
        try:
            raw_qs = scope.get('query_string', b'').decode('utf-8')
            params = parse_qs(raw_qs)
            if 'token' in params and params['token']:
                token = params['token'][0]
                # Debug logging
                logger.info(f"JWT Middleware: Found token in URL query string: {token[:20]}...")
                return token
            else:
                logger.info("JWT Middleware: No token found in query string")
        except Exception as e:
            logger.warning(f"JWT Middleware: Error extracting token from query string: {e}")

        return None

    @database_sync_to_async
    def _authenticate_token(self, token):
        try:
            validated = self.jwt_auth.get_validated_token(token)
            user = self.jwt_auth.get_user(validated)
            return user
        except Exception:
            return None

    @database_sync_to_async
    def _authenticate_session(self, scope):
        """Authenticate using Django session"""
        try:
            from django.contrib.sessions.models import Session
            from django.contrib.auth import get_user_model
            
            # Get session key from cookies
            cookies = dict(scope.get('cookies') or [])
            session_key = cookies.get(b'sessionid')
            
            if not session_key:
                return None
            
            # Decode session key if it's bytes
            if isinstance(session_key, bytes):
                session_key = session_key.decode('utf-8')
            
            # Get session
            try:
                session = Session.objects.get(session_key=session_key)
            except Session.DoesNotExist:
                return None
            
            # Get user from session
            session_data = session.get_decoded()
            user_id = session_data.get('_auth_user_id')
            
            if not user_id:
                return None
            
            User = get_user_model()
            return User.objects.get(pk=user_id)
            
        except Exception:
            return None


def JWTAuthMiddlewareStack(inner):
    """Compose JWT auth first, then Django session auth for fallbacks."""
    return JWTAuthMiddleware(AuthMiddlewareStack(inner))



