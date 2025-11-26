"""
Custom JWT Authentication Backend for User Model with user_id as Primary Key

This authentication backend explicitly handles the custom User model that uses
'user_id' instead of 'id' as the primary key field.
"""

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed
from django.contrib.auth import get_user_model

User = get_user_model()


class CustomJWTAuthentication(JWTAuthentication):
    """
    Custom JWT Authentication that correctly handles User model with user_id primary key
    """
    
    def get_user(self, validated_token):
        """
        Attempts to find and return a user using the given validated token.
        Explicitly uses 'user_id' field to match our custom User model.
        """
        try:
            # Get the user_id from the token payload
            user_id = validated_token.get('user_id')
            
            if user_id is None:
                raise InvalidToken('Token contained no recognizable user identification')
            
            # Query using user_id field explicitly
            try:
                user = User.objects.get(user_id=user_id)
            except User.DoesNotExist:
                raise AuthenticationFailed('User not found', code='user_not_found')
            
            # Check if account is active - prevent inactive users from using existing tokens
            if not user.is_active:
                raise AuthenticationFailed('Your account has been deactivated. Please contact an administrator.', code='user_inactive')
            
            return user
            
        except KeyError:
            raise InvalidToken('Token contained no recognizable user identification')


# Backwards compatibility - export both names
CustomJWTAuth = CustomJWTAuthentication

