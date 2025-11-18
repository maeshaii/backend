"""
Custom Django REST Framework Permission Classes for Role-Based Access Control

This module provides role-based permission classes for the Alumni Tracking System.
All permissions verify authentication first, then check specific roles.

Usage Example:
    from apps.api.permissions import IsAdmin, IsAdminOrPeso
    
    @api_view(['GET'])
    @permission_classes([IsAdmin])
    def admin_only_view(request):
        # Only users with admin role can access this
        pass

Security Features:
    - All unauthorized access attempts are logged
    - User information included in logs for forensics
    - Clear error messages for debugging
"""

from rest_framework import permissions
from rest_framework.permissions import BasePermission
import logging

logger = logging.getLogger(__name__)


class IsAdmin(BasePermission):
    """
    Permission: User must be authenticated AND have admin role
    Usage: @permission_classes([IsAdmin])
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            logger.warning(f"Unauthorized access attempt to {request.path} - No authentication")
            return False
        
        try:
            account_type = getattr(request.user, 'account_type', None)
            if not account_type or not getattr(account_type, 'admin', False):
                logger.warning(
                    f"Unauthorized access attempt to {request.path} by user {request.user.user_id} "
                    f"(username: {request.user.acc_username}) - Not admin"
                )
                return False
            return True
        except Exception as e:
            logger.error(f"Error checking admin permission: {e}")
            return False


class IsPeso(BasePermission):
    """
    Permission: User must be authenticated AND have peso role
    Usage: @permission_classes([IsPeso])
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            account_type = getattr(request.user, 'account_type', None)
            return account_type and getattr(account_type, 'peso', False)
        except Exception:
            return False


class IsCoordinator(BasePermission):
    """
    Permission: User must be authenticated AND have coordinator role
    Usage: @permission_classes([IsCoordinator])
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            account_type = getattr(request.user, 'account_type', None)
            return account_type and getattr(account_type, 'coordinator', False)
        except Exception:
            return False


class IsAlumni(BasePermission):
    """
    Permission: User must be authenticated AND have user (alumni) role
    Usage: @permission_classes([IsAlumni])
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            account_type = getattr(request.user, 'account_type', None)
            return account_type and getattr(account_type, 'user', False)
        except Exception:
            return False


class IsOJT(BasePermission):
    """
    Permission: User must be authenticated AND have ojt role
    Usage: @permission_classes([IsOJT])
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            account_type = getattr(request.user, 'account_type', None)
            return account_type and getattr(account_type, 'ojt', False)
        except Exception:
            return False


class IsAlumniOrOJT(BasePermission):
    """
    Permission: User must be authenticated AND have user OR ojt role
    Usage: @permission_classes([IsAlumniOrOJT])
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        try:
            account_type = getattr(request.user, 'account_type', None)
            if not account_type:
                return False
            return (
                getattr(account_type, 'user', False) or 
                getattr(account_type, 'ojt', False)
            )
        except Exception:
            return False


class IsAdminOrPeso(BasePermission):
    """
    Permission: User must be authenticated AND have admin OR peso role
    Usage: @permission_classes([IsAdminOrPeso])
    Common for: Statistics, exports, reports
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            logger.warning(f"Unauthorized access attempt to {request.path} - No authentication")
            return False
        
        try:
            account_type = getattr(request.user, 'account_type', None)
            if not account_type:
                return False
            
            is_authorized = (
                getattr(account_type, 'admin', False) or 
                getattr(account_type, 'peso', False)
            )
            
            if not is_authorized:
                logger.warning(
                    f"Unauthorized access attempt to {request.path} by user {request.user.user_id} "
                    f"(username: {request.user.acc_username}) - Not admin or peso"
                )
            
            return is_authorized
        except Exception as e:
            logger.error(f"Error checking admin/peso permission: {e}")
            return False


class IsAdminOrCoordinator(BasePermission):
    """
    Permission: User must be authenticated AND have admin OR coordinator role
    Usage: @permission_classes([IsAdminOrCoordinator])
    Common for: OJT management, imports, statistics
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            logger.warning(f"Unauthorized access attempt to {request.path} - No authentication")
            return False
        
        try:
            account_type = getattr(request.user, 'account_type', None)
            if not account_type:
                return False
            
            is_authorized = (
                getattr(account_type, 'admin', False) or 
                getattr(account_type, 'coordinator', False)
            )
            
            if not is_authorized:
                logger.warning(
                    f"Unauthorized access attempt to {request.path} by user {request.user.user_id} "
                    f"(username: {request.user.acc_username}) - Not admin or coordinator"
                )
            
            return is_authorized
        except Exception as e:
            logger.error(f"Error checking admin/coordinator permission: {e}")
            return False


class IsOwnerOrAdmin(BasePermission):
    """
    Permission: User must be the resource owner OR an admin
    Usage: @permission_classes([IsOwnerOrAdmin])
    Note: Requires additional ownership check in view
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated


class IsOwnerOrAdminOrPeso(BasePermission):
    """
    Permission: User must be the resource owner OR admin OR peso
    Usage: @permission_classes([IsOwnerOrAdminOrPeso])
    Note: Requires additional ownership check in view
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated


class IsOwnerOrAdminOrCoordinator(BasePermission):
    """
    Permission: User must be the resource owner OR admin OR coordinator
    Usage: @permission_classes([IsOwnerOrAdminOrCoordinator])
    Note: Requires additional ownership check in view
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
