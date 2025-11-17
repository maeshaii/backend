"""
Security Audit Logging System
Senior Developer Implementation for Enterprise-Grade Security Compliance

This module provides comprehensive security event logging for:
- Authentication attempts (success/failure)
- Authorization failures
- Sensitive data access
- Administrative actions
- Password changes
- Role modifications
- Data exports

All security events are logged with:
- Timestamp
- User ID and username
- IP address
- Action type
- Resource accessed
- Success/failure status
- Additional context
"""
import logging
from datetime import datetime
from django.utils import timezone
from typing import Optional, Dict, Any

# Create dedicated security audit logger
audit_logger = logging.getLogger('security.audit')


class SecurityEventType:
    """Enumeration of security event types"""
    # Authentication Events
    LOGIN_SUCCESS = 'LOGIN_SUCCESS'
    LOGIN_FAILURE = 'LOGIN_FAILURE'
    LOGOUT = 'LOGOUT'
    TOKEN_REFRESH = 'TOKEN_REFRESH'
    TOKEN_REFRESH_FAILED = 'TOKEN_REFRESH_FAILED'
    
    # Authorization Events
    UNAUTHORIZED_ACCESS = 'UNAUTHORIZED_ACCESS'
    PERMISSION_DENIED = 'PERMISSION_DENIED'
    ROLE_CHECK_FAILED = 'ROLE_CHECK_FAILED'
    
    # Password Events
    PASSWORD_CHANGE = 'PASSWORD_CHANGE'
    PASSWORD_RESET_REQUEST = 'PASSWORD_RESET_REQUEST'
    PASSWORD_RESET_COMPLETE = 'PASSWORD_RESET_COMPLETE'
    FIRST_LOGIN_PASSWORD_CHANGE = 'FIRST_LOGIN_PASSWORD_CHANGE'
    
    # Administrative Actions
    USER_CREATED = 'USER_CREATED'
    USER_DELETED = 'USER_DELETED'
    USER_UPDATED = 'USER_UPDATED'
    ROLE_CHANGED = 'ROLE_CHANGED'
    BULK_IMPORT = 'BULK_IMPORT'
    BULK_DELETE = 'BULK_DELETE'
    
    # Data Access Events
    SENSITIVE_DATA_ACCESS = 'SENSITIVE_DATA_ACCESS'
    DATA_EXPORT = 'DATA_EXPORT'
    STATISTICS_EXPORT = 'STATISTICS_EXPORT'
    USER_LIST_ACCESS = 'USER_LIST_ACCESS'
    
    # Messaging Events
    MESSAGE_SENT = 'MESSAGE_SENT'
    SMS_SENT = 'SMS_SENT'
    EMAIL_SENT = 'EMAIL_SENT'
    
    # Security Events
    SUSPICIOUS_ACTIVITY = 'SUSPICIOUS_ACTIVITY'
    RATE_LIMIT_EXCEEDED = 'RATE_LIMIT_EXCEEDED'
    INVALID_TOKEN = 'INVALID_TOKEN'
    CSRF_FAILURE = 'CSRF_FAILURE'


