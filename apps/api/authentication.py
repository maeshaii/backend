"""
Custom JWT Authentication Backend for User Model with user_id as Primary Key

This authentication backend explicitly handles the custom User model that uses
'user_id' instead of 'id' as the primary key field.
"""

import logging
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


class CustomJWTAuthentication(JWTAuthentication):
    """
    Custom JWT Authentication that correctly handles User model with user_id primary key
    """
    
    def authenticate(self, request):
        """
        Override authenticate to add logging for debugging authentication issues
        """
        try:
            # Call parent authenticate method
            result = super().authenticate(request)
            if result:
                user, token = result
                logger.debug(f"CustomJWTAuthentication: Successfully authenticated user {user.user_id}")
            else:
                logger.debug("CustomJWTAuthentication: No valid token found in request")
            return result
        except InvalidToken as e:
            logger.warning(f"CustomJWTAuthentication: Invalid token - {str(e)}")
            raise
        except AuthenticationFailed as e:
            logger.warning(f"CustomJWTAuthentication: Authentication failed - {str(e)}")
            raise
        except Exception as e:
            logger.error(f"CustomJWTAuthentication: Unexpected error during authentication - {str(e)}", exc_info=True)
            raise
    
    def get_user(self, validated_token):
        """
        Attempts to find and return a user using the given validated token.
        Explicitly uses 'user_id' field to match our custom User model.
        """
        try:
            # Get the user_id from the token payload
            user_id = validated_token.get('user_id')
            
            if user_id is None:
                logger.warning(f"CustomJWTAuthentication: Token missing user_id. Token claims: {list(validated_token.keys())}")
                raise InvalidToken('Token contained no recognizable user identification')
            
            # Query using user_id field explicitly
            try:
                user = User.objects.get(user_id=user_id)
                logger.debug(f"CustomJWTAuthentication: Found user {user_id}")
            except User.DoesNotExist:
                logger.warning(f"CustomJWTAuthentication: User with user_id {user_id} not found in database")
                raise AuthenticationFailed('User not found', code='user_not_found')
            
            # Check if account is active - prevent inactive users from using existing tokens
            if not user.is_active:
                logger.warning(f"CustomJWTAuthentication: User {user_id} is inactive")
                raise AuthenticationFailed('This account is deactivated. Please contact the admin.', code='user_inactive')
            
            return user
            
        except KeyError as e:
            logger.warning(f"CustomJWTAuthentication: KeyError getting user_id from token - {str(e)}")
            raise InvalidToken('Token contained no recognizable user identification')
        except (InvalidToken, AuthenticationFailed):
            # Re-raise authentication exceptions
            raise
        except Exception as e:
            logger.error(f"CustomJWTAuthentication: Unexpected error in get_user - {str(e)}", exc_info=True)
            raise AuthenticationFailed(f'Authentication error: {str(e)}', code='authentication_error')


# Backwards compatibility - export both names
CustomJWTAuth = CustomJWTAuthentication

