"""
Security Helper Functions for IDOR Protection
Senior Developer Implementation - Prevents Insecure Direct Object References

IDOR (Insecure Direct Object Reference) is a vulnerability where users can
access/modify resources they shouldn't have access to by manipulating IDs.

Example Attack:
    User A (ID: 5) makes request: /api/notifications?user_id=10
    Without IDOR protection, User A can read User 10's notifications!

This module provides helper functions to prevent IDOR attacks.
"""
import logging
from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


def check_user_access(request, target_user_id, allow_admin=True, allow_owner=True):
    """
    Check if requesting user can access target user's resources
    
    Args:
        request: Django request object with authenticated user
        target_user_id: ID of user whose resource is being accessed
        allow_admin: If True, admins can access any resource
        allow_owner: If True, users can access their own resources
    
    Returns:
        tuple: (is_authorized: bool, error_response: JsonResponse or None)
        
    Usage:
        authorized, error = check_user_access(request, user_id)
        if not authorized:
            return error
        # Continue with authorized access
    """
    try:
        requesting_user = request.user
        
        if not requesting_user or not requesting_user.is_authenticated:
            logger.warning(f"IDOR: Unauthenticated access attempt to user {target_user_id}")
            return False, JsonResponse({
                'success': False,
                'error': 'Authentication required'
            }, status=401)
        
        # Convert target_user_id to int for comparison
        target_id = int(target_user_id)
        requesting_id = requesting_user.user_id
        
        # Check if user is owner
        is_owner = (requesting_id == target_id)
        
        # Check if user is admin
        is_admin = False
        if allow_admin:
            try:
                account_type = getattr(requesting_user, 'account_type', None)
                is_admin = account_type and getattr(account_type, 'admin', False)
            except Exception:
                is_admin = False
        
        # Determine access
        if allow_owner and is_owner:
            return True, None
        
        if allow_admin and is_admin:
            return True, None
        
        # Access denied
        logger.warning(
            f"IDOR ATTACK PREVENTED: User {requesting_id} ({requesting_user.acc_username}) "
            f"attempted to access user {target_id}'s resources. "
            f"Is Owner: {is_owner}, Is Admin: {is_admin}"
        )
        
        return False, JsonResponse({
            'success': False,
            'error': 'Permission denied. You can only access your own resources.'
        }, status=403)
        
    except ValueError:
        logger.error(f"IDOR: Invalid user_id format: {target_user_id}")
        return False, JsonResponse({
            'success': False,
            'error': 'Invalid user ID format'
        }, status=400)
    except Exception as e:
        logger.error(f"IDOR check error: {e}")
        return False, JsonResponse({
            'success': False,
            'error': 'Authorization check failed'
        }, status=500)


def require_owner_or_admin(view_func):
    """
    Decorator to enforce owner-or-admin access control
    
    Usage:
        @api_view(['GET'])
        @permission_classes([IsAuthenticated])
        @require_owner_or_admin
        def get_notifications(request):
            user_id = request.GET.get('user_id')
            # user_id is already validated by decorator
            ...
    
    The decorated view must:
    - Accept user_id from request.GET, request.POST, or request.data
    - OR have user_id in kwargs (from URL path)
    """
    def wrapper(request, *args, **kwargs):
        # Try to get user_id from various sources
        user_id = None
        
        # Check URL kwargs first (e.g., /api/profile/<user_id>/)
        if 'user_id' in kwargs:
            user_id = kwargs['user_id']
        # Check GET parameters
        elif hasattr(request, 'GET') and request.GET.get('user_id'):
            user_id = request.GET.get('user_id')
        # Check POST/PUT data
        elif hasattr(request, 'data') and request.data.get('user_id'):
            user_id = request.data.get('user_id')
        elif hasattr(request, 'POST') and request.POST.get('user_id'):
            user_id = request.POST.get('user_id')
        
        if not user_id:
            return JsonResponse({
                'success': False,
                'error': 'user_id is required'
            }, status=400)
        
        # Check access
        authorized, error_response = check_user_access(request, user_id)
        if not authorized:
            return error_response
        
        # Access granted, proceed to view
        return view_func(request, *args, **kwargs)
    
    return wrapper