class SecurityAudit:
    """Main security audit logging class"""
    
    @staticmethod
    def get_client_ip(request) -> str:
        """Extract client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        return ip
    
    @staticmethod
    def get_user_agent(request) -> str:
        """Extract user agent from request"""
        return request.META.get('HTTP_USER_AGENT', 'unknown')
    
    @staticmethod
    def log_event(
        event_type: str,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        success: bool = True,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        request = None
    ):
        """
        Log a security event
        
        Args:
            event_type: Type of security event (use SecurityEventType constants)
            user_id: ID of user involved
            username: Username of user involved
            ip_address: IP address of client
            success: Whether the action was successful
            resource: Resource that was accessed/modified
            action: Specific action taken
            details: Additional context as dictionary
            request: Django request object (auto-extracts IP and user agent)
        """
        # Extract info from request if provided
        if request:
            if not ip_address:
                ip_address = SecurityAudit.get_client_ip(request)
            user_agent = SecurityAudit.get_user_agent(request)
            
            # Try to get user info from request if not provided
            if not user_id and hasattr(request, 'user') and request.user.is_authenticated:
                user_id = getattr(request.user, 'user_id', None)
                username = getattr(request.user, 'acc_username', None)
        else:
            user_agent = 'unknown'
        
        # Build log message
        timestamp = timezone.now().isoformat()
        status = 'SUCCESS' if success else 'FAILURE'
        
        log_data = {
            'timestamp': timestamp,
            'event_type': event_type,
            'status': status,
            'user_id': user_id or 'anonymous',
            'username': username or 'anonymous',
            'ip_address': ip_address or 'unknown',
            'user_agent': user_agent,
            'resource': resource,
            'action': action,
            'details': details or {}
        }
        
        # Format log message
        msg_parts = [
            f"[{event_type}]",
            f"Status: {status}",
            f"User: {username or 'anonymous'} (ID: {user_id or 'N/A'})",
            f"IP: {ip_address or 'unknown'}"
        ]
        
        if resource:
            msg_parts.append(f"Resource: {resource}")
        if action:
            msg_parts.append(f"Action: {action}")
        if details:
            msg_parts.append(f"Details: {details}")
        
        log_message = " | ".join(msg_parts)
        
        # Log with appropriate level
        if success:
            if event_type in [SecurityEventType.LOGIN_SUCCESS, 
                            SecurityEventType.PASSWORD_CHANGE,
                            SecurityEventType.DATA_EXPORT]:
                audit_logger.info(log_message)
            else:
                audit_logger.debug(log_message)
        else:
            if event_type in [SecurityEventType.LOGIN_FAILURE,
                            SecurityEventType.UNAUTHORIZED_ACCESS,
                            SecurityEventType.SUSPICIOUS_ACTIVITY]:
                audit_logger.warning(log_message)
            else:
                audit_logger.error(log_message)
        
        return log_data
    
    # Convenience methods for common security events
    
    @staticmethod
    def log_login_success(user, request):
        """Log successful login"""
        return SecurityAudit.log_event(
            event_type=SecurityEventType.LOGIN_SUCCESS,
            user_id=getattr(user, 'user_id', None),
            username=getattr(user, 'acc_username', None),
            request=request,
            success=True,
            action='User logged in successfully'
        )
    
    @staticmethod
    def log_login_failure(username: str, request, reason: str = 'Invalid credentials'):
        """Log failed login attempt"""
        return SecurityAudit.log_event(
            event_type=SecurityEventType.LOGIN_FAILURE,
            username=username,
            request=request,
            success=False,
            action='Login attempt failed',
            details={'reason': reason}
        )
    
    @staticmethod
    def log_unauthorized_access(user, request, resource: str, reason: str = 'Insufficient permissions'):
        """Log unauthorized access attempt"""
        return SecurityAudit.log_event(
            event_type=SecurityEventType.UNAUTHORIZED_ACCESS,
            user_id=getattr(user, 'user_id', None) if user else None,
            username=getattr(user, 'acc_username', None) if user else 'anonymous',
            request=request,
            success=False,
            resource=resource,
            action='Access denied',
            details={'reason': reason}
        )
    
    @staticmethod
    def log_password_change(user, request, change_type: str = 'regular'):
        """Log password change"""
        event = (SecurityEventType.FIRST_LOGIN_PASSWORD_CHANGE 
                if change_type == 'first_login' 
                else SecurityEventType.PASSWORD_CHANGE)
        
        return SecurityAudit.log_event(
            event_type=event,
            user_id=getattr(user, 'user_id', None),
            username=getattr(user, 'acc_username', None),
            request=request,
            success=True,
            action='Password changed',
            details={'change_type': change_type}
        )
    
    @staticmethod
    def log_data_export(user, request, export_type: str, record_count: int = 0):
        """Log data export"""
        return SecurityAudit.log_event(
            event_type=SecurityEventType.DATA_EXPORT,
            user_id=getattr(user, 'user_id', None),
            username=getattr(user, 'acc_username', None),
            request=request,
            success=True,
            resource=export_type,
            action='Data exported',
            details={'record_count': record_count}
        )
    
    @staticmethod
    def log_bulk_import(user, request, import_type: str, record_count: int = 0, success_count: int = 0):
        """Log bulk data import"""
        return SecurityAudit.log_event(
            event_type=SecurityEventType.BULK_IMPORT,
            user_id=getattr(user, 'user_id', None),
            username=getattr(user, 'acc_username', None),
            request=request,
            success=True,
            resource=import_type,
            action='Bulk import',
            details={
                'total_records': record_count,
                'successful': success_count,
                'failed': record_count - success_count
            }
        )
    
    @staticmethod
    def log_role_change(admin_user, target_user, request, old_roles: list, new_roles: list):
        """Log role/permission change"""
        return SecurityAudit.log_event(
            event_type=SecurityEventType.ROLE_CHANGED,
            user_id=getattr(admin_user, 'user_id', None),
            username=getattr(admin_user, 'acc_username', None),
            request=request,
            success=True,
            resource=f"User {getattr(target_user, 'user_id', None)}",
            action='Roles modified',
            details={
                'target_user': getattr(target_user, 'acc_username', None),
                'old_roles': old_roles,
                'new_roles': new_roles
            }
        )
    
    @staticmethod
    def log_suspicious_activity(request, activity_type: str, details: dict = None):
        """Log suspicious activity"""
        user = getattr(request, 'user', None)
        return SecurityAudit.log_event(
            event_type=SecurityEventType.SUSPICIOUS_ACTIVITY,
            user_id=getattr(user, 'user_id', None) if user and user.is_authenticated else None,
            username=getattr(user, 'acc_username', None) if user and user.is_authenticated else 'anonymous',
            request=request,
            success=False,
            action=activity_type,
            details=details or {}
        )
    
    @staticmethod
    def log_rate_limit(request, action_type: str, details: dict = None):
        """Log rate limit exceeded"""
        user = getattr(request, 'user', None)
        return SecurityAudit.log_event(
            event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
            user_id=getattr(user, 'user_id', None) if user and user.is_authenticated else None,
            username=getattr(user, 'acc_username', None) if user and user.is_authenticated else 'anonymous',
            request=request,
            success=False,
            action=f'Rate limit exceeded: {action_type}',
            details=details or {}
        )


# Convenience function for quick access
def audit_log(event_type: str, **kwargs):
    """
    Quick access to audit logging
    
    Example:
        audit_log('LOGIN_SUCCESS', user_id=123, username='user123', request=request)
    """
    return SecurityAudit.log_event(event_type, **kwargs)