def check_notification_owner(request, notification):
    """
    Check if user owns a specific notification
    
    Args:
        request: Django request object
        notification: Notification object
    
    Returns:
        tuple: (is_authorized: bool, error_response or None)
    """
    try:
        requesting_user = request.user
        notification_user_id = notification.user_id
        
        if requesting_user.user_id != notification_user_id:
            # Check if admin
            account_type = getattr(requesting_user, 'account_type', None)
            is_admin = account_type and getattr(account_type, 'admin', False)
            
            if not is_admin:
                logger.warning(
                    f"IDOR ATTACK PREVENTED: User {requesting_user.user_id} "
                    f"attempted to access notification belonging to user {notification_user_id}"
                )
                return False, JsonResponse({
                    'success': False,
                    'error': 'Permission denied'
                }, status=403)
        
        return True, None
        
    except Exception as e:
        logger.error(f"Error checking notification ownership: {e}")
        return False, JsonResponse({
            'success': False,
            'error': 'Authorization check failed'
        }, status=500)


def check_post_owner(request, post):
    """
    Check if user owns a specific post
    
    Args:
        request: Django request object
        post: Post object
    
    Returns:
        tuple: (is_authorized: bool, error_response or None)
    """
    try:
        requesting_user = request.user
        post_author_id = post.author.user_id
        
        if requesting_user.user_id != post_author_id:
            # Check if admin
            account_type = getattr(requesting_user, 'account_type', None)
            is_admin = account_type and getattr(account_type, 'admin', False)
            
            if not is_admin:
                logger.warning(
                    f"IDOR ATTACK PREVENTED: User {requesting_user.user_id} "
                    f"attempted to modify post belonging to user {post_author_id}"
                )
                return False, JsonResponse({
                    'success': False,
                    'error': 'You can only modify your own posts'
                }, status=403)
        
        return True, None
        
    except Exception as e:
        logger.error(f"Error checking post ownership: {e}")
        return False, JsonResponse({
            'success': False,
            'error': 'Authorization check failed'
        }, status=500)


def check_comment_owner(request, comment):
    """
    Check if user owns a specific comment
    
    Args:
        request: Django request object
        comment: Comment object
    
    Returns:
        tuple: (is_authorized: bool, error_response or None)
    """
    try:
        requesting_user = request.user
        comment_author_id = comment.user.user_id
        
        if requesting_user.user_id != comment_author_id:
            # Check if admin
            account_type = getattr(requesting_user, 'account_type', None)
            is_admin = account_type and getattr(account_type, 'admin', False)
            
            if not is_admin:
                logger.warning(
                    f"IDOR ATTACK PREVENTED: User {requesting_user.user_id} "
                    f"attempted to modify comment belonging to user {comment_author_id}"
                )
                return False, JsonResponse({
                    'success': False,
                    'error': 'You can only modify your own comments'
                }, status=403)
        
        return True, None
        
    except Exception as e:
        logger.error(f"Error checking comment ownership: {e}")
        return False, JsonResponse({
            'success': False,
            'error': 'Authorization check failed'
        }, status=500)


def validate_user_id_match(request, user_id, operation="access"):
    """
    Validate that the user_id in the request matches the authenticated user
    (unless the user is an admin)
    
    Args:
        request: Django request object
        user_id: The user_id from the request parameter
        operation: String describing what operation is being attempted (for logging)
    
    Returns:
        tuple: (is_valid: bool, error_response or None)
    
    Usage:
        is_valid, error = validate_user_id_match(request, user_id, "delete profile picture")
        if not is_valid:
            return error
    """
    authorized, error = check_user_access(request, user_id, allow_admin=True, allow_owner=True)
    
    if not authorized:
        logger.warning(
            f"IDOR: User {request.user.user_id} attempted to {operation} "
            f"for user {user_id} without permission"
        )
    
    return authorized, error


# Shorthand functions for common checks
def is_owner(request, resource_user_id):
    """Check if requesting user is the owner of the resource"""
    try:
        return request.user.user_id == int(resource_user_id)
    except:
        return False


def is_admin(request):
    """Check if requesting user is an admin"""
    try:
        account_type = getattr(request.user, 'account_type', None)
        return account_type and getattr(account_type, 'admin', False)
    except:
        return False


def is_owner_or_admin(request, resource_user_id):
    """Check if requesting user is owner or admin"""
    return is_owner(request, resource_user_id) or is_admin(request)

