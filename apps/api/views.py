"""
API endpoints for authentication, alumni, OJT, notifications, posts, and related features.
Uses shared models and serializers for data representation. If this file continues to grow, consider splitting endpoints into submodules (e.g., auth_views.py, alumni_views.py, ojt_views.py, post_views.py).
"""

import logging
import uuid
import os
logger = logging.getLogger(__name__)

from django.conf import settings
from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.core.files.storage import default_storage
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.db.models import *
from apps.shared.models import User, AccountType, OJTImport, Notification, Post, Like, Comment, Reply, ContentImage, Repost, UserProfile, AcademicInfo, EmploymentHistory, TrackerData, OJTInfo, UserInitialPassword, DonationRequest, RecentSearch, SendDate, UserPoints, RewardInventoryItem, RewardHistory, RewardRequest, OJTCompanyProfile
from apps.shared.services import UserService
from apps.shared.serializers import UserSerializer, AlumniListSerializer, UserCreateSerializer
import json
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from datetime import datetime, timedelta
import secrets
import string
import base64
from rest_framework_simplejwt.tokens import RefreshToken
import pandas as pd
import io
import os
from django.core.files.uploadedfile import InMemoryUploadedFile
from collections import Counter
from apps.shared.models import Question
from django.core.mail import send_mail
from rest_framework.decorators import api_view, parser_classes, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.parsers import MultiPartParser, JSONParser
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Value, CharField, Q
from django.db import connection
from django.db.utils import ProgrammingError
from django.db.models.functions import Concat, Coalesce
from rest_framework.decorators import api_view
import tempfile
from django.http import FileResponse
from django.db import transaction
from typing import Optional


def _table_exists(table_name: str) -> bool:
    """
    Safely check if a database table exists.
    Prevents runtime errors when migrations haven't been applied yet.
    """
    try:
        with connection.cursor() as cursor:
            tables = connection.introspection.table_names(cursor)
        return table_name in tables
    except Exception:
        return False

# --- Helper Functions ---

def check_rate_limit(user, action_type):
    """
    Check if user has exceeded rate limits for a specific action type.
    
    Returns:
        tuple: (is_allowed: bool, error_message: str, reset_time: datetime or None)
    """
    from apps.shared.models import EngagementPointsSettings, UserActionLog
    from django.utils import timezone
    from datetime import timedelta
    
    try:
        settings = EngagementPointsSettings.get_settings()
        
        # If rate limiting is disabled, allow all actions
        if not settings.rate_limiting_enabled:
            return True, None, None
        
        # Get current time
        now = timezone.now()
        
        # Calculate time windows
        one_hour_ago = now - timedelta(hours=1)
        one_day_ago = now - timedelta(days=1)
        
        # Get limit field names based on action type
        daily_limit_field = f'daily_{action_type}_limit'
        hourly_limit_field = f'hourly_{action_type}_limit'
        
        # Get limits from settings
        daily_limit = getattr(settings, daily_limit_field, None)
        hourly_limit = getattr(settings, hourly_limit_field, None)
        
        # If no limits configured for this action type, allow it
        if daily_limit is None and hourly_limit is None:
            return True, None, None
        
        # Count actions in the last hour
        hourly_count = UserActionLog.objects.filter(
            user=user,
            action_type=action_type,
            action_timestamp__gte=one_hour_ago
        ).count()
        
        # Count actions in the last 24 hours
        daily_count = UserActionLog.objects.filter(
            user=user,
            action_type=action_type,
            action_timestamp__gte=one_day_ago
        ).count()
        
        # Check hourly limit
        if hourly_limit is not None and hourly_count >= hourly_limit:
            # Calculate when the oldest action in the last hour will expire
            oldest_action = UserActionLog.objects.filter(
                user=user,
                action_type=action_type,
                action_timestamp__gte=one_hour_ago
            ).order_by('action_timestamp').first()
            
            if oldest_action:
                reset_time = oldest_action.action_timestamp + timedelta(hours=1)
                time_until_reset = reset_time - now
                minutes = int(time_until_reset.total_seconds() / 60)
                return False, f"You've reached your hourly limit of {hourly_limit} {action_type}s. Try again in {minutes} minute(s).", reset_time
            else:
                return False, f"You've reached your hourly limit of {hourly_limit} {action_type}s. Try again in 1 hour.", now + timedelta(hours=1)
        
        # Check daily limit
        if daily_limit is not None and daily_count >= daily_limit:
            # Calculate when the oldest action in the last 24 hours will expire
            oldest_action = UserActionLog.objects.filter(
                user=user,
                action_type=action_type,
                action_timestamp__gte=one_day_ago
            ).order_by('action_timestamp').first()
            
            if oldest_action:
                reset_time = oldest_action.action_timestamp + timedelta(days=1)
                time_until_reset = reset_time - now
                hours = int(time_until_reset.total_seconds() / 3600)
                return False, f"You've reached your daily limit of {daily_limit} {action_type}s. Try again in {hours} hour(s).", reset_time
            else:
                return False, f"You've reached your daily limit of {daily_limit} {action_type}s. Try again tomorrow.", now + timedelta(days=1)
        
        # All checks passed
        return True, None, None
        
    except Exception as e:
        # If there's an error checking limits, log it but allow the action
        # (fail open to avoid blocking legitimate users due to system errors)
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error checking rate limit for user {user.user_id}, action {action_type}: {e}")
        return True, None, None


def ensure_initial_password_active(user, raw_password: Optional[str] = None, allow_create: bool = False) -> bool:
    """Guarantee the user has an active UserInitialPassword entry.

    Parameters
    ----------
    user: User instance
    raw_password: optional plaintext password to store (only use if you are certain it is current)
    allow_create: when True and the record does not exist, create it (requires raw_password)

    Returns
    -------
    bool
        True if an active record exists or was successfully created/updated.
    """

    try:
        initial = getattr(user, 'initial_password', None)
        updated_fields = []

        if initial:
            if raw_password:
                initial.set_plaintext(raw_password)
                updated_fields.append('password_encrypted')
            if not initial.is_active:
                initial.is_active = True
                updated_fields.append('is_active')
            if updated_fields:
                initial.save(update_fields=updated_fields)
            return True

        if allow_create and raw_password:
            initial = UserInitialPassword.objects.create(user=user)
            initial.set_plaintext(raw_password)
            initial.is_active = True
            initial.save(update_fields=['password_encrypted', 'is_active'])
            return True

        if not initial and not allow_create:
            logger.warning(
                "User %s lacks initial password record; cannot enforce first login without plaintext",
                getattr(user, 'acc_username', user.user_id),
            )
        return False
    except Exception as exc:
        logger.error(
            "Failed to ensure initial password for user %s: %s",
            getattr(user, 'acc_username', user.user_id),
            exc,
        )
        raise

def award_engagement_points(user, action_type):
    """
    Award engagement points to a user for specific actions.
    
    Points are configurable via EngagementPointsSettings model.
    Awards points to Alumni and OJT users.
    OJT users cannot receive tracker_form points since they can't answer the tracker.
    
    Now includes rate limiting to prevent spam.
    """
    try:
        # Get points settings
        from apps.shared.models import EngagementPointsSettings, UserActionLog
        from django.utils import timezone
        settings = EngagementPointsSettings.get_settings()
        
        # Check if points system is enabled
        if not settings.enabled:
            return {'success': True, 'message': 'Points system is disabled'}
        
        # Only award points to Alumni or OJT users
        if not hasattr(user, 'account_type'):
            return {'success': False, 'message': 'User account type not found'}
        
        account_type = user.account_type
        is_alumni = getattr(account_type, 'user', False)
        is_ojt = getattr(account_type, 'ojt', False)
        
        if not (is_alumni or is_ojt):
            return {'success': False, 'message': 'User is not eligible for points'}
        
        # OJT users cannot receive tracker_form points
        if is_ojt and action_type == 'tracker_form':
            return {'success': False, 'message': 'OJT users cannot receive tracker form points'}
        
        # Check rate limits before awarding points
        is_allowed, error_message, reset_time = check_rate_limit(user, action_type)
        if not is_allowed:
            return {
                'success': False,
                'message': error_message,
                'rate_limited': True,
                'reset_time': reset_time.isoformat() if reset_time else None
            }
        
        # Get or create user points
        user_points, created = UserPoints.objects.get_or_create(user=user)
        
        # Award points based on action type using settings from database
        points_map = {
            'like': settings.like_points,
            'comment': settings.comment_points,
            'share': settings.share_points,
            'reply': settings.reply_points,
            'post': settings.post_points,
            'post_with_photo': settings.post_with_photo_points,
            'tracker_form': settings.tracker_form_points
        }
        
        points = points_map.get(action_type, 0)
        if points > 0:
            user_points.add_points(action_type, points)
            
            # Log the action for rate limiting
            UserActionLog.objects.create(
                user=user,
                action_type=action_type,
                action_timestamp=timezone.now()
            )
            
            # Log the points award
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Awarded {points} points to {user.full_name} for {action_type}")
            
            # Broadcast points update via WebSocket for real-time updates
            try:
                from apps.messaging.notification_broadcaster import broadcast_points_update
                from django.db.models import Q
                
                # Get updated points data directly from database
                user_points.refresh_from_db()
                
                # Calculate rank
                higher_points_count = UserPoints.objects.filter(
                    Q(user__account_type__user=True) | Q(user__account_type__ojt=True),
                    total_points__gt=user_points.total_points
                ).count()
                rank = higher_points_count + 1
                
                # Build points breakdown
                points_breakdown = {
                    'likes': {
                        'points': user_points.points_from_likes,
                        'count': user_points.like_count
                    },
                    'comments': {
                        'points': user_points.points_from_comments,
                        'count': user_points.comment_count
                    },
                    'shares': {
                        'points': user_points.points_from_shares,
                        'count': user_points.share_count
                    },
                    'replies': {
                        'points': user_points.points_from_replies,
                        'count': user_points.reply_count
                    },
                    'posts': {
                        'points': user_points.points_from_posts,
                        'count': user_points.post_count
                    },
                    'posts_with_photos': {
                        'points': user_points.points_from_posts_with_photos,
                        'count': user_points.post_with_photo_count
                    },
                    'tracker_form': {
                        'points': user_points.points_from_tracker_form,
                        'count': user_points.tracker_form_count
                    }
                }
                
                broadcast_points_update(user.user_id, {
                    'user_id': user.user_id,
                    'total_points': user_points.total_points,
                    'rank': rank,
                    'points_breakdown': points_breakdown
                })
            except Exception as broadcast_error:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error broadcasting points update for user {user.user_id}: {broadcast_error}")
            
            return {
                'success': True,
                'message': f'Points awarded: {points}',
                'points_awarded': points,
                'total_points': user_points.total_points
            }
        else:
            return {'success': True, 'message': 'No points awarded for this action type'}
            
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error awarding engagement points: {e}")
        return {'success': False, 'message': f'Error awarding points: {str(e)}'}


def deduct_engagement_points(user, action_type):
    """
    Deduct engagement points from a user when they undo an action (e.g., unlike).
    
    Points are configurable via EngagementPointsSettings model.
    Deducts points from Alumni and OJT users.
    """
    try:
        # Get points settings
        from apps.shared.models import EngagementPointsSettings
        from django.utils import timezone
        settings = EngagementPointsSettings.get_settings()
        
        # Check if points system is enabled
        if not settings.enabled:
            return {'success': True, 'message': 'Points system is disabled'}
        
        # Only deduct points from Alumni or OJT users
        if not hasattr(user, 'account_type'):
            return {'success': False, 'message': 'User account type not found'}
        
        account_type = user.account_type
        is_alumni = getattr(account_type, 'user', False)
        is_ojt = getattr(account_type, 'ojt', False)
        
        if not (is_alumni or is_ojt):
            return {'success': False, 'message': 'User is not eligible for points'}
        
        # Get or create user points
        user_points, created = UserPoints.objects.get_or_create(user=user)
        
        # If user points were just created, they have no points to deduct
        if created:
            return {'success': True, 'message': 'No points to deduct'}
        
        # Deduct points based on action type using settings from database
        points_map = {
            'like': settings.like_points,
            'comment': settings.comment_points,
            'share': settings.share_points,
            'reply': settings.reply_points,
            'post': settings.post_points,
            'post_with_photo': settings.post_with_photo_points,
            'tracker_form': settings.tracker_form_points
        }
        
        points = points_map.get(action_type, 0)
        if points > 0:
            user_points.deduct_points(action_type, points)
            
            # Log the points deduction
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Deducted {points} points from {user.full_name} for {action_type}")
            
            # Broadcast points update via WebSocket for real-time updates
            try:
                from apps.messaging.notification_broadcaster import broadcast_points_update
                from django.db.models import Q
                
                # Get updated points data directly from database
                user_points.refresh_from_db()
                
                # Calculate rank
                higher_points_count = UserPoints.objects.filter(
                    Q(user__account_type__user=True) | Q(user__account_type__ojt=True),
                    total_points__gt=user_points.total_points
                ).count()
                rank = higher_points_count + 1
                
                # Build points breakdown
                points_breakdown = {
                    'likes': {
                        'points': user_points.points_from_likes,
                        'count': user_points.like_count
                    },
                    'comments': {
                        'points': user_points.points_from_comments,
                        'count': user_points.comment_count
                    },
                    'shares': {
                        'points': user_points.points_from_shares,
                        'count': user_points.share_count
                    },
                    'replies': {
                        'points': user_points.points_from_replies,
                        'count': user_points.reply_count
                    },
                    'posts': {
                        'points': user_points.points_from_posts,
                        'count': user_points.post_count
                    },
                    'posts_with_photos': {
                        'points': user_points.points_from_posts_with_photos,
                        'count': user_points.post_with_photo_count
                    },
                    'tracker_form': {
                        'points': user_points.points_from_tracker_form,
                        'count': user_points.tracker_form_count
                    }
                }
                
                broadcast_points_update(user.user_id, {
                    'user_id': user.user_id,
                    'total_points': user_points.total_points,
                    'rank': rank,
                    'points_breakdown': points_breakdown
                })
            except Exception as broadcast_error:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error broadcasting points update for user {user.user_id}: {broadcast_error}")
            
            return {
                'success': True,
                'message': f'Points deducted: {points}',
                'points_deducted': points,
                'total_points': user_points.total_points
            }
        else:
            return {'success': True, 'message': 'No points to deduct for this action type'}
            
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error deducting engagement points: {e}")
        return {'success': False, 'message': f'Error deducting points: {str(e)}'}


def get_content_images_safe(content_id, content_type):
    """
    Safely retrieve ContentImage objects with proper error handling.
    Returns empty list if table doesn't exist.
    """
    try:
        content_images = ContentImage.objects.filter(content_type=content_type, content_id=content_id)
        return [{
            'image_id': img.image_id,
            'image_url': img.image.url if img.image else None,
            'order': img.order
        } for img in content_images]
    except Exception as e:
        print(f"Warning: Could not load ContentImage for {content_type} {content_id}: {e}")
        return []

# --- Helpers for Posts ---

@ensure_csrf_cookie
def get_csrf_token(request):
    return JsonResponse({'success': True, 'message': 'CSRF cookie set'})

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods

# Utility: build profile_pic URL with cache-busting when possible
def create_mention_notifications(content, commenter_user, post_id=None, comment_id=None, reply_id=None, forum_id=None, donation_id=None, repost_id=None):
    """Create notifications for users mentioned in content"""
    import re
    from apps.shared.models import Notification
    
    # Find all @mentions in the content
    mention_pattern = r'@([^@\s]+)'
    mentions = re.findall(mention_pattern, content)
    
    for mention in mentions:
        try:
            # Try to find the user by name
            # Split the mention into parts (could be "John Doe" or "John")
            mention_parts = mention.split()
            
            if len(mention_parts) == 1:
                # Single name - search by first name or last name
                user = User.objects.filter(
                    Q(f_name__icontains=mention_parts[0]) | Q(l_name__icontains=mention_parts[0])
                ).first()
            else:
                # Multiple names - search by first and last name
                user = User.objects.filter(
                    Q(f_name__icontains=mention_parts[0]) & Q(l_name__icontains=mention_parts[-1])
                ).first()
            
            if user and user.user_id != commenter_user.user_id:
                # Create notification for the mentioned user
                notification_content = f"{commenter_user.full_name} mentioned you in a comment"
                
                # Add actor ID for profile picture
                notification_content += f"<!--ACTOR_ID:{commenter_user.user_id}-->"
                
                # Add post/comment/reply ID for redirection
                if reply_id:
                    notification_content += f"<!--REPLY_ID:{reply_id}-->"
                
                if comment_id:
                    notification_content += f"<!--COMMENT_ID:{comment_id}-->"
                
                # Add repost ID if present
                if repost_id:
                    notification_content += f"<!--REPOST_ID:{repost_id}-->"
                
                # Add forum, donation, or post ID (in priority order)
                if forum_id:
                    notification_content += f"<!--FORUM_ID:{forum_id}-->"
                elif donation_id:
                    notification_content += f"<!--DONATION_ID:{donation_id}-->"
                elif post_id:
                    notification_content += f"<!--POST_ID:{post_id}-->"
                
                notification = Notification.objects.create(
                    user=user,
                    notif_type='mention',
                    subject='You were mentioned',
                    notifi_content=notification_content,
                    notif_date=timezone.now()
                )
                # Broadcast mention notification in real-time
                try:
                    from apps.messaging.notification_broadcaster import broadcast_notification
                    broadcast_notification(notification)
                except Exception as e:
                    logger.error(f"Error broadcasting mention notification: {e}")
        except Exception as e:
            # Skip if user not found or other error
            continue

def build_profile_pic_url(user, request=None):
    try:
        # Use refactored profile model
        profile = getattr(user, 'profile', None)
        pic = getattr(profile, 'profile_pic', None) if profile else None
        if pic:
            url = pic.url
            # Append last-modified timestamp for cache-busting when available
            try:
                modified = default_storage.get_modified_time(pic.name)
                if modified:
                    url = f"{url}?t={int(modified.timestamp())}"
            except Exception:
                pass

            # Ensure we always return an absolute URL
            try:
                if not str(url).startswith('http'):
                    from django.conf import settings
                    
                    # Try to get base URL from multiple sources (priority order):
                    # 1. Request object (most accurate for mobile)
                    # 2. Environment variable
                    # 3. Settings file
                    # 4. Fallback to localhost
                    base_url = None
                    
                    if request:
                        # Build URL from request (works for mobile accessing via network IP)
                        scheme = 'https' if request.is_secure() else 'http'
                        host = request.get_host()
                        base_url = f"{scheme}://{host}"
                    
                    if not base_url:
                        base_url = os.environ.get('BASE_URL') or getattr(settings, 'BASE_URL', 'http://127.0.0.1:8000')
                    
                    # Avoid double slashes when concatenating
                    if base_url.endswith('/') and str(url).startswith('/'):
                        return f"{base_url[:-1]}{url}"
                    return f"{base_url}{url}"
            except Exception:
                # If anything goes wrong, return the relative URL as a fallback
                return url

            return url
    except Exception:
        pass
    # Return empty string instead of None for consistency
    return ""

def build_image_url(image_field, request=None):
    """Build full URL for ContentImage fields"""
    try:
        if image_field and hasattr(image_field, 'url'):
            url = image_field.url
            print(f'build_image_url - original URL: {url}')
            # If it's already a full URL, return as is
            if url.startswith('http'):
                print(f'build_image_url - already full URL: {url}')
                return url
            # If it's a relative URL, prepend the base URL
            from django.conf import settings
            
            # Try to get the base URL from the request if available
            if request:
                # Get the host from the request
                host = request.get_host()
                scheme = 'https' if request.is_secure() else 'http'
                base_url = f"{scheme}://{host}"
                print(f'build_image_url - using request host: {base_url}')
            else:
                # Fallback to settings or default ngrok URL
                base_url = getattr(settings, 'BASE_URL', 'https://sweaty-salma-catoptrical.ngrok-free.dev')
                print(f'build_image_url - using settings/fallback: {base_url}')
            
            full_url = f"{base_url}{url}"
            print(f'build_image_url - built full URL: {full_url}')
            return full_url
    except Exception as e:
        print(f'build_image_url - error: {e}')
        pass
    return ""

# Utility: extract current user from Authorization header (Bearer/JWT) robustly
def get_current_user_from_request(request):
    auth_header = request.headers.get('Authorization') or request.META.get('HTTP_AUTHORIZATION')
    if not auth_header:
        return None
    try:
        parts = auth_header.strip().split()
        token = None
        if len(parts) == 2:
            # Format: "Bearer <token>" or "JWT <token>"
            token = parts[1].strip('"')
        else:
            # Sometimes the raw token may be provided
            token = parts[0].strip('"')
        if not token:
            return None
        from rest_framework_simplejwt.tokens import AccessToken
        access_token = AccessToken(token)
        current_user_id = access_token.get('user_id') or access_token.get('id')
        if not current_user_id:
            return None
        return User.objects.get(user_id=int(current_user_id))
    except Exception:
        return None

# Note: Passwords must be provided as plaintext credentials. Legacy birthdate-based
# login has been removed. All authentication uses securely hashed passwords.

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def login_view(request):
    """Used by Mobile (legacy) – mobile prefers POST /api/token/ for JWT."""
    """
    Authenticate a user using acc_username and acc_password. Returns user info and account type on success.
    """
    if request.method == "OPTIONS":
        response = JsonResponse({'detail': 'OK'})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken"
        return response
    try:
        data = json.loads(request.body)
        acc_username = data.get('acc_username')
        acc_password = data.get('acc_password')
        if not acc_username or not acc_password:
            return JsonResponse({'success': False, 'message': 'Missing credentials'}, status=400)
        try:
            user = User.objects.get(acc_username=acc_username)
        except User.DoesNotExist:
            logger.warning(f"Login failed: user {acc_username} does not exist.")
            return JsonResponse({'success': False, 'message': 'Invalid credentials'}, status=401)
        if not user.check_password(acc_password):
            logger.warning(f"Login failed: invalid password for user {acc_username}.")
            return JsonResponse({'success': False, 'message': 'Invalid credentials'}, status=401)
        academic = getattr(user, 'academic_info', None)
        profile = getattr(user, 'profile', None)
        return JsonResponse({
            'success': True,
            'message': 'Login successful',
            'user': {
                'id': user.user_id,
                'username': user.acc_username,  # Add username for coordinator identification
                'name': f"{user.f_name} {user.m_name or ''} {user.l_name}".strip(),
                'year_graduated': getattr(academic, 'year_graduated', None) if academic else None,
                'profile_bio': getattr(profile, 'profile_bio', None) if profile else None,
                'profile_pic': build_profile_pic_url(user),
                'account_type': {
                    'admin': user.account_type.admin,
                    'peso': user.account_type.peso,
                    'user': user.account_type.user,
                    'coordinator': user.account_type.coordinator,
                    'ojt': user.account_type.ojt,
                }
            }
        })
    except json.JSONDecodeError:
        logger.error("Login failed: Invalid JSON in request body.")
        return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Login failed: Unexpected error: {e}")
        return JsonResponse({'success': False, 'message': 'Server error'}, status=500)

class CustomTokenObtainPairSerializer(serializers.Serializer):
    """Used by Mobile – issues JWT pair on /api/token/ for acc_username+acc_password."""
    acc_username = serializers.CharField()
    acc_password = serializers.CharField()

    def validate(self, attrs):
        acc_username = attrs.get('acc_username', '').strip()
        acc_password = attrs.get('acc_password', '').strip()
        
        if not acc_username:
            raise serializers.ValidationError('Username is required')
        if not acc_password:
            raise serializers.ValidationError('Password is required')
            
        try:
            user = User.objects.get(acc_username=acc_username)
        except User.DoesNotExist:
            raise serializers.ValidationError('Invalid credentials')

        # Hashed password only
        if not user.check_password(acc_password):
            raise serializers.ValidationError('Invalid credentials')
        refresh = RefreshToken.for_user(user)
        # Determine if the user must change password on first login
        must_change_password = False
        try:
            initial = getattr(user, 'initial_password', None)
            if initial and getattr(initial, 'is_active', False):
                must_change_password = True
        except Exception:
            must_change_password = False
        academic = getattr(user, 'academic_info', None)
        profile = getattr(user, 'profile', None)
        
        # Get follower and following counts (optimized - only if needed)
        followers_count = 0
        following_count = 0
        try:
            # Only fetch counts if user is not admin (admins don't need social counts)
            if not user.account_type.admin:
                from apps.shared.models import Follow
                followers_count = Follow.objects.filter(following=user).count()
                following_count = Follow.objects.filter(follower=user).count()
        except Exception:
            # Fallback to 0 if there are database issues
            followers_count = 0
            following_count = 0
        
        data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': user.user_id,
                'username': user.acc_username,  # Add username for coordinator identification
                'name': f"{user.f_name} {user.m_name or ''} {user.l_name}".strip(),
                'f_name': user.f_name,
                'l_name': user.l_name,
                'acc_username': user.acc_username,  # Keep for backwards compatibility
                'year_graduated': getattr(academic, 'year_graduated', None) if academic else None,
                'profile_bio': getattr(profile, 'profile_bio', None) if profile else None,
                'profile_pic': build_profile_pic_url(user),
                'followers_count': followers_count,
                'following_count': following_count,
                'account_type': {
                    'admin': user.account_type.admin,
                    'peso': user.account_type.peso,
                    'user': user.account_type.user,
                    'coordinator': user.account_type.coordinator,
                    'ojt': user.account_type.ojt,
                }
            },
            'must_change_password': must_change_password,
        }
        return data

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


# ---- Password management ----
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError


@api_view(["POST"]) 
@permission_classes([IsAuthenticated])
def change_password_view(request):
    """Allow authenticated users to change their password securely.

    Request JSON: { "old_password": str, "new_password": str }
    Returns: { success: bool, message: str }
    Also deactivates any active UserInitialPassword record.
    """
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)

    old_password = (data.get('old_password') or '').strip()
    new_password = (data.get('new_password') or '').strip()

    if not old_password or not new_password:
        return JsonResponse({'success': False, 'message': 'Both old and new passwords are required.'}, status=400)

    user = get_current_user_from_request(request)
    if not user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=401)

    if not user.check_password(old_password):
        return JsonResponse({'success': False, 'message': 'Old password is incorrect.'}, status=400)

    # Enforce strong password via Django validators and custom rules
    try:
        validate_password(new_password)
        # Additional custom rules (at least 16 chars, one upper, one lower, one digit, one symbol)
        import re
        if len(new_password) < 16:
            raise DjangoValidationError('Password must be at least 16 characters long.')
        if not re.search(r"[A-Z]", new_password):
            raise DjangoValidationError('Password must contain an uppercase letter.')
        if not re.search(r"[a-z]", new_password):
            raise DjangoValidationError('Password must contain a lowercase letter.')
        if not re.search(r"\d", new_password):
            raise DjangoValidationError('Password must contain a number.')
        if not re.search(r"[^A-Za-z0-9]", new_password):
            raise DjangoValidationError('Password must contain a special character.')
    except DjangoValidationError as e:
        message = '; '.join([str(m) for m in (e.messages if hasattr(e, 'messages') else [str(e)])])
        return JsonResponse({'success': False, 'message': message}, status=400)

    # Save new password
    user.set_password(new_password)
    user.save(update_fields=['acc_password', 'updated_at'])

    # Deactivate initial password record if present
    try:
        initial = getattr(user, 'initial_password', None)
        if initial:
            initial.is_active = False
            initial.save(update_fields=['is_active'])
    except Exception:
        pass

    return JsonResponse({'success': True, 'message': 'Password changed successfully.'})
@api_view(["POST"])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
@csrf_exempt
def import_alumni_view(request):
    if request.method == "OPTIONS":
        response = JsonResponse({'detail': 'OK'})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken"
        return response

    try:
        if 'file' not in request.FILES:
            return JsonResponse({'success': False, 'message': 'No file uploaded'}, status=400)
        file = request.FILES['file']
        batch_year_param = request.POST.get('batch_year', '')
        course_param = request.POST.get('course', '') or request.POST.get('program', '')
        if not file.name.endswith(('.xlsx', '.xls')):
            return JsonResponse({'success': False, 'message': 'Please upload an Excel file (.xlsx or .xls)'}, status=400)
        
        # Read Excel file first to check if it has Year_Graduated and Program columns
        try:
            df = pd.read_excel(file)
            print('HEADERS (before normalization):', list(df.columns))
            
            # Normalize column names by stripping whitespace FIRST
            df.columns = df.columns.str.strip()
            print('HEADERS (after normalization):', list(df.columns))
            
            # Check if Excel has Year_Graduated and Program columns (exported format)
            has_year_column = 'Year_Graduated' in df.columns or 'Batch Graduated' in df.columns
            has_program_column = 'Program' in df.columns or 'Course' in df.columns
            
            # If Excel doesn't have these columns, require form parameters
            if not has_year_column and not has_program_column:
                if not batch_year_param or not course_param:
                    return JsonResponse({'success': False, 'message': 'Batch year and course are required'}, status=400)
            
            # Check if Birthdate column exists before trying to access it
            if 'Birthdate' in df.columns:
                print('DEBUG: Raw birthdate column first 5 rows:')
                print(df['Birthdate'].head())
                print('DEBUG: Birthdate column data types:', df['Birthdate'].dtype)
                
                # Now try to convert birthdate column to proper dates
                try:
                    df['Birthdate'] = pd.to_datetime(df['Birthdate'], errors='coerce')
                    print('DEBUG: After pd.to_datetime conversion:')
                    print(df['Birthdate'].head())
                except Exception as e:
                    print(f"DEBUG: Error converting dates: {e}")
            else:
                print('DEBUG: No Birthdate column found in Excel file')

        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error reading Excel file: {str(e)}'}, status=400)
        
        # Expected columns: keep Birthdate for profile; use Password for login
        required_columns = ['CTU_ID', 'First_Name', 'Last_Name', 'Gender']
        optional_columns = ['Password', 'Birthdate', 'Phone_Number', 'Address', 'Civil Status', 'Social Media']
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return JsonResponse({
                'success': False,
                'message': f'Missing required columns: {", ".join(missing_columns)}'
            }, status=400)
        
        # Get alumni account type (user=True) - ensure AccountType is properly imported
        # Get or create alumni account type to avoid failures when it's missing
        from apps.shared.models import AccountType
        alumni_account_type, _ = AccountType.objects.get_or_create(
            user=True,
            admin=False,
            peso=False,
            coordinator=False,
            ojt=False,
        )
        
        created_count = 0
        skipped_count = 0
        errors = []
        exported_passwords = []  # List to collect (username, password) for export
        
        # Ensure an OJT account type exists; create if missing to avoid failures on fresh DBs
        try:
            ojt_account_type, _ = AccountType.objects.get_or_create(
                ojt=True, admin=False, peso=False, user=False, coordinator=False
            )
        except Exception:
            ojt_account_type = None

        for index, row in df.iterrows():
            try:
                ctu_id = str(row['CTU_ID']).strip()
                first_name = str(row['First_Name']).strip()
                middle_name = str(row.get('Middle_Name', '')).strip() if pd.notna(row.get('Middle_Name')) else ''
                last_name = str(row.get('Last_Nam', row.get('Last_Name', ''))).strip()
                gender = str(row['Gender']).strip().upper()
                password_raw = str(row.get('Password', '')).strip()
                birthdate_val = row.get('Birthdate') if 'Birthdate' in df.columns else None

                print(f"DEBUG: Row {index + 2} - CTU_ID: {ctu_id}, Name: {first_name} {last_name}")
                phone_number = str(row.get('Phone_Number', '')).strip() if pd.notna(row.get('Phone_Number')) else ''
                address = str(row.get('Address', '')).strip() if pd.notna(row.get('Address')) else ''
                civil_status = str(row.get('Civil Status', '')).strip() if pd.notna(row.get('Civil Status', '')) else ''
                social_media = str(row.get('Social Media', '')).strip() if pd.notna(row.get('Social Media', '')) else ''
                
                # Determine batch_year and course: use row values if available, else form parameters
                # Initialize batch_year with default value to prevent scope errors
                batch_year = batch_year_param
                
                if has_year_column:
                    # Check for 'Year_Graduated' first, then 'Batch Graduated'
                    if 'Year_Graduated' in df.columns and pd.notna(row.get('Year_Graduated')):
                        batch_year = str(int(row['Year_Graduated'])) if isinstance(row['Year_Graduated'], (int, float)) else str(row['Year_Graduated']).strip()
                    elif 'Batch Graduated' in df.columns and pd.notna(row.get('Batch Graduated')):
                        batch_year = str(int(row['Batch Graduated'])) if isinstance(row['Batch Graduated'], (int, float)) else str(row['Batch Graduated']).strip()
                
                # Initialize course with default value to prevent scope errors
                course = course_param
                
                if has_program_column:
                    if 'Program' in df.columns and pd.notna(row.get('Program')):
                        course = str(row['Program']).strip()
                    # Legacy support for Course column (will be removed)
                    elif 'Course' in df.columns and pd.notna(row.get('Course')):
                        course = str(row['Course']).strip()
                
                # Get section if available in Excel
                section = str(row.get('Section', '')).strip() if 'Section' in df.columns and pd.notna(row.get('Section')) else ''
                
                print(f"DEBUG: Extracted values - batch_year: '{batch_year}', course: '{course}', gender: '{gender}'")
                
                # Validate required fields
                if not ctu_id or not first_name or not last_name or not gender:
                    print(f"DEBUG: Validation failed - missing required fields: ctu_id='{ctu_id}', first_name='{first_name}', last_name='{last_name}', gender='{gender}'")
                    errors.append(f"Row {index + 2}: Missing required fields (CTU_ID, First_Name, Last_Name, Gender)")
                    continue
                
                # Validate batch_year and course for this row
                if not batch_year:
                    print(f"DEBUG: Validation failed - missing batch_year: '{batch_year}'")
                    errors.append(f"Row {index + 2}: Missing Year_Graduated/Batch Year")
                    continue
                if not course:
                    print(f"DEBUG: Validation failed - missing course: '{course}'")
                    errors.append(f"Row {index + 2}: Missing Program")
                    continue
                
                # Validate gender
                if gender not in ['M', 'F']:
                    print(f"DEBUG: Validation failed - invalid gender: '{gender}'")
                    errors.append(f"Row {index + 2}: Gender must be 'M' or 'F'")
                    continue
                
                print(f"DEBUG: All validations passed for row {index + 2}")
                
                # Determine password: use provided Password column or auto-generate
                if not password_raw:
                    alphabet = string.ascii_letters + string.digits
                    password_raw = ''.join(secrets.choice(alphabet) for _ in range(12))
                
                # Check if user already exists
                if User.objects.filter(acc_username=ctu_id).exists():
                    errors.append(f"Row {index + 2}: CTU ID {ctu_id} already exists (skipped)")
                    skipped_count += 1
                    continue
                
                # Create user and related models securely
                print(f"DEBUG: Creating user {ctu_id} - {first_name} {last_name}")
                user = User.objects.create(
                    acc_username=ctu_id,
                    user_status='active',
                    f_name=first_name,
                    m_name=middle_name,
                    l_name=last_name,
                    gender=gender,
                    account_type=alumni_account_type,
                )
                user.set_password(password_raw)
                user.save()
                print(f"DEBUG: Successfully created user {ctu_id}")
                
                # Store initial password (encrypted) for export/sharing
                # Set is_active=True so users get forced to change password on first login
                ensure_initial_password_active(user, raw_password=password_raw, allow_create=True)
                
                # CRITICAL: Count user creation immediately after successful user creation
                # This ensures accurate count even if related model creation fails
                created_count += 1
                exported_passwords.append({
                    'CTU_ID': ctu_id,
                    'First_Name': first_name,
                    'Last_Name': last_name,
                    'Password': password_raw
                })
                
                # Set profile including birthdate if provided
                profile_kwargs = dict(
                    user=user,
                    phone_num=phone_number or None,
                    address=address or None,
                    civil_status=civil_status or None,
                    social_media=social_media or None,
                )
                
                # Parse birthdate if present
                if birthdate_val and pd.notna(birthdate_val):
                    try:
                        bd = pd.to_datetime(birthdate_val, errors='coerce').date()
                        if bd:
                            profile_kwargs['birthdate'] = bd
                    except Exception as e:
                        print(f"DEBUG: Error parsing birthdate for {ctu_id}: {e}")
                
                try:
                    from apps.shared.models import UserProfile, AcademicInfo, TrackerData, EmploymentHistory
                    UserProfile.objects.create(**profile_kwargs)
                    
                    # Extract academic info from Excel columns
                    academic_kwargs = {
                        'user': user,
                        'year_graduated': int(batch_year) if batch_year.isdigit() else None,
                        'program': course,  # Use 'program' field, not 'course'
                        'section': section,  # Add section from form parameter
                    }
                    
                    # Post graduate degree and further study detection
                    if 'Please specify post graduate/degree.' in df.columns and pd.notna(row.get('Please specify post graduate/degree.')):
                        degree = str(row['Please specify post graduate/degree.']).strip()
                        if degree and degree.lower() not in ['n/a', 'na', '']:
                            academic_kwargs['q_post_graduate_degree'] = degree
                            # If there's a post-graduate degree, they're pursuing further study
                            academic_kwargs['pursue_further_study'] = 'yes'
                            academic_kwargs['q_pursue_study'] = 'yes'
                    
                    AcademicInfo.objects.create(**academic_kwargs)
                    # Extract all tracker data from Excel columns
                    tracker_data_kwargs = {
                        'user': user,
                        'tracker_submitted_at': timezone.now()
                    }
                    
                    # Employment status
                    if 'Are you PRESENTLY employed?' in df.columns and pd.notna(row.get('Are you PRESENTLY employed?')):
                        emp_response = str(row['Are you PRESENTLY employed?']).strip().lower()
                        if emp_response in ['yes', 'y']:
                            tracker_data_kwargs['q_employment_status'] = 'yes'
                        elif emp_response in ['no', 'n']:
                            tracker_data_kwargs['q_employment_status'] = 'no'
                        else:
                            tracker_data_kwargs['q_employment_status'] = 'pending'
                    else:
                        tracker_data_kwargs['q_employment_status'] = 'pending'
                    
                    # Company name
                    if 'Current Company Name' in df.columns and pd.notna(row.get('Current Company Name')):
                        company_name = str(row['Current Company Name']).strip()
                        if company_name and company_name.lower() not in ['n/a', 'na', '']:
                            tracker_data_kwargs['q_company_name'] = company_name
                    
                    # Current position
                    if 'Current Position' in df.columns and pd.notna(row.get('Current Position')):
                        position = str(row['Current Position']).strip()
                        if position and position.lower() not in ['n/a', 'na', '']:
                            tracker_data_kwargs['q_current_position'] = position
                    
                    # Job sector (Public/Private) - normalize for statistics
                    if 'Current Sector of your Job' in df.columns and pd.notna(row.get('Current Sector of your Job')):
                        sector = str(row['Current Sector of your Job']).strip()
                        if sector and sector.lower() not in ['n/a', 'na', '']:
                            # Normalize sector values for statistics queries
                            sector_lower = sector.lower()
                            if sector_lower in ['government', 'public']:
                                tracker_data_kwargs['q_sector_current'] = 'government'
                            elif sector_lower == 'private':
                                tracker_data_kwargs['q_sector_current'] = 'private'
                            else:
                                tracker_data_kwargs['q_sector_current'] = sector
                    
                    # Salary range
                    if 'Current Salary Range' in df.columns and pd.notna(row.get('Current Salary Range')):
                        salary_range = str(row['Current Salary Range']).strip()
                        if salary_range and salary_range.lower() not in ['n/a', 'na', '']:
                            tracker_data_kwargs['q_salary_range'] = salary_range
                    
                    # Employment type (for self-employment detection)
                    if 'Current Company Name' in df.columns and pd.notna(row.get('Current Company Name')):
                        company_name = str(row['Current Company Name']).strip()
                        if company_name and company_name.lower() not in ['n/a', 'na', '']:
                            # Check if it's self-employment based on company name patterns
                            company_lower = company_name.lower()
                            if any(keyword in company_lower for keyword in ['self', 'freelance', 'independent', 'own', 'personal']):
                                tracker_data_kwargs['q_employment_type'] = 'self-employed'
                            else:
                                tracker_data_kwargs['q_employment_type'] = 'employed by company'
                    
                    # Create TrackerData record with all extracted data
                    TrackerData.objects.create(**tracker_data_kwargs)
                    
                    # Create EmploymentHistory record for statistics (CHED, SUC, AACUP)
                    employment_kwargs = {
                        'user': user,
                        'job_alignment_status': 'not_aligned',  # Default
                        'self_employed': False,  # Default
                        'high_position': False,  # Default
                        'absorbed': False,  # Default
                    }
                    
                    # Map TrackerData fields to EmploymentHistory fields
                    if 'Current Company Name' in df.columns and pd.notna(row.get('Current Company Name')):
                        company_name = str(row['Current Company Name']).strip()
                        if company_name and company_name.lower() not in ['n/a', 'na', '']:
                            employment_kwargs['company_name_current'] = company_name
                    
                    if 'Current Position' in df.columns and pd.notna(row.get('Current Position')):
                        position = str(row['Current Position']).strip()
                        if position and position.lower() not in ['n/a', 'na', '']:
                            employment_kwargs['position_current'] = position
                    
                    if 'Current Sector of your Job' in df.columns and pd.notna(row.get('Current Sector of your Job')):
                        sector = str(row['Current Sector of your Job']).strip()
                        if sector and sector.lower() not in ['n/a', 'na', '']:
                            # Use the same normalization as TrackerData
                            sector_lower = sector.lower()
                            if sector_lower in ['government', 'public']:
                                employment_kwargs['sector_current'] = 'government'
                            elif sector_lower == 'private':
                                employment_kwargs['sector_current'] = 'private'
                            else:
                                employment_kwargs['sector_current'] = sector
                    
                    if 'Current Salary Range' in df.columns and pd.notna(row.get('Current Salary Range')):
                        salary_range = str(row['Current Salary Range']).strip()
                        if salary_range and salary_range.lower() not in ['n/a', 'na', '']:
                            employment_kwargs['salary_current'] = salary_range
                    
                    # Determine job alignment based on employment status and position
                    if tracker_data_kwargs.get('q_employment_status') == 'yes':
                        if employment_kwargs.get('position_current'):
                            # Check for high position keywords
                            position_lower = employment_kwargs['position_current'].lower()
                            if any(keyword in position_lower for keyword in ['manager', 'supervisor', 'director', 'lead', 'senior']):
                                employment_kwargs['high_position'] = True
                            
                            # Set self-employment status based on TrackerData
                            if tracker_data_kwargs.get('q_employment_type') == 'self-employed':
                                employment_kwargs['self_employed'] = True
                            
                            # Set absorbed status (typically first job after graduation)
                            # For imported data, leave absorbed as False for now
                            employment_kwargs['absorbed'] = False

                            # Proper job alignment logic - compare position with program
                            employment_record = EmploymentHistory(**employment_kwargs)
                            employment_record.user = user

                            # Try exact match first
                            alignment_result = employment_record._check_job_alignment_for_position(
                                employment_kwargs['position_current'], 
                                course  # Program from Excel
                            )

                            # If no exact match, try fuzzy matching for common IT positions
                            if employment_record.job_alignment_status == 'pending_user_confirmation':
                                position_lower = employment_kwargs['position_current'].lower()
                                course_lower = course.lower() if course else ''

                                # Common IT position keywords for each program
                                bsit_keywords = ['software', 'developer', 'programmer', 'web', 'mobile', 'app', 'system', 'network', 'database', 'tech', 'it']
                                bsis_keywords = ['analyst', 'system', 'business', 'data', 'process', 'workflow', 'management', 'admin']
                                bit_ct_keywords = ['hardware', 'technician', 'repair', 'maintenance', 'support', 'technical', 'engineering']

                                is_aligned = False
                                if 'bsit' in course_lower or 'information technology' in course_lower:
                                    is_aligned = any(keyword in position_lower for keyword in bsit_keywords)
                                    if is_aligned:
                                        employment_record.job_alignment_status = 'aligned'
                                        employment_record.job_alignment_category = 'BSIT'
                                elif 'bsis' in course_lower or 'information system' in course_lower:
                                    is_aligned = any(keyword in position_lower for keyword in bsis_keywords)
                                    if is_aligned:
                                        employment_record.job_alignment_status = 'aligned'
                                        employment_record.job_alignment_category = 'BSIS'
                                elif 'bit-ct' in course_lower or 'computer technology' in course_lower:
                                    is_aligned = any(keyword in position_lower for keyword in bit_ct_keywords)
                                    if is_aligned:
                                        employment_record.job_alignment_status = 'aligned'
                                        employment_record.job_alignment_category = 'BIT-CT'

                            # Update kwargs from calculated alignment
                            employment_kwargs['job_alignment_status'] = employment_record.job_alignment_status
                            employment_kwargs['job_alignment_category'] = employment_record.job_alignment_category
                            employment_kwargs['job_alignment_title'] = employment_record.job_alignment_title
                    else:
                        # For basic info imports (no employment data), they should be pending
                        # Don't set absorbed=True for basic imports
                        employment_kwargs['absorbed'] = False
                    
                    EmploymentHistory.objects.create(**employment_kwargs)
                    
                except Exception as e:
                    print(f"DEBUG: Error creating profile/academic info for {ctu_id}: {e}")
                    # User was already created and counted, so we continue
            except Exception as e:
                errors.append(f"Row {index + 2}: Unexpected error: {str(e)}")
                print(f"DEBUG: Error processing row {index + 2}: {e}")
                import traceback
                print(f"DEBUG: Full traceback: {traceback.format_exc()}")
                continue
        # Invalidate statistics cache after successful import
        try:
            from apps.alumni_stats.decorators import invalidate_statistics_cache
            invalidate_statistics_cache()
            print("DEBUG: Statistics cache invalidated after import")
        except Exception as e:
            print(f"DEBUG: Error invalidating cache: {e}")
        
        # Export passwords to Excel after import
        if exported_passwords:
            df_export = pd.DataFrame(exported_passwords)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
                df_export.to_excel(tmp.name, index=False)
                tmp.seek(0)
                response = FileResponse(open(tmp.name, 'rb'), as_attachment=True, filename='alumni_passwords.xlsx')
                # Add a comment: Only share this file securely with the intended users.
                return response
        return JsonResponse({
            'success': True,
            'message': f'Successfully created {created_count} alumni accounts. Skipped {skipped_count} duplicates.',
            'created_count': created_count,
            'skipped_count': skipped_count,
            'errors': errors
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Server error: {str(e)}'}, status=500)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def alumni_statistics_view(request):
    """Comprehensive alumni statistics including employment status counts and available years."""
    try:
        year = request.GET.get('year')
        course = request.GET.get('program')
        
        # OPTIMIZED: Add select_related() for performance
        alumni_qs = User.objects.filter(account_type__user=True).select_related(
            'academic_info', 'employment', 'tracker_data'
        )
        
        if year and year != 'ALL':
            alumni_qs = alumni_qs.filter(academic_info__year_graduated=year)
        if course and course != 'ALL':
            alumni_qs = alumni_qs.filter(academic_info__program=course)

        total_alumni = alumni_qs.count()

        # OPTIMIZED: Use database aggregation instead of Python loops
        from apps.shared.models import TrackerData, EmploymentHistory
        from django.db.models import Q, Count, Case, When, IntegerField
        
        # Count employment status using database aggregation
        employment_stats = TrackerData.objects.filter(user__in=alumni_qs).aggregate(
            employed=Count('id', filter=Q(q_employment_status__iexact='yes')),
            unemployed=Count('id', filter=Q(q_employment_status__iexact='no')),
            pending_tracker=Count(
                'id',
                filter=(
                    Q(q_employment_status__isnull=True)
                    | Q(q_employment_status='')
                    | Q(q_employment_status__iexact='pending')
                    | Q(q_employment_status__iexact='untracked')
                    | Q(q_employment_status__iexact='n/a')
                    | Q(q_employment_status__iexact='na')
                ),
            ),
        )
        employed = employment_stats['employed']
        unemployed = employment_stats['unemployed']
        pending_tracker = employment_stats['pending_tracker']

        # Count absorbed users (who are also employed)
        absorbed = EmploymentHistory.objects.filter(user__in=alumni_qs, absorbed=True).count()
        
        # Count self-employed users
        self_employed = EmploymentHistory.objects.filter(user__in=alumni_qs, self_employed=True).count()
        
        # Alumni without TrackerData are also considered pending
        alumni_without_tracker = alumni_qs.filter(tracker_data__isnull=True).count()
        
        # Total pending = alumni without tracker + alumni with tracker but no employment status
        pending = pending_tracker + alumni_without_tracker

        # NEW LOGIC: Combine employed and absorbed, but keep track of absorbed count for indicator
        status_counts = {
            'Employed': employed,  # This includes both employed and absorbed
            'Unemployed': unemployed,
            'Self-Employed': self_employed,
            'Pending': pending,
            'Absorbed_Count': absorbed,  # Keep track of absorbed count for frontend indicator
        }

        # Count by year_graduated from AcademicInfo for alumni users (safe even if some lack AcademicInfo)
        year_values = (
            User.objects
            .filter(account_type__user=True)
            .values_list('academic_info__year_graduated', flat=True)
        )
        year_counts = Counter([y for y in year_values if y is not None])
        
        return JsonResponse({
            'success': True,
            'status_counts': status_counts,
            'years': [
                {'year': year, 'count': count}
                for year, count in sorted(year_counts.items(), reverse=True)
            ]
        })
    except Exception as e:
        logger.error(f"Error in alumni_statistics_view: {e}")
        return JsonResponse({'success': False, 'message': 'Failed to load alumni statistics'}, status=500)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def graduation_years_view(request):
    """Get all unique graduation years from alumni data for dropdowns"""
    year_values = (
        User.objects
        .filter(account_type__user=True)
        .values_list('academic_info__year_graduated', flat=True)
        .distinct()
    )
    years = [str(year) for year in sorted(year_values, reverse=True) if year is not None]
    return JsonResponse({
        'success': True,
        'years': years
    })

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def alumni_list_view(request):
    alumni = User.objects.filter(account_type__user=True)
    alumni_data = [
        {
            'id': a.user_id,
            'ctu_id': a.acc_username,
            'name': f"{a.f_name} {a.m_name or ''} {a.l_name}",
            'program': getattr(a.academic_info, 'program', None) if hasattr(a, 'academic_info') else None,
            'batch': getattr(a.academic_info, 'year_graduated', None) if hasattr(a, 'academic_info') else None,
            'status': a.user_status,
            'gender': a.gender,
            'birthdate': str(getattr(a.profile, 'birthdate', None)) if hasattr(a, 'profile') and getattr(a, 'profile', None) else None,
            'phone': getattr(a.profile, 'phone_num', None) if hasattr(a, 'profile') and getattr(a, 'profile', None) else None,
            'address': getattr(a.profile, 'address', None) if hasattr(a, 'profile') and getattr(a, 'profile', None) else None,
            'civilStatus': getattr(a.profile, 'civil_status', None) if hasattr(a, 'profile') and getattr(a, 'profile', None) else None,
            'socialMedia': getattr(a.profile, 'social_media', None) if hasattr(a, 'profile') and getattr(a, 'profile', None) else None,
            'profile_pic': build_profile_pic_url(a),
        }
        for a in alumni
    ]
    return JsonResponse({'success': True, 'alumni': alumni_data})

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def send_reminder_view(request):
    import json
    data = json.loads(request.body)
    emails = data.get('emails', [])
    user_ids = data.get('user_ids', [])
    message = data.get('message', '')
    subject = data.get('subject', 'Tracker Form Reminder')
    # Try to get sender name from request.user if authenticated, else fallback
    sender = 'CCICT'  # Always use CCICT as sender for tracker form notifications
    if not (emails or user_ids) or not message:
        return JsonResponse({'success': False, 'message': 'Missing users or message'}, status=400)
    sent = 0
    # Resolve recipients: prefer user_ids; if emails provided, match via related profile.email
    if user_ids:
        users = list(User.objects.filter(user_id__in=user_ids))
    elif emails:
        # Many deployments store email on UserProfile, not User
        try:
            users = list(User.objects.filter(profile__email__in=emails).select_related('profile'))
        except Exception:
            users = list(User.objects.none())
    else:
        users = []
    tracker_form_base_url = "https://yourdomain.com/tracker/fill"  # Change to your actual domain/path
    for user in users:
        try:
            personalized_message = message.replace('[User\'s Name]', f"{user.f_name} {user.l_name}")
            user_link = f"{tracker_form_base_url}?user={user.user_id}"
            personalized_message = personalized_message.replace('[Tracker Form Link]', user_link)
            notification = Notification.objects.create(
                user=user,
                notif_type=sender,
                notifi_content=personalized_message,
                notif_date=timezone.now(),
                subject=subject
            )
            
            # Broadcast notification in real-time
            try:
                from apps.messaging.notification_broadcaster import broadcast_notification
                broadcast_notification(notification)
            except Exception as e:
                logger.error(f"Error broadcasting tracker reminder notification: {e}")
            sent += 1
        except Exception as e:
            continue
    return JsonResponse({'success': True, 'sent': sent, 'total': len(users)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def send_email_reminder_view(request):
    """
    Send tracker form reminders via email to selected users.
    
    Expected payload:
    {
        "user_ids": [1, 2, 3],
        "message": "HTML formatted message with [User's Name] placeholder",
        "subject": "Email subject",
        "tracker_link_base": "https://domain.com"
    }
    """
    try:
        data = json.loads(request.body)
        user_ids = data.get('user_ids', [])
        message = data.get('message', '')
        subject = data.get('subject', 'CTU Alumni Tracker Form Reminder')
        tracker_link_base = data.get('tracker_link_base', '')
        
        # Validation
        if not user_ids:
            return JsonResponse({
                'success': False, 
                'message': 'No users selected'
            }, status=400)
        
        if not message:
            return JsonResponse({
                'success': False, 
                'message': 'Message content is required'
            }, status=400)
            
        if not tracker_link_base:
            return JsonResponse({
                'success': False, 
                'message': 'Tracker link base URL is required'
            }, status=400)
        
        # Check if email is configured
        if not hasattr(settings, 'EMAIL_HOST') or not settings.EMAIL_HOST:
            return JsonResponse({
                'success': False,
                'message': 'Email is not configured on the server. Please contact the administrator.'
            }, status=500)
        
        # Fetch users with their profiles
        users = User.objects.filter(
            user_id__in=user_ids
        ).select_related('profile')
        
        sent_count = 0
        failed_count = 0
        no_email_count = 0
        errors = []
        
        for user in users:
            try:
                # Check if user has a profile with email
                if not hasattr(user, 'profile') or not user.profile:
                    no_email_count += 1
                    errors.append({
                        'user': f"{user.f_name} {user.l_name}",
                        'reason': 'No profile found'
                    })
                    continue
                
                user_email = user.profile.email
                if not user_email or user_email.strip() == '':
                    no_email_count += 1
                    errors.append({
                        'user': f"{user.f_name} {user.l_name}",
                        'reason': 'No email address'
                    })
                    continue
                
                # Personalize the message
                full_name = f"{user.f_name} {user.l_name}"
                personalized_message = message.replace('[User\'s Name]', full_name)
                
                # Generate tracker link
                tracker_link = f"{tracker_link_base}/alumni/tracker?user_id={user.user_id}"
                
                # Replace the tracker form link placeholder with actual clickable link
                personalized_message = personalized_message.replace(
                    '👉 Fill Out the Tracker Form',
                    f'<a href="{tracker_link}" style="color:#1e4c7a;font-weight:600;text-decoration:underline;">👉 Fill Out the Tracker Form</a>'
                )
                
                # Create HTML email with proper formatting
                html_message = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                </head>
                <body style="margin:0;padding:0;font-family:Arial,sans-serif;background-color:#f4f4f4;">
                    <div style="max-width:600px;margin:20px auto;background-color:#ffffff;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">
                        <div style="background-color:#1e4c7a;color:#ffffff;padding:20px;border-radius:8px 8px 0 0;text-align:center;">
                            <h1 style="margin:0;font-size:24px;">CTU Alumni Tracker Form</h1>
                        </div>
                        <div style="padding:30px;color:#333333;line-height:1.6;">
                            {personalized_message.replace(chr(10), '<br>')}
                        </div>
                        <div style="background-color:#f8f9fa;padding:20px;border-radius:0 0 8px 8px;text-align:center;font-size:12px;color:#666;">
                            <p style="margin:0;">This is an automated message from CTU CCICT Alumni Management System</p>
                            <p style="margin:5px 0 0 0;">Please do not reply to this email</p>
                        </div>
                    </div>
                </body>
                </html>
                """
                
                # Send email using Django's send_mail
                from django.core.mail import EmailMultiAlternatives
                
                email = EmailMultiAlternatives(
                    subject=subject,
                    body=personalized_message,  # Plain text fallback
                    from_email=settings.EMAIL_HOST_USER,
                    to=[user_email],
                )
                email.attach_alternative(html_message, "text/html")
                email.send(fail_silently=False)
                
                sent_count += 1
                logger.info(f"Email sent successfully to {full_name} ({user_email})")
                
            except Exception as e:
                failed_count += 1
                error_msg = str(e)
                logger.error(f"Failed to send email to {user.f_name} {user.l_name}: {error_msg}")
                errors.append({
                    'user': f"{user.f_name} {user.l_name}",
                    'reason': error_msg
                })
        
        # Prepare response
        response_data = {
            'success': sent_count > 0,
            'sent': sent_count,
            'failed': failed_count,
            'no_email': no_email_count,
            'total': len(user_ids)
        }
        
        if errors:
            response_data['errors'] = errors
        
        return JsonResponse(response_data)
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON payload'
        }, status=400)
    except Exception as e:
        logger.error(f"Error in send_email_reminder_view: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Server error: {str(e)}'
        }, status=500)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def notifications_view(request):
    user_id = request.GET.get('user_id')
    if not user_id:
        return JsonResponse({'success': False, 'message': 'user_id is required'}, status=400)
    try:
        user = User.objects.get(user_id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'User not found'}, status=404)
    # Role-based filtering:
    # - Admin: receive SAME notifications as alumni (reminders/thank-you/engagement)
    #          PLUS tracker submission notifications from users who answered the tracker.
    #          Therefore, do not exclude 'CCICT' (reminders/thank-you) for admins.
    # - Alumni/OJT/PESO: receive tracker reminders + thank you + like/comment/repost (hide admin-only tracker submissions)
    if getattr(user.account_type, 'admin', False):
        notifications = (
            Notification.objects
            .filter(user_id=user_id)
            .order_by('-notif_date')
        )
    else:
        notifications = (
            Notification.objects
            .filter(user_id=user_id)
            .exclude(notif_type__iexact='tracker_submission')
            .order_by('-notif_date')
        )
    notif_list = []
    import re
    print(f"🔔 DEBUG: Fetching notifications for user {user_id}, found {notifications.count()} notifications")
    for n in notifications:
        entry = {
            'id': n.notification_id,
            'type': n.notif_type,
            'subject': getattr(n, 'subject', None) or 'Tracker Form Reminder',
            'content': n.notifi_content,
            'date': n.notif_date.strftime('%Y-%m-%d %H:%M:%S'),
            'is_read': getattr(n, 'is_read', False),
        }
        print(f"🔔 DEBUG: Notification {n.notification_id}: {n.notif_type} - {n.notifi_content}")
        # Extract follower profile link if present (e.g., /alumni/profile/<id>)
        try:
            match = re.search(r"/alumni/profile/(\d+)", n.notifi_content or '')
            if match:
                follower_id = int(match.group(1))
                entry['link'] = f"/alumni/profile/{follower_id}"
                entry['link_user_id'] = follower_id
        except Exception:
            pass
        notif_list.append(entry)
    return JsonResponse({'success': True, 'notifications': notif_list})

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def notifications_count_view(request):
    user_id = request.GET.get('user_id')
    if not user_id:
        return JsonResponse({'success': False, 'message': 'user_id is required'}, status=400)
    try:
        user = User.objects.get(user_id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'User not found'}, status=404)

    # Count UNREAD notifications only, based on user type
    if hasattr(user.account_type, 'user') and user.account_type.user:
        count = Notification.objects.filter(user_id=user_id, is_read=False).count()
    elif hasattr(user.account_type, 'ojt') and user.account_type.ojt:
        count = Notification.objects.filter(user_id=user_id, is_read=False).exclude(notif_type__iexact='tracker').count()
    else:
        count = Notification.objects.filter(user_id=user_id, is_read=False).exclude(notif_type__iexact='tracker').count()

    return JsonResponse({'success': True, 'count': count})

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_notification_as_read(request):
    """Mark a notification as read"""
    notification_id = request.data.get('notification_id')
    if not notification_id:
        return JsonResponse({'success': False, 'message': 'notification_id is required'}, status=400)
    
    try:
        notification = Notification.objects.get(notification_id=notification_id)
        notification.is_read = True
        notification.save()
        return JsonResponse({'success': True, 'message': 'Notification marked as read'})
    except Notification.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Notification not found'}, status=404)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_all_notifications_as_read(request):
    """Mark all notifications as read for a user"""
    user_id = request.data.get('user_id')
    if not user_id:
        return JsonResponse({'success': False, 'message': 'user_id is required'}, status=400)
    
    try:
        user = User.objects.get(user_id=user_id)
        count = Notification.objects.filter(user_id=user_id, is_read=False).update(is_read=True)
        return JsonResponse({'success': True, 'message': f'{count} notifications marked as read', 'count': count})
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'User not found'}, status=404)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_peso_users_view(request):
    """Get admin and PESO users for dynamic ID resolution."""
    try:
        # Get admin users
        admin_users = User.objects.filter(account_type__admin=True).values_list('user_id', flat=True)
        # Get PESO users  
        peso_users = User.objects.filter(account_type__peso=True).values_list('user_id', flat=True)
        
        return JsonResponse({
            'success': True,
            'admin_user_ids': list(admin_users),
            'peso_user_ids': list(peso_users)
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def users_list_view(request):
    user = request.user
    # Allow any authenticated user to fetch suggested users
    current_user_id = request.GET.get('current_user_id')
    
    # If no current_user_id provided, use the authenticated user's ID
    if not current_user_id:
        current_user_id = str(user.user_id)
    
    try:
        # Parse current_user_id to int if possible for safety
        try:
            current_user_id_int = int(current_user_id) if current_user_id is not None else None
        except (TypeError, ValueError):
            current_user_id_int = None

        # Exclude admin users and the current logged-in user, randomize and limit
        users_qs = (
            User.objects
            .filter(account_type__admin=False)
            .select_related('profile', 'academic_info')
        )
        if current_user_id_int is not None:
            users_qs = users_qs.exclude(user_id=current_user_id_int)
        users = users_qs.order_by('?')[:10]
        users_data = []
        for u in users:
            try:
                users_data.append({
                    'id': u.user_id,
                    'name': f"{u.f_name} {u.m_name or ''} {u.l_name}".strip(),
                    'profile_pic': build_profile_pic_url(u),
                    'batch': getattr(u.academic_info, 'year_graduated', None) if u.academic_info else None,
                    'account_type': {
                        'admin': u.account_type.admin,
                        'peso': u.account_type.peso,
                        'user': u.account_type.user,
                        'coordinator': u.account_type.coordinator,
                        'ojt': u.account_type.ojt,
                    },
                })
            except Exception:
                continue
        return JsonResponse({'success': True, 'users': users_data})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def delete_notifications_view(request):
    import json
    try:
        data = json.loads(request.body)
        notif_ids = data.get('notification_ids', [])
        if not notif_ids:
            return JsonResponse({'success': False, 'message': 'No notification IDs provided'}, status=400)
        from apps.shared.models import Notification
        deleted, _ = Notification.objects.filter(notification_id__in=notif_ids).delete()
        return JsonResponse({'success': True, 'deleted': deleted})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)
# OJT-specific import function for coordinators
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def import_ojt_view(request):
    print("IMPORT OJT VIEW CALLED")  # Debug print
    if request.method == "OPTIONS":
        response = JsonResponse({'detail': 'OK'})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken"
        return response

    try:
        if 'file' not in request.FILES:
            return JsonResponse({'success': False, 'message': 'No file uploaded'}, status=400)

        file = request.FILES['file']
        batch_year = request.POST.get('batch_year', '')
        course = request.POST.get('program', '')
        coordinator_username = request.POST.get('coordinator_username', '')

        print(f"DEBUG - Form data received:")
        print(f"  batch_year: '{batch_year}'")
        print(f"  course: '{course}'")
        print(f"  coordinator_username: '{coordinator_username}'")

        if not file.name.endswith(('.xlsx', '.xls')):
            return JsonResponse({'success': False, 'message': 'Please upload an Excel file (.xlsx or .xls)'}, status=400)
        
        if not coordinator_username:
            return JsonResponse({'success': False, 'message': 'Missing coordinator username'}, status=400)
        
        # batch_year is now optional - will be auto-detected for second imports

        # Read Excel file
        try:
            df = pd.read_excel(file)
            print('OJT IMPORT - HEADERS:', list(df.columns))
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error reading Excel file: {str(e)}'}, status=400)

        # Auto-detect batch year: from existing user, Excel column, or current year + 1
        from datetime import datetime
        is_second_import = False
        auto_detected_year = None
        
        # Try 1: Check if users already exist (second import - highest priority)
        if df.shape[0] > 0:
            first_ctu_id = str(df.iloc[0].get('CTU_ID', '')).strip()
            if first_ctu_id:
                existing_user = User.objects.filter(acc_username=first_ctu_id).first()
                if existing_user and hasattr(existing_user, 'academic_info') and existing_user.academic_info:
                    is_second_import = True
                    auto_detected_year = existing_user.academic_info.year_graduated
                    print(f'🔍 SECOND IMPORT DETECTED! User {first_ctu_id} exists with year {auto_detected_year}')
        
        # Try 2: Check if Excel has Batch_Year column (optional override)
        if not auto_detected_year and 'Batch_Year' in df.columns and df.shape[0] > 0:
            excel_year = df.iloc[0].get('Batch_Year')
            if pd.notna(excel_year):
                try:
                    auto_detected_year = int(excel_year)
                    print(f'✓ Batch year detected from Excel Batch_Year column: {auto_detected_year}')
                except:
                    pass
        
        # Try 3: Use current year + 1 (default for new students)
        # Logic: If importing in 2025, students graduate in 2026
        if not auto_detected_year:
            current_year = datetime.now().year
            auto_detected_year = current_year + 1
            print(f'✓ Auto-calculated batch year: Current year ({current_year}) + 1 = {auto_detected_year}')
        
        # Set batch_year
        if not batch_year:
            batch_year = str(auto_detected_year)
            print(f'✓ Using batch year: {batch_year}')
        
        # Auto-detect sections from Excel file
        detected_sections = []
        if 'Section' in df.columns:
            detected_sections = df['Section'].dropna().astype(str).str.strip().unique().tolist()
            detected_sections = [s for s in detected_sections if s and s != '']
            print(f'OJT IMPORT - DETECTED SECTIONS FROM EXCEL: {detected_sections}')
        else:
            # If no Section column, try to detect from existing students (for second import)
            print(f'OJT IMPORT - NO SECTION COLUMN, detecting from existing students...')
            ctu_ids = df['CTU_ID'].dropna().astype(str).str.strip().tolist()
            existing_sections = User.objects.filter(
                acc_username__in=ctu_ids,
                account_type__ojt=True
            ).select_related('academic_info').values_list('academic_info__section', flat=True).distinct()
            
            existing_sections = [s for s in existing_sections if s]
            
            if existing_sections:
                detected_sections = list(existing_sections)
                print(f'OJT IMPORT - DETECTED SECTIONS FROM EXISTING STUDENTS: {detected_sections}')
            else:
                # Brand new import - use "4-A" as default (4th year, section A)
                detected_sections = ["4-A"]
                print(f'OJT IMPORT - NEW IMPORT, USING DEFAULT SECTION: 4-A (4th year, section A)')

        # DEBUG: Show exact column names from Excel BEFORE normalization
        print(f"📋 EXCEL COLUMNS (before normalization): {list(df.columns)}")
        
        # Normalize flexible header names for common variants
        try:
            # Create a case-insensitive mapping
            rename_map = {}
            for col in df.columns:
                col_lower = str(col).lower().strip()
                
                # First Name variants
                if col_lower in ['firstname', 'first name']:
                    rename_map[col] = 'First_Name'
                # Middle Name variants
                elif col_lower in ['middlename', 'middle name']:
                    rename_map[col] = 'Middle_Name'
                # Last Name variants
                elif col_lower in ['lastname', 'last name']:
                    rename_map[col] = 'Last_Name'
                # Contact Number variants
                elif col_lower in ['contactno', 'contact no', 'contact_no', 'contact number']:
                    rename_map[col] = 'Contact_No'
                # Company name variants
                elif col_lower in ['company name', 'company_name', 'companyname', 'company']:
                    rename_map[col] = 'Company'
                # Company Address variants
                elif col_lower in ['companyaddress', 'company address']:
                    rename_map[col] = 'Company_Address'
                # Company Email variants
                elif col_lower in ['companyemail', 'company email']:
                    rename_map[col] = 'Company_Email'
                # Company Contact variants
                elif col_lower in ['companycontact', 'company contact']:
                    rename_map[col] = 'Company_Contact'
                # Contact person name variants
                elif col_lower in ['contactperson', 'contact_person', 'contact person name', 'contact person']:
                    rename_map[col] = 'Contact_Person'
                # Contact person position variants
                elif col_lower in ['contact_person_position', 'contact person position', 'contactpersonposition', 'position']:
                    rename_map[col] = 'Position'
                # Status variants
                elif col_lower in ['ojt_status', 'ojtstatus', 'ojt status']:
                    rename_map[col] = 'Status'
                # Date variants
                elif col_lower in ['ojt_start_date', 'start_date', 'start date']:
                    rename_map[col] = 'Ojt_Start_Date'
                elif col_lower in ['ojt_end_date', 'end_date', 'end date']:
                    rename_map[col] = 'Ojt_End_Date'
                # Civil Status
                elif col_lower == 'civil status':
                    rename_map[col] = 'Civil_Status'
                # Social Media
                elif col_lower == 'social media':
                    rename_map[col] = 'Social_Media'
                # Batch Year
                elif col_lower in ['batch year', 'batch_year', 'year']:
                    rename_map[col] = 'Batch_Year'
            
            if rename_map:
                print(f"🔄 Renaming columns: {rename_map}")
                df.rename(columns=rename_map, inplace=True)
        except Exception as e:
            print(f"⚠️ Column rename failed: {e}")
            pass
        
        # DEBUG: Show column names AFTER normalization
        print(f"📋 EXCEL COLUMNS (after normalization): {list(df.columns)}")

        # TWO-STEP IMPORT SUPPORT:
        # FIRST IMPORT: CTU_ID + Personal info (creates users)
        # SECOND IMPORT: CTU_ID only (updates company info for existing users)
        # CTU_ID is the ONLY truly required column - system auto-detects if user exists
        required_columns = ['CTU_ID']
        optional_columns = ['First_Name', 'Last_Name', 'Gender', 'Password', 'Birthdate', 'Phone_Number', 'Address', 'Civil_Status', 'Social_Media',
                           'Company Name', 'Company', 'Company_Address', 'Company_Email', 'Company_Contact',
                           'Contact_Person', 'Position', 'Start_Date', 'End_Date', 'Status']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return JsonResponse({
                'success': False,
                'message': f'Missing required OJT columns: {", ".join(missing_columns)}'
            }, status=400)
        print(f"✅ Smart import enabled: CTU_ID required, other fields auto-validated per row")

        # Create import record
        # Normalize batch_year to a single 4-digit year if possible
        try:
            import re
            match = re.search(r"(20\d{2})", str(batch_year))
            normalized_year = int(match.group(1)) if match else int(str(batch_year).strip())
        except Exception:
            normalized_year = batch_year

        # Create import records for each detected section
        import_records = []
        for section in detected_sections:
            import_record = OJTImport.objects.create(
                coordinator=coordinator_username,
                batch_year=normalized_year,
                course=course or 'Unknown',  # Provide default if empty
                section=section,
                file_name=file.name
            )
            import_records.append(import_record)

        created_count = 0
        skipped_count = 0
        updating_count = 0  # Count students getting updated (2nd import)
        retaking_count = 0  # Count students retaking OJT in a different batch
        errors = []
        exported_passwords = []  # List to collect (username, password) for export
        total_rows = int(getattr(df, 'shape', [0])[0] or 0)
        deactivated_count = 0  # Count old batch students deactivated
        reactivated_count = 0  # Count students reactivated (same CTU_ID in new batch)

        # Ensure OJT account type exists for new OJT users
        try:
            ojt_account_type, _ = AccountType.objects.get_or_create(
                admin=False,
                peso=False,
                user=False,
                coordinator=False,
                ojt=True,
            )
        except Exception:
            ojt_account_type = None
        
        # ===== NEW BATCH IMPORT LOGIC =====
        # Step 1: Get all CTU_IDs from the new import
        new_import_ctu_ids = set()
        for idx, row in df.iterrows():
            ctu_id = str(row.get('CTU_ID', '')).strip()
            if ctu_id:
                new_import_ctu_ids.add(ctu_id)
        print(f"📋 New import contains {len(new_import_ctu_ids)} unique CTU_IDs")
        
        # Step 2: Find all existing OJT students from old batches for this coordinator
        from django.db.models import Q
        from apps.shared.models import AcademicInfo
        
        # Get all import records by this coordinator (except current batch)
        old_imports = OJTImport.objects.filter(
            coordinator=coordinator_username
        ).exclude(batch_year=normalized_year)
        
        # Get year+section combinations from old imports
        old_year_sections = set()
        for imp in old_imports:
            year = getattr(imp, 'batch_year', None)
            section = getattr(imp, 'section', None)
            if year:
                old_year_sections.add((year, section))
        
        # Find all OJT students from old batches (only if old imports exist)
        old_batch_users = User.objects.none()  # Start with empty queryset
        
        if old_year_sections:
            # Find all OJT students from old batches
            old_batch_users = User.objects.filter(
                account_type__ojt=True,
                user_status__iexact='Active',
                academic_info__isnull=False  # Ensure academic_info exists
            ).select_related('academic_info', 'ojt_info')
            
            # Filter by coordinator's old year+section combinations
            year_section_filters = Q()
            for year, section in old_year_sections:
                if section:
                    year_section_filters |= Q(academic_info__year_graduated=year, academic_info__section=section)
                else:
                    year_section_filters |= Q(academic_info__year_graduated=year)
            
            if year_section_filters:
                old_batch_users = old_batch_users.filter(year_section_filters)
        
        # Step 3: Deactivate students NOT in the new import
        # Special rule: If OJT status is "Incomplete", deactivation is based on the NEW batch's send date
        # (SendDate is already imported at the top of the file)
        
        # Check if new batch has a send date set
        new_batch_send_date = None
        try:
            # Try to find send date for the new batch
            new_batch_send_date_obj = SendDate.objects.filter(
                coordinator=coordinator_username,
                batch_year=normalized_year
            ).first()
            
            if new_batch_send_date_obj and new_batch_send_date_obj.send_date:
                new_batch_send_date = new_batch_send_date_obj.send_date
                print(f"📅 New batch ({normalized_year}) has send date: {new_batch_send_date}")
            else:
                print(f"📅 New batch ({normalized_year}) has no send date set")
        except Exception as e:
            print(f"⚠️ Could not check send date for new batch: {e}")
        
        for old_user in old_batch_users:
            old_ctu_id = old_user.acc_username
            
            if old_ctu_id not in new_import_ctu_ids:
                # Check OJT status before deactivating
                should_deactivate = True
                skip_reason = None
                
                # Get OJT info if exists
                try:
                    # Use select_related to efficiently get OJT info if it exists
                    ojt_info = getattr(old_user, 'ojt_info', None)
                    ojt_status = ojt_info.ojtstatus if ojt_info and ojt_info.ojtstatus else None
                    
                    # If OJT status is "Incomplete", check if new batch send date has passed
                    # Keep incomplete students active until new batch send date is overdue
                    if ojt_status and str(ojt_status).strip().lower() in ['incomplete', 'in complete']:
                        if new_batch_send_date:
                            # Check if send date has passed (is overdue)
                            today = timezone.now().date()
                            if today < new_batch_send_date:
                                # Send date has NOT passed yet - DO NOT deactivate incomplete students
                                should_deactivate = False
                                days_until_due = (new_batch_send_date - today).days
                                skip_reason = f"OJT status is Incomplete and new batch ({normalized_year}) send date ({new_batch_send_date}) is not yet due ({days_until_due} days remaining) - will keep active"
                                print(f"🟡 Skipping deactivation for {old_ctu_id}: {skip_reason}")
                            else:
                                # Send date has passed (overdue) - deactivate incomplete students
                                should_deactivate = True
                                days_overdue = (today - new_batch_send_date).days
                                print(f"⚠️ OJT status is Incomplete and new batch ({normalized_year}) send date ({new_batch_send_date}) is overdue ({days_overdue} days) - will deactivate {old_ctu_id}")
                        else:
                            # New batch has no send date - proceed with normal deactivation
                            print(f"⚠️ OJT status is Incomplete but new batch ({normalized_year}) has no send date - will deactivate {old_ctu_id}")
                            should_deactivate = True
                    else:
                        # OJT status is not "Incomplete" - proceed with normal deactivation
                        should_deactivate = True
                except Exception as e:
                    # If error accessing OJT info, proceed with normal deactivation
                    print(f"⚠️ Could not check OJT status for {old_ctu_id}: {e}")
                    should_deactivate = True
                
                if should_deactivate:
                    # Student not in new import - deactivate them
                    old_user.user_status = 'Inactive'
                    old_user.save(update_fields=['user_status'])
                    deactivated_count += 1
                    print(f"🔴 Deactivated old batch student: {old_ctu_id} (not in new import)")
                else:
                    # Skip deactivation due to incomplete OJT status
                    print(f"🟡 Skipped deactivation for {old_ctu_id}: {skip_reason}")
            else:
                # Student IS in new import - ensure they're active (will be updated)
                if old_user.user_status != 'Active':
                    old_user.user_status = 'Active'
                    old_user.save(update_fields=['user_status'])
                    reactivated_count += 1
                    print(f"🟢 Reactivated student: {old_ctu_id} (in new import)")
        
        print(f"📊 Batch import summary:")
        print(f"   - Deactivated {deactivated_count} old batch students")
        print(f"   - Reactivated {reactivated_count} students (will be updated)")
        print(f"   - Processing {len(new_import_ctu_ids)} students from new import")
        # ===== END NEW BATCH IMPORT LOGIC =====
        
        for index, row in df.iterrows():
            print(f"--- Processing Row {index+2} ---")
            try:
                # --- Field Extraction and Cleaning ---
                ctu_id = str(row.get('CTU_ID', '')).strip()
                
                print(f"\n{'='*80}")
                print(f"🔍 PROCESSING ROW {index+2} - CTU_ID: {ctu_id}")
                print(f"{'='*80}")
                
                first_name = str(row.get('First_Name', '')).strip()
                middle_name = str(row.get('Middle_Name', '')).strip() if pd.notna(row.get('Middle_Name')) else ''
                last_name = str(row.get('Last_Name', '')).strip()
                gender_raw = str(row.get('Gender', '')).strip()
                
                # DEBUG: Show all available columns and company data
                print(f"📋 Available columns in this row: {list(row.keys())}")
                print(f"📦 Company data from Excel:")
                print(f"   'Company': '{row.get('Company')}' (exists: {'Company' in row})")
                print(f"   'Company_Address': '{row.get('Company_Address')}' (exists: {'Company_Address' in row})")
                print(f"   'Company_Email': '{row.get('Company_Email')}' (exists: {'Company_Email' in row})")
                print(f"   'Company_Contact': '{row.get('Company_Contact')}' (exists: {'Company_Contact' in row})")
                print(f"👤 Personal data: First='{first_name}', Last='{last_name}', Gender='{gender_raw}'")
                # Normalize gender values
                if gender_raw.upper() in ['MALE', 'M']:
                    gender = 'M'
                elif gender_raw.upper() in ['FEMALE', 'F']:
                    gender = 'F'
                else:
                    gender = gender_raw.upper()
                # --- Section Handling ---
                # Use section from Excel file if available, otherwise use first detected section
                excel_section = str(row.get('Section', '')).strip()
                if excel_section and excel_section in detected_sections:
                    user_section = excel_section
                    print(f"Row {index+2} - Using Excel section: '{excel_section}'")
                else:
                    # Use the first detected section as default
                    user_section = detected_sections[0] if detected_sections else f"{batch_year}-A"
                    print(f"Row {index+2} - Using default section: '{user_section}'")

                # --- Password Handling (no birthdate login) ---
                password_raw = str(row.get('Password', '')).strip()
                if not password_raw:
                    alphabet = string.ascii_letters + string.digits
                    password_raw = ''.join(secrets.choice(alphabet) for _ in range(12))
                    print(f"Row {index+2} - Generated password: {password_raw}")
                else:
                    print(f"Row {index+2} - Using provided password: {password_raw}")

                # --- Age not derived from password; keep None unless separately provided
                age = None

                # --- Parse OJT Status from Excel ---
                ojt_status = 'Ongoing'  # Default status
                if 'Status' in row and pd.notna(row.get('Status')):
                    excel_status = str(row.get('Status')).strip()
                    # Normalize status values
                    if excel_status.lower() in ['completed', 'complete', 'done']:
                        ojt_status = 'Completed'
                    elif excel_status.lower() in ['ongoing', 'active', 'in progress']:
                        ojt_status = 'Ongoing'
                    elif excel_status.lower() in ['incomplete', 'failed', 'dropped', 'not started']:
                        ojt_status = 'Not Started'
                    else:
                        ojt_status = excel_status  # Use as-is if not recognized
                    print(f"Row {index+2} - Status from Excel: '{excel_status}' -> Normalized to: '{ojt_status}'")
                else:
                    print(f"Row {index+2} - No Status in Excel, defaulting to: '{ojt_status}'")

                # --- Parse OJT Start/End Dates ---
                ojt_start_date = None
                ojt_end_date = None

                # Try different possible column names for start date
                start_date_raw = row.get('Ojt_Start_Date') or row.get('Start_Date')
                print(f"Row {index+2} - Raw Start Date: '{start_date_raw}', Type: {type(start_date_raw)}")
                if pd.notna(start_date_raw):
                    try:
                        # Try multiple date parsing methods
                        ojt_start_date = pd.to_datetime(start_date_raw, dayfirst=True).date()
                        if ojt_start_date and ojt_start_date.year > 2020:  # Valid date check
                            print(f"Row {index+2} - Parsed start date successfully: {ojt_start_date}")
                        else:
                            print(f"Row {index+2} - Invalid start date: {ojt_start_date}")
                            ojt_start_date = None
                    except Exception as e:
                        print(f"Row {index+2} - FAILED to parse start date. Error: {e}")
                        ojt_start_date = None
                else:
                    print(f"Row {index+2} - No start date found in row")

                # Try different possible column names for end date
                end_date_raw = row.get('Ojt_End_Date') or row.get('End_Date')
                print(f"Row {index+2} - Raw End Date: '{end_date_raw}', Type: {type(end_date_raw)}")
                if pd.notna(end_date_raw):
                    try:
                        ojt_end_date = pd.to_datetime(end_date_raw, dayfirst=True).date()
                        print(f"Row {index+2} - Parsed end date successfully: {ojt_end_date}")
                    except Exception as e:
                        print(f"Row {index+2} - FAILED to parse end date. Error: {e}")
                        ojt_end_date = None

                # --- Validation Check ---
                # CTU_ID is always required
                if not ctu_id:
                    error_msg = f"Row {index + 2}: Missing CTU_ID (required)"
                    print(f"SKIPPING: {error_msg}")
                    errors.append(error_msg)
                    skipped_count += 1
                    continue
                
                # Check if user exists - if yes, other fields are optional (update mode)
                # If no, First_Name, Last_Name, Gender are required (create mode)
                existing_user_check = User.objects.filter(acc_username=ctu_id).first()
                
                print(f"Row {index+2} - CTU_ID: {ctu_id}, User exists: {existing_user_check is not None}")
                
                # IMPORTANT: Check if this CTU_ID was imported by a different coordinator
                if existing_user_check:
                    # Check if user has academic_info (OJT students should have this)
                    if hasattr(existing_user_check, 'academic_info') and existing_user_check.academic_info:
                        user_year = existing_user_check.academic_info.year_graduated
                        user_section = getattr(existing_user_check.academic_info, 'section', None) or ''
                        
                        # Find which coordinator(s) imported this user's year+section
                        existing_imports = OJTImport.objects.filter(
                            batch_year=user_year,
                            section=user_section
                        )
                        
                        if existing_imports.exists():
                            # Check all imports for this year+section
                            coordinators_for_this_batch = set()
                            for imp in existing_imports:
                                coordinators_for_this_batch.add(imp.coordinator)
                            
                            # If any coordinator other than current one imported this batch, block it
                            other_coordinators = coordinators_for_this_batch - {coordinator_username}
                            if other_coordinators:
                                original_coordinator = list(other_coordinators)[0]  # Get first other coordinator
                                error_msg = f"Row {index + 2}: CTU_ID {ctu_id} was already imported by {original_coordinator} (batch {user_year}, section {user_section}). Cannot import to {coordinator_username}."
                                print(f"❌ BLOCKED: {error_msg}")
                                errors.append(error_msg)
                                skipped_count += 1
                                continue
                            else:
                                print(f"✅ CTU_ID {ctu_id} was imported by same coordinator ({coordinator_username}) - allowing update")
                        else:
                            # User exists but no import record - might be from old system
                            # Check if user is OJT type - if yes, block it to prevent conflicts
                            if existing_user_check.account_type and existing_user_check.account_type.ojt:
                                error_msg = f"Row {index + 2}: CTU_ID {ctu_id} already exists as OJT student (batch {user_year}, section {user_section}) but has no import record. Cannot import to prevent conflicts."
                                print(f"❌ BLOCKED: {error_msg}")
                                errors.append(error_msg)
                                skipped_count += 1
                                continue
                
                if not existing_user_check:
                    # NEW USER - require all fields (including personal info AND company info)
                    print(f"Row {index+2} - NEW USER MODE - validating required fields...")
                    
                    # Extract additional required fields - Personal Info
                    birthdate_raw = row.get('Birthdate')
                    contact_no = str(row.get('Contact_No', '')).strip() if pd.notna(row.get('Contact_No')) else ''
                    email = str(row.get('Email', '')).strip() if pd.notna(row.get('Email')) else ''
                    address = str(row.get('Address', '')).strip() if pd.notna(row.get('Address')) else ''
                    
                    # Extract required company fields
                    company_name = str(row.get('Company', '')).strip() if pd.notna(row.get('Company')) else ''
                    company_address = str(row.get('Company_Address', '')).strip() if pd.notna(row.get('Company_Address')) else ''
                    company_email = str(row.get('Company_Email', '')).strip() if pd.notna(row.get('Company_Email')) else ''
                    company_contact = str(row.get('Company_Contact', '')).strip() if pd.notna(row.get('Company_Contact')) else ''
                    contact_person = str(row.get('Contact_Person', '')).strip() if pd.notna(row.get('Contact_Person')) else ''
                    position = str(row.get('Position', '')).strip() if pd.notna(row.get('Position')) else ''
                    
                    # FIRST IMPORT: Require basic personal info + contact details
                    # Company info can be added later via second import
                    required_personal_data = {
                        "FirstName": first_name,
                        "LastName": last_name,
                        "Gender": gender,
                        "Section": excel_section,
                        "Birthdate": birthdate_raw if pd.notna(birthdate_raw) else None,
                        "ContactNo": contact_no,
                        "Email": email,
                        "Address": address
                    }
                    missing_fields = [key for key, value in required_personal_data.items() if not value]

                    if missing_fields:
                        error_msg = f"Row {index + 2}: New user requires - {', '.join(missing_fields)}"
                        print(f"SKIPPING: {error_msg}")
                        errors.append(error_msg)
                        skipped_count += 1
                        continue
                    
                    # Optional fields (nice to have but not required)
                    # MiddleName only - all other personal fields are now required
                    # Company fields are ALL optional for first import
                    print(f"Row {index+2} - ✅ Required fields validated. Optional field: MiddleName={bool(middle_name)}")
                    print(f"Row {index+2} - Company info (optional): CompanyName={bool(company_name)}, Address={bool(company_address)}, Email={bool(company_email)}, Contact={bool(company_contact)}, Person={bool(contact_person)}, Position={bool(position)}")

                    # --- Gender Validation for new users ---
                    if gender not in ['M', 'F']:
                        error_msg = f"Row {index + 2}: Gender must be 'M'/'Male' or 'F'/'Female', but was '{gender}' (from raw: '{gender_raw}')"
                        print(f"SKIPPING: {error_msg}")
                        errors.append(error_msg)
                        skipped_count += 1
                        continue
                    
                    # --- Birthdate Validation (OPTIONAL - only validate if provided) ---
                    bd = None  # Default to None if not provided
                    if pd.notna(birthdate_raw):
                        try:
                            bd = pd.to_datetime(birthdate_raw, errors='coerce').date()
                            if bd and (bd.year < 1900 or bd.year > 2020):
                                error_msg = f"Row {index + 2}: Invalid birthdate '{birthdate_raw}'. Must be between 1900-2020."
                                print(f"SKIPPING: {error_msg}")
                                errors.append(error_msg)
                                skipped_count += 1
                                continue
                        except Exception as e:
                            print(f"Row {index + 2}: WARNING - Could not parse birthdate '{birthdate_raw}', setting to None")
                            bd = None
                    else:
                        print(f"Row {index + 2} - No birthdate provided (optional field)")
                else:
                    # EXISTING USER - fields are optional, use existing data if not provided
                    print(f"Row {index+2} - UPDATE MODE ACTIVATED - User {ctu_id} exists, proceeding with company data update...")

                # If a user with this CTU_ID already exists, update academic year/course
                existing_user = User.objects.filter(acc_username=ctu_id).first()
                if existing_user:
                    try:
                        print(f"Row {index+2} - User {ctu_id} already exists, checking batch year...")
                        
                        # Ensure related models exist
                        from apps.shared.models import UserProfile, AcademicInfo, OJTInfo, EmploymentHistory, OJTCompanyProfile
                        profile, _ = UserProfile.objects.get_or_create(user=existing_user)
                        academic, _ = AcademicInfo.objects.get_or_create(user=existing_user)
                        
                        # CHECK: Is student being imported for a DIFFERENT batch year? (Retaking OJT)
                        # If yes, delete old OJT data from previous batch and start fresh
                        old_batch_year = academic.year_graduated
                        new_batch_year = int(normalized_year) if str(normalized_year).isdigit() else None
                        
                        if old_batch_year and new_batch_year and old_batch_year != new_batch_year:
                            # CHECK: Is student already APPROVED (alumni)? 
                            # If yes, BLOCK retaking - alumni cannot retake OJT
                            is_alumni = existing_user.account_type and existing_user.account_type.user == True
                            
                            if is_alumni:
                                # BLOCK: Alumni cannot retake OJT
                                print(f"Row {index+2} - ⚠️ BLOCKED: Student {ctu_id} is already APPROVED (alumni) in batch {old_batch_year}")
                                print(f"Row {index+2} - Alumni cannot retake OJT. Skipping import for this user.")
                                errors.append(f"Row {index+2}: Student {ctu_id} ({first_name} {last_name}) is already APPROVED (alumni) and cannot retake OJT.")
                                skipped_count += 1
                                continue  # Skip this student, move to next row
                            
                            # Student is NOT alumni (INCOMPLETE or failed) - Allow retaking
                            print(f"Row {index+2} - RETAKING OJT! Student was in batch {old_batch_year}, now importing for batch {new_batch_year}")
                            print(f"Row {index+2} - Student is NOT alumni (INCOMPLETE/failed), retaking is allowed.")
                            print(f"Row {index+2} - Deleting old OJT data from batch {old_batch_year}...")
                            
                            # Delete old OJT data
                            OJTInfo.objects.filter(user=existing_user).delete()
                            OJTCompanyProfile.objects.filter(user=existing_user).delete()
                            
                            # REACTIVATE ACCOUNT: Reset account type to OJT
                            if not existing_user.account_type:
                                existing_user.account_type = ojt_account_type
                                existing_user.save()
                            else:
                                # Ensure OJT flag is set
                                existing_user.account_type.ojt = True
                                existing_user.account_type.save()
                                print(f"Row {index+2} - Account reactivated as OJT student")
                            
                            retaking_count += 1
                            print(f"Row {index+2} - Old OJT data deleted. Student will start fresh in batch {new_batch_year}")
                        
                        # Update section ONLY if explicitly provided in Excel (not auto-generated)
                        # For second imports without Section column, keep existing section
                        excel_section_provided = 'Section' in row and pd.notna(row.get('Section')) and str(row.get('Section')).strip()
                        if excel_section_provided:
                            academic.section = user_section
                            academic.save()
                            print(f"Row {index+2} - Updated section to: {user_section}")
                        else:
                            print(f"Row {index+2} - No Section in Excel, keeping existing section: {academic.section}")
                        
                        ojt_info, _ = OJTInfo.objects.get_or_create(user=existing_user)
                        employment, _ = EmploymentHistory.objects.get_or_create(user=existing_user)
                        
                        # Check if employment already has a company (for detecting first vs second import)
                        has_existing_company = employment.company_name_current and str(employment.company_name_current).strip()
                        
                        # Check if user has initial password record (indicates account was already created)
                        from apps.shared.models import UserInitialPassword
                        has_initial_password = UserInitialPassword.objects.filter(user=existing_user).exists()
                        
                        # Ensure a first-login record exists and is active for coordinator-managed accounts
                        ensure_initial_password_active(
                            existing_user,
                            raw_password=password_raw if password_raw else None,
                            allow_create=bool(password_raw),
                        )
                        print(f"Row {index+2} - Initial password record ensured/activated for {ctu_id}")

                        # Update names to match latest import where present (only if provided in Excel)
                        updated = False
                        if first_name:
                            existing_user.f_name = first_name
                            updated = True
                        if middle_name:
                            existing_user.m_name = middle_name
                            updated = True
                        if last_name:
                            existing_user.l_name = last_name
                            updated = True
                        if gender and gender in ['M', 'F']:
                            existing_user.gender = gender
                            updated = True
                        
                        if updated:
                            existing_user.save()
                            print(f"Row {index+2} - Updated user personal info")
                        else:
                            print(f"Row {index+2} - No personal info changes, keeping existing data")

                        # Update academic info from batch and course
                        # Save normalized batch year
                        try:
                            academic.year_graduated = int(normalized_year)
                        except Exception:
                            pass
                        if course:
                            academic.program = course
                        academic.save()

                        # Update profile birthdate if present
                        if pd.notna(row.get('Birthdate')):
                            try:
                                bd = pd.to_datetime(row.get('Birthdate'), errors='coerce').date()
                                if bd:
                                    profile.birthdate = bd
                            except Exception:
                                pass
                        profile.save()

                        # Update employment company and start date from spreadsheet
                        company_name = (
                            row.get('Company Name')
                            or row.get('Company')
                            or row.get('Company name current')
                        )
                        
                        # Check if company info is being provided in this import
                        has_new_company_info = pd.notna(company_name) and str(company_name).strip()
                        
                        if has_new_company_info:
                            employment.company_name_current = str(company_name).strip()
                            
                            # If this is SECOND import (has new company but didn't have one before)
                            # Set start date to TODAY automatically
                            if not has_existing_company:
                                from django.utils import timezone
                                ojt_start_date = timezone.now().date()
                                print(f"Row {index+2} - SECOND IMPORT DETECTED! Auto-setting start_date to TODAY: {ojt_start_date}")
                                
                                # Calculate end date from SendDate for this batch
                                from apps.shared.models import SendDate
                                send_date_obj = SendDate.objects.filter(
                                    batch_year=normalized_year,
                                    coordinator=coordinator_username
                                ).first()
                                
                                if send_date_obj and send_date_obj.send_date:
                                    ojt_end_date = send_date_obj.send_date
                                    print(f"Row {index+2} - Auto-calculated end_date from SendDate: {ojt_end_date}")
                        
                        # Update company detail fields (after column normalization)
                        company_address = row.get('Company_Address')
                        company_email = row.get('Company_Email')
                        company_contact = row.get('Company_Contact')
                        contact_person = row.get('Contact_Person')  # Normalized from Contact_Person_Name
                        position = row.get('Position')  # Normalized from Contact_Person_Position
                        
                        print(f"Row {index+2} - 📦 Reading company details from normalized columns:")
                        print(f"  Company_Address: '{company_address}' (notna: {pd.notna(company_address)}, type: {type(company_address)})")
                        print(f"  Company_Email: '{company_email}' (notna: {pd.notna(company_email)}, type: {type(company_email)})")
                        print(f"  Company_Contact: '{company_contact}' (notna: {pd.notna(company_contact)}, type: {type(company_contact)})")
                        print(f"  Contact_Person: '{contact_person}' (notna: {pd.notna(contact_person)}, type: {type(contact_person)})")
                        print(f"  Position: '{position}' (notna: {pd.notna(position)}, type: {type(position)})")
                        
                        if pd.notna(company_address) and str(company_address).strip():
                            employment.company_address = str(company_address).strip()
                            print(f"  -> Set company_address to: '{employment.company_address}'")
                        if pd.notna(company_email) and str(company_email).strip():
                            employment.company_email = str(company_email).strip()
                            print(f"  -> Set company_email to: '{employment.company_email}'")
                        if pd.notna(company_contact) and str(company_contact).strip():
                            employment.company_contact = str(company_contact).strip()
                            print(f"  -> Set company_contact to: '{employment.company_contact}'")
                        if pd.notna(contact_person) and str(contact_person).strip():
                            employment.contact_person = str(contact_person).strip()
                            print(f"  -> Set contact_person to: '{employment.contact_person}'")
                        if pd.notna(position) and str(position).strip():
                            employment.position = str(position).strip()
                            print(f"  -> Set position to: '{employment.position}'")
                        
                        if 'ojt_start_date' in locals() and ojt_start_date:
                            employment.date_started = ojt_start_date
                        employment.save()

                        # Update OJT info (status, dates if parsed)
                        # STATUS is ONLY changeable if start_date exists
                        if 'ojt_start_date' in locals() and ojt_start_date:
                            ojt_info.ojtstatus = ojt_status
                            print(f"Row {index+2} - Start date exists, status set to: '{ojt_status}'")
                        else:
                            # Keep existing status or set to 'Not Started' if no start date
                            if not ojt_info.ojtstatus:
                                ojt_info.ojtstatus = 'Not Started'
                            print(f"Row {index+2} - No start date, status remains: '{ojt_info.ojtstatus}'")
                        
                        # Set start/end dates
                        if 'ojt_start_date' in locals() and ojt_start_date:
                            ojt_info.ojt_start_date = ojt_start_date
                        if 'ojt_end_date' in locals() and ojt_end_date:
                            ojt_info.ojt_end_date = ojt_end_date
                        ojt_info.save()
                        
                        # Update or create OJT Company Profile
                        try:
                            ojt_company_profile, created = OJTCompanyProfile.objects.get_or_create(
                                user=existing_user,
                                defaults={
                                    'company_name': str(company_name).strip().upper() if has_new_company_info else None,
                                    'start_date': ojt_start_date if 'ojt_start_date' in locals() else None,
                                    'end_date': ojt_end_date if 'ojt_end_date' in locals() else None,
                                }
                            )
                            
                            if not created:
                                # Update existing profile
                                if has_new_company_info:
                                    ojt_company_profile.company_name = str(company_name).strip().upper()
                                if 'ojt_start_date' in locals() and ojt_start_date:
                                    ojt_company_profile.start_date = ojt_start_date
                                if 'ojt_end_date' in locals() and ojt_end_date:
                                    ojt_company_profile.end_date = ojt_end_date
                            
                            # Update company details
                            company_address = row.get('Company_Address')
                            company_email = row.get('Company_Email')
                            company_contact = row.get('Company_Contact')
                            contact_person = row.get('Contact_Person')
                            position = row.get('Position')
                            
                            if pd.notna(company_address) and str(company_address).strip():
                                ojt_company_profile.company_address = str(company_address).strip()
                            if pd.notna(company_email) and str(company_email).strip():
                                ojt_company_profile.company_email = str(company_email).strip()
                            if pd.notna(company_contact) and str(company_contact).strip():
                                ojt_company_profile.company_contact = str(company_contact).strip()
                            if pd.notna(contact_person) and str(contact_person).strip():
                                ojt_company_profile.contact_person = str(contact_person).strip()
                            if pd.notna(position) and str(position).strip():
                                ojt_company_profile.position = str(position).strip()
                            
                            ojt_company_profile.save()
                            print(f"Row {index+2} - Updated OJT Company Profile for {company_name}")
                        except Exception as e:
                            print(f"Row {index+2} - Failed to update OJT Company Profile: {e}")
                            pass

                        # User already existed - don't count as "created", just updated
                        updating_count += 1
                        print(f"Row {index+2} - ✅ UPDATE COMPLETE: User information updated (updating_count: {updating_count})")
                        continue
                    except Exception as _e:
                        # Fall through to try creating a new one if update fails
                        import traceback
                        print(f"Row {index+2} - ❌ EXCEPTION during update for {ctu_id}: {_e}")
                        print(f"Row {index+2} - Traceback: {traceback.format_exc()}")
                        print(f"Row {index+2} - Will skip this row due to error")
                        errors.append(f"Row {index+2}: Update failed for {ctu_id} - {str(_e)}")
                        skipped_count += 1
                        continue

                # --- Create OJT user securely ---
                ojt_user = User.objects.create(
                    acc_username=ctu_id,
                    user_status='active',
                    f_name=first_name,
                    m_name=middle_name,
                    l_name=last_name,
                    gender=gender,
                    account_type=ojt_account_type or AccountType.objects.get(ojt=True, admin=False, peso=False, user=False, coordinator=False),
                )
                ojt_user.set_password(password_raw)
                ojt_user.save()
                # Store initial password (encrypted)
                # Set is_active=True so users get forced to change password on first login
                ensure_initial_password_active(ojt_user, raw_password=password_raw, allow_create=True)
                from apps.shared.models import UserProfile, AcademicInfo, EmploymentHistory, OJTInfo
                birthdate_val = row.get('Birthdate')
                # Extract phone number from Contact_No column (your Excel uses Contact_No, not Phone_Number)
                phone_num = str(row.get('Contact_No', '')).strip() if pd.notna(row.get('Contact_No')) else None
                # Clean up phone number format (remove scientific notation)
                if phone_num and 'E+' in phone_num:
                    try:
                        phone_num = str(int(float(phone_num)))
                    except:
                        pass
                
                profile_kwargs = dict(
                    user=ojt_user,
                    age=None,
                    phone_num=phone_num,
                    address=str(row.get('Address', '')).strip() if pd.notna(row.get('Address')) else None,
                    civil_status=str(row.get('Civil_Status', '')).strip() if pd.notna(row.get('Civil_Status')) else None,
                    social_media=str(row.get('Social_Media', '')).strip() if pd.notna(row.get('Social_Media')) else None,
                )
                if pd.notna(birthdate_val):
                    try:
                        # Try different date formats
                        bd = pd.to_datetime(birthdate_val, errors='coerce').date()
                        if bd and bd.year > 1900:  # Valid date check
                            profile_kwargs['birthdate'] = bd
                    except Exception as e:
                        print(f"Row {index+2} - Failed to parse birthdate '{birthdate_val}': {e}")
                        pass
                UserProfile.objects.create(**profile_kwargs)
                # Employment: company name and details
                company_name_new = (
                    row.get('Company Name')
                    or row.get('Company')
                    or row.get('Company name current')
                )
                # Note: OJT company data should NOT be copied to EmploymentHistory
                # EmploymentHistory is for actual employment after graduation, not OJT
                # OJT data should only be stored in OJTInfo model
                print(f"Row {index+2} - NEW USER - OJT company data will be stored in OJTInfo only")
                AcademicInfo.objects.create(
                    user=ojt_user,
                    year_graduated=int(normalized_year) if str(normalized_year).isdigit() else None,
                    program=course if course else 'OJT',  # Use program field, set default if empty
                    section=user_section,  # Use the determined section (from Excel or form)
                )
                # Create OJT info
                try:
                    # STATUS is ONLY set if start_date exists, otherwise set to 'Not Started'
                    final_status = ojt_status if ('ojt_start_date' in locals() and ojt_start_date) else 'Not Started'
                    
                    OJTInfo.objects.create(
                        ojt_start_date=ojt_start_date if 'ojt_start_date' in locals() else None,
                        user=ojt_user,
                        ojt_end_date=ojt_end_date if 'ojt_end_date' in locals() else None,
                        ojtstatus=final_status,
                    )
                    if 'ojt_start_date' in locals() and ojt_start_date:
                        print(f"Row {index+2} - Created new user with status: '{final_status}' (start date exists)")
                    else:
                        print(f"Row {index+2} - Created new user with status: '{final_status}' (no start date - first import)")
                except Exception:
                    pass
                # Create OJT Company Profile
                try:
                    from apps.shared.models import OJTCompanyProfile
                    ojt_company_kwargs = {
                        'user': ojt_user,
                        'company_name': str(company_name_new).strip().upper() if pd.notna(company_name_new) and str(company_name_new).strip() else None,
                        'start_date': ojt_start_date if 'ojt_start_date' in locals() else None,
                        'end_date': ojt_end_date,
                    }
                    
                    # Add company details if available
                    company_address_new = row.get('Company_Address')
                    company_email_new = row.get('Company_Email')
                    company_contact_new = row.get('Company_Contact')
                    contact_person_new = row.get('Contact_Person')
                    position_new = row.get('Position')
                    
                    if pd.notna(company_address_new) and str(company_address_new).strip():
                        ojt_company_kwargs['company_address'] = str(company_address_new).strip()
                    if pd.notna(company_email_new) and str(company_email_new).strip():
                        ojt_company_kwargs['company_email'] = str(company_email_new).strip()
                    if pd.notna(company_contact_new) and str(company_contact_new).strip():
                        ojt_company_kwargs['company_contact'] = str(company_contact_new).strip()
                    if pd.notna(contact_person_new) and str(contact_person_new).strip():
                        ojt_company_kwargs['contact_person'] = str(contact_person_new).strip()
                    if pd.notna(position_new) and str(position_new).strip():
                        ojt_company_kwargs['position'] = str(position_new).strip()
                    
                    OJTCompanyProfile.objects.create(**ojt_company_kwargs)
                    print(f"Row {index+2} - Created OJT Company Profile for {company_name_new}")
                except Exception as e:
                    print(f"Row {index+2} - Failed to create OJT Company Profile: {e}")
                    pass
                exported_passwords.append({
                    'CTU_ID': ctu_id,
                    'First_Name': first_name,
                    'Last_Name': last_name,
                    'Password': password_raw
                })

                print(f"SUCCESS: Created OJT record for CTU_ID {ctu_id} with password: {password_raw}")
                print(f"🔍 DEBUG: Added to exported_passwords list. Total count: {len(exported_passwords)}")
                created_count += 1

            except Exception as e:
                error_msg = f"Row {index + 2}: An unexpected error occurred - {str(e)}"
                print(f"ERROR: {error_msg}")
                errors.append(error_msg)
                skipped_count += 1
                continue

        # Update import records with actual created count (after section filtering)
        for import_record in import_records:
            import_record.records_imported = created_count
            if errors:
                import_record.status = 'Partial' if created_count > 0 else 'Failed'
            import_record.save()

        # Export passwords to Excel after import
        print(f"🔍 DEBUG: exported_passwords count: {len(exported_passwords)}")
        print(f"🔍 DEBUG: created_count: {created_count}")
        print(f"🔍 DEBUG: exported_passwords: {exported_passwords}")
        
        # Always return JSON response, but include password data
        total_processed = created_count + skipped_count
        second_import_count = total_processed - created_count - skipped_count
        
        response_data = {
            'success': True,
            'message': f'OJT import completed. Created: {created_count}, Updated: {updating_count}, Skipped: {skipped_count}, Deactivated: {deactivated_count}',
            'created_count': created_count,
            'updating_count': updating_count,
            'skipped_count': skipped_count,
            'retaking_count': retaking_count,
            'deactivated_count': deactivated_count,  # Old batch students deactivated
            'reactivated_count': reactivated_count,  # Students reactivated (same CTU_ID)
            'errors': errors[:10],  # Limit errors to first 10
            'passwords': exported_passwords,  # Include passwords in response (only for first import)
            'sections': detected_sections,  # Include detected sections
            'batch_year': normalized_year  # Include batch year for filename generation
        }
        
        if retaking_count > 0:
            response_data['message'] += f' 🔄 {retaking_count} student(s) retaking OJT (account reactivated, old data cleared).'
        
        if exported_passwords:
            print(f"🔍 DEBUG: Created {len(exported_passwords)} passwords for export")
            response_data['message'] += f' ✅ {len(exported_passwords)} passwords generated (First Import).'
        else:
            response_data['message'] += ' ℹ️ No passwords generated (Second Import - company info updated).'
        
        if detected_sections:
            response_data['message'] += f' Detected sections: {", ".join(detected_sections)}'
        
        return JsonResponse(response_data)

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"IMPORT ERROR DETAILS: {error_details}")
        return JsonResponse({'success': False, 'message': f'Import failed: {str(e)}'}, status=500)

# OJT statistics for coordinators
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ojt_statistics_view(request):
    try:
        coordinator_username = request.GET.get('coordinator', '')

        # Get all unique year+section combinations from OJTImport records
        # For each, count the ACTUAL users that exist in the database for that year
        year_section_counts = {}
        try:
            from apps.shared.models import OJTImport
            from django.db.models import Q
            
            # Get imports filtered by coordinator
            import_filter = OJTImport.objects.all()
            if coordinator_username:
                import_filter = import_filter.filter(coordinator=coordinator_username)
            
            print(f"DEBUG: Filtering by coordinator: {coordinator_username}")
            print(f"DEBUG: Found {import_filter.count()} import records")
            
            # Get unique year+section combinations from imports (ONLY from this coordinator's imports)
            unique_year_sections = {}
            for imp in import_filter:
                y = getattr(imp, 'batch_year', None)
                section = getattr(imp, 'section', None) or 'Unknown'
                
                if y is not None:
                    key = (y, section)
                    unique_year_sections[key] = True
            
            print(f"DEBUG: Unique year+section combinations from imports: {unique_year_sections.keys()}")
            
            # If coordinator is specified, ONLY show year+section combinations from their imports
            # Don't add users from other coordinators
            if not coordinator_username:
                # Admin view - can see all users, but still only from import records
                # Add year+section from actual users that have import records
                all_imports = OJTImport.objects.all()
                all_import_year_sections = set()
                for imp in all_imports:
                    y = getattr(imp, 'batch_year', None)
                    section = getattr(imp, 'section', None) or 'Unknown'
                    if y is not None:
                        all_import_year_sections.add((y, section))
                
                # Only add users that match import records
                actual_users = User.objects.filter(
                    account_type__ojt=True
                ).exclude(
                    acc_username=settings.DEFAULT_COORDINATOR_USERNAME
                ).exclude(
                    f_name='Coordinator'
                ).select_related('academic_info')
                
                for user in actual_users:
                    if hasattr(user, 'academic_info') and user.academic_info:
                        year = user.academic_info.year_graduated
                        section = user.academic_info.section or 'Unknown'
                        if year and (year, section) in all_import_year_sections:
                            unique_year_sections[(year, section)] = True
            
            print(f"DEBUG: Unique year+section combinations (final): {unique_year_sections.keys()}")
            
            # Now count actual OJT users for each year and section (exclude alumni and coordinators)
            for (year, section) in unique_year_sections.keys():
                # Count actual OJT users in database for this year AND section
                # Only count active OJT students, NOT alumni
                user_query = User.objects.filter(
                    academic_info__year_graduated=year,
                    academic_info__section=section,
                    account_type__ojt=True,  # Only count OJT students, not alumni
                    user_status__iexact='Active'  # Only count active students
                ).exclude(
                    acc_username=settings.DEFAULT_COORDINATOR_USERNAME  # Exclude coordinator users
                ).exclude(
                    f_name='Coordinator'  # Exclude any user with name "Coordinator"
                )
                
                # If coordinator is specified, ensure users match their imports
                if coordinator_username:
                    # Double-check: verify this year+section was imported by this coordinator
                    coordinator_has_import = OJTImport.objects.filter(
                        coordinator=coordinator_username,
                        batch_year=year,
                        section=section
                    ).exists()
                    
                    if not coordinator_has_import:
                        # Skip this year+section if coordinator didn't import it
                        continue
                
                ojt_count = user_query.count()
                
                # Only show cards with actual OJT students (don't count alumni)
                if ojt_count > 0:
                    year_section_counts[(year, section)] = ojt_count
                    print(f"DEBUG: Year {year}, Section {section}: {ojt_count} OJT students")
            
            print(f"DEBUG: year_section_counts final: {year_section_counts}")
                
        except Exception as e:
            print(f"DEBUG: Error grouping by section: {e}")
            import traceback
            traceback.print_exc()

        # Convert to the format expected by frontend
        years_list = []
        for (year, section), count in year_section_counts.items():
            years_list.append({
                'year': year, 
                'section': section,
                'count': count
            })
        
        # Sort by year (descending) then by section
        years_list.sort(key=lambda x: (x['year'] is None, x['year'] or 0, x['section'] or ''), reverse=True)

        return JsonResponse({'success': True, 'years': years_list, 'total_records': sum(year_section_counts.values())})

    except Exception as e:
        return JsonResponse({'success': True, 'years': [], 'total_records': 0, 'note': str(e)})
# OJT data by year for coordinators
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ojt_by_year_view(request):
    try:
        year = request.GET.get('year', '')
        coordinator_username = request.GET.get('coordinator', '')
        section = request.GET.get('section', '')

        if not year:
            return JsonResponse({'success': False, 'message': 'Year parameter is required'}, status=400)

        # Be lenient: extract a 4-digit year from the string (e.g., "2025 ", "2025-2026")
        try:
            import re
            match = re.search(r"(20\d{2})", str(year))
            year_int = int(match.group(1)) if match else int(str(year).strip())
        except Exception:
            return JsonResponse({'success': False, 'message': 'Invalid year parameter'}, status=400)

        # Get coordinator's imported year+section combinations if coordinator is specified
        coordinator_year_sections = set()
        coordinator_year_sections_normalized = set()  # For flexible matching
        if coordinator_username:
            try:
                from apps.shared.models import OJTImport
                coordinator_imports = OJTImport.objects.filter(coordinator=coordinator_username)
                for imp in coordinator_imports:
                    y = getattr(imp, 'batch_year', None)
                    s = getattr(imp, 'section', None)
                    # Normalize section: strip whitespace, handle None
                    s_normalized = s.strip() if s else ''
                    if y:
                        coordinator_year_sections.add((y, s_normalized))
                        # Also add with original value for flexible matching
                        coordinator_year_sections_normalized.add((y, s_normalized))
                        if s and s.strip() and s.strip() != s_normalized:
                            coordinator_year_sections_normalized.add((y, s.strip()))
                print(f"DEBUG: Coordinator {coordinator_username} has imports for: {coordinator_year_sections}")
            except Exception as e:
                print(f"ERROR getting coordinator imports: {e}")
                import traceback
                traceback.print_exc()
        
        # Normalize section for comparison (empty string or None both become '')
        normalized_section = section.strip() if section else ''
        # Check if the OJT company profile table is available (some environments may be mid-migration)
        ojt_company_profile_exists = _table_exists(OJTCompanyProfile._meta.db_table)
        select_related_fields = ['profile', 'academic_info', 'ojt_info', 'employment', 'initial_password']
        if ojt_company_profile_exists:
            select_related_fields.append('ojt_company_profile')
        
        # Filter by section if provided
        if normalized_section:
            print(f"DEBUG: Filtering by section: {normalized_section}")
            # Filter by actual section stored in AcademicInfo - ONLY OJT STUDENTS
            ojt_data = (
                User.objects
                .filter(
                    academic_info__year_graduated=year_int, 
                    academic_info__section=normalized_section,
                    account_type__ojt=True  # Only OJT students, not alumni
                )
                .exclude(acc_username=settings.DEFAULT_COORDINATOR_USERNAME)  # Exclude coordinator user
                .exclude(f_name='Coordinator')  # Exclude any user with name "Coordinator"
                .select_related(*select_related_fields)
                .order_by('l_name', 'f_name')
            )
            
            # If coordinator is specified, ensure this year+section was imported by them
            if coordinator_username:
                # Check if this year+section combination exists in coordinator's imports
                # Try both exact match and normalized match
                section_key = normalized_section
                section_found = (
                    (year_int, section_key) in coordinator_year_sections or
                    (year_int, section_key) in coordinator_year_sections_normalized
                )
                
                if not section_found:
                    # This year+section was not imported by this coordinator, return empty
                    ojt_data = User.objects.none()
                    print(f"DEBUG: Year {year_int}, Section {section_key} not imported by {coordinator_username}")
                    print(f"DEBUG: Available sections: {[s for y, s in coordinator_year_sections if y == year_int]}")
        else:
            # No section filter - show all users for the year
            # If no coordinator is specified, this is likely an admin request
            # Admin should only see users that were sent to admin
            if not coordinator_username:
                print(f"🔍 DEBUG: Admin request - filtering by is_sent_to_admin=True")
                ojt_data = (
                    User.objects
                    .filter(
                        academic_info__year_graduated=year_int, 
                        ojt_info__is_sent_to_admin=True,
                        account_type__ojt=True  # Only OJT students
                    )
                    .exclude(acc_username=settings.DEFAULT_COORDINATOR_USERNAME)  # Exclude coordinator user
                    .exclude(f_name='Coordinator')  # Exclude any user with name "Coordinator"
                    .select_related(*select_related_fields)
                    .order_by('l_name', 'f_name')
                )
            else:
                # Coordinator request - show only OJT users for year+section combinations they imported
                from django.db.models import Q
                year_section_filters = Q()
                has_filters = False
                for (y, s) in coordinator_year_sections:
                    if y == year_int:  # Only include sections for this year
                        has_filters = True
                        s_normalized = s or ''  # Normalize None to empty string
                        if s_normalized:
                            year_section_filters |= Q(academic_info__year_graduated=y, academic_info__section=s_normalized)
                        else:
                            year_section_filters |= Q(academic_info__year_graduated=y)
                
                if has_filters and year_section_filters:
                    try:
                        ojt_data = (
                            User.objects
                            .filter(
                                year_section_filters,
                                account_type__ojt=True  # Only OJT students, not alumni
                            )
                            .exclude(acc_username=settings.DEFAULT_COORDINATOR_USERNAME)  # Exclude coordinator user
                            .exclude(f_name='Coordinator')  # Exclude any user with name "Coordinator"
                    .select_related(*select_related_fields)
                            .order_by('l_name', 'f_name')
                        )
                    except Exception as e:
                        print(f"ERROR in ojt_by_year_view filter: {e}")
                        import traceback
                        traceback.print_exc()
                        ojt_data = User.objects.none()
                else:
                    # No imports for this year by this coordinator
                    ojt_data = User.objects.none()
                    print(f"DEBUG: Coordinator {coordinator_username} has no imports for year {year_int}")

        # Fallbacks to avoid empty UI and help coordinators verify recent imports
        # BUT: Only apply fallback for coordinator requests, NOT for admin requests
        # AND: Only show users from coordinator's imports
        if not ojt_data.exists() and coordinator_username:
            # 1) Prefer recently created/updated users from coordinator's imports
            try:
                from django.db.models import Q
                recent_since = timezone.now() - timedelta(days=1)
                
                # Build filter for coordinator's year+section combinations
                year_section_filters = Q()
                for (y, s) in coordinator_year_sections:
                    if s:
                        year_section_filters |= Q(academic_info__year_graduated=y, academic_info__section=s)
                    else:
                        year_section_filters |= Q(academic_info__year_graduated=y)
                
                if year_section_filters:
                    recent_users = (
                        User.objects
                        .filter(
                            year_section_filters,
                            updated_at__gte=recent_since,
                            account_type__ojt=True
                        )
                        .exclude(acc_username='1334335')  # Exclude Carlo Mendoza (4-B)
                        .exclude(acc_username=settings.DEFAULT_COORDINATOR_USERNAME)  # Exclude coordinator user
                        .exclude(f_name='Coordinator')  # Exclude any user with name "Coordinator"
                    .select_related(*select_related_fields)
                        .order_by('-updated_at', 'l_name', 'f_name')
                    )
                else:
                    recent_users = User.objects.none()
            except Exception:
                recent_users = User.objects.none()

            if recent_users.exists():
                ojt_data = recent_users
            # Don't show all OJT users as fallback - respect coordinator isolation

        ojt_list = []
        for ojt in ojt_data:
            # Debug: Check the actual values
            ojt_info = getattr(ojt, 'ojt_info', None)
            is_sent_to_admin_val = getattr(ojt_info, 'is_sent_to_admin', False) if ojt_info else False
            print(f"🔍 DEBUG Backend: User {ojt.f_name} {ojt.l_name} (ID: {ojt.user_id})")
            print(f"   OJT Info exists: {ojt_info is not None}")
            print(f"   is_sent_to_admin: {is_sent_to_admin_val} (type: {type(is_sent_to_admin_val)})")
            print(f"   Account Type: {getattr(ojt, 'account_type', None)}")
            account_type_debug = getattr(ojt, 'account_type', None)
            print(f"   Is Alumni (user=True): {getattr(account_type_debug, 'user', False) if account_type_debug else False}")
            
            # Debug company details
            employment_debug = getattr(ojt, 'employment', None)
            print(f"   Employment exists: {employment_debug is not None}")
            if employment_debug:
                print(f"   Company Address: {getattr(employment_debug, 'company_address', None)}")
                print(f"   Company Email: {getattr(employment_debug, 'company_email', None)}")
                print(f"   Company Contact: {getattr(employment_debug, 'company_contact', None)}")
                print(f"   Contact Person: {getattr(employment_debug, 'contact_person', None)}")
                print(f"   Position: {getattr(employment_debug, 'position', None)}")
            
            # Safe access to related objects with null checks
            profile = getattr(ojt, 'profile', None) if hasattr(ojt, 'profile') else None
            academic_info = getattr(ojt, 'academic_info', None) if hasattr(ojt, 'academic_info') else None
            employment = getattr(ojt, 'employment', None) if hasattr(ojt, 'employment') else None
            ojt_info = getattr(ojt, 'ojt_info', None) if hasattr(ojt, 'ojt_info') else None
            ojt_company_profile = None
            if ojt_company_profile_exists:
                try:
                    ojt_company_profile = ojt.ojt_company_profile
                except (AttributeError, OJTCompanyProfile.DoesNotExist):
                    ojt_company_profile = None
            account_type = getattr(ojt, 'account_type', None) if hasattr(ojt, 'account_type') else None
            initial_password = getattr(ojt, 'initial_password', None) if hasattr(ojt, 'initial_password') else None
            
            user_data = {
                'id': ojt.user_id,
                'ctu_id': ojt.acc_username,
                'name': f"{ojt.f_name} {ojt.l_name}",
                'first_name': ojt.f_name,
                'middle_name': ojt.m_name,
                'last_name': ojt.l_name,
                'gender': ojt.gender,
                'birthdate': getattr(profile, 'birthdate', None) if profile else None,
                'age': getattr(profile, 'calculated_age', None) if profile else None,
                'phone_number': getattr(profile, 'phone_num', None) if profile else None,
                'address': getattr(profile, 'address', None) if profile else None,
                'civil_status': getattr(profile, 'civil_status', None) if profile else None,
                'social_media': getattr(profile, 'social_media', None) if profile else None,
                'course': getattr(academic_info, 'program', None) if academic_info else None,
                # Use OJT Company Profile for OJT students, not EmploymentHistory
                'company': getattr(ojt_company_profile, 'company_name', None) if ojt_company_profile else None,
                'company_address': getattr(ojt_company_profile, 'company_address', None) if ojt_company_profile else None,
                'company_email': getattr(ojt_company_profile, 'company_email', None) if ojt_company_profile else None,
                'company_contact': getattr(ojt_company_profile, 'company_contact', None) if ojt_company_profile else None,
                'contact_person': getattr(ojt_company_profile, 'contact_person', None) if ojt_company_profile else None,
                'position': getattr(ojt_company_profile, 'position', None) if ojt_company_profile else None,
                'ojt_start_date': getattr(ojt_company_profile, 'start_date', None) if ojt_company_profile else None,
                'ojt_end_date': getattr(ojt_info, 'ojt_end_date', None) if ojt_info else None,
                'ojt_status': getattr(ojt_info, 'ojtstatus', None) or 'Pending' if ojt_info else 'Pending',
                'is_sent_to_admin': is_sent_to_admin_val,
                'is_alumni': getattr(account_type, 'user', False) if account_type else False,
                'batch_year': getattr(academic_info, 'year_graduated', None) if academic_info else None,
                'password': initial_password.get_plaintext() if initial_password else None,
            }
            
            print(f"🔍 DEBUG: Adding user data with company details:")
            print(f"   company_address: {user_data['company_address']}")
            print(f"   company_email: {user_data['company_email']}")
            print(f"   company_contact: {user_data['company_contact']}")
            print(f"   contact_person: {user_data['contact_person']}")
            print(f"   position: {user_data['position']}")
            
            ojt_list.append(user_data)

        response_data = {
            'success': True,
            'ojt_data': ojt_list
        }
        
        # Debug: Print the final response data
        print(f"🔍 DEBUG Final Response Data:")
        for i, user in enumerate(ojt_list):
            print(f"   User {i+1}: {user['name']} - is_sent_to_admin: {user['is_sent_to_admin']} (type: {type(user['is_sent_to_admin'])})")
        
        return JsonResponse(response_data)

    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"ERROR in ojt_by_year_view: {str(e)}")
        print(f"TRACEBACK: {error_traceback}")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# Clear OJT data for a specific batch year
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ojt_clear_view(request):
    try:
        data = json.loads(request.body or '{}')
        year = data.get('batch_year')
        if not year:
            return JsonResponse({'success': False, 'message': 'batch_year is required'}, status=400)

        try:
            import re
            match = re.search(r"(20\d{2})", str(year))
            year_int = int(match.group(1)) if match else int(str(year).strip())
        except Exception:
            return JsonResponse({'success': False, 'message': 'Invalid batch_year'}, status=400)

        # Delete AcademicInfo with that year and any OJTInfo for those users
        from apps.shared.models import AcademicInfo, OJTInfo, OJTImport
        with transaction.atomic():
            users_qs = User.objects.filter(academic_info__year_graduated=year_int)
            OJTInfo.objects.filter(user__in=users_qs).delete()
            AcademicInfo.objects.filter(user__in=users_qs, year_graduated=year_int).delete()
            # Remove import records for this batch so the card disappears
            OJTImport.objects.filter(batch_year=year_int).delete()

        return JsonResponse({'success': True, 'message': f'Cleared OJT data for batch {year_int}'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# OJT Company Statistics for coordinators
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ojt_company_statistics_view(request):
    """
    Returns company statistics with count of OJT students per company
    """
    try:
        coordinator_username = request.GET.get('coordinator', '')
        
        from apps.shared.models import OJTCompanyProfile
        from django.db.models import Count
        
        # Base query - get all OJT company profiles
        company_profiles = OJTCompanyProfile.objects.all()
        
        # Filter by coordinator if provided
        if coordinator_username:
            # Get OJT users managed by this coordinator
            # First get all imports by this coordinator to find which years/sections they manage
            from apps.shared.models import OJTImport
            coordinator_imports = OJTImport.objects.filter(coordinator=coordinator_username)
            
            # Get unique year+section combinations
            year_sections = set()
            for imp in coordinator_imports:
                year = getattr(imp, 'batch_year', None)
                section = getattr(imp, 'section', None)
                if year:
                    year_sections.add((year, section))
            
            # Filter users by these year+section combinations
            from django.db.models import Q
            year_section_filters = Q()
            for year, section in year_sections:
                if section:
                    year_section_filters |= Q(user__academic_info__year_graduated=year, user__academic_info__section=section)
                else:
                    year_section_filters |= Q(user__academic_info__year_graduated=year)
            
            if year_section_filters:
                company_profiles = company_profiles.filter(year_section_filters)
        
        # Group by company name and count
        company_stats = (
            company_profiles
            .exclude(company_name__isnull=True)
            .exclude(company_name='')
            .exclude(user__acc_username=settings.DEFAULT_COORDINATOR_USERNAME)  # Exclude coordinator users
            .values('company_name')
            .annotate(student_count=Count('id'))
            .order_by('-student_count', 'company_name')
        )
        
        # Format the response
        companies = []
        total_students = 0
        for stat in company_stats:
            companies.append({
                'company_name': stat['company_name'],
                'count': stat['student_count']
            })
            total_students += stat['student_count']
        
        return JsonResponse({
            'success': True,
            'companies': companies,
            'total_companies': len(companies),
            'total_students': total_students
        })
        
    except Exception as e:
        print(f"Error in ojt_company_statistics_view: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ojt_students_by_company_view(request):
    """
    Returns list of students for a specific company
    """
    try:
        company_name = request.GET.get('company', '')
        coordinator_username = request.GET.get('coordinator', '')
        
        if not company_name:
            return JsonResponse({'success': False, 'message': 'Company name is required'}, status=400)
        
        from apps.shared.models import EmploymentHistory
        
        print(f"🔍 Looking for company: '{company_name}'")
        print(f"🔍 Coordinator: '{coordinator_username}'")
        
        # Get all employment records for this company (without filtering by active status)
        all_employment_records = EmploymentHistory.objects.filter(
            company_name_current__iexact=company_name
        ).select_related('user', 'user__ojt_info', 'user__academic_info', 'user__account_type')
        
        print(f"📊 Found {all_employment_records.count()} total EmploymentHistory records for company '{company_name}'")
        
        # Filter by coordinator if provided (only for active students list)
        employment_records = all_employment_records
        if coordinator_username:
            from apps.shared.models import OJTImport
            coordinator_imports = OJTImport.objects.filter(coordinator=coordinator_username)
            
            # Get unique year+section combinations
            year_sections = set()
            for imp in coordinator_imports:
                year = getattr(imp, 'batch_year', None)
                section = getattr(imp, 'section', None)
                if year:
                    year_sections.add((year, section))
            
            # Filter by coordinator's year+section combinations
            from django.db.models import Q
            year_section_filters = Q()
            for (year, section) in year_sections:
                if section:
                    year_section_filters |= Q(user__academic_info__year_graduated=year, user__academic_info__section=section)
                else:
                    year_section_filters |= Q(user__academic_info__year_graduated=year)
            
            if year_section_filters:
                employment_records = employment_records.filter(year_section_filters)
                print(f"📊 After coordinator filter: {employment_records.count()} records")
        
        # Build student list (only active OJT students)
        students = []
        for emp in employment_records:
            user = emp.user
            ojt_info = getattr(user, 'ojt_info', None)
            
            # Only include active OJT students (not alumni)
            if user.account_type and user.account_type.ojt and (not hasattr(user, 'user_status') or getattr(user, 'user_status', '').lower() == 'active'):
                students.append({
                    'ctu_id': user.acc_username,
                    'first_name': user.f_name or '',
                    'last_name': user.l_name or '',
                    'company': emp.company_name_current or '',
                    'company_address': emp.company_address or '',
                    'company_email': emp.company_email or '',
                    'company_contact': emp.company_contact or '',
                    'contact_person': emp.contact_person or '',
                    'position': emp.position or '',
                    'status': ojt_info.ojtstatus if ojt_info else 'Not Started'
                })
                print(f"✅ Added student: {user.acc_username} with company data")
        
        print(f"📊 Active students found: {len(students)}")
        
        # Get company profile information (even if no active students)
        company_profile = None
        from apps.shared.models import OJTCompanyProfile
        from django.db.models import Q
        
        print(f"🔍 Building company profile...")
        
        # First, try to get from active students (if any)
        if students and len(students) > 0:
            company_profile = {
                'company_name': students[0].get('company', company_name),
                'company_address': students[0].get('company_address', '') or '',
                'company_email': students[0].get('company_email', '') or '',
                'company_contact': students[0].get('company_contact', '') or '',
                'contact_person': students[0].get('contact_person', '') or '',
                'position': students[0].get('position', '') or ''
            }
            print(f"✅ Got company profile from active students: {company_profile}")
        
        # If no profile from active students, try OJTCompanyProfile
        if not company_profile or (not company_profile.get('company_address') and not company_profile.get('company_email') and not company_profile.get('company_contact')):
            company_profiles = OJTCompanyProfile.objects.filter(
                company_name__iexact=company_name
            ).select_related('user', 'user__academic_info')
            
            # Filter by coordinator if provided
            if coordinator_username:
                from apps.shared.models import OJTImport
                coordinator_imports = OJTImport.objects.filter(coordinator=coordinator_username)
                
                # Get unique year+section combinations
                year_sections = set()
                for imp in coordinator_imports:
                    year = getattr(imp, 'batch_year', None)
                    section = getattr(imp, 'section', None)
                    if year:
                        year_sections.add((year, section))
                
                # Filter by coordinator's year+section combinations
                year_section_filters = Q()
                for year, section in year_sections:
                    if section:
                        year_section_filters |= Q(user__academic_info__year_graduated=year, user__academic_info__section=section)
                    else:
                        year_section_filters |= Q(user__academic_info__year_graduated=year)
                
                if year_section_filters:
                    company_profiles = company_profiles.filter(year_section_filters)
            
            # Get the first company profile with the most complete information
            for profile in company_profiles:
                if profile.company_address or profile.company_email or profile.company_contact or profile.contact_person:
                    company_profile = {
                        'company_name': profile.company_name or company_name,
                        'company_address': profile.company_address or '',
                        'company_email': profile.company_email or '',
                        'company_contact': profile.company_contact or '',
                        'contact_person': profile.contact_person or '',
                        'position': profile.position or ''
                    }
                    break
        
        # If still no profile, try EmploymentHistory (even for inactive students)
        if not company_profile or (not company_profile.get('company_address') and not company_profile.get('company_email') and not company_profile.get('company_contact') and not company_profile.get('contact_person')):
            print(f"🔍 No profile from active students, searching ALL EmploymentHistory records...")
            
            # Use the all_employment_records we already fetched (includes inactive users)
            print(f"📊 Checking {all_employment_records.count()} EmploymentHistory records...")
            
            # Try to find one with company details
            for idx, emp_record in enumerate(all_employment_records):
                print(f"   Record {idx+1}: user={emp_record.user.acc_username}, address={bool(emp_record.company_address)}, email={bool(emp_record.company_email)}, contact={bool(emp_record.company_contact)}, person={bool(emp_record.contact_person)}")
                if emp_record.company_address or emp_record.company_email or emp_record.company_contact or emp_record.contact_person:
                    company_profile = {
                        'company_name': emp_record.company_name_current or company_name,
                        'company_address': emp_record.company_address or '',
                        'company_email': emp_record.company_email or '',
                        'company_contact': emp_record.company_contact or '',
                        'contact_person': emp_record.contact_person or '',
                        'position': emp_record.position or ''
                    }
                    print(f"✅ Found company profile from EmploymentHistory record {idx+1}: {company_profile}")
                    break
            
            # If still nothing, just get the first one (even if empty)
            if (not company_profile or (not company_profile.get('company_address') and not company_profile.get('company_email') and not company_profile.get('company_contact'))) and all_employment_records.exists():
                first_emp = all_employment_records.first()
                company_profile = {
                    'company_name': first_emp.company_name_current or company_name,
                    'company_address': first_emp.company_address or '',
                    'company_email': first_emp.company_email or '',
                    'company_contact': first_emp.company_contact or '',
                    'contact_person': first_emp.contact_person or '',
                    'position': first_emp.position or ''
                }
                print(f"⚠️ Using first EmploymentHistory record (may be empty): {company_profile}")
        
        # If still no profile, create empty structure
        if not company_profile:
            company_profile = {
                'company_name': company_name,
                'company_address': '',
                'company_email': '',
                'company_contact': '',
                'contact_person': '',
                'position': ''
            }
        
        # Debug logging
        print(f"📊 Company Profile Final Result for '{company_name}':")
        print(f"   - Students found: {len(students)}")
        print(f"   - Company profile: {company_profile}")
        print(f"   - Has address: {bool(company_profile.get('company_address'))}")
        print(f"   - Has email: {bool(company_profile.get('company_email'))}")
        print(f"   - Has contact: {bool(company_profile.get('company_contact'))}")
        print(f"   - Has contact person: {bool(company_profile.get('contact_person'))}")
        
        # Ensure company_profile is always a dict, never None
        if company_profile is None:
            company_profile = {
                'company_name': company_name,
                'company_address': '',
                'company_email': '',
                'company_contact': '',
                'contact_person': '',
                'position': ''
            }
        
        response_data = {
            'success': True,
            'students': students,
            'count': len(students),
            'company_profile': company_profile  # Always include company profile
        }
        
        print(f"📤 PRE-RESPONSE CHECK:")
        print(f"   - response_data keys: {list(response_data.keys())}")
        print(f"   - company_profile in response_data: {'company_profile' in response_data}")
        print(f"   - company_profile value: {response_data.get('company_profile')}")
        print(f"   - company_profile type: {type(response_data.get('company_profile'))}")
        print(f"📤 Sending response with company_profile: {response_data['company_profile']}")
        
        return JsonResponse(response_data, safe=False)
        
    except Exception as e:
        print(f"Error in ojt_students_by_company_view: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

# Get all OJT students for a coordinator (for export to update template)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_ojt_students_view(request):
    """
    Returns list of all OJT students for a coordinator
    Used for exporting student list to fill company info
    """
    try:
        coordinator_username = request.GET.get('coordinator', '')
        section_filter = request.GET.get('section', '')  # Optional section filter
        
        if not coordinator_username:
            return JsonResponse({'success': False, 'message': 'Coordinator username is required'}, status=400)
        
        from apps.shared.models import User, OJTImport, AcademicInfo, OJTInfo
        
        # Get all imports by this coordinator
        coordinator_imports = OJTImport.objects.filter(coordinator=coordinator_username)
        
        # Get unique year+section combinations
        year_sections = set()
        for imp in coordinator_imports:
            year = getattr(imp, 'batch_year', None)
            section = getattr(imp, 'section', None)
            if year and section:
                year_sections.add((year, section))
        
        # Get all OJT users matching these year+section combinations
        students_data = []
        for year, section in year_sections:
            # Filter by section if provided
            if section_filter and section != section_filter:
                continue
                
            users = User.objects.filter(
                account_type__ojt=True,
                academic_info__year_graduated=year,
                academic_info__section=section,
                user_status__iexact='Active'  # Only active students
            ).select_related('ojt_info', 'academic_info')
            
            for user in users:
                students_data.append({
                    'ctu_id': user.acc_username,
                    'first_name': user.f_name or '',
                    'last_name': user.l_name or '',
                    'section': getattr(user.academic_info, 'section', '') if hasattr(user, 'academic_info') else '',
                    'status': getattr(user.ojt_info, 'ojtstatus', 'Ongoing') if hasattr(user, 'ojt_info') else 'Ongoing',
                })
        
        return JsonResponse({
            'success': True,
            'students': students_data,
            'count': len(students_data)
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# Update OJT status for a specific user
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ojt_status_update_view(request):
    try:
        data = json.loads(request.body or '{}')
        user_id = data.get('user_id')
        status_val = (data.get('status') or '').strip()
        print(f"OJT Status Update - User ID: {user_id}, Status: {status_val}")

        if not user_id or not status_val:
            print("Missing user_id or status")
            return JsonResponse({'success': False, 'message': 'user_id and status are required'}, status=400)
        
        try:
            user = User.objects.get(user_id=int(user_id))
            print(f"Found user: {user.acc_username}")
        except User.DoesNotExist:
            print(f"User not found with ID: {user_id}")
            return JsonResponse({'success': False, 'message': 'User not found'}, status=404)
        
        from apps.shared.models import OJTInfo, OJTImport
        
        # Allow coordinators to set status to "Completed" before sending to admin
        if status_val == 'Completed':
            print(f"🔍 DEBUG: User {user.acc_username} setting status to Completed - allowing this change")
        
        ojt_info, created = OJTInfo.objects.get_or_create(user=user)
        print(f"OJTInfo created: {created}, existing ojtstatus: {ojt_info.ojtstatus}")
        ojt_info.ojtstatus = status_val
        ojt_info.save()
        print(f"Updated ojtstatus to: {ojt_info.ojtstatus}")
        return JsonResponse({'success': True})
    except Exception as e:
        print(f"Error in ojt_status_update_view: {str(e)}")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# Clear ALL OJT-related data imported (OJT users, OJTInfo, OJTImport, and AcademicInfo for OJT users)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ojt_clear_all_view(request):
    try:
        from apps.shared.models import (
            OJTImport, OJTInfo, AcademicInfo, OJTCompanyProfile,
            UserProfile, EmploymentHistory, UserInitialPassword, SendDate
        )
        with transaction.atomic():
            # Identify OJT users
            ojt_users = User.objects.filter(account_type__ojt=True)
            user_count = ojt_users.count()
            
            print(f"🗑️ Clearing all OJT data for {user_count} OJT users...")
            
            # Delete all related data for OJT users
            ojt_info_count = OJTInfo.objects.filter(user__in=ojt_users).delete()[0]
            ojt_company_count = OJTCompanyProfile.objects.filter(user__in=ojt_users).delete()[0]
            academic_count = AcademicInfo.objects.filter(user__in=ojt_users).delete()[0]
            profile_count = UserProfile.objects.filter(user__in=ojt_users).delete()[0]
            employment_count = EmploymentHistory.objects.filter(user__in=ojt_users).delete()[0]
            password_count = UserInitialPassword.objects.filter(user__in=ojt_users).delete()[0]
            
            # Delete the OJT users themselves
            ojt_users.delete()
            
            # Remove import history to hide cards
            import_count = OJTImport.objects.all().delete()[0]
            
            # Clear all scheduled send dates
            send_date_count = SendDate.objects.all().delete()[0]
            
            print(f"✅ Deleted: {user_count} users, {ojt_info_count} OJT info, {ojt_company_count} company profiles")
            print(f"   {academic_count} academic records, {profile_count} user profiles")
            print(f"   {employment_count} employment records, {password_count} passwords")
            print(f"   {import_count} import records, {send_date_count} send date schedules")
            
        return JsonResponse({
            'success': True, 
            'message': f'All OJT data cleared successfully! Deleted {user_count} OJT users and all related data.',
            'deleted_counts': {
                'users': user_count,
                'ojt_info': ojt_info_count,
                'company_profiles': ojt_company_count,
                'academic_records': academic_count,
                'user_profiles': profile_count,
                'employment_records': employment_count,
                'passwords': password_count,
                'import_records': import_count,
                'send_dates': send_date_count
            }
        })
    except Exception as e:
        import traceback
        print(f"❌ Error clearing OJT data: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# Coordinator requests: send completed list to admin (no-op storage, returns counts)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def send_completed_to_admin_view(request):
    try:
        data = json.loads(request.body or '{}')
        year = data.get('year')
        user_ids = data.get('user_ids') or []

        # Compute how many completed for the given year if provided; otherwise all
        users_qs = User.objects.all().select_related('academic_info', 'ojt_info')
        year_int = None
        if year is not None and str(year).strip() != '':
            try:
                import re
                match = re.search(r"(20\d{2})", str(year))
                year_int = int(match.group(1)) if match else int(str(year).strip())
            except Exception:
                year_int = None
        if year_int is not None:
            users_qs = users_qs.filter(academic_info__year_graduated=year_int)

        # If user_ids are provided, filter by those specific users (this ensures section-specific sending)
        if user_ids:
            users_qs = users_qs.filter(user_id__in=[int(x) for x in user_ids])
            print(f"🔍 DEBUG: Filtering by specific user IDs: {user_ids}")
        else:
            print(f"🔍 DEBUG: No user IDs provided, using all users for year {year_int}")

        completed_count = users_qs.filter(ojt_info__ojtstatus='Completed').count()
        print(f"🔍 DEBUG: Found {completed_count} completed users to send to admin")

        # Mark individual users as sent to admin
        from apps.shared.models import OJTInfo
        from django.utils import timezone
        
        sent_users_count = 0
        completed_users = users_qs.filter(ojt_info__ojtstatus='Completed')
        print(f"🔍 DEBUG: Processing {completed_users.count()} completed users")
        
        for user in completed_users:
            # Skip users who are already alumni (already approved)
            if getattr(user.account_type, 'user', False):
                print(f"Skipping already approved user: {user.acc_username}")
                continue
                
            try:
                # Debug: Show user details including section
                section = getattr(user.academic_info, 'section', 'Unknown') if hasattr(user, 'academic_info') and user.academic_info else 'Unknown'
                print(f"🔍 DEBUG: Processing user {user.acc_username} (ID: {user.user_id}) from section {section}")
                
                ojt_info, created = OJTInfo.objects.get_or_create(user=user)
                ojt_info.is_sent_to_admin = True
                ojt_info.sent_to_admin_date = timezone.now()
                ojt_info.save()
                sent_users_count += 1
                print(f"Marked user {user.acc_username} as sent to admin")
            except Exception as e:
                print(f"Error marking user {user.acc_username} as sent to admin: {e}")

        # Mark the specific sections as requested by coordinator
        try:
            from apps.shared.models import OJTImport
            coord_name = getattr(getattr(request, 'user', None), 'acc_username', None) or getattr(getattr(request, 'user', None), 'username', '') or ''
            
            # Get the sections of the users that were sent to admin
            sent_sections = set()
            for user in completed_users:
                if hasattr(user, 'academic_info') and user.academic_info and user.academic_info.section:
                    sent_sections.add(user.academic_info.section)
            
            print(f"🔍 DEBUG: Updating OJTImport status to 'Requested' for sections: {sent_sections}")
            
            # Update existing OJTImport records for the sent sections
            for section in sent_sections:
                try:
                    obj = OJTImport.objects.get(batch_year=year_int, section=section)
                    obj.status = 'Requested'
                    obj.coordinator = coord_name or obj.coordinator
                    obj.records_imported = sent_users_count
                    obj.save()
                    print(f"🔍 DEBUG: Updated OJTImport for year {year_int}, section {section} to status 'Requested'")
                except OJTImport.DoesNotExist:
                    print(f"🔍 DEBUG: No OJTImport record found for year {year_int}, section {section}")
                    # Create a new record if none exists
                    OJTImport.objects.create(
                        batch_year=year_int,
                        section=section,
                        coordinator=coord_name,
                        course='BSIT',  # Default course
                        file_name='send_to_admin',
                        records_imported=sent_users_count,
                        status='Requested',
                    )
                    print(f"🔍 DEBUG: Created new OJTImport record for year {year_int}, section {section}")
        except Exception as e:
            print(f"Error updating OJTImport: {e}")

        return JsonResponse({'success': True, 'completed_count': sent_users_count})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# Coordinator requests count for admin dashboard
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def coordinator_requests_count_view(request):
    try:
        year = request.GET.get('year')
        # Count distinct batches requested by coordinators
        from apps.shared.models import OJTImport
        qs = OJTImport.objects.filter(status='Requested')
        if year is not None and str(year).strip() != '':
            try:
                import re
                match = re.search(r"(20\d{2})", str(year))
                year_int = int(match.group(1)) if match else int(str(year).strip())
                qs = qs.filter(batch_year=year_int)
            except Exception:
                pass
        requested_years = set(qs.values_list('batch_year', flat=True).distinct())

        # Fallback: also include any batches that currently have at least one Completed student (exclude alumni)
        try:
            users_qs = User.objects.filter(
                ojt_info__ojtstatus='Completed',
                ojt_info__is_sent_to_admin=True  # Only count students sent to admin
            ).exclude(
                account_type__user=True  # Exclude alumni (already approved)
            ).select_related('academic_info')
            if year is not None and str(year).strip() != '':
                try:
                    users_qs = users_qs.filter(academic_info__year_graduated=year_int)
                except Exception:
                    pass
            completed_years = set(users_qs.values_list('academic_info__year_graduated', flat=True).distinct())
            requested_years = requested_years.union({y for y in completed_years if y is not None})
        except Exception:
            pass

        count_val = len({y for y in requested_years if y is not None})
        return JsonResponse({'success': True, 'count': count_val})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# List requested batches with simple counts
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def coordinator_requests_list_view(request):
    try:
        from apps.shared.models import OJTImport
        items = []
        
        # Debug: Check all OJTImport records
        all_imports = OJTImport.objects.all()
        print(f"DEBUG: Total OJTImport records: {all_imports.count()}")
        for imp in all_imports:
            print(f"DEBUG: Year: {imp.batch_year}, Status: {imp.status}, Course: {imp.course}")
        
        # Base: group Requested imports by year and course, take max count to avoid duplicates
        try:
            from django.db.models import Max, Value as V
            from django.db.models.functions import Coalesce
            requested_imports = OJTImport.objects.filter(status='Requested')
            print(f"🔍 DEBUG coordinator_requests_list_view: Found {requested_imports.count()} Requested imports")
            
            # Debug: Show all OJTImport records
            all_imports = OJTImport.objects.all()
            print(f"🔍 DEBUG coordinator_requests_list_view: Total OJTImport records: {all_imports.count()}")
            for imp in all_imports:
                print(f"🔍 DEBUG coordinator_requests_list_view: Year: {imp.batch_year}, Status: {imp.status}, Course: {imp.course}")
            
            # Count actual unapproved students instead of using records_imported
            for imp in requested_imports:
                year = imp.batch_year
                course = imp.course or 'OJT'  # Default to 'OJT' if course is empty
                
                # Count students who are completed, sent to admin, but not yet alumni for this year/course
                unapproved_count = User.objects.filter(
                    academic_info__year_graduated=year,
                    academic_info__program=course,
                    ojt_info__ojtstatus='Completed',
                    ojt_info__is_sent_to_admin=True  # Only count students sent to admin
                ).exclude(
                    account_type__user=True  # Exclude alumni (already approved)
                ).count()
                
                print(f"🔍 DEBUG: Year {year}, Program {course} - Unapproved count: {unapproved_count}")
                
                # Only include if there are actually unapproved students
                if unapproved_count > 0:
                    items.append({
                        'batch_year': year,
                        'course': course,
                        'count': unapproved_count
                    })
        except Exception as e:
            print(f"DEBUG: Exception in grouped query: {e}")
            # Fallback: if aggregation not available, compute max per year and course in Python
            by_year_course = {}
            for imp in OJTImport.objects.filter(status='Requested').order_by('-batch_year'):
                year = getattr(imp, 'batch_year', None)
                course = getattr(imp, 'course', '')
                count_val = getattr(imp, 'records_imported', 0) or 0
                if year is None:
                    continue
                key = (year, course)
                by_year_course[key] = max(by_year_course.get(key, 0), count_val)
            for (y, course), c in by_year_course.items():
                items.append({'batch_year': y, 'course': course, 'count': c})

        # Fallback: for any batch lacking a Requested import but has Completed users sent to admin
        # BUT only if there's no Approved OJTImport for that batch
        try:
            completed_years_courses = (
                User.objects.filter(
                    ojt_info__ojtstatus='Completed',
                    ojt_info__is_sent_to_admin=True  # Only include students sent to admin
                )
                .exclude(account_type__user=True)  # Exclude alumni
                .values('academic_info__year_graduated', 'academic_info__program')
                .annotate()
            )
            existing_keys = {(it['batch_year'], it.get('course', '')) for it in items if it.get('batch_year') is not None}
            
            # Get all approved batches to exclude them from fallback
            approved_batches = set(OJTImport.objects.filter(status='Approved').values_list('batch_year', flat=True))
            print(f"DEBUG: Approved batches: {approved_batches}")
            print(f"DEBUG: Existing keys from main query: {existing_keys}")
            
            for row in completed_years_courses:
                y = row.get('academic_info__year_graduated')
                course = row.get('academic_info__program', '') or 'OJT'  # Default to 'OJT' if empty
                print(f"DEBUG: Checking completed year {y}, course {course}")
                if y and (y, course) not in existing_keys and y not in approved_batches:
                    # Count only students who are completed AND sent to admin (not yet approved)
                    count = User.objects.filter(
                        academic_info__year_graduated=y, 
                        academic_info__program=course,
                        ojt_info__ojtstatus='Completed',
                        ojt_info__is_sent_to_admin=True  # Only show students sent to admin
                    ).exclude(
                        account_type__user=True  # Exclude alumni (already approved)
                    ).count()
                    print(f"DEBUG: Adding fallback item for year {y}, course {course}, count {count}")
                    if count > 0:  # Only add if there are actually students to show
                        items.append({'batch_year': y, 'course': course, 'count': count})
                else:
                    print(f"DEBUG: Skipping year {y}, course {course} - existing_keys: {(y, course) in existing_keys}, approved: {y in approved_batches}")
        except Exception as e:
            print(f"DEBUG: Exception in fallback: {e}")
            pass

        # Sort newest first and ensure unique year-course combinations
        dedup = {}
        for it in items:
            y = it.get('batch_year')
            course = it.get('course', '')
            if y is None:
                continue
            key = (y, course)
            dedup[key] = max(dedup.get(key, 0), int(it.get('count') or 0))
        items = [{'batch_year': y, 'course': course, 'count': c} for (y, course), c in dedup.items()]
        items.sort(key=lambda x: int(x['batch_year']), reverse=True)
        return JsonResponse({'success': True, 'items': items})
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"❌ ERROR in coordinator_requests_list_view: {str(e)}")
        print(f"❌ TRACEBACK: {error_traceback}")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)



# Admin approves a coordinator request for a given batch year
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def approve_coordinator_request_view(request):
    try:
        data = json.loads(request.body or '{}')
        year = data.get('year')
        if year is None:
            return JsonResponse({'success': False, 'message': 'Missing year'}, status=400)

        from apps.shared.models import OJTImport
        # Normalize year to int if possible
        try:
            year_int = int(str(year))
        except Exception:
            return JsonResponse({'success': False, 'message': 'Invalid year'}, status=400)

        updated = OJTImport.objects.filter(batch_year=year_int, status='Requested').update(status='Approved')
        return JsonResponse({'success': True, 'approved': updated, 'year': year_int})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def get_coordinator_sections_view(request):
    """Get sections that a coordinator has previously imported"""
    try:
        coordinator_username = request.GET.get('coordinator', '') or request.POST.get('coordinator', '')
        
        if not coordinator_username:
            return JsonResponse({'success': False, 'message': 'Coordinator username required'}, status=400)
        
        # Get unique sections from OJTImport records for this coordinator
        from apps.shared.models import OJTImport
        sections = OJTImport.objects.filter(
            coordinator=coordinator_username,
            section__isnull=False
        ).exclude(
            section=''
        ).values_list('section', flat=True).distinct().order_by('section')
        
        # Also get sections from actual user records for this coordinator
        from apps.shared.models import User
        user_sections = User.objects.filter(
            account_type__ojt=True,
            academic_info__isnull=False
        ).exclude(
            academic_info__section__isnull=True
        ).exclude(
            academic_info__section=''
        ).values_list('academic_info__section', flat=True).distinct().order_by('academic_info__section')
        
        # Combine and deduplicate sections
        all_sections = list(set(list(sections) + list(user_sections)))
        all_sections.sort()
        
        return JsonResponse({
            'success': True,
            'sections': all_sections
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def available_years_view(request):
    """Get all available graduation years from AcademicInfo"""
    try:
        from apps.shared.models import AcademicInfo
        
        # Get all unique graduation years, ordered by year descending
        years = AcademicInfo.objects.filter(
            year_graduated__isnull=False
        ).values_list('year_graduated', flat=True).distinct().order_by('-year_graduated')
        
        # Convert to list and filter out None values
        years_list = [year for year in years if year is not None]
        
        # If no years exist in database, provide a default range of recent years
        if not years_list:
            current_year = 2024
            years_list = list(range(current_year, current_year - 10, -1))  # 2024 down to 2015
        
        return JsonResponse({
            'success': True,
            'years': years_list
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)
def approve_ojt_to_alumni_view(request):
    """Approve completed OJT students to become alumni with password generation"""
    try:
        print("approve_ojt_to_alumni_view: start")
        data = json.loads(request.body or '{}')
        year = data.get('year')
        if year is None:
            return JsonResponse({'success': False, 'message': 'Missing year'}, status=400)

        from apps.shared.models import User, AccountType, OJTInfo, UserInitialPassword, AcademicInfo
        from django.db import transaction
        import secrets
        import string
        from django.contrib.auth.hashers import make_password

        # Normalize year to int if possible
        try:
            year_int = int(str(year))
        except Exception as e:
            print(f"approve_ojt_to_alumni_view: invalid year {year} err={e}")
            return JsonResponse({'success': False, 'message': 'Invalid year'}, status=400)

        # Get an alumni account type (user=True). If duplicates exist, take the first; create if none.
        try:
            alumni_type = AccountType.objects.filter(user=True).first()
            if not alumni_type:
                alumni_type = AccountType.objects.create(user=True, admin=False, peso=False, coordinator=False, ojt=False)
        except Exception:
            alumni_type = AccountType.objects.filter(user=True).first() or AccountType.objects.create(user=True, admin=False, peso=False, coordinator=False, ojt=False)

        # Find completed OJT students for this year who were sent to admin and haven't been converted to alumni yet
        completed_ojt_users = User.objects.filter(
            account_type__ojt=True,
            ojt_info__ojtstatus='Completed',
            ojt_info__is_sent_to_admin=True,  # Only approve students who were sent to admin
            academic_info__year_graduated=year_int
        ).exclude(
            # Exclude users who are already alumni
            account_type__user=True
        ).select_related('ojt_info', 'academic_info')

        print(f"Found {completed_ojt_users.count()} completed OJT students for year {year_int}")
        if not completed_ojt_users.exists():
            return JsonResponse({
                'success': False, 
                'message': f'No completed OJT students found for year {year_int}'
            }, status=400)

        approved_count = 0
        batch_created = False
        errors = []

        print(f"approve_ojt_to_alumni_view: candidates={completed_ojt_users.count()}")
        with transaction.atomic():
            # Check if alumni batch already exists
            existing_alumni = User.objects.filter(
                account_type__user=True,
                academic_info__year_graduated=year_int
            ).exists()

            if not existing_alumni:
                batch_created = True

            # Remove the coordinator request card after approval
            from apps.shared.models import OJTImport
            print(f"🔍 DEBUG: Before approval - checking OJTImport records for year {year_int}")
            requested_before = OJTImport.objects.filter(batch_year=year_int, status='Requested')
            print(f"🔍 DEBUG: Found {requested_before.count()} records with status 'Requested' for year {year_int}")
            
            updated_imports = OJTImport.objects.filter(batch_year=year_int, status='Requested').update(status='Approved')
            print(f"🔍 DEBUG: Updated {updated_imports} OJTImport records from Requested to Approved for year {year_int}")
            
            # Verify the update
            requested_after = OJTImport.objects.filter(batch_year=year_int, status='Requested')
            approved_after = OJTImport.objects.filter(batch_year=year_int, status='Approved')
            print(f"🔍 DEBUG: After update - Requested: {requested_after.count()}, Approved: {approved_after.count()}")

            for user in completed_ojt_users:
                try:
                    print(f"processing user_id={user.user_id} username={user.acc_username}")
                    
                    # Update user to alumni account type (keep existing password)
                    user.account_type = alumni_type
                    user.user_status = 'active'
                    # Do NOT update password - keep the existing OJT password
                    user.save()

                    # Reactivate first-login flag so alumni must change the coordinator-issued password
                    ensure_initial_password_active(user)

                    # Clear sent to admin flag since user is now approved
                    if hasattr(user, 'ojt_info') and user.ojt_info:
                        user.ojt_info.is_sent_to_admin = False
                        user.ojt_info.save()

                    # Do NOT create/update UserInitialPassword - keep existing password

                    # Ensure academic info year_graduated is set
                    if hasattr(user, 'academic_info') and user.academic_info:
                            if not getattr(user.academic_info, 'year_graduated', None):
                                user.academic_info.year_graduated = year_int
                            user.academic_info.save()

                    # Create TrackerData record for newly approved alumni so they appear in statistics
                    from apps.shared.models import TrackerData
                    TrackerData.objects.get_or_create(
                        user=user,
                        defaults={
                            'q_employment_status': None,  # Will be 'pending' until they fill tracker
                            'tracker_submitted_at': None
                        }
                    )

                    # Do NOT include password in response - user keeps existing password

                    approved_count += 1
                except Exception as conv_e:
                    import traceback
                    traceback.print_exc()
                    errors.append({'user_id': user.user_id, 'username': user.acc_username, 'error': str(conv_e)})

        return JsonResponse({
            'success': True if approved_count > 0 else False,
            'approved': approved_count,
            'year': year_int,
            'batch_created': batch_created,
            'batch_year': str(year_int),
            'message': f'Successfully approved {approved_count} OJT student(s) to alumni. They keep their existing passwords.',
            'errors': errors
        }, status=200 if approved_count > 0 else 400)

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"approve_ojt_to_alumni_view: ERROR {e}")
        # Return a 200 with success False so the UI can show the message
        return JsonResponse({'success': False, 'message': str(e)}, status=200)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def approve_individual_ojt_to_alumni_view(request):
    """Approve a single OJT student to become alumni with password generation"""
    try:
        data = json.loads(request.body or '{}')
        user_id = data.get('user_id')
        if user_id is None:
            return JsonResponse({'success': False, 'message': 'Missing user_id'}, status=400)

        from apps.shared.models import User, AccountType, OJTInfo, UserInitialPassword, AcademicInfo
        from django.db import transaction
        import secrets
        import string
        from django.contrib.auth.hashers import make_password

        try:
            user = User.objects.get(user_id=int(user_id))
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'User not found'}, status=404)

        # Check if user is already an alumni
        if user.account_type and user.account_type.user:
            return JsonResponse({
                'success': False, 
                'message': 'User is already an alumni'
            }, status=400)
        
        # Check if user was sent to admin
        if not hasattr(user, 'ojt_info') or not user.ojt_info or not user.ojt_info.is_sent_to_admin:
            return JsonResponse({
                'success': False, 
                'message': 'User was not sent to admin for approval'
            }, status=400)

        # Check if user has OJT info and is completed/approved
        try:
            ojt_info = user.ojt_info
            if ojt_info.ojtstatus not in ['Completed', 'Approved']:
                return JsonResponse({
                    'success': False, 
                    'message': f'User OJT status is {ojt_info.ojtstatus}, must be Completed or Approved'
                }, status=400)
        except OJTInfo.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'User has no OJT information'}, status=400)

        # Get an alumni account type (user=True). If duplicates exist, take the first; create if none.
        try:
            alumni_type = AccountType.objects.filter(user=True).first()
            if not alumni_type:
                alumni_type = AccountType.objects.create(user=True, admin=False, peso=False, coordinator=False, ojt=False)
        except Exception:
            alumni_type = AccountType.objects.filter(user=True).first() or AccountType.objects.create(user=True, admin=False, peso=False, coordinator=False, ojt=False)

        # Get batch year from academic info (use year_graduated)
        try:
            batch_year = getattr(user.academic_info, 'year_graduated', None)
            if not batch_year:
                return JsonResponse({'success': False, 'message': 'User has no batch year'}, status=400)
        except AcademicInfo.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'User has no academic information'}, status=400)

        with transaction.atomic():
            # Check if alumni batch already exists (query by year_graduated)
            existing_alumni = User.objects.filter(
                account_type__user=True,
                academic_info__year_graduated=batch_year
            ).exists()

            batch_created = not existing_alumni

            # Update user to alumni account type (keep existing password)
            user.account_type = alumni_type
            user.user_status = 'active'
            # Do NOT update password - keep the existing OJT password
            user.save()

            # Do NOT create/update UserInitialPassword - keep existing password
            ensure_initial_password_active(user)

            # Ensure academic info year_graduated is set
            if hasattr(user, 'academic_info') and user.academic_info:
                if not getattr(user.academic_info, 'year_graduated', None):
                    user.academic_info.year_graduated = batch_year
                    user.academic_info.save()

            # Create TrackerData record for newly approved alumni so they appear in statistics
            from apps.shared.models import TrackerData
            TrackerData.objects.get_or_create(
                user=user,
                defaults={
                    'q_employment_status': None,  # Will be 'pending' until they fill tracker
                    'tracker_submitted_at': None
                }
            )

        return JsonResponse({
            'success': True,
            'approved': 1,
            'year': batch_year,
            'batch_created': batch_created,
            'batch_year': str(batch_year),
            'message': 'Successfully approved OJT student to alumni. User keeps existing password.'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@api_view(["GET","PUT"])
@permission_classes([IsAuthenticated])
def profile_bio_view(request, user_id):
    try:
        user = User.objects.get(user_id=user_id)
        profile = getattr(user, 'profile', None)
        if profile is None:
            from apps.shared.models import UserProfile
            profile, _ = UserProfile.objects.get_or_create(user=user)
        if request.method == "GET":
            return JsonResponse({'profile_bio': profile.profile_bio or ''})
        elif request.method == "PUT":
            data = json.loads(request.body)
            profile.profile_bio = data.get('profile_bio', '')
            profile.save()
            return JsonResponse({'profile_bio': profile.profile_bio})
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)

@api_view(['PUT'])
@parser_classes([MultiPartParser])
@permission_classes([IsAuthenticated])
def update_alumni_profile(request):
    user_id = request.GET.get('user_id')
    if not user_id:
        return Response({'message': 'Missing user_id'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(user_id=user_id)
        from apps.shared.models import UserProfile
        profile, _ = UserProfile.objects.get_or_create(user=user)

        bio = request.data.get('bio')
        if bio is not None:
            profile.profile_bio = bio

        if 'profile_pic' in request.FILES:
            profile.profile_pic = request.FILES['profile_pic']

        profile.save()

        return Response({
            'user': {
                'id': user.user_id,
                'name': f"{user.f_name} {user.m_name or ''} {user.l_name}".strip(),
                'profile_pic': profile.profile_pic.url if profile.profile_pic else None,
                'bio': profile.profile_bio,
            }
        })

    except User.DoesNotExist:
        return Response({'message': 'User not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def alumni_profile_view(request, user_id):
    """Get and update alumni profile data for Settings page."""
    try:
        logger.info(f"alumni_profile_view called for user_id: {user_id}, request.user: {request.user.user_id}")
        
        user = User.objects.select_related('profile').get(user_id=user_id)
        # Ensure user has a profile, create one if it doesn't exist
        if not hasattr(user, 'profile') or not user.profile:
            from apps.shared.models import UserProfile
            UserProfile.objects.create(user=user)
            user.refresh_from_db()
        
        # For GET requests, allow any authenticated user to view profiles
        # For PUT requests, only allow users to edit their own profile or admins to edit any profile
        if request.method == 'PUT' and request.user.user_id != user_id and not request.user.account_type.admin:
            logger.warning(f"Permission denied: request.user {request.user.user_id} trying to edit user {user_id}")
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        if request.method == 'GET':
            # Record recent search when viewing someone else's profile
            try:
                viewer_id = getattr(request.user, 'user_id', None) or getattr(request.user, 'id', None)
                if viewer_id and int(viewer_id) != int(user_id):
                    try:
                        from apps.shared.models import RecentSearch
                        RecentSearch.objects.filter(owner=request.user, searched_user=user).delete()
                        RecentSearch.objects.create(owner=request.user, searched_user=user)
                        logger.info("alumni_profile_view recent search created owner=%s searched_user=%s", viewer_id, user.user_id)
                    except Exception as e:
                        logger.warning("alumni_profile_view recent search insert skipped: %s", e)
            except Exception:
                pass

            # Return profile data in the format expected by Settings.tsx
            profile_data = {
                'user_id': user.user_id,
                'f_name': user.f_name or '',
                'l_name': user.l_name or '',
                'm_name': user.m_name or '',
                'civil_status': user.profile.civil_status if hasattr(user, 'profile') and user.profile else '',
                'contact_number': user.profile.phone_num if hasattr(user, 'profile') and user.profile else '',
                'email': user.profile.email if hasattr(user, 'profile') and user.profile else '',
                'address': user.profile.address if hasattr(user, 'profile') and user.profile else '',
                'home_address': user.profile.home_address if hasattr(user, 'profile') and user.profile else '',
                'social_media': user.profile.social_media if hasattr(user, 'profile') and user.profile else '',
                'profile_bio': user.profile.profile_bio if hasattr(user, 'profile') and user.profile else '',
                'profile_pic': build_profile_pic_url(user) if hasattr(user, 'profile') and user.profile else "",
                'account_type': {
                    'admin': getattr(user.account_type, 'admin', False),
                    'peso': getattr(user.account_type, 'peso', False),
                    'ccict': getattr(user.account_type, 'ccict', False),
                    'user': getattr(user.account_type, 'user', False),
                    'ojt': getattr(user.account_type, 'ojt', False),
                    'coordinator': getattr(user.account_type, 'coordinator', False),
                }
            }
            return JsonResponse(profile_data)
            
        elif request.method == 'PUT':
            data = json.loads(request.body)
            
            # Update User table fields
            if 'f_name' in data:
                user.f_name = data['f_name']
            if 'm_name' in data:
                user.m_name = data['m_name']
            if 'l_name' in data:
                user.l_name = data['l_name']
            user.save()
            
            # Update UserProfile table fields
            from apps.shared.models import UserProfile
            profile, created = UserProfile.objects.get_or_create(user=user)
            
            if 'contact_number' in data:
                profile.phone_num = data['contact_number']
            if 'email' in data:
                profile.email = data['email']
            if 'address' in data:
                profile.address = data['address']
            if 'home_address' in data:
                profile.home_address = data['home_address']
            if 'civil_status' in data:
                profile.civil_status = data['civil_status']
            if 'social_media' in data:
                profile.social_media = data['social_media']
            # PESO: update partnered companies list
            
            profile.save()
            
            return JsonResponse({'message': 'Profile updated successfully'})
            
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def alumni_employment_view(request, user_id):
    """Get and update alumni employment data."""
    try:
        from apps.shared.models import User, EmploymentHistory, TrackerData, OJTCompanyProfile
        from apps.shared.services import UserService
        
        user = User.objects.get(user_id=user_id)
        
        # Determine account type
        is_alumni = user.account_type.user if hasattr(user.account_type, 'user') else False
        is_ojt = user.account_type.ojt if hasattr(user.account_type, 'ojt') else False
        
        if request.method == 'GET':
            # Get employment data
            employment_data = UserService.get_user_with_related_data(user_id)
            employment = employment_data.get('employment')
            academic_info = employment_data.get('academic_info')
            tracker_data = employment_data.get('tracker_data')
            
            # For OJT accounts, return data from OJTCompanyProfile
            if is_ojt:
                # Get OJT company profile
                ojt_company_profile = None
                try:
                    ojt_company_profile = OJTCompanyProfile.objects.get(user=user)
                except OJTCompanyProfile.DoesNotExist:
                    ojt_company_profile = None
                
                return JsonResponse({
                    'account_type': 'ojt',
                    # Basic employment info from OJTCompanyProfile
                    'organization_name': ojt_company_profile.company_name or '' if ojt_company_profile else '',
                    'date_hired': employment.date_started.strftime('%Y-%m-%d') if employment and employment.date_started else '',
                    'position': employment.position_current or '' if employment else '',
                    'sector': employment.sector_current or '' if employment else '',
                    'scope_current': employment.scope_current or '' if employment else '',
                    'employment_duration_current': employment.employment_duration_current or '' if employment else '',
                    'salary_current': employment.salary_current or '' if employment else '',
                    'company_address': ojt_company_profile.company_address or '' if ojt_company_profile else '',
                    'company_email': ojt_company_profile.company_email or '' if ojt_company_profile else '',
                    'company_contact': ojt_company_profile.company_contact or '' if ojt_company_profile else '',
                    'contact_person': ojt_company_profile.contact_person or '' if ojt_company_profile else '',
                    'position_alt': ojt_company_profile.position or '' if ojt_company_profile else '',
                    # Start date from OJTCompanyProfile
                    'ojt_start_date': ojt_company_profile.start_date.strftime('%Y-%m-%d') if ojt_company_profile and ojt_company_profile.start_date else '',
                    # Additional EmploymentHistory fields
                    'awards_recognition_current': employment.awards_recognition_current or '' if employment else '',
                    'self_employed': employment.self_employed if employment else False,
                    'high_position': employment.high_position if employment else False,
                    'absorbed': employment.absorbed if employment else False,
                    'has_employment_data': bool(ojt_company_profile and ojt_company_profile.company_name and ojt_company_profile.company_name.strip() != '')
                })
            
            # For Alumni accounts, temporarily return coming soon placeholder
            if is_alumni:
                return JsonResponse({
                    'account_type': 'alumni',
                    'message': 'Coming soon',
                    'has_tracker_data': False
                })
            else:
                # OJT without employment - return empty EmploymentHistory fields only
                return JsonResponse({
                    'account_type': 'ojt',
                    'has_employment_data': False,
                    'organization_name': '',
                    'date_hired': '',
                    'position': '',
                    'sector': '',
                    'scope_current': '',
                    'employment_duration_current': '',
                    'salary_current': '',
                    'company_address': '',
                    'company_email': '',
                    'company_contact': '',
                    'contact_person': '',
                    'position_alt': '',
                    'awards_recognition_current': '',
                    'self_employed': False,
                    'high_position': False,
                    'absorbed': False
                })
                
        elif request.method == 'PUT':
            data = json.loads(request.body)
            
            # For OJT accounts, only update EmploymentHistory fields (no Part III/IV)
            if is_ojt:
                employment, created = EmploymentHistory.objects.get_or_create(user=user)
                
                # Update only EmploymentHistory fields (no Part III/IV mapping)
                if 'organization_name' in data:
                    employment.company_name_current = data.get('organization_name', '')
                if 'date_hired' in data:
                    date_started = None
                    if data.get('date_hired'):
                        try:
                            from datetime import datetime
                            date_started = datetime.strptime(data['date_hired'], '%Y-%m-%d').date()
                        except (ValueError, TypeError):
                            date_started = None
                    employment.date_started = date_started
                if 'position' in data:
                    employment.position_current = data.get('position', '')
                if 'sector' in data:
                    employment.sector_current = data.get('sector', '')
                if 'scope_current' in data:
                    employment.scope_current = data.get('scope_current', '')
                if 'employment_duration_current' in data:
                    employment.employment_duration_current = data.get('employment_duration_current', '')
                if 'salary_current' in data:
                    employment.salary_current = data.get('salary_current', '')
                if 'company_address' in data:
                    employment.company_address = data.get('company_address', '')
                if 'company_email' in data:
                    employment.company_email = data.get('company_email', '')
                if 'company_contact' in data:
                    employment.company_contact = data.get('company_contact', '')
                if 'contact_person' in data:
                    employment.contact_person = data.get('contact_person', '')
                if 'position_alt' in data:
                    employment.position = data.get('position_alt', '')
                if 'awards_recognition_current' in data:
                    employment.awards_recognition_current = data.get('awards_recognition_current', '')
                
                employment.save()
                
                return JsonResponse({
                    'success': True,
                    'message': 'Employment data updated successfully'
                })
            
            # For Alumni accounts, handle Part III/IV fields mapping
            # Handle date parsing
            date_started = None
            if data.get('date_hired'):
                try:
                    from datetime import datetime
                    date_started = datetime.strptime(data.get('date_hired'), '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    # If date parsing fails, set to None
                    date_started = None
            
            # Handle study start date parsing for Part IV
            study_start_date = None
            if data.get('study_start_date'):
                try:
                    from datetime import datetime
                    study_start_date = datetime.strptime(data.get('study_start_date'), '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    study_start_date = None
            
            # Handle unemployment reasons - save to TrackerData
            if data.get('unemployment_reason') or data.get('q_unemployment_reason'):
                unemployment_reasons = data.get('unemployment_reason') or data.get('q_unemployment_reason', [])
                # Ensure it's a list
                if isinstance(unemployment_reasons, str):
                    import json
                    try:
                        unemployment_reasons = json.loads(unemployment_reasons)
                    except:
                        unemployment_reasons = [unemployment_reasons]
                
                # Update TrackerData with unemployment reasons
                tracker_data, created = TrackerData.objects.get_or_create(user=user)
                tracker_data.q_unemployment_reason = unemployment_reasons if isinstance(unemployment_reasons, list) else [unemployment_reasons]
                tracker_data.q_employment_status = 'unemployed'
                tracker_data.save()
                
                # Clear employment history if unemployed
                if hasattr(user, 'employment'):
                    employment = user.employment
                    employment.company_name_current = ''
                    employment.position_current = ''
                    employment.save()
                
                return JsonResponse({'success': True, 'message': 'Unemployment information saved successfully'})
            
            # Map frontend fields to backend model fields
            employment_data = {
                'company_name_current': data.get('organization_name', '') or data.get('current_company_name', ''),
                'date_started': date_started,
                'position_current': data.get('position', '') or data.get('current_position', ''),
                'employment_duration_current': data.get('employment_status', '') or data.get('current_employment_status', '') or data.get('employment_duration', ''),
                'company_address': data.get('company_address', ''),
                'sector_current': data.get('sector', '') or data.get('current_sector', '') or data.get('employment_sector', ''),
                'scope_current': data.get('scope_current', '') or data.get('current_scope', ''),
                'salary_current': data.get('salary_current', '') or data.get('salary_range', ''),
                'awards_recognition_current': data.get('awards_recognition_current', '') or data.get('received_awards', ''),
                'supporting_document_current': data.get('supporting_document_current', '') or data.get('employment_supporting_doc', ''),
                'supporting_document_awards_recognition': data.get('supporting_document_awards_recognition', '') or data.get('awards_supporting_doc', '')
            }
            
            # Update employment using service
            try:
                from apps.shared.models import AcademicInfo
                employment = UserService.update_employment_status(user, employment_data)
                
                # Update Part IV: Further Study fields in AcademicInfo
                academic_info, created = AcademicInfo.objects.get_or_create(user=user)
                if data.get('study_start_date') or data.get('q_study_start_date'):
                    academic_info.q_study_start_date = study_start_date or (academic_info.q_study_start_date if hasattr(academic_info, 'q_study_start_date') else None)
                if data.get('post_graduate_degree') or data.get('q_post_graduate_degree'):
                    academic_info.q_post_graduate_degree = data.get('post_graduate_degree') or data.get('q_post_graduate_degree', '')
                if data.get('institution_name') or data.get('q_institution_name'):
                    academic_info.q_institution_name = data.get('institution_name') or data.get('q_institution_name', '')
                if data.get('units_obtained') or data.get('q_units_obtained'):
                    academic_info.q_units_obtained = data.get('units_obtained') or data.get('q_units_obtained', '')
                academic_info.save()
                
                # Update TrackerData with dropdown values from Part III
                tracker_data, created = TrackerData.objects.get_or_create(user=user)
                tracker_data.q_employment_status = 'employed'
                
                # Update Part III dropdown fields in TrackerData
                if data.get('employment_type'):
                    tracker_data.q_employment_type = data.get('employment_type')
                if data.get('current_employment_status'):
                    tracker_data.q_employment_permanent = data.get('current_employment_status')
                if data.get('current_company_name'):
                    tracker_data.q_company_name = data.get('current_company_name')
                if data.get('current_position'):
                    tracker_data.q_current_position = data.get('current_position')
                if data.get('current_sector'):
                    tracker_data.q_sector_current = data.get('current_sector')
                if data.get('current_scope'):
                    tracker_data.q_scope_current = data.get('current_scope')
                if data.get('employment_duration'):
                    tracker_data.q_employment_duration = data.get('employment_duration')
                if data.get('salary_range'):
                    tracker_data.q_salary_range = data.get('salary_range')
                if data.get('received_awards'):
                    tracker_data.q_awards_received = data.get('received_awards')
                
                if not data.get('unemployment_reason') and not data.get('q_unemployment_reason'):
                    tracker_data.q_unemployment_reason = None
                tracker_data.save()
                
                return JsonResponse({'success': True, 'message': 'Employment details updated successfully'})
            except Exception as service_error:
                print(f"Error in UserService.update_employment_status: {service_error}")
                import traceback
                print(f"Service error traceback: {traceback.format_exc()}")
                return JsonResponse({'error': f'Service error: {str(service_error)}'}, status=500)
            
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        import traceback
        print(f"Error in alumni_employment_view: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_following_for_mentions(request):
    """Get list of users that current user follows for @mentions"""
    try:
        current_user = get_current_user_from_request(request)
        if not current_user:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        from apps.shared.models import Follow
        following = Follow.objects.filter(follower=current_user).select_related('following')
        
        following_data = []
        for follow_obj in following:
            followed_user = follow_obj.following
            following_data.append({
                'user_id': followed_user.user_id,
                'name': f"{followed_user.f_name} {followed_user.m_name or ''} {followed_user.l_name}".strip(),
                'f_name': followed_user.f_name,
                'm_name': followed_user.m_name,
                'l_name': followed_user.l_name,
                'profile_pic': build_profile_pic_url(followed_user),
            })
        
        return JsonResponse({
            'success': True,
            'following': following_data
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_post_from_comment(request, comment_id):
    """Get the post ID from a comment ID for notification redirects"""
    try:
        comment = Comment.objects.select_related('post', 'forum', 'repost', 'donation_request').get(comment_id=comment_id)
        
        # Determine the type of content and get the appropriate ID
        if comment.post:
            return JsonResponse({
                'success': True,
                'post_id': comment.post.post_id,
                'post_type': 'post'
            })
        elif comment.forum:
            return JsonResponse({
                'success': True,
                'post_id': comment.forum.forum_id,
                'post_type': 'forum'
            })
        elif comment.repost:
            return JsonResponse({
                'success': True,
                'post_id': comment.repost.repost_id,
                'post_type': 'repost'
            })
        elif comment.donation_request:
            return JsonResponse({
                'success': True,
                'post_id': comment.donation_request.donation_id,
                'post_type': 'donation'
            })
        else:
            return JsonResponse({'error': 'Comment has no associated content'}, status=400)
            
    except Comment.DoesNotExist:
        return JsonResponse({'error': 'Comment not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_comment_from_reply(request, reply_id):
    """Get the comment ID from a reply ID for notification redirects"""
    try:
        reply = Reply.objects.select_related('comment').get(reply_id=reply_id)
        
        return JsonResponse({
            'success': True,
            'comment_id': reply.comment.comment_id
        })
            
    except Reply.DoesNotExist:
        return JsonResponse({'error': 'Reply not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET'])
def search_alumni(request):
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'results': []})
    
    # Split query into individual words for better matching
    query_words = query.split()
    
    # Build Q objects for each word
    q_objects = Q()
    for word in query_words:
        q_objects |= (
            Q(f_name__icontains=word) |
            Q(m_name__icontains=word) |
            Q(l_name__icontains=word)
        )
    
    # Also search for the full query as a single string
    q_objects |= (
        Q(f_name__icontains=query) |
        Q(m_name__icontains=query) |
        Q(l_name__icontains=query)
    )
    
    # Search by first, middle, or last name (case-insensitive)
    users = User.objects.filter(
        q_objects,
        Q(account_type__user=True) | Q(account_type__admin=True) | Q(account_type__peso=True) | Q(account_type__ojt=True)
    )[:10]
    results = [
        {
            'id': u.user_id,
            'name': f"{u.f_name} {u.l_name}",
            'profile_pic': u.profile.profile_pic.url if hasattr(u, 'profile') and u.profile and u.profile.profile_pic else None,
            'account_type': {
                'user': getattr(u.account_type, 'user', False),
                'admin': getattr(u.account_type, 'admin', False),
                'peso': getattr(u.account_type, 'peso', False),
                'ojt': getattr(u.account_type, 'ojt', False),
            }
        }
        for u in users
    ]
    return JsonResponse({'results': results})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_alumni_profile_pic(request):
    user_id = request.GET.get('user_id')
    if not user_id:
        return Response({'message': 'Missing user_id'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(user_id=user_id)
        from apps.shared.models import UserProfile
        profile, _ = UserProfile.objects.get_or_create(user=user)
        if profile.profile_pic:
            # Delete the file from storage
            try:
                file_path = profile.profile_pic.path
            except Exception:
                file_path = None
            profile.profile_pic.delete(save=False)
            profile.profile_pic = None
            profile.save()
            # Also remove local file if path is available
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass
        return Response({'success': True})
    except User.DoesNotExist:
        return Response({'message': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
# mobile side
@api_view(["GET", "PUT", "DELETE"])
@permission_classes([IsAuthenticatedOrReadOnly])
def post_detail_view(request, post_id):
    try:
        post = Post.objects.get(post_id=post_id)
    except Post.DoesNotExist:
        return JsonResponse({'error': 'Post not found'}, status=404)

    if request.method == "GET":
        try:
            # Get repost information for THIS specific post
            reposts = Repost.objects.filter(post=post).select_related('user')
            repost_data = []
            for repost in reposts:
                # Get repost likes count and data
                repost_likes = Like.objects.filter(repost=repost).select_related('user')
                repost_likes_count = repost_likes.count()
                repost_likes_data = []
                for like in repost_likes:
                    repost_likes_data.append({
                        'like_id': like.like_id,
                        'user': {
                            'user_id': like.user.user_id,
                            'f_name': like.user.f_name,
                            'm_name': like.user.m_name,
                            'l_name': like.user.l_name,
                            'profile_pic': build_profile_pic_url(like.user),
                        }
                    })

                # Get repost comments count and data
                repost_comments = Comment.objects.filter(repost=repost).select_related('user').order_by('-date_created')
                repost_comments_count = repost_comments.count()
                repost_comments_data = []
                for comment in repost_comments:
                    # Get replies count for this comment
                    replies_count = Reply.objects.filter(comment=comment).count()
                    
                    repost_comments_data.append({
                        'comment_id': comment.comment_id,
                        'comment_content': comment.comment_content,
                        'date_created': comment.date_created.isoformat() if comment.date_created else None,
                        'replies_count': replies_count,
                        'user': {
                            'user_id': comment.user.user_id,
                            'f_name': comment.user.f_name,
                            'm_name': comment.user.m_name,
                            'l_name': comment.user.l_name,
                            'profile_pic': build_profile_pic_url(comment.user),
                        }
                    })

                repost_data.append({
                    'repost_id': repost.repost_id,
                    'repost_date': repost.repost_date.isoformat(),
                    'repost_caption': repost.caption,
                    'likes_count': repost_likes_count,
                    'comments_count': repost_comments_count,
                    'likes': repost_likes_data,
                    'comments': repost_comments_data,
                    'user': {
                        'user_id': repost.user.user_id,
                        'f_name': repost.user.f_name,
                        'm_name': repost.user.m_name,
                        'l_name': repost.user.l_name,
                        'profile_pic': build_profile_pic_url(repost.user),
                    }
                })

            # Get comments for THIS specific post
            comments = Comment.objects.filter(post=post).select_related('user').order_by('-date_created')
            comments_data = []
            for comment in comments:
                comments_data.append({
                    'comment_id': comment.comment_id,
                    'comment_content': comment.comment_content,
                    'date_created': comment.date_created.isoformat() if comment.date_created else None,
                    'user': {
                        'user_id': comment.user.user_id,
                        'f_name': comment.user.f_name,
                        'm_name': comment.user.m_name,
                        'l_name': comment.user.l_name,
                        'profile_pic': build_profile_pic_url(comment.user),
                    }
                })

            # Get likes for THIS specific post with user information
            likes = Like.objects.filter(post=post).select_related('user')
            likes_data = []
            for like in likes:
                # If profile_pic missing, send initials so client can render fallback
                pic = build_profile_pic_url(like.user)
                initials = None
                if not pic:
                    try:
                        f = (like.user.f_name or '').strip()[:1].upper()
                        l = (like.user.l_name or '').strip()[:1].upper()
                        initials = f + l if (f or l) else None
                    except Exception:
                        initials = None
                likes_data.append({
                    'like_id': like.like_id,
                    'user_id': like.user.user_id,
                    'f_name': like.user.f_name,
                    'm_name': like.user.m_name,
                    'l_name': like.user.l_name,
                    'profile_pic': pic,
                    'initials': initials,
                })

            # Get multiple images for the post
            post_images = []
            #shaira
            # Use the new ContentImage model
            try:
                content_images = ContentImage.objects.filter(content_type='post', content_id=post.post_id)
                for img in content_images:
                    image_url = build_image_url(img.image, request)
                    post_images.append({
                        'image_id': img.image_id,
                        'image_url': image_url,
                        'order': img.order
                    })
            except Exception as img_error:
                # Fallback if ContentImage table doesn't exist yet (migrations not run)
                print(f"Warning: Could not load ContentImage: {img_error}")
                post_images = []

            post_data = {
                'post_id': post.post_id,
                'post_content': post.post_content,
                'post_image': (post.post_image.url if getattr(post, 'post_image', None) else None),  # Backward compatibility
                'post_images': post_images,  # Multiple images
                'type': post.type,
                'created_at': post.created_at.isoformat() if hasattr(post, 'created_at') else None,
                'likes_count': len(likes_data),
                'comments_count': post.comments.count() if hasattr(post, 'comments') else 0,
                'reposts_count': post.reposts.count() if hasattr(post, 'reposts') else 0,
                'likes': likes_data,
                'reposts': repost_data,
                'comments': comments_data,
                'user': {
                    'user_id': post.user.user_id,
                    'f_name': post.user.f_name,
                    'm_name': post.user.m_name,
                    'l_name': post.user.l_name,
                    'profile_pic': build_profile_pic_url(post.user),
                },
                'category': {
                }
            }
            return JsonResponse(post_data)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


@api_view(["GET"]) 
@permission_classes([IsAuthenticated])
def post_likes_view(request, post_id):
    """Used by Mobile – list of users who liked a post.

    Response shape mirrors likes data used in feeds and detail:
      { likes: [ { user_id, f_name, l_name, profile_pic, initials? } ] }
    """
    try:
        post = Post.objects.get(post_id=post_id)
    except Post.DoesNotExist:
        return JsonResponse({'error': 'Post not found'}, status=404)

    likes = Like.objects.filter(post=post).select_related('user')
    data = []
    for l in likes:
        pic = build_profile_pic_url(l.user)
        initials = None
        if not pic:
            try:
                f = (l.user.f_name or '').strip()[:1].upper()
                s = (l.user.l_name or '').strip()[:1].upper()
                initials = (f + s) if (f or s) else None
            except Exception:
                initials = None
        data.append({
            'user_id': l.user.user_id,
            'f_name': l.user.f_name,
            'l_name': l.user.l_name,
            'profile_pic': pic,
            'initials': initials,
        })
    return JsonResponse({'likes': data})


# ==========================
# Repost interactions (Used by Mobile)
# ==========================
@api_view(["GET"]) 
@permission_classes([IsAuthenticated])
def repost_detail_view(request, repost_id):
    """Used by Mobile – return repost with its own likes/comments and original content summary."""
    print(f"🔍 DEBUG: repost_detail_view called with repost_id={repost_id}")
    try:
        repost = Repost.objects.select_related('post', 'user', 'post__user', 'forum', 'donation_request').get(repost_id=repost_id)
        print(f"🔍 DEBUG: Found repost {repost_id}: user={repost.user.user_id}, post={repost.post.post_id if repost.post else None}, donation={repost.donation_request.donation_id if repost.donation_request else None}")
    except Repost.DoesNotExist:
        print(f"❌ DEBUG: Repost {repost_id} not found")
        return JsonResponse({'error': 'Repost not found'}, status=404)
    except Exception as e:
        print(f"❌ DEBUG: Error fetching repost {repost_id}: {str(e)}")
        return JsonResponse({'error': f'Error fetching repost: {str(e)}'}, status=500)

    likes = Like.objects.filter(repost=repost).select_related('user')
    comments = Comment.objects.filter(repost=repost).select_related('user')
    
    # Build original content data based on repost type
    original_data = None
    if repost.post:
        # Post repost
        original_data = {
            'type': 'post',
            'post_id': repost.post.post_id,
            'user': {
                'user_id': repost.post.user.user_id,
                'f_name': repost.post.user.f_name,
                'l_name': repost.post.user.l_name,
                'profile_pic': build_profile_pic_url(repost.post.user),
            },
            'content': repost.post.post_content,
            'post_image': (repost.post.post_image.url if getattr(repost.post, 'post_image', None) else None),
            'post_images': [{
                'image_id': img.image_id,
                'image_url': (build_image_url(img.image, request) or (getattr(img.image, 'url', None) or '')),
                'order': img.order
            } for img in repost.post.images.all()],
            'created_at': repost.post.created_at.isoformat() if hasattr(repost.post, 'created_at') else None,
        }
    elif repost.forum:
        # Forum repost
        original_data = {
            'type': 'forum',
            'forum_id': repost.forum.forum_id,
            'user': {
                'user_id': repost.forum.user.user_id,
                'f_name': repost.forum.user.f_name,
                'l_name': repost.forum.user.l_name,
                'profile_pic': build_profile_pic_url(repost.forum.user),
            },
            'content': repost.forum.content,
            'forum_type': repost.forum.type,
            'images': [{
                'image_id': img.image_id,
                'image_url': (build_image_url(img.image, request) or (getattr(img.image, 'url', None) or '')),
                'order': img.order
            } for img in repost.forum.images.all()],
            'created_at': repost.forum.created_at.isoformat() if hasattr(repost.forum, 'created_at') else None,
        }
    elif repost.donation_request:
        # Donation repost
        original_data = {
            'type': 'donation',
            'donation_id': repost.donation_request.donation_id,
            'user': {
                'user_id': repost.donation_request.user.user_id,
                'f_name': repost.donation_request.user.f_name,
                'l_name': repost.donation_request.user.l_name,
                'profile_pic': build_profile_pic_url(repost.donation_request.user),
            },
            'content': repost.donation_request.description,
            'status': repost.donation_request.status,
            'images': [{
                'image_id': img.image_id,
                'image_url': (build_image_url(img.image, request) or (getattr(img.image, 'url', None) or '')),
                'order': img.order
            } for img in repost.donation_request.images.all()],
            'created_at': repost.donation_request.created_at.isoformat() if hasattr(repost.donation_request, 'created_at') else None,
        }
    
    data = {
        'repost_id': repost.repost_id,
        'caption': repost.caption,
        'repost_date': repost.repost_date.isoformat() if repost.repost_date else None,
        'user': {
            'user_id': repost.user.user_id,
            'f_name': repost.user.f_name,
            'l_name': repost.user.l_name,
            'profile_pic': build_profile_pic_url(repost.user),
        },
        'likes_count': likes.count(),
        'comments_count': comments.count(),
        'likes': [{
            'user_id': l.user.user_id,
            'f_name': l.user.f_name,
            'l_name': l.user.l_name,
            'profile_pic': build_profile_pic_url(l.user),
            'initials': None if build_profile_pic_url(l.user) else (
                ((l.user.f_name or '').strip()[:1].upper() + (l.user.l_name or '').strip()[:1].upper()) 
                if ((l.user.f_name or '').strip() or (l.user.l_name or '').strip()) else None
            ),
        } for l in likes],
        'comments': [{
            'comment_id': c.comment_id,
            'comment_content': c.comment_content,
            'date_created': c.date_created.isoformat() if c.date_created else None,
            'replies_count': Reply.objects.filter(comment=c).count(),
            'user': {
                'user_id': c.user.user_id,
                'f_name': c.user.f_name,
                'l_name': c.user.l_name,
                'profile_pic': build_profile_pic_url(c.user),
            }
        } for c in comments],
        'original': original_data
    }
    return JsonResponse(data)


@api_view(["POST", "DELETE"]) 
@permission_classes([IsAuthenticated])
def repost_like_view(request, repost_id):
    try:
        repost = Repost.objects.select_related('user', 'post', 'donation_request', 'forum').get(repost_id=repost_id)
        print(f"🔍 DEBUG: Found repost {repost_id}: user={repost.user.user_id}, post={repost.post.post_id if repost.post else None}, donation={repost.donation_request.donation_id if repost.donation_request else None}")
    except Repost.DoesNotExist:
        print(f"❌ DEBUG: Repost {repost_id} not found")
        return JsonResponse({'error': 'Repost not found'}, status=404)
    except Exception as e:
        print(f"❌ DEBUG: Error fetching repost {repost_id}: {str(e)}")
        return JsonResponse({'error': f'Error fetching repost: {str(e)}'}, status=500)
    
    user = request.user
    print(f"🔍 DEBUG: User {user.user_id} trying to like repost {repost_id}")
    
    if request.method == "POST":
        try:
            # Like the repost
            like, created = Like.objects.get_or_create(
                user=user, 
                repost=repost,
                defaults={
                    'post': None,
                    'forum': None,
                    'donation_request': None
                }
            )
            print(f"🔍 DEBUG: Like created={created}, like_id={like.like_id if like else None}")
            
            if created:
                # Award engagement points for liking
                award_engagement_points(user, 'like')
                
                # Create notification for repost owner (only if the liker is not the repost owner)
                if user.user_id != repost.user.user_id:
                    # Determine repost type
                    if repost.donation_request:
                        repost_type = "donation repost"
                    elif repost.forum:
                        repost_type = "forum repost"
                    else:
                        repost_type = "repost"
                    
                    print(f"🔍 DEBUG: Creating notification for user {repost.user.user_id}, repost_type={repost_type}")
                    
                    # Build notification content with appropriate ID based on repost type
                    if repost.post:
                        notif_content = f"{user.full_name} liked your {repost_type}<!--POST_ID:{repost.post.post_id}--><!--REPOST_ID:{repost.repost_id}--><!--ACTOR_ID:{user.user_id}-->"
                    elif repost.forum:
                        notif_content = f"{user.full_name} liked your {repost_type}<!--FORUM_ID:{repost.forum.forum_id}--><!--REPOST_ID:{repost.repost_id}--><!--ACTOR_ID:{user.user_id}-->"
                    elif repost.donation_request:
                        notif_content = f"{user.full_name} liked your {repost_type}<!--DONATION_ID:{repost.donation_request.donation_id}--><!--REPOST_ID:{repost.repost_id}--><!--ACTOR_ID:{user.user_id}-->"
                    else:
                        notif_content = f"{user.full_name} liked your {repost_type}<!--REPOST_ID:{repost.repost_id}--><!--ACTOR_ID:{user.user_id}-->"
                    
                    notification = Notification.objects.create(
                        user=repost.user,
                        notif_type='like',
                        subject='Repost Liked',
                        notifi_content=notif_content,
                        notif_date=timezone.now()
                    )
                    print(f"🔔 DEBUG: Created repost like notification for user {repost.user.user_id}: {notification.notifi_content}")
                    # Broadcast repost like notification in real-time
                    try:
                        from apps.messaging.notification_broadcaster import broadcast_notification
                        broadcast_notification(notification)
                    except Exception as e:
                        logger.error(f"Error broadcasting repost like notification: {e}")
                else:
                    print(f"🔍 DEBUG: User {user.user_id} is the repost owner, no notification created")
                    
                return JsonResponse({'success': True, 'message': 'Repost liked'})
            else:
                print(f"🔍 DEBUG: Repost {repost_id} already liked by user {user.user_id}")
                return JsonResponse({'success': False, 'message': 'Repost already liked'})
        except Exception as e:
            print(f"❌ DEBUG: Error in repost like creation: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': f'Error liking repost: {str(e)}'}, status=500)
    elif request.method == "DELETE":
        # Unlike the repost
        try:
            like = Like.objects.get(user=user, repost=repost)
            like.delete()
            # Deduct engagement points for unliking
            deduct_engagement_points(user, 'like')
            return JsonResponse({'success': True, 'message': 'Repost unliked'})
        except Like.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Repost not liked'})


@api_view(["GET"]) 
@permission_classes([IsAuthenticated])
def repost_likes_list_view(request, repost_id):
    try:
        repost = Repost.objects.get(repost_id=repost_id)
    except Repost.DoesNotExist:
        return JsonResponse({'error': 'Repost not found'}, status=404)
#shaira    
    # Get likes for this repost
    likes = Like.objects.filter(repost=repost).select_related('user')
    likes_data = []
    for like in likes:
        likes_data.append({
            'like_id': like.like_id,
            'user': {
                'user_id': like.user.user_id,
                'f_name': like.user.f_name,
                'm_name': like.user.m_name,
                'l_name': like.user.l_name,
                'profile_pic': build_profile_pic_url(like.user),
            }
        })
    return JsonResponse({'likes': likes_data})
@api_view(["GET", "POST"]) 
@permission_classes([IsAuthenticated])
def repost_comments_view(request, repost_id):
    try:
        repost = Repost.objects.get(repost_id=repost_id)
    except Repost.DoesNotExist:
        return JsonResponse({'error': 'Repost not found'}, status=404)
 #shaira   
    if request.method == 'GET':
        # Get comments for this repost
        comments = Comment.objects.filter(repost=repost).select_related('user').order_by('-date_created')
        comments_data = []
        for comment in comments:
            comments_data.append({
                'comment_id': comment.comment_id,
                'comment_content': comment.comment_content,
                'date_created': comment.date_created.isoformat() if comment.date_created else None,
                'user': {
                    'user_id': comment.user.user_id,
                    'f_name': comment.user.f_name,
                    'm_name': comment.user.m_name,
                    'l_name': comment.user.l_name,
                    'profile_pic': build_profile_pic_url(comment.user),
                }
            })
        return JsonResponse({'comments': comments_data})
    else:
        try:
            payload = json.loads(request.body or '{}')
            content = (payload.get('comment_content') or '').strip()
            if not content:
                return JsonResponse({'error': 'content required'}, status=400)
            
            # Create comment
            comment = Comment.objects.create(
                repost=repost,
                user=request.user,
                comment_content=content,
                date_created=timezone.now()
            )
            
            # Determine repost type and original content info
            if repost.donation_request:
                repost_type = "donation repost"
                repost_forum_id = None
                repost_donation_id = repost.donation_request.donation_id
                repost_post_id = None
            elif repost.forum:
                repost_type = "forum repost"
                repost_forum_id = repost.forum.forum_id
                repost_donation_id = None
                repost_post_id = None
            elif repost.post:
                repost_type = "repost"
                repost_forum_id = None
                repost_donation_id = None
                repost_post_id = repost.post.post_id
            else:
                repost_type = "repost"
                repost_forum_id = None
                repost_donation_id = None
                repost_post_id = None
            
            # Create mention notifications with repost context
            create_mention_notifications(
                content,
                request.user,
                comment_id=comment.comment_id,
                post_id=repost_post_id,
                forum_id=repost_forum_id,
                donation_id=repost_donation_id,
                repost_id=repost.repost_id
            )
            
            # Create notification for repost owner
            if request.user.user_id != repost.user.user_id:
                # Build notification content with appropriate ID based on repost type
                if repost.post:
                    notif_content = f"{request.user.full_name} commented on your {repost_type}<!--POST_ID:{repost.post.post_id}--><!--REPOST_ID:{repost.repost_id}--><!--COMMENT_ID:{comment.comment_id}--><!--ACTOR_ID:{request.user.user_id}-->"
                elif repost.forum:
                    notif_content = f"{request.user.full_name} commented on your {repost_type}<!--FORUM_ID:{repost.forum.forum_id}--><!--REPOST_ID:{repost.repost_id}--><!--COMMENT_ID:{comment.comment_id}--><!--ACTOR_ID:{request.user.user_id}-->"
                elif repost.donation_request:
                    notif_content = f"{request.user.full_name} commented on your {repost_type}<!--DONATION_ID:{repost.donation_request.donation_id}--><!--REPOST_ID:{repost.repost_id}--><!--COMMENT_ID:{comment.comment_id}--><!--ACTOR_ID:{request.user.user_id}-->"
                else:
                    notif_content = f"{request.user.full_name} commented on your {repost_type}<!--REPOST_ID:{repost.repost_id}--><!--COMMENT_ID:{comment.comment_id}--><!--ACTOR_ID:{request.user.user_id}-->"
                
                notification = Notification.objects.create(
                    user=repost.user,
                    notif_type='comment',
                    subject='Repost Commented',
                    notifi_content=notif_content,
                    notif_date=timezone.now()
                )
                
                # Broadcast repost comment notification in real-time
                try:
                    from apps.messaging.notification_broadcaster import broadcast_notification
                    broadcast_notification(notification)
                except Exception as e:
                    logger.error(f"Error broadcasting repost comment notification: {e}")
            
            return JsonResponse({'success': True, 'comment_id': comment.comment_id})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


@api_view(["PUT", "DELETE"]) 
@permission_classes([IsAuthenticated])
def repost_comment_edit_view(request, repost_id, comment_id):
    try:
        repost = Repost.objects.get(repost_id=repost_id)
    except Repost.DoesNotExist:
        return JsonResponse({'error': 'Repost not found'}, status=404)
    try:
        comment = Comment.objects.get(comment_id=comment_id, repost=repost)
    except Comment.DoesNotExist:
        return JsonResponse({'error': 'Comment not found'}, status=404)
    # Allow comment owner OR repost owner to delete/edit comment
    if comment.user.user_id != request.user.user_id and repost.user.user_id != request.user.user_id:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    if request.method == 'PUT':
        try:
            payload = json.loads(request.body or '{}')
            comment.comment_content = (payload.get('comment_content') or '').strip()
            comment.save(update_fields=['comment_content'])
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    else:
        # Deduct engagement points for deleting comment
        deduct_engagement_points(comment.user, 'comment')
        comment.delete()
        return JsonResponse({'success': True})

@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
def post_like_view(request, post_id):
    try:
        post = Post.objects.get(post_id=post_id)
        user = request.user

        if request.method == "POST":
            # Like the post
            like, created = Like.objects.get_or_create(
                user=user, 
                post=post,
                defaults={
                    'forum': None,
                    'repost': None,
                    'donation_request': None
                }
            )
            if created:
                # Award engagement points (+1 for like)
                award_engagement_points(user, 'like')
                
                # Create notification for post owner (only if the liker is not the post owner)
                if user.user_id != post.user.user_id:
                    like_notification = Notification.objects.create(
                        user=post.user,
                        notif_type='like',
                        subject='Post Liked',
                        notifi_content=f"{user.full_name} liked your post<!--POST_ID:{post.post_id}--><!--ACTOR_ID:{user.user_id}-->",
                        notif_date=timezone.now()
                    )
                    
                    # Broadcast like notification in real-time
                    try:
                        from apps.messaging.notification_broadcaster import broadcast_notification
                        broadcast_notification(like_notification)
                    except Exception as e:
                        logger.error(f"Error broadcasting like notification: {e}")
                return JsonResponse({'success': True, 'message': 'Post liked'})
            else:
                return JsonResponse({'success': False, 'message': 'Post already liked'})
        elif request.method == "DELETE":
            # Unlike the post
            try:
                like = Like.objects.get(user=user, post=post)
                like.delete()
                # Deduct engagement points for unliking
                deduct_engagement_points(user, 'like')
                return JsonResponse({'success': True, 'message': 'Post unliked'})
            except Like.DoesNotExist:
                return JsonResponse({'success': False, 'message': 'Post not liked'})
    except Post.DoesNotExist:
        return JsonResponse({'error': 'Post not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(["GET", "PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def post_edit_view(request, post_id):
    try:
        post = Post.objects.get(post_id=post_id)
        user = request.user

        # Allow only if owner or admin
        if post.user.user_id != user.user_id and not getattr(user.account_type, 'admin', False):
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        if request.method == "GET":
            # Reuse the detailed serialization from post_detail_view
            return post_detail_view(request, post_id)

        if request.method == "PUT":
            data = json.loads(request.body)
            post_content = data.get('post_content')

            if post_content is not None:
                post.post_content = post_content
            post.save()
            return JsonResponse({'success': True, 'message': 'Post updated'})

        elif request.method == "DELETE":
            try:
                # Check if post has images before deletion to determine point type
                has_images = ContentImage.objects.filter(content_type='post', content_id=post.post_id).exists()
                
                # Delete related images using ContentImage
                content_images = ContentImage.objects.filter(content_type='post', content_id=post.post_id)
                for img in content_images:
                    if getattr(img, 'image', None):
                        img.image.delete(save=False)
                content_images.delete()

                # Deduct engagement points before deleting the post
                if has_images:
                    deduct_engagement_points(user, 'post_with_photo')
                else:
                    deduct_engagement_points(user, 'post')

                # Finally delete the post itself
                post.delete()
                return JsonResponse({'success': True, 'message': 'Post deleted'})

            except Exception as e:
                logger.error(f"post_edit_view DELETE failed for post_id={post_id}: {e}")
                return JsonResponse(
                    {'success': False, 'message': 'Delete failed', 'error': str(e)},
                    status=500
                )

    except Post.DoesNotExist:
        return JsonResponse({'error': 'Post not found'}, status=404)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def comment_edit_view(request, post_id, comment_id):
    try:
        # First verify the post exists
        post = Post.objects.get(post_id=post_id)
        # Then get the comment that belongs to this specific post
        comment = Comment.objects.get(comment_id=comment_id, post=post)
        user = request.user
        # Allow if user owns the comment, or user owns the post, or user is admin
        if not (
            comment.user.user_id == user.user_id or
            post.user.user_id == user.user_id or
            getattr(user.account_type, 'admin', False)
        ):
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        if request.method == "PUT":
            data = json.loads(request.body)
            comment_content = data.get('comment_content')
            if comment_content is not None:
                comment.comment_content = comment_content
                comment.save()
                return JsonResponse({'success': True, 'message': 'Comment updated'})
            else:
                return JsonResponse({'error': 'No content provided'}, status=400)
        elif request.method == "DELETE":
            # Deduct engagement points for deleting comment
            deduct_engagement_points(comment.user, 'comment')
            comment.delete()
            return JsonResponse({'success': True, 'message': 'Comment deleted'})
    except Post.DoesNotExist:
        return JsonResponse({'error': 'Post not found'}, status=404)
    except Comment.DoesNotExist:
        return JsonResponse({'error': 'Comment not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def post_comments_view(request, post_id):
    try:
        post = Post.objects.get(post_id=post_id)

        if request.method == "GET":
            # Get comments for the post
            comments = Comment.objects.filter(post=post).select_related('user').order_by('-date_created')
            comments_data = []

            for comment in comments:
                # Get reply count for this comment
                reply_count = Reply.objects.filter(comment=comment).count()
                
                comments_data.append({
                    'comment_id': comment.comment_id,
                    'comment_content': comment.comment_content,
                    'date_created': comment.date_created.isoformat(),
                    'replies_count': reply_count,
                    'user': {
                        'user_id': comment.user.user_id,
                        'f_name': comment.user.f_name,
                        'm_name': comment.user.m_name,
                        'l_name': comment.user.l_name,
                        'profile_pic': build_profile_pic_url(comment.user),
                    }
                })

            return JsonResponse({'comments': comments_data})
        elif request.method == "POST":
            data = json.loads(request.body)
            user = request.user

            # Create comment
            comment = Comment.objects.create(
                user=user,
                post=post,
                comment_content=data.get('comment_content', ''),
                date_created=timezone.now()
            )
            
            # Award engagement points (+3 for comment)
            award_engagement_points(user, 'comment')

            # Create mention notifications
            create_mention_notifications(
                data.get('comment_content', ''),
                user,
                post_id=post.post_id,
                comment_id=comment.comment_id
            )

            # Create notification for post owner
            if user.user_id != post.user.user_id:
                comment_notification = Notification.objects.create(
                    user=post.user,
                    notif_type='comment',
                    subject='Post Commented',
                    notifi_content=f"{user.full_name} commented on your post<!--POST_ID:{post.post_id}--><!--COMMENT_ID:{comment.comment_id}--><!--ACTOR_ID:{user.user_id}-->",
                    notif_date=timezone.now()
                )
                
                # Broadcast comment notification in real-time
                try:
                    from apps.messaging.notification_broadcaster import broadcast_notification
                    broadcast_notification(comment_notification)
                except Exception as e:
                    logger.error(f"Error broadcasting comment notification: {e}")

            return JsonResponse({
                'success': True,
                'message': 'Comment added',
                'comment_id': comment.comment_id
            })
    except Post.DoesNotExist:
        return JsonResponse({'error': 'Post not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
# Reply API Views - Handle comment replies
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def comment_replies_view(request, comment_id):
    """Handle replies to comments"""
    try:
        comment = Comment.objects.select_related('post', 'forum', 'repost', 'donation_request').get(comment_id=comment_id)
        
        if request.method == "GET":
            # Get replies for the comment
            replies = Reply.objects.filter(comment=comment).select_related('user').order_by('date_created')
            replies_data = []
            
            for reply in replies:
                replies_data.append({
                    'reply_id': reply.reply_id,
                    'reply_content': reply.reply_content,
                    'date_created': reply.date_created.isoformat(),
                    'user': {
                        'user_id': reply.user.user_id,
                        'f_name': reply.user.f_name,
                        'm_name': reply.user.m_name,
                        'l_name': reply.user.l_name,
                        'profile_pic': build_profile_pic_url(reply.user),
                    }
                })
            
            return JsonResponse({
                'success': True,
                'replies': replies_data
            })
            
        elif request.method == "POST":
            data = json.loads(request.body)
            user = request.user
            
            # Create reply
            reply = Reply.objects.create(
                user=user,
                comment=comment,
                reply_content=data.get('reply_content', ''),
                date_created=timezone.now()
            )
            
            # Award engagement points (+2 for reply)
            award_engagement_points(user, 'reply')
            
            # Determine context info for notifications (post, forum, donation, or repost)
            reply_post_id = None
            reply_forum_id = None
            reply_donation_id = None
            reply_repost_id = None
            
            if comment.post:
                reply_post_id = comment.post.post_id
            elif comment.forum:
                reply_forum_id = comment.forum.forum_id
            elif comment.donation_request:
                reply_donation_id = comment.donation_request.donation_id
            elif comment.repost:
                reply_repost_id = comment.repost.repost_id
                # Also get the original content ID from the repost
                if comment.repost.post:
                    reply_post_id = comment.repost.post.post_id
                elif comment.repost.forum:
                    reply_forum_id = comment.repost.forum.forum_id
                elif comment.repost.donation_request:
                    reply_donation_id = comment.repost.donation_request.donation_id
            
            # Create mention notifications
            create_mention_notifications(
                data.get('reply_content', ''),
                user,
                post_id=reply_post_id,
                forum_id=reply_forum_id,
                donation_id=reply_donation_id,
                comment_id=comment.comment_id,
                reply_id=reply.reply_id,
                repost_id=reply_repost_id
            )
            
            # Create notification for comment owner
            if user.user_id != comment.user.user_id:
                # Build notification content based on comment context
                if comment.repost:
                    # Comment is on a repost - include REPOST_ID
                    if comment.repost.post:
                        notif_content = f"{user.full_name} replied to your comment<!--COMMENT_ID:{comment.comment_id}--><!--REPLY_ID:{reply.reply_id}--><!--POST_ID:{comment.repost.post.post_id}--><!--REPOST_ID:{comment.repost.repost_id}--><!--ACTOR_ID:{user.user_id}-->"
                    elif comment.repost.forum:
                        notif_content = f"{user.full_name} replied to your comment<!--COMMENT_ID:{comment.comment_id}--><!--REPLY_ID:{reply.reply_id}--><!--FORUM_ID:{comment.repost.forum.forum_id}--><!--REPOST_ID:{comment.repost.repost_id}--><!--ACTOR_ID:{user.user_id}-->"
                    elif comment.repost.donation_request:
                        notif_content = f"{user.full_name} replied to your comment<!--COMMENT_ID:{comment.comment_id}--><!--REPLY_ID:{reply.reply_id}--><!--DONATION_ID:{comment.repost.donation_request.donation_id}--><!--REPOST_ID:{comment.repost.repost_id}--><!--ACTOR_ID:{user.user_id}-->"
                    else:
                        notif_content = f"{user.full_name} replied to your comment<!--COMMENT_ID:{comment.comment_id}--><!--REPLY_ID:{reply.reply_id}--><!--REPOST_ID:{comment.repost.repost_id}--><!--ACTOR_ID:{user.user_id}-->"
                elif comment.post:
                    notif_content = f"{user.full_name} replied to your comment<!--COMMENT_ID:{comment.comment_id}--><!--REPLY_ID:{reply.reply_id}--><!--POST_ID:{comment.post.post_id}--><!--ACTOR_ID:{user.user_id}-->"
                elif comment.forum:
                    notif_content = f"{user.full_name} replied to your comment<!--COMMENT_ID:{comment.comment_id}--><!--REPLY_ID:{reply.reply_id}--><!--FORUM_ID:{comment.forum.forum_id}--><!--ACTOR_ID:{user.user_id}-->"
                elif comment.donation_request:
                    notif_content = f"{user.full_name} replied to your comment<!--COMMENT_ID:{comment.comment_id}--><!--REPLY_ID:{reply.reply_id}--><!--DONATION_ID:{comment.donation_request.donation_id}--><!--ACTOR_ID:{user.user_id}-->"
                else:
                    notif_content = f"{user.full_name} replied to your comment<!--COMMENT_ID:{comment.comment_id}--><!--REPLY_ID:{reply.reply_id}--><!--ACTOR_ID:{user.user_id}-->"
                
                notification = Notification.objects.create(
                    user=comment.user,
                    notif_type='reply',
                    subject='Comment Replied',
                    notifi_content=notif_content,
                    notif_date=timezone.now()
                )
                
                # Broadcast reply notification in real-time
                try:
                    from apps.messaging.notification_broadcaster import broadcast_notification
                    broadcast_notification(notification)
                except Exception as e:
                    logger.error(f"Error broadcasting reply notification: {e}")
            
            return JsonResponse({
                'success': True,
                'message': 'Reply added',
                'reply': {
                    'reply_id': reply.reply_id,
                    'reply_content': reply.reply_content,
                    'date_created': reply.date_created.isoformat(),
                    'user': {
                        'user_id': reply.user.user_id,
                        'f_name': reply.user.f_name,
                        'm_name': reply.user.m_name,
                        'l_name': reply.user.l_name,
                        'profile_pic': build_profile_pic_url(reply.user),
                    }
                }
            })
            
    except Comment.DoesNotExist:
        return JsonResponse({'error': 'Comment not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def reply_edit_view(request, comment_id, reply_id):
    """Handle editing and deleting replies"""
    try:
        comment = Comment.objects.get(comment_id=comment_id)
        reply = Reply.objects.get(reply_id=reply_id, comment=comment)
        user = request.user
        
        # Check if user owns the reply
        if reply.user.user_id != user.user_id:
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        if request.method == "PUT":
            data = json.loads(request.body)
            reply.reply_content = data.get('reply_content', reply.reply_content)
            reply.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Reply updated',
                'reply': {
                    'reply_id': reply.reply_id,
                    'reply_content': reply.reply_content,
                    'date_created': reply.date_created.isoformat(),
                    'user': {
                        'user_id': reply.user.user_id,
                        'f_name': reply.user.f_name,
                        'm_name': reply.user.m_name,
                        'l_name': reply.user.l_name,
                        'profile_pic': build_profile_pic_url(reply.user),
                    }
                }
            })
            
        elif request.method == "DELETE":
            # Get the reply user before deletion
            reply_user = reply.user
            # Deduct engagement points for deleting reply
            deduct_engagement_points(reply_user, 'reply')
            reply.delete()
            return JsonResponse({
                'success': True,
                'message': 'Reply deleted'
            })
            
    except Comment.DoesNotExist:
        return JsonResponse({'error': 'Comment not found'}, status=404)
    except Reply.DoesNotExist:
        return JsonResponse({'error': 'Reply not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# Recent Search API Views
@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def recent_searches_view(request):
    """Handle recent searches with mobile optimization and enhanced error handling"""
    try:
        logger.info("recent_searches_view %s by user=%s", request.method, getattr(request.user, 'user_id', None) or getattr(request.user, 'id', None))
        user = request.user
        
        if request.method == "GET":
            # Support optional ?limit= query param (default to 10, max 50 for safety)
            try:
                limit_param = request.GET.get('limit')
                limit = int(limit_param) if limit_param is not None else 10
            except (TypeError, ValueError):
                limit = 10
            if limit <= 0:
                limit = 10
            limit = min(limit, 50)

            recent_query = RecentSearch.objects.filter(owner=user).select_related('searched_user').order_by('-created_at')
            if limit:
                recent_query = recent_query[:limit]
            
            searches_data = []
            flat_recent = []
            for search in recent_query:
                searched_user = search.searched_user
                user_payload = {
                    'user_id': getattr(searched_user, 'user_id', getattr(searched_user, 'id', None)),
                    'f_name': getattr(searched_user, 'f_name', '') or getattr(searched_user, 'first_name', ''),
                    'm_name': getattr(searched_user, 'm_name', ''),
                    'l_name': getattr(searched_user, 'l_name', '') or getattr(searched_user, 'last_name', ''),
                    'profile_pic': build_profile_pic_url(searched_user),
                }
                entry = {
                    'id': search.id,
                    'searched_user': user_payload,
                    'created_at': search.created_at.isoformat()
                }
                searches_data.append(entry)
                flat_recent.append({
                    'id': search.id,
                    'user_id': user_payload['user_id'],
                    'f_name': user_payload['f_name'],
                    'l_name': user_payload['l_name'],
                    'profile_pic': user_payload['profile_pic'],
                    'created_at': entry['created_at'],
                })
            
            logger.info("recent_searches_view GET returning %s rows", len(searches_data))
            legacy_payload = [
                {
                    'id': entry['id'],
                    'user_id': entry['user_id'],
                    'f_name': entry['f_name'],
                    'l_name': entry['l_name'],
                    'profile_pic': entry['profile_pic'],
                    'created_at': entry['created_at']
                }
                for entry in flat_recent
            ]

            return JsonResponse({
                'success': True,
                'recent_searches': searches_data,
                'recent': legacy_payload,  # Backwards compatibility for mobile clients
                'count': len(searches_data)
            })
            
        elif request.method == "POST":
            try:
                data = json.loads(request.body or '{}')
            except json.JSONDecodeError:
                return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
                
            searched_user_id = data.get('searched_user_id')
            
            # Enhanced input validation
            if not isinstance(searched_user_id, int):
                return JsonResponse({'success': False, 'error': 'searched_user_id must be an integer'}, status=400)
            
            # Handle self-search edge case (mobile-friendly)
            current_user_id = getattr(user, 'user_id', getattr(user, 'id', None))
            if searched_user_id == current_user_id:
                return JsonResponse({'success': True, 'message': 'Self-search ignored'})
            
            try:
                searched_user = User.objects.get(user_id=searched_user_id)
            except User.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'User not found'}, status=404)
            
            # Mobile optimization: Delete existing entry first to maintain order
            RecentSearch.objects.filter(owner=user, searched_user=searched_user).delete()
            RecentSearch.objects.create(owner=user, searched_user=searched_user)
            
            logger.info("recent_searches_view POST created owner=%s searched_user=%s", 
                       getattr(user, 'user_id', None) or getattr(user, 'id', None), 
                       getattr(searched_user, 'user_id', None) or getattr(searched_user, 'id', None))
            
            # Mobile-friendly: Limit total searches to prevent bloat
            total_searches = RecentSearch.objects.filter(owner=user).count()
            if total_searches > 10:
                # Keep only the 10 most recent
                old_searches = RecentSearch.objects.filter(owner=user).order_by('-created_at')[10:]
                RecentSearch.objects.filter(id__in=[s.id for s in old_searches]).delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Recent search saved'
            })
            
        elif request.method == "DELETE":
            # Clear all recent searches (mobile-friendly)
            RecentSearch.objects.filter(owner=user).delete()
            logger.info("recent_searches_view DELETE cleared all searches for user=%s", 
                       getattr(user, 'user_id', None) or getattr(user, 'id', None))
            return JsonResponse({'success': True, 'message': 'All recent searches cleared'})
            
    except Exception as e:
        logger.error(f"recent_searches_view error: {e}")
        return JsonResponse({'success': False, 'error': 'Server error'}, status=500)

@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def recent_search_delete_view(request, search_id):
    """Delete a specific recent search"""
    try:
        user = request.user
        recent_search = RecentSearch.objects.get(id=search_id, owner=user)
        recent_search.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Recent search deleted'
        })
        
    except RecentSearch.DoesNotExist:
        return JsonResponse({'error': 'Recent search not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def post_delete_view(request, post_id):
    try:
        post = Post.objects.get(post_id=post_id)
        user = request.user

        # Allow deletion if user owns the post OR user is admin
        if post.user.user_id != user.user_id and not getattr(user.account_type, 'admin', False):
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        try:
            # Check if post has images before deletion to determine point type
            has_images = False
            try:
                has_images = ContentImage.objects.filter(content_type='post', content_id=post.post_id).exists()
            except Exception as e:
                logger.warning(f"Could not check ContentImage for post deletion points: {e}")
            
            # Best-effort cleanup of associated uploaded files before deletion
            if getattr(post, 'post_image', None):
                try:
                    post.post_image.delete(save=False)
                except Exception:
                    pass

            images_rel = getattr(post, 'images', None)
            if images_rel is not None:
                for img in list(images_rel.all()):
                    try:
                        if getattr(img, 'image', None):
                            img.image.delete(save=False)
                    except Exception:
                        pass
                images_rel.all().delete()

            # Delete related images using ContentImage
            content_images = ContentImage.objects.filter(content_type='post', content_id=post.post_id)
            for img in content_images:
                if getattr(img, 'image', None):
                    img.image.delete(save=False)
            content_images.delete()

            # Deduct engagement points before deleting the post
            if has_images:
                deduct_engagement_points(user, 'post_with_photo')
            else:
                deduct_engagement_points(user, 'post')

            # Finally delete the post itself
            post.delete()
            return JsonResponse({'success': True, 'message': 'Post deleted'})

        except Exception as e:
            logger.error(f"post_delete_view failed for post_id={post_id}: {e}")
            return JsonResponse(
                {'success': False, 'message': 'Delete failed', 'error': str(e)},
                status=500
            )

    except Post.DoesNotExist:
        return JsonResponse({'error': 'Post not found'}, status=404)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
@api_view(["POST"]) 
@permission_classes([IsAuthenticated])
def post_repost_view(request, post_id):
    if request.method == "OPTIONS":
        response = JsonResponse({'detail': 'OK'})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken, Authorization"
        return response

    try:
        post = Post.objects.get(post_id=post_id)

        # Get user from token
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return JsonResponse({'error': 'Authentication required'}, status=401)

        token = auth_header.split(' ')[1]
        try:
            from rest_framework_simplejwt.tokens import AccessToken
            access_token = AccessToken(token)
            user_id = access_token['user_id']
            user = User.objects.get(user_id=user_id)
        except Exception as e:
            return JsonResponse({'error': 'Invalid token'}, status=401)

        # Create repost with optional caption
        payload = {}
        try:
            payload = json.loads(request.body or "{}")
        except Exception:
            payload = {}
        caption = (payload.get('caption') or '').strip() or None
        repost = Repost.objects.create(
            user=user,
            post=post,
            repost_date=timezone.now(),
            caption=caption,
        )
        
        # Award engagement points (+5 for share/repost)
        award_engagement_points(user, 'share')

        # Create notification for post owner (only if the reposter is not the post owner)
        if user.user_id != post.user.user_id:
            repost_notification = Notification.objects.create(
                user=post.user,
                notif_type='repost',
                subject='Post Reposted',
                notifi_content=(
                    f"{user.full_name} reposted your post"
                    f"<!--REPOST_ID:{repost.repost_id}-->"
                    f"<!--POST_ID:{post.post_id}-->"
                    f"<!--ACTOR_ID:{user.user_id}-->"
                ),
                notif_date=timezone.now()
            )
            
            # Broadcast repost notification in real-time
            try:
                from apps.messaging.notification_broadcaster import broadcast_notification
                broadcast_notification(repost_notification)
            except Exception as e:
                logger.error(f"Error broadcasting repost notification: {e}")

        return JsonResponse({
            'success': True,
            'repost_id': repost.repost_id,
            'message': 'Post reposted successfully'
        })
    except Post.DoesNotExist:
        return JsonResponse({'error': 'Post not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(["PUT", "DELETE"]) 
@permission_classes([IsAuthenticated])
def repost_delete_view(request, repost_id):
    """
    Unified handler for editing and deleting reposts (post, forum, and donation reposts)
    """
    try:
        repost = Repost.objects.get(repost_id=repost_id)

        # Check if user owns the repost
        if repost.user.user_id != request.user.user_id:
            return JsonResponse({'error': 'Unauthorized - You can only edit/delete your own reposts'}, status=403)

        if request.method == 'PUT':
            # Edit repost caption
            try:
                data = json.loads(request.body or '{}')
                caption = (data.get('caption') or '').strip() or None
                repost.caption = caption
                repost.save(update_fields=['caption'])
                print(f"✏️ DEBUG: User {request.user.user_id} edited repost {repost_id}, new caption: {caption}")
                return JsonResponse({'success': True, 'message': 'Repost updated successfully'})
            except Exception as e:
                print(f"❌ ERROR editing repost {repost_id}: {str(e)}")
                return JsonResponse({'success': False, 'error': str(e)}, status=400)

        elif request.method == 'DELETE':
            # Delete repost
            print(f"🗑️ DEBUG: User {request.user.user_id} deleting repost {repost_id}")
            # Deduct engagement points for deleting repost (share)
            deduct_engagement_points(request.user, 'share')
            repost.delete()
            return JsonResponse({'success': True, 'message': 'Repost deleted successfully'})
            
    except Repost.DoesNotExist:
        return JsonResponse({'error': 'Repost not found'}, status=404)
    except Exception as e:
        print(f"❌ ERROR in repost_delete_view: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def alumni_followers_view(request, user_id):
    if request.method == "OPTIONS":
        response = JsonResponse({'detail': 'OK'})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken, Authorization"
        return response

    try:
        user = User.objects.get(user_id=user_id)
        from apps.shared.models import Follow
        followers = Follow.objects.filter(following=user).select_related('follower')
        if not followers.exists():
            return JsonResponse({
                'success': True,
                'followers': [],
                'message': 'no followers',
                'count': 0
            })
        followers_data = []
        for follow_obj in followers:
            follower = follow_obj.follower
            followers_data.append({
                'user_id': follower.user_id,
                'ctu_id': follower.acc_username,
                'name': ' '.join(filter(None, [follower.f_name, follower.m_name, follower.l_name])),
                'f_name': follower.f_name,
                'm_name': follower.m_name,
                'l_name': follower.l_name,
                'profile_pic': build_profile_pic_url(follower),
                'followed_at': follow_obj.followed_at.isoformat()
            })
        return JsonResponse({
            'success': True,
            'followers': followers_data,
            'count': len(followers_data)
        })
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def alumni_following_view(request, user_id):
    if request.method == "OPTIONS":
        response = JsonResponse({'detail': 'OK'})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken, Authorization"
        return response

    try:
        user = User.objects.get(user_id=user_id)
        from apps.shared.models import Follow
        following = Follow.objects.filter(follower=user).select_related('following')
        if not following.exists():
            return JsonResponse({
                'success': True,
                'following': [],
                'message': 'no following',
                'count': 0
            })
        following_data = []
        for follow_obj in following:
            followed_user = follow_obj.following
            following_data.append({
                'user_id': followed_user.user_id,
                'ctu_id': followed_user.acc_username,
                'name': ' '.join(filter(None, [followed_user.f_name, followed_user.m_name, followed_user.l_name])),
                'f_name': followed_user.f_name,
                'm_name': followed_user.m_name,
                'l_name': followed_user.l_name,
                'profile_pic': build_profile_pic_url(followed_user),
                'followed_at': follow_obj.followed_at.isoformat()
            })
        return JsonResponse({
            'success': True,
            'following': following_data,
            'count': len(following_data)
        })
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from apps.shared.models import Follow
from apps.shared.models import Forum, Like, Comment, Repost, Post, Notification

# ==========================
# Helper Functions
# ==========================

def notify_users_of_admin_peso_post(post_author, post_type="post", post_id=None):
    """Notify all OJT and alumni users when admin or PESO users post"""
    try:
        # Check if the post author is admin or PESO
        if not (post_author.account_type.admin or post_author.account_type.peso):
            return 0  # Only notify for admin/PESO posts
        
        # Get all OJT and alumni users
        ojt_users = User.objects.filter(account_type__ojt=True)
        alumni_users = User.objects.filter(account_type__user=True)
        
        # Combine both user types
        target_users = list(ojt_users) + list(alumni_users)
        
        # Create notification for each user
        notifications_created = 0
        for user in target_users:
            # Skip notifying the post author themselves
            if user.user_id == post_author.user_id:
                continue
                
            # Get author's profile picture URL
            profile_pic_url = ""
            if hasattr(post_author, 'profile') and post_author.profile and post_author.profile.profile_pic:
                profile_pic_url = post_author.profile.profile_pic.url
            
            # Determine author label
            if post_author.account_type.admin:
                author_label = "Admin"
            elif post_author.account_type.peso:
                author_label = "PESO"
            
            # Determine notification content based on post type and author label
            if post_type == "forum":
                content = f"{author_label} posted a new forum discussion."
                subject = f"New Forum Discussion from {author_label}"
            elif post_type == "donation":
                content = f"{author_label} created a new donation request."
                subject = f"New Donation Request from {author_label}"
            else:
                content = f"{author_label} shared a new post."
                subject = f"New Post from {author_label}"
            
            # Add author info (hidden metadata)
            content += f"<!--AUTHOR_ID:{post_author.user_id}-->"
            content += f"<!--AUTHOR_NAME:{post_author.full_name}-->"
            
            # Add post link if available
            if post_id:
                if post_type == "forum":
                    content += f"<!--FORUM_ID:{post_id}-->"
                elif post_type == "donation":
                    content += f"<!--DONATION_ID:{post_id}-->"
                else:
                    content += f"<!--POST_ID:{post_id}-->"
            
            notification = Notification.objects.create(
                user=user,
                notif_type='admin_peso_post',
                subject=subject,
                notifi_content=content,
                notif_date=timezone.now()
            )
            
            # Broadcast notification in real-time
            try:
                from apps.messaging.notification_broadcaster import broadcast_notification
                broadcast_notification(notification)
            except Exception as e:
                logger.error(f"Error broadcasting admin/peso post notification: {e}")
            notifications_created += 1
        
        return notifications_created
        
    except Exception as e:
        print(f"Error creating notifications: {e}")
        return 0
# ==========================
# Forum API (shared_forum links to shared_post)
# ==========================
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, JSONParser])
def forum_list_create_view(request):
    try:
        if request.method == "POST":
            # Handle both FormData and JSON requests using request.data
            data = request.data
            content = data.get('post_content') or data.get('content') or ''
            
            logger.info(f'Forum POST received - Content: {content[:50] if content else "None"}...')
            logger.info(f'Forum POST data keys: {list(data.keys())}')
            logger.info(f'Forum POST - Has "image": {"image" in data}, Has "images": {"images" in data}')
            if 'images' in data:
                logger.info(f'Forum POST - images type: {type(data["images"])}, count: {len(data["images"]) if isinstance(data["images"], list) else "N/A"}')
            
            if not str(content).strip():
                return JsonResponse({'error': 'content required'}, status=400)
            
            # Create Forum post directly (no Post model)
            forum = Forum.objects.create(
                user=request.user,
                content=content,
                type='forum',
            )
            
            # Handle image uploads - base64 or FormData
            import uuid
            import base64
            from django.core.files.base import ContentFile
            
            try:
                # Handle base64 encoded image (single image from web frontend)
                if 'image' in data and data['image'] and isinstance(data['image'], str) and data['image'].startswith('data:image'):
                    logger.info('Received base64 image for forum')
                    try:
                        format, imgstr = data['image'].split(';base64,')
                        ext = format.split('/')[-1]
                        img_data = base64.b64decode(imgstr)
                        file_name = f"{uuid.uuid4()}.{ext}"
                        
                        # Create ContentImage instance for forum
                        forum_image = ContentImage.objects.create(
                            content_type='forum',
                            content_id=forum.forum_id,
                            order=0
                        )
                        forum_image.image.save(file_name, ContentFile(img_data), save=True)
                        logger.info(f'Saved base64 forum image: {forum_image.image.url}')
                    except Exception as img_exc:
                        logger.error(f'Error saving base64 forum image: {img_exc}')
                
                # Handle multiple base64 encoded images (from web frontend with multiple images)
                elif 'images' in data and isinstance(data['images'], list) and len(data['images']) > 0:
                    logger.info(f'Received {len(data["images"])} base64 images for forum')
                    for index, image_data in enumerate(data['images']):
                        if image_data and isinstance(image_data, str) and image_data.startswith('data:image'):
                            try:
                                format, imgstr = image_data.split(';base64,')
                                ext = format.split('/')[-1]
                                img_data = base64.b64decode(imgstr)
                                file_name = f"{uuid.uuid4()}.{ext}"
                                
                                # Create ContentImage instance for forum
                                forum_image = ContentImage.objects.create(
                                    content_type='forum',
                                    content_id=forum.forum_id,
                                    order=index
                                )
                                forum_image.image.save(file_name, ContentFile(img_data), save=True)
                                logger.info(f'Saved base64 forum image {index}: {forum_image.image.url}')
                            except Exception as img_exc:
                                logger.error(f'Error saving base64 forum image {index}: {img_exc}')
                
                # Handle FormData file uploads (from mobile app)
                elif hasattr(request, 'FILES') and request.FILES:
                    logger.info(f'Received {len(request.FILES)} files via FormData for forum')
                    
                    # Get all image files and sort them by key to ensure consistent ordering
                    image_files = []
                    for key, file in request.FILES.items():
                        if key.startswith('images') and file:
                            image_files.append((key, file))
                    
                    # Sort by key to ensure consistent ordering (images[0], images[1], etc.)
                    image_files.sort(key=lambda x: x[0])
                    
                    for order_index, (key, file) in enumerate(image_files):
                        try:
                            # Create ContentImage instance for forum
                            forum_image = ContentImage.objects.create(
                                content_type='forum',
                                content_id=forum.forum_id,
                                order=order_index
                            )
                            forum_image.image.save(file.name, file, save=True)
                            logger.info(f'Saved FormData forum image {order_index}: {forum_image.image.url}')
                        except Exception as e:
                            logger.error(f'Error saving FormData forum image {order_index}: {e}')
                            continue
            except Exception as e:
                logger.error(f'Error handling images for forum: {e}')
            
            # Notify OJT and alumni users if post author is admin or PESO
            notify_users_of_admin_peso_post(request.user, "forum", forum.forum_id)
            
            return JsonResponse({'success': True, 'forum_id': forum.forum_id})

        # GET list - filter by user's batch (year_graduated)
        current_user_batch = None
        if hasattr(request.user, 'academic_info') and request.user.academic_info:
            current_user_batch = request.user.academic_info.year_graduated
        
        # Only show forum posts from users in the same batch
        if current_user_batch:
            forums = Forum.objects.select_related('user', 'user__academic_info').filter(
                user__academic_info__year_graduated=current_user_batch
            ).order_by('-forum_id')
        else:
            # If user has no batch info, show no forum posts
            forums = Forum.objects.none()
        
        items = []
        for f in forums:
            try:
                # Get likes, comments, and reposts data (using shared tables)
                likes = Like.objects.filter(forum=f).select_related('user')
                comments = Comment.objects.filter(forum=f).select_related('user').order_by('-date_created')
                reposts = Repost.objects.filter(forum=f).select_related('user')
                
                likes_count = likes.count()
                comments_count = comments.count()
                reposts_count = reposts.count()
                is_liked = Like.objects.filter(forum=f, user=request.user).exists()
                
                # Get forum images
                forum_images = []
                if hasattr(f, 'images'):
                    for img in f.images.all():
                        forum_images.append({
                            'image_id': img.image_id,
                            'image_url': img.image.url,
                            'order': img.order
                        })
                
                items.append({
                    'post_id': f.forum_id,  # Use forum_id as post_id for frontend compatibility
                    'post_content': f.content,
                    'post_image': None,  # Forum posts don't have single image
                    'post_images': forum_images,  # Multiple images
                    'type': 'forum',
                    'created_at': f.created_at.isoformat() if f.created_at else None,
                    'likes_count': likes_count,
                    'comments_count': comments_count,
                    'reposts_count': reposts_count,
                    'is_liked': is_liked,
                    'likes': [{
                        'user_id': l.user.user_id,
                        'f_name': l.user.f_name,
                        'm_name': l.user.m_name,
                        'l_name': l.user.l_name,
                        'profile_pic': build_profile_pic_url(l.user),
                        'initials': None if build_profile_pic_url(l.user) else (
                            ((l.user.f_name or '').strip()[:1].upper() + (l.user.l_name or '').strip()[:1].upper()) 
                            if ((l.user.f_name or '').strip() or (l.user.l_name or '').strip()) else None
                        ),
                    } for l in likes],
                    'comments': [{
                        'comment_id': c.comment_id,
                        'comment_content': c.comment_content,
                        'date_created': c.date_created.isoformat() if c.date_created else None,
                        'user': {
                            'user_id': c.user.user_id,
                            'f_name': c.user.f_name,
                            'm_name': c.user.m_name,
                            'l_name': c.user.l_name,
                            'profile_pic': build_profile_pic_url(c.user),
                        }
                    } for c in comments],
                    'reposts': [{
                        'repost_id': r.repost_id,
                        'repost_date': r.repost_date.isoformat(),
                        'repost_caption': r.caption,
                        'user': {
                            'user_id': r.user.user_id,
                            'f_name': r.user.f_name,
                            'm_name': r.user.m_name,
                            'l_name': r.user.l_name,
                            'profile_pic': build_profile_pic_url(r.user),
                        },
                        # Get repost likes and comments
                        'likes': [{
                            'like_id': like.like_id,
                            'user_id': like.user.user_id,
                            'user': {
                                'user_id': like.user.user_id,
                                'f_name': like.user.f_name,
                                'm_name': like.user.m_name,
                                'l_name': like.user.l_name,
                                'profile_pic': build_profile_pic_url(like.user),
                            }
                        } for like in Like.objects.filter(repost=r).select_related('user')],
                        'likes_count': Like.objects.filter(repost=r).count(),
                        'comments': [{
                            'comment_id': comment.comment_id,
                            'comment_content': comment.comment_content,
                            'date_created': comment.date_created.isoformat() if comment.date_created else None,
                            'replies_count': Reply.objects.filter(comment=comment).count(),
                            'user': {
                                'user_id': comment.user.user_id,
                                'f_name': comment.user.f_name,
                                'm_name': comment.user.m_name,
                                'l_name': comment.user.l_name,
                                'profile_pic': build_profile_pic_url(comment.user),
                            }
                        } for comment in Comment.objects.filter(repost=r).select_related('user').order_by('-date_created')],
                        'comments_count': Comment.objects.filter(repost=r).count(),
                        'original_post': {
                            'post_id': f.forum_id,
                            'post_content': f.content,
                            'post_image': None,  # Forum posts don't have single image
                            'created_at': f.created_at.isoformat() if f.created_at else None,
                            'user': {
                                'user_id': f.user.user_id,
                                'f_name': f.user.f_name,
                                'm_name': f.user.m_name,
                                'l_name': f.user.l_name,
                                'profile_pic': build_profile_pic_url(f.user),
                            }
                        }
                    } for r in reposts],
                    'user': {
                        'user_id': f.user.user_id,
                        'f_name': f.user.f_name,
                        'm_name': f.user.m_name,
                        'l_name': f.user.l_name,
                        'profile_pic': build_profile_pic_url(f.user),
                    }
                })
            except Exception as e:
                print(f"Error processing forum {f.forum_id}: {str(e)}")
                import traceback
                traceback.print_exc()
                continue
        return JsonResponse({'forums': items})
    except Exception as e:
        print(f"Error in forum_list_create_view: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'forums': [], 'error': str(e)}, status=200)
@api_view(["GET", "PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def forum_detail_edit_view(request, forum_id):
    try:
        forum = Forum.objects.select_related('user', 'user__academic_info').get(forum_id=forum_id)
        
        # Check if user can access this forum post (same batch only)
        current_user_batch = None
        if hasattr(request.user, 'academic_info') and request.user.academic_info:
            current_user_batch = request.user.academic_info.year_graduated
        
        forum_user_batch = None
        if hasattr(forum.user, 'academic_info') and forum.user.academic_info:
            forum_user_batch = forum.user.academic_info.year_graduated
        
        # Only allow access if same batch or if user is the author
        if current_user_batch != forum_user_batch and request.user.user_id != forum.user.user_id:
            return JsonResponse({'error': 'Access denied - different batch'}, status=403)
            
    except Forum.DoesNotExist:
        return JsonResponse({'error': 'Forum not found'}, status=404)

    # Authorization for mutating
    is_owner = request.user.user_id == forum.user.user_id
    is_admin = getattr(getattr(request.user, 'account_type', None), 'admin', False)

    if request.method == "GET":
        try:
            likes = Like.objects.filter(forum=forum).select_related('user')
            comments = Comment.objects.filter(forum=forum).select_related('user').order_by('-date_created')
            reposts = Repost.objects.filter(forum=forum).select_related('user')
            is_liked = Like.objects.filter(forum=forum, user=request.user).exists()
            
            # Get images from ContentImage model
            post_images = []
            try:
                content_images = ContentImage.objects.filter(content_type='forum', content_id=forum.forum_id).order_by('order')
                post_images = [{
                    'image_id': img.image_id,
                    'image_url': img.image.url if img.image else None,
                    'order': img.order
                } for img in content_images]
            except Exception as e:
                print(f"Warning: Could not load ContentImage for forum: {e}")
                post_images = []

            return JsonResponse({
                'post_id': forum.forum_id,
                'post_content': forum.content,
                'post_image': None,  # Forum posts don't have single image
                'post_images': post_images,  # Use ContentImage instead
                'type': 'forum',
                'created_at': forum.created_at.isoformat() if forum.created_at else None,
                'likes_count': likes.count(),
                'comments_count': comments.count(),
                'reposts_count': reposts.count(),
                'liked_by_user': is_liked,
                'likes': [{
                    'user_id': l.user.user_id,
                    'f_name': l.user.f_name,
                    'm_name': l.user.m_name,
                    'l_name': l.user.l_name,
                    'profile_pic': build_profile_pic_url(l.user),
                    'initials': None if build_profile_pic_url(l.user) else (
                        ((l.user.f_name or '').strip()[:1].upper() + (l.user.l_name or '').strip()[:1].upper()) 
                        if ((l.user.f_name or '').strip() or (l.user.l_name or '').strip()) else None
                    ),
                } for l in likes],
                'comments': [{
                    'comment_id': c.comment_id,
                    'comment_content': c.comment_content,
                    'date_created': c.date_created.isoformat() if c.date_created else None,
                    'user': {
                        'user_id': c.user.user_id,
                        'f_name': c.user.f_name,
                        'm_name': c.user.m_name,
                        'l_name': c.user.l_name,
                        'profile_pic': build_profile_pic_url(c.user),
                    }
                } for c in comments],
                'reposts': [{
                    'repost_id': r.repost_id,
                    'repost_date': r.repost_date.isoformat() if r.repost_date else None,
                    'repost_caption': r.caption,
                    'user': {
                        'user_id': r.user.user_id,
                        'f_name': r.user.f_name,
                        'm_name': r.user.m_name,
                        'l_name': r.user.l_name,
                        'profile_pic': build_profile_pic_url(r.user),
                    },
                    'original_post': {
                        'post_id': forum.forum_id,
                        'post_content': forum.content,
                        'post_image': None,  # Forum posts don't have single image
                        'post_images': post_images,  # Use ContentImage instead
                        'created_at': forum.created_at.isoformat() if forum.created_at else None,
                        'user': {
                            'user_id': forum.user.user_id,
                            'f_name': forum.user.f_name,
                            'm_name': forum.user.m_name,
                            'l_name': forum.user.l_name,
                            'profile_pic': build_profile_pic_url(forum.user),
                        }
                    }
                } for r in reposts],
                'user': {
                    'user_id': forum.user.user_id,
                    'f_name': forum.user.f_name,
                    'm_name': forum.user.m_name,
                    'l_name': forum.user.l_name,
                    'profile_pic': build_profile_pic_url(forum.user),
                }
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    if request.method == "PUT":
        if not (is_owner or is_admin):
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        data = json.loads(request.body or "{}")
        content = data.get('post_content') or data.get('content')
        if content is not None:
            forum.content = content
        forum.save()
        return JsonResponse({'success': True, 'message': 'Forum updated'})

    if request.method == "DELETE":
        if not (is_owner or is_admin):
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        # delete forum directly (cascades remove related likes, comments, reposts)
        forum.delete()
        return JsonResponse({'success': True, 'message': 'Forum deleted'})
@api_view(["POST", "DELETE"]) 
@permission_classes([IsAuthenticated])
def forum_like_view(request, forum_id):
    try:
        forum = Forum.objects.select_related('user', 'user__academic_info').get(forum_id=forum_id)
        
        # Check if user can access this forum post (same batch only)
        current_user_batch = None
        if hasattr(request.user, 'academic_info') and request.user.academic_info:
            current_user_batch = request.user.academic_info.year_graduated
        
        forum_user_batch = None
        if hasattr(forum.user, 'academic_info') and forum.user.academic_info:
            forum_user_batch = forum.user.academic_info.year_graduated
        
        # Only allow access if same batch
        if current_user_batch != forum_user_batch:
            return JsonResponse({'error': 'Access denied - different batch'}, status=403)
        if request.method == 'POST':
            like, created = Like.objects.get_or_create(
                forum=forum, 
                user=request.user,
                defaults={
                    'post': None,
                    'repost': None,
                    'donation_request': None
                }
            )
            if created:
                # Award engagement points for liking
                award_engagement_points(request.user, 'like')
                
            if created and request.user.user_id != forum.user.user_id:
                notification = Notification.objects.create(
                    user=forum.user,
                    notif_type='like',
                    subject='Forum Liked',
                    notifi_content=f"{request.user.full_name} liked your forum post<!--FORUM_ID:{forum.forum_id}-->",
                    notif_date=timezone.now()
                )
                
                # Broadcast forum like notification in real-time
                try:
                    from apps.messaging.notification_broadcaster import broadcast_notification
                    broadcast_notification(notification)
                except Exception as e:
                    logger.error(f"Error broadcasting forum like notification: {e}")
            return JsonResponse({'success': True})
        else:
            try:
                like = Like.objects.get(forum=forum, user=request.user)
                like.delete()
                # Deduct engagement points for unliking
                deduct_engagement_points(request.user, 'like')
            except Like.DoesNotExist:
                pass
            return JsonResponse({'success': True})
    except Forum.DoesNotExist:
        return JsonResponse({'error': 'Forum not found'}, status=404)


@api_view(["GET", "POST"]) 
@permission_classes([IsAuthenticated])
def forum_comments_view(request, forum_id):
    try:
        forum = Forum.objects.select_related('user', 'user__academic_info').get(forum_id=forum_id)
        
        # Check if user can access this forum post (same batch only)
        current_user_batch = None
        if hasattr(request.user, 'academic_info') and request.user.academic_info:
            current_user_batch = request.user.academic_info.year_graduated
        
        forum_user_batch = None
        if hasattr(forum.user, 'academic_info') and forum.user.academic_info:
            forum_user_batch = forum.user.academic_info.year_graduated
        
        # Only allow access if same batch
        if current_user_batch != forum_user_batch:
            return JsonResponse({'error': 'Access denied - different batch'}, status=403)
        if request.method == 'GET':
            comments = Comment.objects.filter(forum=forum).select_related('user').order_by('-date_created')
            #shaira
            data = []
            for c in comments:
                # Get reply count for this comment
                reply_count = Reply.objects.filter(comment=c).count()
                data.append({
                    'comment_id': c.comment_id,
                    'comment_content': c.comment_content,
                    'date_created': c.date_created.isoformat() if c.date_created else None,
                    'replies_count': reply_count,
                    'user': {
                        'user_id': c.user.user_id,
                        'f_name': c.user.f_name,
                        'l_name': c.user.l_name,
                        'profile_pic': build_profile_pic_url(c.user),
                    }
                })
            return JsonResponse({'comments': data})
        else:
            payload = json.loads(request.body or "{}")
            content = payload.get('comment_content') or ''
            comment = Comment.objects.create(
                user=request.user,
                forum=forum,
                comment_content=content,
                date_created=timezone.now()
            )
            
            # Create mention notifications
            create_mention_notifications(
                content,
                request.user,
                comment_id=comment.comment_id,
                forum_id=forum.forum_id
            )
            
            if request.user.user_id != forum.user.user_id:
                forum_comment_notification = Notification.objects.create(
                    user=forum.user,
                    notif_type='comment',
                    subject='Forum Commented',
                    notifi_content=f"{request.user.full_name} commented on your forum post<!--FORUM_ID:{forum.forum_id}--><!--COMMENT_ID:{comment.comment_id}--><!--ACTOR_ID:{request.user.user_id}-->",
                    notif_date=timezone.now()
                )
                
                # Broadcast forum comment notification in real-time
                try:
                    from apps.messaging.notification_broadcaster import broadcast_notification
                    broadcast_notification(forum_comment_notification)
                except Exception as e:
                    logger.error(f"Error broadcasting forum comment notification: {e}")
            return JsonResponse({'success': True, 'comment_id': comment.comment_id})
    except Forum.DoesNotExist:
        return JsonResponse({'error': 'Forum not found'}, status=404)


@api_view(["PUT", "DELETE"]) 
@permission_classes([IsAuthenticated])
def forum_comment_edit_view(request, forum_id, comment_id):
    try:
        forum = Forum.objects.get(forum_id=forum_id)
        comment = Comment.objects.get(comment_id=comment_id, forum=forum)
        
        # Check if current user owns this comment OR owns the post
        comment_owner = comment.user.user_id == request.user.user_id
        post_owner = forum.user.user_id == request.user.user_id
        
        if not (comment_owner or post_owner):
            return JsonResponse({'error': 'Unauthorized'}, status=403)
            
        if request.method == 'PUT':
            # Only comment owner can edit
            if not comment_owner:
                return JsonResponse({'error': 'Only comment owner can edit'}, status=403)
            data = json.loads(request.body or "{}")
            content = data.get('comment_content')
            if content is None:
                return JsonResponse({'error': 'No content provided'}, status=400)
            comment.comment_content = content
            comment.save()
            return JsonResponse({'success': True})
        else:
            # Both comment owner and post owner can delete
            # Deduct engagement points for deleting comment
            deduct_engagement_points(comment.user, 'comment')
            comment.delete()
            return JsonResponse({'success': True})
    except Comment.DoesNotExist:
        return JsonResponse({'error': 'Comment not found'}, status=404)


@api_view(["POST"]) 
@permission_classes([IsAuthenticated])
def forum_repost_view(request, forum_id):
    try:
        forum = Forum.objects.select_related('user', 'user__academic_info').get(forum_id=forum_id)
        
        # Check if user can access this forum post (same batch only)
        current_user_batch = None
        if hasattr(request.user, 'academic_info') and request.user.academic_info:
            current_user_batch = request.user.academic_info.year_graduated
        
        forum_user_batch = None
        if hasattr(forum.user, 'academic_info') and forum.user.academic_info:
            forum_user_batch = forum.user.academic_info.year_graduated
        
        # Only allow access if same batch
        if current_user_batch != forum_user_batch:
            return JsonResponse({'error': 'Access denied - different batch'}, status=403)
        
        # Create repost with optional caption
        payload = {}
        try:
            payload = json.loads(request.body or "{}")
        except Exception:
            payload = {}
        caption = (payload.get('caption') or '').strip() or None
        
        r = Repost.objects.create(
            forum=forum, 
            user=request.user, 
            repost_date=timezone.now(),
            caption=caption
        )
        
        # Award engagement points (+5 for share/repost)
        award_engagement_points(request.user, 'share')
        
        # Create notification for forum owner (only if the reposter is not the forum owner)
        if request.user.user_id != forum.user.user_id:
            forum_repost_notification = Notification.objects.create(
                user=forum.user,
                notif_type='repost',
                subject='Forum Reposted',
                notifi_content=f"{request.user.full_name} reposted your forum post<!--FORUM_ID:{forum.forum_id}--><!--ACTOR_ID:{request.user.user_id}-->",
                notif_date=timezone.now()
            )
            
            # Broadcast forum repost notification in real-time
            try:
                from apps.messaging.notification_broadcaster import broadcast_notification
                broadcast_notification(forum_repost_notification)
            except Exception as e:
                logger.error(f"Error broadcasting forum repost notification: {e}")
        return JsonResponse({'success': True, 'repost_id': r.repost_id})
    except Forum.DoesNotExist:
        return JsonResponse({'error': 'Forum not found'}, status=404)


@api_view(["DELETE"]) 
@permission_classes([IsAuthenticated])
def forum_repost_delete_view(request, repost_id):
    try:
        r = Repost.objects.get(repost_id=repost_id)
        if r.user.user_id != request.user.user_id:
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        # Deduct engagement points for deleting repost (share)
        deduct_engagement_points(request.user, 'share')
        r.delete()
        return JsonResponse({'success': True})
    except Repost.DoesNotExist:
        return JsonResponse({'error': 'Repost not found'}, status=404)


# ==========================
# Legacy: user_posts_view (for compatibility with existing routes)
# ==========================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_posts_view(request, user_id):
    try:
        posts = Post.objects.filter(user__user_id=user_id).select_related('user').order_by('-post_id')
        data = []
        for post in posts:
            try:
                likes_count = Like.objects.filter(post=post).count()
                comments_count = Comment.objects.filter(post=post).count()
                reposts_count = Repost.objects.filter(post=post).count()
                data.append({
                    'post_id': post.post_id,
                    'post_content': post.post_content,
                    'post_image': getattr(post, 'post_image', None) and (post.post_image.url if hasattr(post.post_image, 'url') else None),
                    'type': post.type,
                    'created_at': getattr(post, 'created_at', None).isoformat() if getattr(post, 'created_at', None) else None,
                    'likes_count': likes_count,
                    'comments_count': comments_count,
                    'reposts_count': reposts_count,
                    'user': {
                        'user_id': post.user.user_id,
                        'f_name': post.user.f_name,
                        'l_name': post.user.l_name,
                        'profile_pic': build_profile_pic_url(post.user),
                    }
                })
            except Exception:
                continue
        return JsonResponse({'posts': data})
    except Exception as e:
        return JsonResponse({'posts': [], 'error': str(e)})

@api_view(["POST","DELETE"])
@permission_classes([IsAuthenticated])
def follow_user_view(request, user_id):
    if request.method == "OPTIONS":
        response = JsonResponse({'detail': 'OK'})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "POST, DELETE, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken, Authorization"
        return response

    try:
        # Authenticate via JWT manually to avoid issues with custom user
        current_user = get_current_user_from_request(request)
        if not current_user:
            return JsonResponse({'error': 'Authentication required'}, status=401)

        user_to_follow = User.objects.get(user_id=user_id)

        if current_user.user_id == user_to_follow.user_id:
            return JsonResponse({'error': 'Cannot follow yourself'}, status=400)

        if request.method == 'POST':
            follow_obj, created = Follow.objects.get_or_create(
                follower=current_user,
                following=user_to_follow
            )
            if created:
                # Notify the followed user
                try:
                    follow_notification = Notification.objects.create(
                        user=user_to_follow,
                        notif_type='follow',
                        subject='New Follower',
                        notifi_content=f"{current_user.full_name}|{current_user.user_id} started following you.",
                        notif_date=timezone.now()
                    )
                    
                    # Broadcast follow notification in real-time
                    try:
                        from apps.messaging.notification_broadcaster import broadcast_notification
                        broadcast_notification(follow_notification)
                    except Exception as e:
                        logger.error(f"Error broadcasting follow notification: {e}")
                except Exception as e:
                    logger.error(f"Error creating follow notification: {e}")
                return JsonResponse({
                    'success': True,
                    'message': f'Successfully followed {user_to_follow.f_name} {user_to_follow.m_name or ""} {user_to_follow.l_name}'.strip()
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Already following this user'
                }, status=400)

        elif request.method == 'DELETE':
            try:
                follow_obj = Follow.objects.get(
                    follower=current_user,
                    following=user_to_follow
                )
                follow_obj.delete()
                return JsonResponse({
                    'success': True,
                    'message': f'Successfully unfollowed {user_to_follow.f_name} {user_to_follow.m_name or ""} {user_to_follow.l_name}'.strip()
                })
            except Follow.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Not following this user'
                }, status=400)

    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def check_follow_status_view(request, user_id):
    if request.method == "OPTIONS":
        response = JsonResponse({'detail': 'OK'})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken, Authorization"
        return response

    try:
        # Get the user to check
        user_to_check = User.objects.get(user_id=user_id)

        # Get the current user from token
        auth_header = request.headers.get('Authorization') or request.META.get('HTTP_AUTHORIZATION')
        if not auth_header or not auth_header.startswith('Bearer '):
            # If no authentication, return not following
            return JsonResponse({
                'success': True,
                'is_following': False
            })

        token = auth_header.split(' ')[1]
        try:
            from rest_framework_simplejwt.tokens import AccessToken
            access_token = AccessToken(token)
            current_user_id = access_token.get('user_id') or access_token.get('id')
            current_user = User.objects.get(user_id=int(current_user_id))
        except Exception as e:
            # If token is invalid, return not following
            return JsonResponse({
                'success': True,
                'is_following': False
            })

        # Check if current user is following the target user
        from apps.shared.models import Follow
        is_following = Follow.objects.filter(
            follower=current_user,
            following=user_to_check
        ).exists()

        return JsonResponse({
            'success': True,
            'is_following': is_following
        })

    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def mutual_follows_view(request, user_id):
    """Get mutual follows between current user and target user"""
    if request.method == "OPTIONS":
        response = JsonResponse({'detail': 'OK'})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken, Authorization"
        return response

    try:
        current_user = get_current_user_from_request(request)
        if not current_user:
            return JsonResponse({'error': 'Authentication required'}, status=401)

        target_user = User.objects.get(user_id=user_id)
        
        from apps.shared.models import Follow
        
        # Get users that both current_user and target_user follow
        current_user_following = set(Follow.objects.filter(follower=current_user).values_list('following_id', flat=True))
        target_user_following = set(Follow.objects.filter(follower=target_user).values_list('following_id', flat=True))
        
        # Find mutual follows
        mutual_follow_ids = current_user_following.intersection(target_user_following)
        
        if not mutual_follow_ids:
            return JsonResponse({
                'success': True,
                'mutual_follows': [],
                'count': 0
            })
        
        # Get mutual follow user details
        mutual_follows = User.objects.filter(user_id__in=mutual_follow_ids)
        mutual_follows_data = []
        
        for user in mutual_follows:
            mutual_follows_data.append({
                'user_id': user.user_id,
                'ctu_id': user.acc_username,
                'name': ' '.join(filter(None, [user.f_name, user.m_name, user.l_name])),
                'f_name': user.f_name,
                'm_name': user.m_name,
                'l_name': user.l_name,
                'profile_pic': build_profile_pic_url(user),
            })
        
        return JsonResponse({
            'success': True,
            'mutual_follows': mutual_follows_data,
            'count': len(mutual_follows_data)
        })
        
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def online_users_view(request):
    """Get online users that the current user has mutual follows with"""
    if request.method == "OPTIONS":
        response = JsonResponse({'detail': 'OK'})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken, Authorization"
        return response

    try:
        current_user = get_current_user_from_request(request)
        if not current_user:
            return JsonResponse({'error': 'Authentication required'}, status=401)

        from apps.shared.models import Follow
        from apps.messaging.connection_manager import connection_manager
        
        # Get all users that current user follows
        following_ids = set(Follow.objects.filter(follower=current_user).values_list('following_id', flat=True))
        
        # Get all users that follow current user
        follower_ids = set(Follow.objects.filter(following=current_user).values_list('follower_id', flat=True))
        
        # Find mutual follows
        mutual_follow_ids = following_ids.intersection(follower_ids)
        
        if not mutual_follow_ids:
            return JsonResponse({
                'success': True,
                'online_users': [],
                'count': 0
            })
        
        # Get online status for mutual follows
        online_users = []
        for user_id in mutual_follow_ids:
            # Check if user is online (has active connections)
            user_connections = connection_manager.get_user_connections(user_id)
            if user_connections:
                try:
                    user = User.objects.get(user_id=user_id)
                    online_users.append({
                        'user_id': user.user_id,
                        'ctu_id': user.acc_username,
                        'name': ' '.join(filter(None, [user.f_name, user.m_name, user.l_name])),
                        'f_name': user.f_name,
                        'm_name': user.m_name,
                        'l_name': user.l_name,
                        'profile_pic': build_profile_pic_url(user),
                        'is_online': True,
                        'last_seen': timezone.now().isoformat()
                    })
                except User.DoesNotExist:
                    continue
        
        return JsonResponse({
            'success': True,
            'online_users': online_users,
            'count': len(online_users)
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, JSONParser])
def posts_view(request):
    """Used by Mobile – GET list posts, POST create post."""
    try:
        user = request.user
        from apps.shared.models import Follow, User as SharedUser
        if user.account_type.admin or user.account_type.peso:
            # Exclude forum posts from regular posts feed
            posts = Post.objects.exclude(type='forum').select_related('user').order_by('-post_id')
        elif user.account_type.user or user.account_type.ojt:
            followed_users = Follow.objects.filter(follower=user).values_list('following', flat=True)
            admin_users = SharedUser.objects.filter(account_type__admin=True).values_list('user_id', flat=True)
            peso_users = SharedUser.objects.filter(account_type__peso=True).values_list('user_id', flat=True)
            
            # Exclude forum posts from regular posts feed
            posts = Post.objects.filter(
                Q(user__in=followed_users) |
                Q(user__in=admin_users) |
                Q(user__in=peso_users) |
                Q(user=user)
            ).exclude(type='forum').select_related('user').order_by('-post_id')
        else:
            # Exclude forum posts from regular posts feed
            posts = Post.objects.exclude(type='forum').select_related('user').order_by('-post_id')
        if request.method == "POST":
            # Handle both JSON and FormData requests using request.data
            data = request.data
            post_content = data.get('post_content') or ''
            post_type = data.get('type') or 'personal'

            print(f"POST request received - User: {request.user.user_id}, Content: {post_content[:50]}..., Type: {post_type}")
            print(f"Data keys: {list(data.keys())}")
            print(f"Request FILES: {bool(request.FILES)}")
            if request.FILES:
                print(f"FILES keys: {list(request.FILES.keys())}")
            if 'post_images' in data:
                print(f"post_images received: {len(data.get('post_images', []))} images")
                print(f"post_images type: {type(data.get('post_images'))}")
                if data.get('post_images'):
                    print(f"First image preview: {str(data.get('post_images')[0])[:100]}...")
            if 'post_image' in data:
                print(f"post_image received: {bool(data.get('post_image'))}")

            if not post_content.strip():
                return JsonResponse({'success': False, 'message': 'post_content is required'}, status=400)

            new_post = Post.objects.create(
                user=request.user,
                post_content=post_content,
                type=post_type,
            )
            
            print(f"Post created successfully - ID: {new_post.post_id}, User: {new_post.user.user_id}")
            
            # Notify OJT and alumni users if post author is admin or PESO
            notify_users_of_admin_peso_post(request.user, "post", new_post.post_id)

            # --- HANDLE MULTIPLE IMAGES ---
            import sys
            
            try:
                print("Starting image processing...")
                # Handle FormData file uploads (mobile app) - check this first
                if request.FILES:
                    print(f'Received {len(request.FILES)} files via FormData')
                    print(f'File keys: {list(request.FILES.keys())}')
                    
                    # Get all image files and sort them by key to ensure consistent ordering
                    image_files = []
                    for key, file in request.FILES.items():
                        if key.startswith('images') and file:
                            image_files.append((key, file))
                    
                    # Sort by key to ensure consistent ordering (images[0], images[1], etc.)
                    image_files.sort(key=lambda x: x[0])
                    
                    for order_index, (key, file) in enumerate(image_files):
                        print(f'Processing file {order_index}: key={key}, file={file}, name={file.name}, size={file.size}')
                        try:
                            # Create ContentImage instance for post
                            print(f'Creating ContentImage for post {new_post.post_id}, order {order_index}')
                            post_image = ContentImage.objects.create(
                                content_type='post',
                                content_id=new_post.post_id,
                                order=order_index
                            )
                            print(f'ContentImage created with ID {post_image.image_id}')
                            
                            # Save the file
                            print(f'Saving file {file.name} to ContentImage')
                            post_image.image.save(file.name, file, save=True)
                            
                            # Verify the file was saved
                            if post_image.image:
                                print(f'Saved FormData image {order_index}: {post_image.image.url}')
                            else:
                                print(f'Warning: File not properly saved for image {order_index}')
                        except Exception as img_exc:
                            print(f'Error saving FormData image {order_index}: {img_exc}')
                            import traceback
                            traceback.print_exc()
                
                # Handle multiple images (base64) - for JSON requests
                elif 'post_images' in data and data['post_images']:
                    print(f'Received {len(data["post_images"])} images in data')
                    print(f'post_images type: {type(data["post_images"])}')
                    
                    for index, post_image_data in enumerate(data['post_images']):
                        print(f'Processing image {index}: {str(post_image_data)[:50]}...')
                        if post_image_data and post_image_data.startswith('data:image'):
                            try:
                                print(f'Decoding base64 image {index}...')
                                format, imgstr = post_image_data.split(';base64,')
                                ext = format.split('/')[-1]
                                img_data = base64.b64decode(imgstr)
                                file_name = f"{uuid.uuid4()}.{ext}"
                                
                                print(f'Creating ContentImage for post {new_post.post_id}, order {index}')
                                # Create ContentImage instance for post
                                post_image = ContentImage.objects.create(
                                    content_type='post',
                                    content_id=new_post.post_id,
                                    order=index
                                )
                                print(f'ContentImage created with ID {post_image.image_id}')
                                
                                print(f'Saving image file {file_name}...')
                                post_image.image.save(file_name, ContentFile(img_data), save=True)
                                print(f'Saved multiple image {index}: {post_image.image.url}')
                            except Exception as img_exc:
                                print(f'Error saving multiple image {index}: {img_exc}')
                                import traceback
                                traceback.print_exc()
                
                # Handle single image (backward compatibility)
                elif 'post_image' in data and data['post_image']:
                    print('Received post_image in data')
                    post_image_data = data['post_image']
                    if post_image_data.startswith('data:image'):
                        try:
                            format, imgstr = post_image_data.split(';base64,')
                            ext = format.split('/')[-1]
                            img_data = base64.b64decode(imgstr)
                            file_name = f"{uuid.uuid4()}.{ext}"
                            
                            # Create ContentImage instance for post
                            post_image = ContentImage.objects.create(
                                content_type='post',
                                content_id=new_post.post_id,
                                order=0
                            )
                            post_image.image.save(file_name, ContentFile(img_data), save=True)
                            print(f'Saved single image: {post_image.image.url}')
                        except Exception as img_exc:
                            print(f'Error saving single image: {img_exc}')
                
                if not request.FILES and 'post_image' not in data and 'post_images' not in data:
                    print('No images in data')
            except Exception as e:
                print(f'Exception in image handling: {e}')
            # --- END IMAGE HANDLING ---
            
            # Award engagement points (for post with or without photo)
            has_images = False
            try:
                has_images = ContentImage.objects.filter(content_type='post', content_id=new_post.post_id).exists()
            except Exception as e:
                print(f"Warning: Could not check ContentImage for engagement points: {e}")
            
            if has_images:
                award_engagement_points(request.user, 'post_with_photo')
            else:
                award_engagement_points(request.user, 'post')

            # Get multiple images for response
            post_images = []
            # Use the new ContentImage model
            try:
                content_images = ContentImage.objects.filter(content_type='post', content_id=new_post.post_id)
                for img in content_images:
                    post_images.append({
                        'image_id': img.image_id,
                        'image_url': img.image.url,
                        'order': img.order
                    })
            except Exception as e:
                print(f"Warning: Could not load ContentImage for response: {e}")
                post_images = []
            
            return JsonResponse({
                'success': True,
                'post': {
                    'post_id': new_post.post_id,
                    'post_content': new_post.post_content,
                    'post_image': (new_post.post_image.url if getattr(new_post, 'post_image', None) else None),  # Backward compatibility
                    'post_images': post_images,  # Multiple images
                    'type': new_post.type,
                    'created_at': new_post.created_at.isoformat() if hasattr(new_post, 'created_at') else None,
                    'user': {
                        'user_id': request.user.user_id,
                        'f_name': request.user.f_name,
                        'l_name': request.user.l_name,
                        'profile_pic': build_profile_pic_url(request.user),
                    },
                    'category': {
                    }
                }
            }, status=201)

        # Use the filtered posts from above (don't override with all posts)
        # Build a combined feed with both posts and reposts as separate items
        feed_items = []
        
        print(f"GET request - Found {posts.count()} posts for user {user.user_id}")

        for post in posts:
            try:
                # Get likes count
                likes_count = Like.objects.filter(post=post).count()
                # Get comments count
                comments_count = Comment.objects.filter(post=post).count()
                # Get reposts count
                reposts_count = Repost.objects.filter(post=post).count()

                # Check if current user liked this post
                is_liked = Like.objects.filter(post=post, user=user).exists()

                # Get likes data
                likes = Like.objects.filter(post=post).select_related('user')
                likes_data = []
                for like in likes:
                    pic = build_profile_pic_url(like.user)
                    initials = None
                    if not pic:
                        try:
                            f = (like.user.f_name or '').strip()[:1].upper()
                            l = (like.user.l_name or '').strip()[:1].upper()
                            initials = f + l if (f or l) else None
                        except Exception:
                            initials = None
                    likes_data.append({
                        'user_id': like.user.user_id,
                        'f_name': like.user.f_name,
                        'm_name': like.user.m_name,
                        'l_name': like.user.l_name,
                        'profile_pic': pic,
                        'initials': initials,
                    })

                # Get comments for the post
                comments = Comment.objects.filter(post=post).select_related('user').order_by('-date_created')
                comments_data = []
                for comment in comments:
                    comments_data.append({
                        'comment_id': comment.comment_id,
                        'comment_content': comment.comment_content,
                        'date_created': comment.date_created.isoformat(),
                        'user': {
                            'user_id': comment.user.user_id,
                            'f_name': comment.user.f_name,
                            'm_name': comment.user.m_name,
                            'l_name': comment.user.l_name,
                            'profile_pic': build_profile_pic_url(comment.user),
                        }
                    })

                # Get multiple images for the post
                post_images = []
                seen_urls = set()  # Track seen URLs to prevent duplicates
                try:
                    print(f'Processing images for post {post.post_id}')
                    # Use direct ContentImage query to avoid duplicates
                    content_images = ContentImage.objects.filter(content_type='post', content_id=post.post_id).order_by('order')
                    print(f'Direct ContentImage query found {content_images.count()} images')
                    for img in content_images:
                        image_url = build_image_url(img.image, request)
                        # Only add if not seen before
                        if image_url and image_url not in seen_urls:
                            seen_urls.add(image_url)
                            print(f'Adding image: {image_url}')
                            post_images.append({
                                'image_id': img.image_id,
                                'image_url': image_url,
                                'order': img.order
                            })
                        else:
                            print(f'Skipping duplicate image: {image_url}')
                except Exception as img_error:
                    print(f"Error processing images for post {post.post_id}: {img_error}")
                    post_images = []  # Ensure post_images is always set

                # Add the original post as a feed item
                feed_items.append({
                    'post_id': post.post_id,
                    'post_content': post.post_content,
                    'post_image': (post.post_image.url if getattr(post, 'post_image', None) else None),  # Backward compatibility
                    'post_images': post_images,  # Multiple images
                    'type': post.type,
                    'created_at': post.created_at.isoformat() if hasattr(post, 'created_at') else None,
                    'likes_count': likes_count,
                    'comments_count': comments_count,
                    'reposts_count': reposts_count,
                    'is_liked': is_liked,
                    'likes': likes_data,
                    'comments': comments_data,
                    'user': {
                        'user_id': post.user.user_id,
                        'f_name': post.user.f_name,
                        'm_name': post.user.m_name,
                        'l_name': post.user.l_name,
                        'profile_pic': build_profile_pic_url(post.user),
                    },
                    'category': {
                    },
                    'item_type': 'post',  # Mark as original post
                    'sort_date': post.created_at.isoformat() if hasattr(post, 'created_at') else None,
                })
                
                # Add each repost as a separate feed item
                reposts = Repost.objects.filter(post=post).select_related('user', 'post', 'post__user')
                for repost in reposts:
                    try:
                        # Get repost likes count and data
                        repost_likes = Like.objects.filter(repost=repost).select_related('user')
                        repost_likes_count = repost_likes.count()
                        
                        # Check if current user liked this repost
                        repost_is_liked = Like.objects.filter(repost=repost, user=user).exists()
                        
                        repost_likes_data = []
                        for like in repost_likes:
                            repost_likes_data.append({
                                'like_id': like.like_id,
                                'user_id': like.user.user_id,
                                'user': {
                                    'user_id': like.user.user_id,
                                    'f_name': like.user.f_name,
                                    'm_name': like.user.m_name,
                                    'l_name': like.user.l_name,
                                    'profile_pic': build_profile_pic_url(like.user),
                                }
                            })

                        # Get repost comments count and data
                        repost_comments = Comment.objects.filter(repost=repost).select_related('user')
                        repost_comments_count = repost_comments.count()
                        repost_comments_data = []
                        for comment in repost_comments:
                            # Get replies count for this comment
                            replies_count = Reply.objects.filter(comment=comment).count()
                            
                            repost_comments_data.append({
                                'comment_id': comment.comment_id,
                                'comment_content': comment.comment_content,
                                'date_created': comment.date_created.isoformat() if comment.date_created else None,
                                'replies_count': replies_count,
                                'user': {
                                    'user_id': comment.user.user_id,
                                    'f_name': comment.user.f_name,
                                    'm_name': comment.user.m_name,
                                    'l_name': comment.user.l_name,
                                    'profile_pic': build_profile_pic_url(comment.user),
                                }
                            })

                        feed_items.append({
                            'repost_id': repost.repost_id,
                            'repost_date': repost.repost_date.isoformat(),
                            'repost_caption': repost.caption,
                            'likes_count': repost_likes_count,
                            'comments_count': repost_comments_count,
                            'is_liked': repost_is_liked,
                            'likes': repost_likes_data,
                            'comments': repost_comments_data,
                            'user': {
                                'user_id': repost.user.user_id,
                                'f_name': repost.user.f_name,
                                'm_name': repost.user.m_name,
                                'l_name': repost.user.l_name,
                                'profile_pic': build_profile_pic_url(repost.user),
                            },
                            'original_post': {
                                'post_id': post.post_id,
                                'post_content': post.post_content,
                                'post_image': (post.post_image.url if getattr(post, 'post_image', None) else None),  # Backward compatibility
                                'post_images': post_images,  # Multiple images (already calculated above)
                                'created_at': post.created_at.isoformat() if hasattr(post, 'created_at') else None,
                                'user': {
                                    'user_id': post.user.user_id,
                                    'f_name': post.user.f_name,
                                    'm_name': post.user.m_name,
                                    'l_name': post.user.l_name,
                                    'profile_pic': build_profile_pic_url(post.user),
                                }
                            },
                            'item_type': 'repost',  # Mark as repost
                            'sort_date': repost.repost_date.isoformat(),
                        })
                    except Exception:
                        continue
            except Exception as e:
                print(f"Error processing post {post.post_id}: {e}")
                continue

        # Sort all feed items by date (most recent first)
        feed_items.sort(key=lambda x: x.get('sort_date') or '', reverse=True)
        
        return JsonResponse({'posts': feed_items})
    except Exception as e:
        import traceback
        logger.error(f"posts_view failed: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({'posts': [], 'error': str(e)}, status=500)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def debug_posts_view(request):
    """Debug endpoint to check posts in database"""
    try:
        total_posts = Post.objects.count()
        recent_posts = Post.objects.select_related('user').order_by('-post_id')[:5]
        
        posts_data = []
        for post in recent_posts:
            posts_data.append({
                'post_id': post.post_id,
                'user_id': post.user.user_id,
                'user_name': f"{post.user.f_name} {post.user.l_name}",
                'content': post.post_content[:100],
                'created_at': post.created_at.isoformat() if hasattr(post, 'created_at') else None,
                'type': post.type
            })
        
        return JsonResponse({
            'total_posts': total_posts,
            'recent_posts': posts_data,
            'user_info': {
                'user_id': request.user.user_id,
                'account_type': {
                    'admin': request.user.account_type.admin,
                    'peso': request.user.account_type.peso,
                    'user': request.user.account_type.user,
                    'ojt': request.user.account_type.ojt
                }
            }
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def posts_by_user_type_view(request):
    """Get posts filtered by user type (alumni, OJT, etc.)"""
    try:
        user_type = request.GET.get('user_type', 'all')

        if user_type == 'alumni':
            users = User.objects.filter(account_type__user=True)
        elif user_type == 'ojt':
            users = User.objects.filter(account_type__ojt=True)
        elif user_type == 'coordinator':
            users = User.objects.filter(account_type__coordinator=True)
        elif user_type == 'admin':
            users = User.objects.filter(account_type__admin=True)
        elif user_type == 'peso':
            users = User.objects.filter(account_type__peso=True)
        else:
            users = User.objects.all()

        posts = Post.objects.filter(user__in=users).select_related('user').order_by('-post_id')
        posts_data = []

        for post in posts:
            try:
                # Get likes count
                likes_count = Like.objects.filter(post=post).count()
                # Get comments count
                comments_count = Comment.objects.filter(post=post).count()
                # Get reposts count
                reposts_count = Repost.objects.filter(post=post).count()
                
                # Check if current user liked this post
                is_liked = Like.objects.filter(post=post, user=request.user).exists()
                
                # Get comments for this post
                comments = Comment.objects.filter(post=post).select_related('user').order_by('-created_at')[:10]
                comments_data = []
                for comment in comments:
                    comments_data.append({
                        'id': comment.comment_id,
                        'comment_content': comment.comment_content,
                        'created_at': comment.created_at.isoformat() if hasattr(comment, 'created_at') else None,
                        'user': {
                            'id': comment.user.user_id,
                            'f_name': comment.user.f_name,
                            'm_name': comment.user.m_name,
                            'l_name': comment.user.l_name,
                            'profile_pic': build_profile_pic_url(comment.user),
                        }
                    })

                posts_data.append({
                    'id': post.post_id,
                    'post_content': post.post_content,
                    'post_image': (post.post_image.url if getattr(post, 'post_image', None) else None),
                    'created_at': post.created_at.isoformat() if hasattr(post, 'created_at') else None,
                    'likes_count': likes_count,
                    'comments_count': comments_count,
                    'is_liked': is_liked,
                    'comments': comments_data,
                        'user': {
                            'id': post.user.user_id,
                            'f_name': post.user.f_name,
                            'm_name': post.user.m_name,
                            'l_name': post.user.l_name,
                            'profile_pic': build_profile_pic_url(post.user),
                        }
                })
            except Exception:
                continue

        return JsonResponse({'posts': posts_data})
    except Exception as e:
        logger.error(f"posts_by_user_type_view failed: {e}")
        return JsonResponse({'posts': []}, status=200)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_all_alumni(request):
    """Get all alumni with pagination and search capabilities"""
    try:
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 20))
        search = request.GET.get('search', '').strip()
        
        # Base queryset
        alumni = User.objects.filter(account_type__user=True).select_related('profile', 'academic_info')
        
        # Apply search if provided
        if search:
            alumni = alumni.filter(
                Q(f_name__icontains=search) |
                Q(m_name__icontains=search) |
                Q(l_name__icontains=search) |
                Q(acc_username__icontains=search)
            )
        
        # Calculate pagination
        total_count = alumni.count()
        start = (page - 1) * limit
        end = start + limit
        
        # Get paginated results
        alumni_page = alumni[start:end]
        
        alumni_data = []
        for a in alumni_page:
            try:
                alumni_data.append({
                    'id': a.user_id,
                    'ctu_id': a.acc_username,
                    'name': f"{a.f_name} {a.m_name or ''} {a.l_name}".strip(),
                    'program': getattr(a.academic_info, 'program', None) if hasattr(a, 'academic_info') else None,
                    'batch': getattr(a.academic_info, 'year_graduated', None) if hasattr(a, 'academic_info') else None,
                    'status': a.user_status,
                    'gender': a.gender,
                    'birthdate': str(getattr(a.profile, 'birthdate', None)) if hasattr(a, 'profile') and getattr(a, 'profile', None) else None,
                    'phone': getattr(a.profile, 'phone_num', None) if hasattr(a, 'profile') and getattr(a, 'profile', None) else None,
                    'address': getattr(a.profile, 'address', None) if hasattr(a, 'profile') and getattr(a, 'profile', None) else None,
                    'civilStatus': getattr(a.profile, 'civil_status', None) if hasattr(a, 'profile') and getattr(a, 'profile', None) else None,
                    'socialMedia': getattr(a.profile, 'social_media', None) if hasattr(a, 'profile') and getattr(a, 'profile', None) else None,
                    'profile_pic': build_profile_pic_url(a),
                })
            except Exception:
                continue
        
        return JsonResponse({
            'success': True,
            'alumni': alumni_data,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total_count,
                'pages': (total_count + limit - 1) // limit
            }
        })
    except Exception as e:
        logger.error(f"get_all_alumni failed: {e}")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def users_alumni_view(request):
    """Get alumni by year with proper employment data (not OJT data)"""
    try:
        year = request.GET.get('year', '').strip()
        
        # Base query for alumni
        alumni_qs = User.objects.filter(account_type__user=True).select_related('academic_info', 'profile')
        
        # Filter by year if provided
        if year and year.isdigit():
            alumni_qs = alumni_qs.filter(academic_info__year_graduated=int(year))
        
        alumni_data = []
        for a in alumni_qs:
            try:
                # Get employment data from tracker responses, not OJT data
                employment_status = 'Pending'  # Default status
                current_position = 'Not disclosed'
                current_salary = 'Not disclosed'
                
                # Try to get employment data from tracker responses
                try:
                    from apps.shared.models import TrackerData
                    tracker_data = TrackerData.objects.filter(user=a).order_by('-tracker_submitted_at').first()
                    if tracker_data:
                        # Get employment status from tracker
                        if hasattr(tracker_data, 'q_employment_status'):
                            if tracker_data.q_employment_status and tracker_data.q_employment_status.lower() == 'yes':
                                employment_status = 'Employed'
                            elif tracker_data.q_employment_status and tracker_data.q_employment_status.lower() == 'no':
                                employment_status = 'Unemployed'
                            else:
                                employment_status = 'Pending'
                        
                        # Get current position from tracker
                        if hasattr(tracker_data, 'q_current_position') and tracker_data.q_current_position:
                            current_position = tracker_data.q_current_position
                        
                        # Get current salary from tracker
                        if hasattr(tracker_data, 'q_salary_range') and tracker_data.q_salary_range:
                            current_salary = tracker_data.q_salary_range
                except Exception:
                    pass  # Use defaults if tracker data not available
                
                alumni_data.append({
                    'id': a.user_id,
                    'ctu_id': a.acc_username,
                    'name': f"{a.f_name} {a.m_name or ''} {a.l_name}".strip(),
                    'first_name': a.f_name,
                    'middle_name': a.m_name,
                    'last_name': a.l_name,
                    'program': getattr(a.academic_info, 'program', None) if hasattr(a, 'academic_info') else None,
                    'batch': getattr(a.academic_info, 'year_graduated', None) if hasattr(a, 'academic_info') else None,
                    'employment_status': employment_status,
                    'current_position': current_position,
                    'current_salary': current_salary,
                    'status': a.user_status,
                    'gender': a.gender,
                    'birthdate': str(getattr(a.profile, 'birthdate', None)) if hasattr(a, 'profile') and getattr(a, 'profile', None) else None,
                    'phone': getattr(a.profile, 'phone_num', None) if hasattr(a, 'profile') and getattr(a, 'profile', None) else None,
                    'address': getattr(a.profile, 'address', None) if hasattr(a, 'profile') and getattr(a, 'profile', None) else None,
                    'civilStatus': getattr(a.profile, 'civil_status', None) if hasattr(a, 'profile') and getattr(a, 'profile', None) else None,
                    'socialMedia': getattr(a.profile, 'social_media', None) if hasattr(a, 'profile') and getattr(a, 'profile', None) else None,
                    'profile_pic': build_profile_pic_url(a),
                })
            except Exception:
                continue
        
        response = JsonResponse({
            'success': True,
            'alumni': alumni_data,
            'timestamp': timezone.now().isoformat()
        })
        # Add cache-busting headers to prevent browser caching
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
    except Exception as e:
        logger.error(f"users_alumni_view failed: {e}")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def userprofile_social_media_view(request, user_id):
    """Get or update user's social media"""
    try:
        # Get user's profile
        user = get_object_or_404(User, user_id=user_id)
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        if request.method == 'GET':
            return Response({
                'success': True,
                'social_media': profile.social_media or ''
            })
        
        elif request.method == 'PUT':
            data = request.data
            social_media = data.get('social_media', '').strip()
            
            profile.social_media = social_media if social_media else None
            profile.save()
            
            return Response({
                'success': True,
                'social_media': profile.social_media or '',
                'message': 'Social media updated successfully'
            })
            
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=400)
@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def userprofile_email_view(request, user_id):
    """Get or update user's email"""
    try:
        # Get user's profile
        user = get_object_or_404(User, user_id=user_id)
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        if request.method == 'GET':
            return Response({
                'success': True,
                'email': profile.email or ''
            })
        
        elif request.method == 'PUT':
            data = request.data
            email = data.get('email', '').strip()
            
            # Validate email format if provided
            if email and '@' not in email:
                return Response({
                    'success': False,
                    'error': 'Invalid email format'
                }, status=400)
            
            profile.email = email if email else None
            profile.save()
            
            return Response({
                'success': True,
                'email': profile.email or '',
                'message': 'Email updated successfully'
            })
            
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=400)

@api_view(["POST"])
def forgot_password_view(request):
    """
    Forgot password endpoint - validates user credentials and generates temporary password.
    Only available for alumni (user=True) and OJT (ojt=True) account types.
    """
    if request.method == "OPTIONS":
        response = JsonResponse({'detail': 'OK'})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken"
        return response

    try:
        data = json.loads(request.body)
        ctu_id = data.get('ctu_id', '').strip()
        email = data.get('email', '').strip()
        last_name = data.get('last_name', '').strip()
        first_name = data.get('first_name', '').strip()
        middle_name = data.get('middle_name', '').strip()

        # Validate required fields
        if not all([ctu_id, email, last_name, first_name]):
            return JsonResponse({
                'success': False, 
                'message': 'All fields are required: CTU ID, Email, Last Name, First Name'
            }, status=400)

        # Find user by CTU ID
        try:
            user = User.objects.select_related('profile', 'account_type').get(acc_username=ctu_id)
        except User.DoesNotExist:
            logger.warning(f"Forgot password failed: CTU ID {ctu_id} does not exist.")
            return JsonResponse({
                'success': False, 
                'message': 'Invalid credentials. Please check your information and try again.'
            }, status=404)

        # Check if user is alumni or OJT (not admin, peso, or coordinator)
        if not (user.account_type.user or user.account_type.ojt):
            logger.warning(f"Forgot password denied: User {ctu_id} is not alumni or OJT.")
            return JsonResponse({
                'success': False, 
                'message': 'Password reset is only available for alumni and OJT students.'
            }, status=403)

        # Validate credentials against user data
        profile = getattr(user, 'profile', None)
        user_email = getattr(profile, 'email', None) if profile else None
        
        # Case-insensitive comparison for names and email
        # Check middle name if provided, otherwise allow empty middle name
        middle_name_match = True
        if middle_name:  # If middle name is provided, it must match
            user_middle_name = user.m_name or ''
            middle_name_match = user_middle_name.lower() == middle_name.lower()
        
        if (user.f_name.lower() != first_name.lower() or 
            user.l_name.lower() != last_name.lower() or
            not middle_name_match or
            (user_email and user_email.lower() != email.lower())):
            logger.warning(f"Forgot password failed: Credential mismatch for user {ctu_id}.")
            return JsonResponse({
                'success': False, 
                'message': 'Invalid credentials. Please check your information and try again.'
            }, status=400)

        # Generate temporary password
        alphabet = string.ascii_letters + string.digits
        temp_password = ''.join(secrets.choice(alphabet) for _ in range(12))
        
        # Update user password
        user.set_password(temp_password)
        user.save()
        
        # Store temporary password for tracking
        try:
            initial_password, created = UserInitialPassword.objects.get_or_create(user=user)
            initial_password.set_plaintext(temp_password)
            initial_password.is_active = True
            initial_password.save()
        except Exception as e:
            logger.error(f"Failed to store initial password for user {ctu_id}: {e}")
            # Continue anyway - password was already updated

        logger.info(f"Temporary password generated for user {ctu_id} ({user.full_name})")
        
        return JsonResponse({
            'success': True,
            'message': 'Temporary password generated successfully',
            'temp_password': temp_password,
            'user_name': user.full_name
        })

    except json.JSONDecodeError:
        logger.error("Forgot password failed: Invalid JSON in request body.")
        return JsonResponse({'success': False, 'message': 'Invalid request format'}, status=400)
    except Exception as e:
        logger.error(f"Forgot password failed: Unexpected error: {e}")
        return JsonResponse({'success': False, 'message': 'Server error occurred'}, status=500)
# Donation API Views
@api_view(['GET', 'POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser, MultiPartParser])
def donation_requests_view(request):
    """Handle donation request listing and creation"""
    if request.method == 'GET':
        try:
            # Get all donation requests with user info
            donations = DonationRequest.objects.select_related('user').all()
            logger.info(f"Found {donations.count()} donation requests in database")
            
            donation_data = []
            for donation in donations:
                # Get likes and comments for this donation
                likes = Like.objects.filter(donation_request=donation)
                comments = Comment.objects.filter(donation_request=donation).select_related('user')
                # Get reposts for this donation
                reposts = Repost.objects.filter(donation_request=donation).select_related('user').prefetch_related('user__profile', 'user__academic_info')
                
                # Check if current user liked this donation
                is_liked = Like.objects.filter(donation_request=donation, user=request.user).exists()
                
                donation_info = {
                    'donation_id': donation.donation_id,
                    'user': {
                        'user_id': donation.user.user_id,
                        'f_name': donation.user.f_name,
                        'm_name': donation.user.m_name,
                        'l_name': donation.user.l_name,
                        'profile_pic': build_profile_pic_url(donation.user),
                        'year_graduated': donation.user.academic_info.year_graduated if hasattr(donation.user, 'academic_info') and donation.user.academic_info.year_graduated else None,
                        'batch': donation.user.academic_info.year_graduated if hasattr(donation.user, 'academic_info') and donation.user.academic_info.year_graduated else None,
                        'name': f"{donation.user.f_name} {donation.user.m_name} {donation.user.l_name}".strip()
                    },
                    'description': donation.description,
                    'status': donation.status,
                    'created_at': donation.created_at.isoformat(),
                    'updated_at': donation.updated_at.isoformat(),
                    'images': get_content_images_safe(donation.donation_id, 'donation'),
                    'likes_count': likes.count(),
                    'comments_count': comments.count(),
                    'reposts_count': reposts.count(),
                    'is_liked': is_liked,
                    'likes': [
                        {
                            'like_id': like.like_id,
                            'user': {
                                'user_id': like.user.user_id,
                                'f_name': like.user.f_name,
                                'm_name': like.user.m_name,
                                'l_name': like.user.l_name,
                                'profile_pic': like.user.profile.profile_pic.url if hasattr(like.user, 'profile') and like.user.profile.profile_pic else None
                            }
                        } for like in likes
                    ],
                    'comments': [
                        {
                            'comment_id': comment.comment_id,
                            'comment_content': comment.comment_content,
                            'date_created': comment.date_created.isoformat(),
                            'user': {
                                'user_id': comment.user.user_id,
                                'f_name': comment.user.f_name,
                                'm_name': comment.user.m_name,
                                'l_name': comment.user.l_name,
                                'profile_pic': comment.user.profile.profile_pic.url if hasattr(comment.user, 'profile') and comment.user.profile.profile_pic else None
                            }
                        } for comment in comments
                    ],
                    'reposts': [
                        {
                            'repost_id': repost.repost_id,
                            'repost_date': repost.repost_date.isoformat(),
                            'repost_caption': repost.caption,
                            'user': {
                                'user_id': repost.user.user_id,
                                'f_name': repost.user.f_name,
                                'm_name': repost.user.m_name,
                                'l_name': repost.user.l_name,
                                'profile_pic': repost.user.profile.profile_pic.url if hasattr(repost.user, 'profile') and repost.user.profile.profile_pic else None,
                            },
                            'likes_count': Like.objects.filter(repost=repost).count(),
                            'comments_count': Comment.objects.filter(repost=repost).count(),
                            'is_liked': Like.objects.filter(repost=repost, user=request.user).exists(),
                            'likes': [
                                {
                                    'like_id': like.like_id,
                                    'user_id': like.user.user_id,
                                    'user': {
                                        'user_id': like.user.user_id,
                                        'f_name': like.user.f_name,
                                        'm_name': like.user.m_name,
                                        'l_name': like.user.l_name,
                                        'profile_pic': build_profile_pic_url(like.user),
                                    }
                                } for like in Like.objects.filter(repost=repost).select_related('user')
                            ],
                            'comments': [
                                {
                                    'comment_id': comment.comment_id,
                                    'comment_content': comment.comment_content,
                                    'date_created': comment.date_created.isoformat(),
                                    'replies_count': Reply.objects.filter(comment=comment).count(),
                                    'user': {
                                        'user_id': comment.user.user_id,
                                        'f_name': comment.user.f_name,
                                        'm_name': comment.user.m_name,
                                        'l_name': comment.user.l_name,
                                        'profile_pic': comment.user.profile.profile_pic.url if hasattr(comment.user, 'profile') and comment.user.profile.profile_pic else None
                                    }
                                } for comment in Comment.objects.filter(repost=repost).select_related('user')
                            ],
                            'original_post': {
                                'donation_id': donation.donation_id,
                                'post_content': donation.description,
                                'post_images': get_content_images_safe(donation.donation_id, 'donation'),
                                'status': donation.status,
                                'created_at': donation.created_at.isoformat(),
                                'user': {
                                    'user_id': donation.user.user_id,
                                    'f_name': donation.user.f_name,
                                    'm_name': donation.user.m_name,
                                    'l_name': donation.user.l_name,
                                    'profile_pic': build_profile_pic_url(donation.user),
                                }
                            }
                        } for repost in reposts
                    ]
                }
                donation_data.append(donation_info)
            
            response_data = {
                'success': True,
                'donations': donation_data
            }
            
            logger.info(f"Returning {len(donation_data)} donations to frontend")
            return JsonResponse(response_data)
            
        except Exception as e:
            logger.error(f"Error fetching donation requests: {e}")
            return JsonResponse({'success': False, 'message': 'Failed to fetch donation requests'}, status=500)
    
    elif request.method == 'POST':
        try:
            data = request.data
            description = data.get('description')
            images = data.get('images', [])
            
            logger.info(f"Creating donation request for user {request.user.user_id}: {description[:50]}...")
            
            if not description or not description.strip():
                logger.warning("Donation request failed: Description is required")
                return JsonResponse({'success': False, 'message': 'Description is required'}, status=400)
            
            # Create donation request
            donation = DonationRequest.objects.create(
                user=request.user,
                description=description.strip()
            )
            
            # Notify OJT and alumni users if post author is admin or PESO
            notify_users_of_admin_peso_post(request.user, "donation", donation.donation_id)
            
            # Handle image uploads if any
            # Handle FormData file uploads (mobile app)
            if request.FILES:
                logger.info(f'Received {len(request.FILES)} files via FormData for donation')
                
                # Get all image files and sort them by key to ensure consistent ordering
                image_files = []
                for key, file in request.FILES.items():
                    if key.startswith('images') and file:
                        image_files.append((key, file))
                
                # Sort by key to ensure consistent ordering
                image_files.sort(key=lambda x: x[0])
                
                for order_index, (key, file) in enumerate(image_files):
                    try:
                        # Create ContentImage instance for donation
                        donation_image = ContentImage.objects.create(
                            content_type='donation',
                            content_id=donation.donation_id,
                            order=order_index
                        )
                        donation_image.image.save(file.name, file, save=True)
                        logger.info(f'Saved FormData donation image {order_index}: {donation_image.image.url}')
                    except Exception as e:
                        logger.error(f'Error saving FormData donation image {order_index}: {e}')
                        continue
            # Handle base64 images (backward compatibility)
            elif images:
                for index, image_data in enumerate(images):
                    if image_data and image_data.startswith('data:image'):
                        # Handle base64 image data
                        try:
                            format, imgstr = image_data.split(';base64,')
                            ext = format.split('/')[-1]
                            imgdata = base64.b64decode(imgstr)
                            
                            # Create a unique filename
                            filename = f"donation_{donation.donation_id}_image_{index}_{uuid.uuid4().hex[:8]}.{ext}"
                            
                            # Save the image
                            donation_image = ContentImage.objects.create(
                                content_type='donation',
                                content_id=donation.donation_id,
                                order=index
                            )
                            donation_image.image.save(filename, ContentFile(imgdata), save=True)
                            
                        except Exception as e:
                            logger.error(f"Error saving donation image {index}: {e}")
                            # Continue with other images even if one fails
                            continue
            
            # Return the created donation with full details
            likes = Like.objects.filter(donation_request=donation)
            comments = Comment.objects.filter(donation_request=donation).select_related('user')
            reposts = Repost.objects.filter(donation_request=donation)
            
            donation_info = {
                'donation_id': donation.donation_id,
                'user': {
                    'user_id': donation.user.user_id,
                    'f_name': donation.user.f_name,
                    'm_name': donation.user.m_name,
                    'l_name': donation.user.l_name,
                    'profile_pic': donation.user.profile.profile_pic.url if hasattr(donation.user, 'profile') and donation.user.profile.profile_pic else None,
                    'year_graduated': donation.user.academic_info.year_graduated if hasattr(donation.user, 'academic_info') and donation.user.academic_info.year_graduated else None,
                    'batch': donation.user.academic_info.year_graduated if hasattr(donation.user, 'academic_info') and donation.user.academic_info.year_graduated else None,
                    'name': f"{donation.user.f_name} {donation.user.m_name} {donation.user.l_name}".strip()
                },
                'description': donation.description,
                'status': donation.status,
                'created_at': donation.created_at.isoformat(),
                'updated_at': donation.updated_at.isoformat(),
                                'images': get_content_images_safe(donation.donation_id, 'donation'),
                'likes_count': likes.count(),
                'comments_count': comments.count(),
                'reposts_count': reposts.count(),
                'likes': [],
                'comments': [],
                'reposts': []
            }
            
            response_data = {
                'success': True,
                'message': 'Donation request created successfully',
                'donation': donation_info
            }
            
            logger.info(f"Successfully created donation request {donation.donation_id} for user {request.user.user_id}")
            return JsonResponse(response_data)
            
        except Exception as e:
            logger.error(f"Error creating donation request: {e}")
            return JsonResponse({'success': False, 'message': 'Failed to create donation request'}, status=500)


@api_view(['POST', 'DELETE'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def donation_like_view(request, donation_id):
    """Handle donation like/unlike"""
    try:
        donation = DonationRequest.objects.get(donation_id=donation_id)
        
        if request.method == 'POST':
            # Like the donation
            like, created = Like.objects.get_or_create(
                donation_request=donation,
                user=request.user,
                defaults={
                    'post': None,
                    'forum': None,
                    'repost': None
                }
            )
            
            if created:
                # Award engagement points for liking
                award_engagement_points(request.user, 'like')
                
                # Create notification for donation owner
                if request.user.user_id != donation.user.user_id:
                    notification = Notification.objects.create(
                        user=donation.user,
                        notif_type='like',
                        subject='Donation Liked',
                        notifi_content=f"{request.user.full_name} liked your donation post<!--DONATION_ID:{donation.donation_id}-->",
                        notif_date=timezone.now()
                    )
                    # Broadcast donation like notification in real-time
                    try:
                        from apps.messaging.notification_broadcaster import broadcast_notification
                        broadcast_notification(notification)
                    except Exception as e:
                        logger.error(f"Error broadcasting donation like notification: {e}")
                return JsonResponse({'success': True, 'message': 'Donation liked'})
            else:
                return JsonResponse({'success': False, 'message': 'Already liked'})
        
        elif request.method == 'DELETE':
            # Unlike the donation
            try:
                like = Like.objects.get(donation_request=donation, user=request.user)
                like.delete()
                # Deduct engagement points for unliking
                deduct_engagement_points(request.user, 'like')
                return JsonResponse({'success': True, 'message': 'Donation unliked'})
            except Like.DoesNotExist:
                return JsonResponse({'success': False, 'message': 'Not liked'})
                
    except DonationRequest.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Donation request not found'}, status=404)
    except Exception as e:
        logger.error(f"Error handling donation like: {e}")
        return JsonResponse({'success': False, 'message': 'Failed to handle like'}, status=500)


@api_view(['GET', 'POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def donation_comments_view(request, donation_id):
    """Handle donation comments"""
    try:
        donation = DonationRequest.objects.get(donation_id=donation_id)
        
        if request.method == 'GET':
            # Get all comments for this donation
            comments = Comment.objects.filter(donation_request=donation).select_related('user')
            
            comments_data = []
            for comment in comments:
                # Get reply count for this comment
                reply_count = Reply.objects.filter(comment=comment).count()
                comments_data.append({
                    'comment_id': comment.comment_id,
                    'comment_content': comment.comment_content,
                    'date_created': comment.date_created.isoformat(),
                    'replies_count': reply_count,
                    'user': {
                        'user_id': comment.user.user_id,
                        'f_name': comment.user.f_name,
                        'm_name': comment.user.m_name,
                        'l_name': comment.user.l_name,
                        'profile_pic': comment.user.profile.profile_pic.url if hasattr(comment.user, 'profile') and comment.user.profile.profile_pic else None
                    }
                })
            
            return JsonResponse({
                'success': True,
                'comments': comments_data
            })
        
        elif request.method == 'POST':
            # Create a new comment
            data = request.data
            comment_content = data.get('comment_content', '').strip()
            
            if not comment_content:
                return JsonResponse({'success': False, 'message': 'Comment content is required'}, status=400)
            
            comment = Comment.objects.create(
                donation_request=donation,
                user=request.user,
                comment_content=comment_content,
                date_created=timezone.now()
            )
            
            # Create mention notifications
            create_mention_notifications(
                comment_content,
                request.user,
                comment_id=comment.comment_id,
                donation_id=donation.donation_id
            )
            
            # Create notification for donation owner
            if request.user.user_id != donation.user.user_id:
                notification = Notification.objects.create(
                    user=donation.user,
                    notif_type='comment',
                    subject='Donation Commented',
                    notifi_content=f"{request.user.full_name} commented on your donation post<!--DONATION_ID:{donation.donation_id}--><!--COMMENT_ID:{comment.comment_id}--><!--ACTOR_ID:{request.user.user_id}-->",
                    notif_date=timezone.now()
                )
                # Broadcast donation comment notification in real-time
                try:
                    from apps.messaging.notification_broadcaster import broadcast_notification
                    broadcast_notification(notification)
                except Exception as e:
                    logger.error(f"Error broadcasting donation comment notification: {e}")
            
            # Return the full comment data
            comment_data = {
                'comment_id': comment.comment_id,
                'comment_content': comment.comment_content,
                'date_created': comment.date_created.isoformat(),
                'user': {
                    'user_id': comment.user.user_id,
                    'f_name': comment.user.f_name,
                    'm_name': comment.user.m_name,
                    'l_name': comment.user.l_name,
                    'profile_pic': comment.user.profile.profile_pic.url if hasattr(comment.user, 'profile') and comment.user.profile.profile_pic else None
                }
            }
            
            return JsonResponse({
                'success': True,
                'message': 'Comment added successfully',
                'comment': comment_data
            })
            
    except DonationRequest.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Donation request not found'}, status=404)
    except Exception as e:
        logger.error(f"Error handling donation comments: {e}")
        return JsonResponse({'success': False, 'message': 'Failed to handle comments'}, status=500)


@api_view(['PUT', 'DELETE'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def donation_comment_edit_view(request, donation_id, comment_id):
    """Handle donation comment edit/delete"""
    try:
        donation = DonationRequest.objects.get(donation_id=donation_id)
        comment = Comment.objects.get(comment_id=comment_id, donation_request=donation)
        
        # Allow comment owner OR donation owner to delete/edit comment
        comment_owner = comment.user.user_id == request.user.user_id
        donation_owner = donation.user.user_id == request.user.user_id
        
        if not (comment_owner or donation_owner):
            return JsonResponse({'error': 'Unauthorized'}, status=403)
            
        if request.method == 'PUT':
            # Only comment owner can edit
            if not comment_owner:
                return JsonResponse({'error': 'Only comment owner can edit'}, status=403)
            data = request.data
            content = data.get('comment_content')
            if content is None:
                return JsonResponse({'error': 'No content provided'}, status=400)
            comment.comment_content = content
            comment.save()
            return JsonResponse({'success': True})
        else:
            # Both comment owner and donation owner can delete
            # Deduct engagement points for deleting comment
            deduct_engagement_points(comment.user, 'comment')
            comment.delete()
            return JsonResponse({'success': True})
    except DonationRequest.DoesNotExist:
        return JsonResponse({'error': 'Donation request not found'}, status=404)
    except Comment.DoesNotExist:
        return JsonResponse({'error': 'Comment not found'}, status=404)
    except Exception as e:
        logger.error(f"Error handling donation comment edit/delete: {e}")
        return JsonResponse({'success': False, 'message': 'Failed to handle comment operation'}, status=500)


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def donation_repost_view(request, donation_id):
    """Handle donation reposting"""
    try:
        donation = DonationRequest.objects.get(donation_id=donation_id)
        
        # Get caption from request data
        caption = request.data.get('caption', '')
        if caption:
            caption = caption.strip() or None
        
        # Create a repost of the donation
        repost = Repost.objects.create(
            donation_request=donation,
            user=request.user,
            caption=caption,
            repost_date=timezone.now()
        )
        
        # Award engagement points (+5 for share/repost)
        award_engagement_points(request.user, 'share')
        
        # Create notification for donation owner (only if the reposter is not the donation owner)
        if request.user.user_id != donation.user.user_id:
            notification = Notification.objects.create(
                user=donation.user,
                notif_type='repost',
                subject='Donation Reposted',
                notifi_content=f"{request.user.full_name} reposted your donation request<!--DONATION_ID:{donation.donation_id}--><!--ACTOR_ID:{request.user.user_id}-->",
                notif_date=timezone.now()
            )
            # Broadcast donation repost notification in real-time
            try:
                from apps.messaging.notification_broadcaster import broadcast_notification
                broadcast_notification(notification)
            except Exception as e:
                logger.error(f"Error broadcasting donation repost notification: {e}")
        
        return JsonResponse({
            'success': True,
            'message': 'Donation reposted successfully',
            'repost_id': repost.repost_id
        })
        
    except DonationRequest.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Donation request not found'}, status=404)
    except Exception as e:
        logger.error(f"Error reposting donation: {e}")
        return JsonResponse({'success': False, 'message': 'Failed to repost donation'}, status=500)

@api_view(['GET', 'PUT', 'DELETE'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def donation_detail_edit_view(request, donation_id):
    """Handle donation detail view, edit, and delete"""
    try:
        donation = DonationRequest.objects.get(donation_id=donation_id)
        
        if request.method == 'GET':
            # Get likes, comments, and reposts for this donation
            likes = Like.objects.filter(donation_request=donation).select_related('user')
            comments = Comment.objects.filter(donation_request=donation).select_related('user').order_by('-date_created')
            reposts = Repost.objects.filter(donation_request=donation).select_related('user')
            is_liked = Like.objects.filter(donation_request=donation, user=request.user).exists()
            
            # Return donation details with full interaction data
            donation_info = {
                'donation_id': donation.donation_id,
                'post_id': donation.donation_id,  # Add for compatibility with frontend
                'user': {
                    'user_id': donation.user.user_id,
                    'f_name': donation.user.f_name or '',
                    'm_name': donation.user.m_name or '',
                    'l_name': donation.user.l_name or '',
                    'profile_pic': build_profile_pic_url(donation.user),
                    'year_graduated': donation.user.academic_info.year_graduated if hasattr(donation.user, 'academic_info') and donation.user.academic_info.year_graduated else None,
                    'batch': donation.user.academic_info.year_graduated if hasattr(donation.user, 'academic_info') and donation.user.academic_info.year_graduated else None,
                    'name': f"{donation.user.f_name or ''} {donation.user.m_name or ''} {donation.user.l_name or ''}".strip()
                },
                'description': donation.description,
                'status': donation.status,
                'created_at': donation.created_at.isoformat(),
                'updated_at': donation.updated_at.isoformat(),
                                'images': get_content_images_safe(donation.donation_id, 'donation'),
                'likes_count': likes.count(),
                'comments_count': comments.count(),
                'reposts_count': reposts.count(),
                'liked_by_user': is_liked,
                'likes': [{
                    'user_id': l.user.user_id,
                    'f_name': l.user.f_name,
                    'l_name': l.user.l_name,
                    'profile_pic': build_profile_pic_url(l.user),
                    'initials': None if build_profile_pic_url(l.user) else (
                        ((l.user.f_name or '').strip()[:1].upper() + (l.user.l_name or '').strip()[:1].upper()) 
                        if ((l.user.f_name or '').strip() or (l.user.l_name or '').strip()) else None
                    ),
                } for l in likes],
                'comments': [{
                    'comment_id': c.comment_id,
                    'comment_content': c.comment_content,
                    'date_created': c.date_created.isoformat() if c.date_created else None,
                    'user': {
                        'user_id': c.user.user_id,
                        'f_name': c.user.f_name,
                        'l_name': c.user.l_name,
                        'profile_pic': build_profile_pic_url(c.user),
                    }
                } for c in comments],
                'reposts': [{
                    'repost_id': r.repost_id,
                    'repost_date': r.repost_date.isoformat() if r.repost_date else None,
                    'repost_caption': r.caption,
                    'likes_count': Like.objects.filter(repost=r).count(),
                    'comments_count': Comment.objects.filter(repost=r).count(),
                    'likes': [{
                        'user_id': l.user.user_id,
                        'f_name': l.user.f_name,
                        'm_name': l.user.m_name,
                        'l_name': l.user.l_name,
                        'profile_pic': build_profile_pic_url(l.user),
                        'initials': None if build_profile_pic_url(l.user) else (
                            ((l.user.f_name or '').strip()[:1].upper() + (l.user.l_name or '').strip()[:1].upper()) 
                            if ((l.user.f_name or '').strip() or (l.user.l_name or '').strip()) else None
                        ),
                    } for l in Like.objects.filter(repost=r).select_related('user')],
                    'comments': [{
                        'comment_id': c.comment_id,
                        'comment_content': c.comment_content,
                        'date_created': c.date_created.isoformat() if c.date_created else None,
                        'user': {
                            'user_id': c.user.user_id,
                            'f_name': c.user.f_name,
                            'm_name': c.user.m_name,
                            'l_name': c.user.l_name,
                            'profile_pic': build_profile_pic_url(c.user),
                        }
                    } for c in Comment.objects.filter(repost=r).select_related('user').order_by('-date_created')],
                    'user': {
                        'user_id': r.user.user_id,
                        'f_name': r.user.f_name,
                        'l_name': r.user.l_name,
                        'profile_pic': build_profile_pic_url(r.user),
                    },
                    'original_donation': {
                        'donation_id': donation.donation_id,
                        'description': donation.description,
                        'created_at': donation.created_at.isoformat(),
                        'user': {
                            'user_id': donation.user.user_id,
                            'f_name': donation.user.f_name,
                            'l_name': donation.user.l_name,
                            'profile_pic': build_profile_pic_url(donation.user),
                        }
                    }
                } for r in reposts]
            }
            
            return JsonResponse(donation_info)
            
        elif request.method == 'PUT':
            # Update donation
            data = request.data
            
            if 'description' in data:
                donation.description = data['description']
            
            if 'status' in data:
                donation.status = data['status']
            
            donation.updated_at = timezone.now()
            donation.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Donation updated successfully',
                'donation_id': donation.donation_id
            })
            
        elif request.method == 'DELETE':
            # Delete donation
            donation.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Donation deleted successfully'
            })
            
    except DonationRequest.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Donation request not found'}, status=404)
    except Exception as e:
        logger.error(f"Error in donation detail/edit/delete: {e}")
        return JsonResponse({'success': False, 'message': 'Failed to process request'}, status=500)

@api_view(['GET', 'POST', 'DELETE'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def recent_searches_view(request):
    """Manage per-user recent searches.
    GET: list up to ?limit=10
    POST: { searched_user_id }
    DELETE: clear all
    """
    try:
        from apps.messaging.notification_broadcaster import broadcast_recent_search_update

        def serialize_recent_searches(owner, limit_value=10):
            try:
                limit_value = int(limit_value)
            except (TypeError, ValueError):
                limit_value = 10
            limit_value = max(1, min(limit_value, 50))

            qs = (
                RecentSearch.objects
                .filter(owner=owner)
                .select_related('searched_user')
                .order_by('-created_at')[:limit_value]
            )

            detailed_results = []
            legacy_results = []
            for rs in qs:
                searched_user = rs.searched_user
                user_payload = {
                    'user_id': getattr(searched_user, 'user_id', getattr(searched_user, 'id', None)),
                    'f_name': getattr(searched_user, 'f_name', '') or getattr(searched_user, 'first_name', ''),
                    'm_name': getattr(searched_user, 'm_name', ''),
                    'l_name': getattr(searched_user, 'l_name', '') or getattr(searched_user, 'last_name', ''),
                    'profile_pic': build_profile_pic_url(searched_user),
                }
                detailed_results.append({
                    'id': rs.id,
                    'searched_user': user_payload,
                    'created_at': rs.created_at.isoformat(),
                })
                legacy_results.append({
                    'id': rs.id,
                    'user_id': user_payload['user_id'],
                    'f_name': user_payload['f_name'],
                    'l_name': user_payload['l_name'],
                    'profile_pic': user_payload['profile_pic'],
                    'created_at': rs.created_at.isoformat(),
                })
            return detailed_results, legacy_results

        logger.info("recent_searches_view %s by user=%s", request.method, getattr(getattr(request, 'user', None), 'user_id', None) or getattr(getattr(request, 'user', None), 'id', None))
        if request.method == 'GET':
            detailed_results, legacy_results = serialize_recent_searches(request.user, request.GET.get('limit', '10'))
            logger.info("recent_searches_view GET returning %s rows", len(detailed_results))
            return JsonResponse({
                'success': True,
                'recent_searches': detailed_results,
                'recent': legacy_results,
                'count': len(detailed_results),
            })

        if request.method == 'POST':
            try:
                body = json.loads(request.body or '{}')
            except Exception:
                body = {}
            target_id = body.get('searched_user_id')
            if not isinstance(target_id, int):
                return JsonResponse({ 'success': False, 'message': 'searched_user_id is required' }, status=400)
            if target_id == getattr(request.user, 'id', getattr(request.user, 'user_id', None)):
                return JsonResponse({ 'success': True })
            # Use primary key lookup; our User model uses user_id as PK
            logger.info("recent_searches_view POST target_id=%s", target_id)
            target = get_object_or_404(User, pk=target_id)
            RecentSearch.objects.filter(owner=request.user, searched_user=target).delete()
            RecentSearch.objects.create(owner=request.user, searched_user=target)
            logger.info("recent_searches_view POST created owner=%s searched_user=%s", getattr(request.user, 'user_id', None) or getattr(request.user, 'id', None), getattr(target, 'user_id', None) or getattr(target, 'id', None))

            # Diagnostics: log DB connection and counts to ensure we're writing to the expected database
            try:
                from django.db import connection
                settings_dict = getattr(connection, 'settings_dict', {})
                db_name = settings_dict.get('NAME')
                db_host = settings_dict.get('HOST')
                db_port = settings_dict.get('PORT')
                owner_count = RecentSearch.objects.filter(owner=request.user).count()
                logger.info("recent_searches_view DB: name=%s host=%s port=%s owner_recent_count=%s", db_name, db_host, db_port, owner_count)
            except Exception as diag_e:
                logger.warning("recent_searches_view diagnostics failed: %s", diag_e)

            detailed_results, legacy_results = serialize_recent_searches(request.user)
            broadcast_recent_search_update(
                getattr(request.user, 'user_id', None) or getattr(request.user, 'id', None),
                detailed_results,
                legacy_results
            )

            return JsonResponse({ 'success': True })

        if request.method == 'DELETE':
            RecentSearch.objects.filter(owner=request.user).delete()
            detailed_results, legacy_results = serialize_recent_searches(request.user)
            broadcast_recent_search_update(
                getattr(request.user, 'user_id', None) or getattr(request.user, 'id', None),
                detailed_results,
                legacy_results
            )
            return JsonResponse({ 'success': True })

        return JsonResponse({ 'success': False, 'message': 'Method not allowed' }, status=405)
    except Exception as e:
        logger.error(f"recent_searches_view error: {e}")
        return JsonResponse({ 'success': False, 'message': 'Server error' }, status=500)


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def set_send_date_view(request):
    """Set send date for OJT students"""
    try:
        data = request.data
        print(f"🔍 DEBUG set_send_date_view - Received data: {data}")
        
        coordinator = data.get('coordinator_username') or data.get('coordinator')
        batch_year = data.get('batch_year')
        section = data.get('section')
        send_date = data.get('send_date')
        
        print(f"🔍 DEBUG set_send_date_view - coordinator: {coordinator}, batch_year: {batch_year}, section: {section}, send_date: {send_date}")
        
        if not all([coordinator, batch_year, send_date]):
            print(f"❌ Missing required fields - coordinator: {bool(coordinator)}, batch_year: {bool(batch_year)}, send_date: {bool(send_date)}")
            return JsonResponse({
                'success': False,
                'message': f'Missing required fields - coordinator: {bool(coordinator)}, batch_year: {bool(batch_year)}, send_date: {bool(send_date)}'
            }, status=400)
        
        # Validate date format
        try:
            from datetime import datetime
            send_date_obj = datetime.strptime(send_date, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid date format. Use YYYY-MM-DD'
            }, status=400)
        
        # Check if batch has already been processed
        try:
            existing_send_date = SendDate.objects.get(
                coordinator=coordinator,
                batch_year=batch_year,
                section=None
            )
            if existing_send_date.is_processed:
                print(f"❌ Batch {batch_year} has already been processed (is_processed=True)")
                return JsonResponse({
                    'success': False,
                    'message': f'Batch {batch_year} has already been processed. Cannot modify send date for completed batches.'
                }, status=400)
        except SendDate.DoesNotExist:
            pass  # No existing record, can proceed
        
        # Create or update SendDate record for the entire batch (section=None for batch-wide)
        send_date_record, created = SendDate.objects.get_or_create(
            coordinator=coordinator,
            batch_year=batch_year,
            section=None,  # None means entire batch
            defaults={
                'send_date': send_date_obj,
                'is_processed': False
            }
        )
        
        if not created:
            send_date_record.send_date = send_date_obj
            send_date_record.is_processed = False
            send_date_record.save()
        
        # Update all OJT students' end dates to match the send date
        # This ensures consistent end dates across the batch
        # IMPORTANT: Only update students imported by this coordinator
        try:
            from apps.shared.models import User, OJTInfo, AcademicInfo, OJTImport
            from django.db.models import Q
            
            # Get year+section combinations imported by this coordinator
            coordinator_imports = OJTImport.objects.filter(coordinator=coordinator)
            coordinator_year_sections = set()
            for imp in coordinator_imports:
                y = getattr(imp, 'batch_year', None)
                s = getattr(imp, 'section', None) or ''
                if y == batch_year:  # Only for this batch year
                    coordinator_year_sections.add((y, s))
            
            # Build filter for coordinator's year+section combinations
            year_section_filters = Q()
            has_filters = False
            for (y, s) in coordinator_year_sections:
                if y == batch_year:
                    has_filters = True
                    if s:
                        year_section_filters |= Q(academic_info__year_graduated=y, academic_info__section=s)
                    else:
                        year_section_filters |= Q(academic_info__year_graduated=y)
            
            updated_count = 0
            if has_filters and year_section_filters:
                # Only update students from this coordinator's imports
                students = User.objects.filter(
                    year_section_filters,
                    account_type__ojt=True
                ).select_related('ojt_info', 'academic_info')
                
                print(f"🔍 Found {students.count()} OJT students in batch {batch_year} imported by {coordinator}")
                
                for student in students:
                    if hasattr(student, 'ojt_info') and student.ojt_info:
                        # Update the end date to match the scheduled send date
                        student.ojt_info.ojt_end_date = send_date_obj
                        student.ojt_info.save()
                        updated_count += 1
                        print(f"  ✓ Updated end date for {student.full_name or student.acc_username} to {send_date_obj}")
            else:
                print(f"⚠️ No students found for coordinator {coordinator} in batch {batch_year}")
            
            print(f"✅ Updated {updated_count} students' end dates to {send_date_obj}")
        except Exception as update_error:
            print(f"⚠️ Warning: Could not update student end dates: {update_error}")
            import traceback
            traceback.print_exc()
            # Don't fail the whole operation if this fails
        
        print(f"✅ Successfully set send date for batch {batch_year}: {send_date_obj}")
        
        return JsonResponse({
            'success': True,
            'message': f'Send date set successfully for entire batch {batch_year}. All student end dates updated to {send_date_obj}. On this date, completed OJT students will be automatically sent to admin.',
            'send_date': send_date,
            'batch_year': batch_year,
            'scope': 'entire_batch',
            'students_updated': updated_count if 'updated_count' in locals() else 0
        })
        
    except Exception as e:
        print(f"❌ Error in set_send_date_view: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Error setting send date: {str(e)}'
        }, status=500)

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def check_all_sent_status_view(request):
    """Check if all completed OJT students are already sent to admin for a specific batch"""
    try:
        coordinator = request.GET.get('coordinator', '')
        batch_year = request.GET.get('batch_year', '')
        
        # Base query
        base_query = User.objects.filter(
            account_type__ojt=True,
            ojt_info__ojtstatus='Completed'
        ).exclude(acc_username=settings.DEFAULT_COORDINATOR_USERNAME)
        
        # Filter by batch year if provided
        if batch_year and batch_year != 'ALL':
            try:
                year = int(batch_year)
                base_query = base_query.filter(academic_info__year_graduated=year)
            except (ValueError, TypeError):
                pass
        
        # Count completed students NOT sent to admin
        completed_not_sent = base_query.filter(
            ojt_info__is_sent_to_admin=False
        ).count()
        
        # Count completed students already sent
        completed_sent = base_query.filter(
            ojt_info__is_sent_to_admin=True
        ).count()
        
        all_sent = (completed_not_sent == 0 and completed_sent > 0)
        
        return JsonResponse({
            'success': True,
            'all_sent': all_sent,
            'completed_not_sent': completed_not_sent,
            'completed_sent': completed_sent,
            'total_completed': completed_not_sent + completed_sent,
            'batch_year': batch_year
        })
        
    except Exception as e:
        logger.error(f"check_all_sent_status_view error: {e}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def get_send_dates_view(request):
    """Get scheduled send dates for a coordinator"""
    try:
        coordinator = request.GET.get('coordinator', '')
        print(f"🔍 DEBUG get_send_dates_view - coordinator: {coordinator}")
        
        if not coordinator:
            return JsonResponse({
                'success': False,
                'message': 'Coordinator parameter is required'
            }, status=400)
        
        # Get ALL send dates for this coordinator (both processed and unprocessed)
        # This allows the frontend to show warnings about already processed batches
        send_dates = SendDate.objects.filter(
            coordinator=coordinator
        ).order_by('-is_processed', 'send_date')  # Processed first, then by date
        
        scheduled_dates = []
        for sd in send_dates:
            scheduled_dates.append({
                'id': sd.id,
                'batch_year': sd.batch_year,
                'section': sd.section,
                'send_date': sd.send_date.strftime('%Y-%m-%d'),
                'is_processed': sd.is_processed,
                'processed_at': sd.processed_at.strftime('%Y-%m-%d %H:%M:%S') if sd.processed_at else None,
                'created_at': sd.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        print(f"📋 Found {len(scheduled_dates)} send dates (processed: {sum(1 for sd in scheduled_dates if sd['is_processed'])}, unprocessed: {sum(1 for sd in scheduled_dates if not sd['is_processed'])})")
        
        return JsonResponse({
            'success': True,
            'scheduled_dates': scheduled_dates,
            'count': len(scheduled_dates)
        })
        
    except Exception as e:
        logger.error(f"get_send_dates_view error: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Error fetching send dates: {str(e)}'
        }, status=500)


@api_view(['DELETE'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def delete_send_date_view(request):
    """Delete/remove a scheduled send date (idempotent operation)"""
    try:
        data = request.data
        coordinator = data.get('coordinator_username') or data.get('coordinator')
        batch_year = data.get('batch_year')
        
        print(f"🔍 DEBUG delete_send_date_view - coordinator: {coordinator}, batch_year: {batch_year}")
        
        if not all([coordinator, batch_year]):
            return JsonResponse({
                'success': False,
                'message': 'Missing required fields - coordinator and batch_year are required'
            }, status=400)
        
        # Delete the send date record (if exists)
        deleted_count, _ = SendDate.objects.filter(
            coordinator=coordinator,
            batch_year=batch_year,
            section=None,  # None means entire batch
            is_processed=False
        ).delete()
        
        # Return success regardless of whether records were found (idempotent operation)
        # This prevents errors when trying to delete already-deleted schedules
        if deleted_count > 0:
            print(f"✅ Successfully deleted {deleted_count} send date(s) for batch {batch_year}")
            return JsonResponse({
                'success': True,
                'message': f'Scheduled send date removed successfully for batch {batch_year}',
                'deleted_count': deleted_count
            })
        else:
            print(f"ℹ️ No send date found for batch {batch_year} (already removed or never existed)")
            return JsonResponse({
                'success': True,
                'message': f'Schedule already removed or does not exist for batch {batch_year}',
                'deleted_count': 0
            })
        
    except Exception as e:
        print(f"❌ Error in delete_send_date_view: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Error deleting send date: {str(e)}'
        }, status=500)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def engagement_leaderboard_view(request):
    """
    Get engagement points leaderboard for Alumni and OJT users.
    Returns top users ranked by total points.
    """
    try:
        limit = int(request.GET.get('limit', 50))  # Default to top 50
        user_type = request.GET.get('user_type', 'all')  # Keep for API compatibility
        
        # Base query for users with points - ALUMNI and OJT users
        points_query = UserPoints.objects.select_related('user', 'user__profile', 'user__academic_info', 'user__account_type')
        
        # Include both Alumni and OJT users
        points_query = points_query.filter(
            Q(user__account_type__user=True) | Q(user__account_type__ojt=True)
        )
        
        # Order by total points descending and limit
        top_users = points_query.order_by('-total_points')[:limit]
        
        leaderboard_data = []
        for rank, user_points in enumerate(top_users, start=1):
            user = user_points.user
            profile = getattr(user, 'profile', None)
            academic_info = getattr(user, 'academic_info', None)
            account_type = getattr(user, 'account_type', None)
            
            # Determine user type
            is_ojt = getattr(account_type, 'ojt', False)
            is_alumni = getattr(account_type, 'user', False)
            user_role = 'OJT' if is_ojt else 'Alumni' if is_alumni else 'Unknown'
            
            leaderboard_data.append({
                'rank': rank,
                'user_id': user.user_id,
                'name': user.full_name,
                'profile_pic': profile.profile_pic.url if profile and profile.profile_pic else None,
                'user_type': user_role,
                'year_graduated': academic_info.year_graduated if academic_info else None,
                'program': academic_info.program if academic_info else None,
                'total_points': user_points.total_points,
                'points_breakdown': {
                    'likes': {
                        'points': user_points.points_from_likes,
                        'count': user_points.like_count
                    },
                    'comments': {
                        'points': user_points.points_from_comments,
                        'count': user_points.comment_count
                    },
                    'shares': {
                        'points': user_points.points_from_shares,
                        'count': user_points.share_count
                    },
                    'replies': {
                        'points': user_points.points_from_replies,
                        'count': user_points.reply_count
                    },
                    'posts': {
                        'points': getattr(user_points, 'points_from_posts', 0),
                        'count': getattr(user_points, 'post_count', 0)
                    },
                    'posts_with_photos': {
                        'points': user_points.points_from_posts_with_photos,
                        'count': user_points.post_with_photo_count
                    },
                    'tracker_form': {
                        'points': user_points.points_from_tracker_form,
                        'count': user_points.tracker_form_count
                    }
                },
                'last_updated': user_points.updated_at.isoformat()
            })
        
        return JsonResponse({
            'success': True,
            'leaderboard': leaderboard_data,
            'count': len(leaderboard_data),
            'filter': {
                'user_type': user_type,
                'limit': limit
            }
        })
        
    except Exception as e:
        logger.error(f"engagement_leaderboard_view error: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Error fetching leaderboard: {str(e)}'
        }, status=500)


# ============================
# Engagement Points Settings API Endpoints
# ============================

@api_view(['GET', 'POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def engagement_points_settings_view(request):
    """
    GET: Get current engagement points settings (accessible to all authenticated users).
    POST: Update engagement points settings (admin only).
    """
    try:
        from apps.shared.models import EngagementPointsSettings
        settings = EngagementPointsSettings.get_settings()
        
        # Handle GET request - accessible to all authenticated users
        if request.method == 'GET':
            return JsonResponse({
                'success': True,
                'settings': {
                    'enabled': settings.enabled,
                    'like_points': settings.like_points,
                    'comment_points': settings.comment_points,
                    'share_points': settings.share_points,
                    'reply_points': settings.reply_points,
                    'post_points': settings.post_points,
                    'post_with_photo_points': settings.post_with_photo_points,
                    'tracker_form_points': settings.tracker_form_points,
                    # Rate limiting settings
                    'rate_limiting_enabled': settings.rate_limiting_enabled,
                    'daily_like_limit': settings.daily_like_limit,
                    'daily_comment_limit': settings.daily_comment_limit,
                    'daily_share_limit': settings.daily_share_limit,
                    'daily_reply_limit': settings.daily_reply_limit,
                    'daily_post_limit': settings.daily_post_limit,
                    'daily_post_with_photo_limit': settings.daily_post_with_photo_limit,
                    'daily_tracker_form_limit': settings.daily_tracker_form_limit,
                    'hourly_like_limit': settings.hourly_like_limit,
                    'hourly_comment_limit': settings.hourly_comment_limit,
                    'hourly_share_limit': settings.hourly_share_limit,
                    'hourly_reply_limit': settings.hourly_reply_limit,
                    'hourly_post_limit': settings.hourly_post_limit,
                    'hourly_post_with_photo_limit': settings.hourly_post_with_photo_limit,
                    'hourly_tracker_form_limit': settings.hourly_tracker_form_limit,
                }
            })
        
        # Handle POST request - admin only
        elif request.method == 'POST':
            # Check if user is admin
            user = request.user
            if not (hasattr(user, 'account_type') and getattr(user.account_type, 'admin', False)):
                return JsonResponse({
                    'success': False,
                    'message': 'Admin access required'
                }, status=403)
            
            # Update settings from request data
            data = request.data
            
            if 'enabled' in data:
                settings.enabled = bool(data['enabled'])
            
            if 'like' in data:
                settings.like_points = int(data['like'])
            
            if 'comment' in data:
                settings.comment_points = int(data['comment'])
            
            if 'share' in data:
                settings.share_points = int(data['share'])
            
            if 'reply' in data:
                settings.reply_points = int(data['reply'])
            
            if 'post' in data:
                settings.post_points = int(data['post'])
            
            if 'post_with_photo' in data:
                settings.post_with_photo_points = int(data['post_with_photo'])
            
            if 'tracker_form' in data:
                settings.tracker_form_points = int(data['tracker_form'])
            
            # Update rate limiting settings
            if 'rate_limiting_enabled' in data:
                settings.rate_limiting_enabled = bool(data['rate_limiting_enabled'])
            
            if 'daily_like_limit' in data:
                settings.daily_like_limit = int(data['daily_like_limit'])
            if 'daily_comment_limit' in data:
                settings.daily_comment_limit = int(data['daily_comment_limit'])
            if 'daily_share_limit' in data:
                settings.daily_share_limit = int(data['daily_share_limit'])
            if 'daily_reply_limit' in data:
                settings.daily_reply_limit = int(data['daily_reply_limit'])
            if 'daily_post_limit' in data:
                settings.daily_post_limit = int(data['daily_post_limit'])
            if 'daily_post_with_photo_limit' in data:
                settings.daily_post_with_photo_limit = int(data['daily_post_with_photo_limit'])
            if 'daily_tracker_form_limit' in data:
                settings.daily_tracker_form_limit = int(data['daily_tracker_form_limit'])
            
            if 'hourly_like_limit' in data:
                settings.hourly_like_limit = int(data['hourly_like_limit'])
            if 'hourly_comment_limit' in data:
                settings.hourly_comment_limit = int(data['hourly_comment_limit'])
            if 'hourly_share_limit' in data:
                settings.hourly_share_limit = int(data['hourly_share_limit'])
            if 'hourly_reply_limit' in data:
                settings.hourly_reply_limit = int(data['hourly_reply_limit'])
            if 'hourly_post_limit' in data:
                settings.hourly_post_limit = int(data['hourly_post_limit'])
            if 'hourly_post_with_photo_limit' in data:
                settings.hourly_post_with_photo_limit = int(data['hourly_post_with_photo_limit'])
            if 'hourly_tracker_form_limit' in data:
                settings.hourly_tracker_form_limit = int(data['hourly_tracker_form_limit'])
            
            settings.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Points settings updated successfully',
                'settings': {
                    'enabled': settings.enabled,
                    'like': settings.like_points,
                    'comment': settings.comment_points,
                    'share': settings.share_points,
                    'reply': settings.reply_points,
                    'post': settings.post_points,
                    'post_with_photo': settings.post_with_photo_points,
                    'tracker_form': settings.tracker_form_points
                }
            })
        
    except ValueError as e:
        return JsonResponse({
            'success': False,
            'message': f'Invalid value: {str(e)}'
        }, status=400)
    except Exception as e:
        logger.error(f"engagement_points_settings_view error: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=500)


# ============================
# Reward Inventory API Endpoints
# ============================

@api_view(['GET', 'POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def inventory_items_view(request):
    """
    GET: List all inventory items (users can view available items, admin can see all)
    POST: Create a new inventory item (admin only)
    """
    try:
        user = request.user
        is_admin = hasattr(user, 'account_type') and user.account_type.admin
        
        if request.method == 'GET':
            # Fetch all inventory items
            items = RewardInventoryItem.objects.all().order_by('-created_at')
            
            items_data = []
            for item in items:
                # Users can only see items with quantity > 0
                if not is_admin and item.quantity <= 0:
                    continue
                    
                items_data.append({
                    'id': item.item_id,
                    'name': item.name,
                    'type': item.type,
                    'quantity': item.quantity,
                    'value': item.value,
                    'created_at': item.created_at.isoformat(),
                    'updated_at': item.updated_at.isoformat()
                })
            
            return JsonResponse({
                'success': True,
                'items': items_data,
                'count': len(items_data)
            })
        
        # POST method requires admin access
        if not is_admin:
            return JsonResponse({
                'success': False,
                'message': 'Admin access required'
            }, status=403)
        
        elif request.method == 'POST':
            # Create new inventory item
            data = json.loads(request.body)
            
            name = data.get('name', '').strip()
            item_type = data.get('type', '').strip()
            quantity = data.get('quantity', 0)
            value = data.get('value', '').strip()
            
            # Validation
            if not name:
                return JsonResponse({
                    'success': False,
                    'message': 'Item name is required'
                }, status=400)
            
            if not item_type:
                return JsonResponse({
                    'success': False,
                    'message': 'Item type is required'
                }, status=400)
            
            if not isinstance(quantity, int) or quantity < 1:
                return JsonResponse({
                    'success': False,
                    'message': 'Quantity must be at least 1'
                }, status=400)
            
            if not value or value == '0':
                return JsonResponse({
                    'success': False,
                    'message': 'Value is required and cannot be 0'
                }, status=400)
            
            # Create item
            new_item = RewardInventoryItem.objects.create(
                name=name,
                type=item_type,
                quantity=quantity,
                value=value
            )
            
            logger.info(f"Admin {user.full_name} created inventory item: {name}")
            
            return JsonResponse({
                'success': True,
                'message': 'Item added successfully',
                'item': {
                    'id': new_item.item_id,
                    'name': new_item.name,
                    'type': new_item.type,
                    'quantity': new_item.quantity,
                    'value': new_item.value,
                    'created_at': new_item.created_at.isoformat(),
                    'updated_at': new_item.updated_at.isoformat()
                }
            }, status=201)
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"inventory_items_view error: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=500)


@api_view(['PUT', 'DELETE'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def inventory_item_detail_view(request, item_id):
    """
    PUT: Update an inventory item
    DELETE: Delete an inventory item
    (admin only)
    """
    try:
        # Check if user is admin
        user = request.user
        if not hasattr(user, 'account_type') or not user.account_type.admin:
            return JsonResponse({
                'success': False,
                'message': 'Admin access required'
            }, status=403)
        
        # Get item
        try:
            item = RewardInventoryItem.objects.get(item_id=item_id)
        except RewardInventoryItem.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Item not found'
            }, status=404)
        
        if request.method == 'PUT':
            # Update item
            data = json.loads(request.body)
            
            name = data.get('name', '').strip()
            item_type = data.get('type', '').strip()
            quantity = data.get('quantity', 0)
            value = data.get('value', '').strip()
            
            # Validation
            if not name:
                return JsonResponse({
                    'success': False,
                    'message': 'Item name is required'
                }, status=400)
            
            if not item_type:
                return JsonResponse({
                    'success': False,
                    'message': 'Item type is required'
                }, status=400)
            
            if not isinstance(quantity, int) or quantity < 1:
                return JsonResponse({
                    'success': False,
                    'message': 'Quantity must be at least 1'
                }, status=400)
            
            if not value or value == '0':
                return JsonResponse({
                    'success': False,
                    'message': 'Value is required and cannot be 0'
                }, status=400)
            
            # Update fields
            item.name = name
            item.type = item_type
            item.quantity = quantity
            item.value = value
            item.save()
            
            logger.info(f"Admin {user.full_name} updated inventory item: {name}")
            
            return JsonResponse({
                'success': True,
                'message': 'Item updated successfully',
                'item': {
                    'id': item.item_id,
                    'name': item.name,
                    'type': item.type,
                    'quantity': item.quantity,
                    'value': item.value,
                    'created_at': item.created_at.isoformat(),
                    'updated_at': item.updated_at.isoformat()
                }
            })
        
        elif request.method == 'DELETE':
            # Delete item
            item_name = item.name
            item.delete()
            
            logger.info(f"Admin {user.full_name} deleted inventory item: {item_name}")
            
            return JsonResponse({
                'success': True,
                'message': 'Item deleted successfully'
            })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"inventory_item_detail_view error: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=500)


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def give_reward_view(request):
    """
    Give a reward to a user (admin only)
    Creates a notification for the recipient
    """
    try:
        # Check if user is admin
        admin_user = request.user
        if not hasattr(admin_user, 'account_type') or not admin_user.account_type.admin:
            return JsonResponse({
                'success': False,
                'message': 'Admin access required'
            }, status=403)
        
        data = json.loads(request.body)
        user_id = data.get('user_id')
        reward_id = data.get('reward_id')
        is_tracker_reward = data.get('is_tracker_reward', False)  # Optional parameter
        
        if not user_id or not reward_id:
            return JsonResponse({
                'success': False,
                'message': 'User ID and Reward ID are required'
            }, status=400)
        
        # Get recipient user
        try:
            recipient = User.objects.get(user_id=user_id)
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'User not found'
            }, status=404)
        
        # Get reward item
        try:
            reward_item = RewardInventoryItem.objects.get(item_id=reward_id)
        except RewardInventoryItem.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Reward item not found'
            }, status=404)
        
        # Check if item has stock
        if reward_item.quantity <= 0:
            return JsonResponse({
                'success': False,
                'message': 'Reward item is out of stock'
            }, status=400)
        
        # Extract point value from reward item (e.g., "10 pts" -> 10)
        import re
        points_match = re.search(r'(\d+)', reward_item.value)
        required_points = int(points_match.group(1)) if points_match else 0
        
        # Get or create user points
        user_points, created = UserPoints.objects.get_or_create(user=recipient)
        
        # For tracker rewards, skip point deduction (admin reward, not point redemption)
        if not is_tracker_reward:
            # Check if user has enough points (only for regular rewards)
            if user_points.total_points < required_points:
                return JsonResponse({
                    'success': False,
                    'message': f'User does not have enough points. Required: {required_points}, Available: {user_points.total_points}'
                }, status=400)
            
            # Deduct points from user (only for regular rewards)
            user_points.total_points -= required_points
            user_points.save()
        
        # Decrease quantity
        reward_item.quantity -= 1
        reward_item.save()
        
        # Save to reward history
        RewardHistory.objects.create(
            user=recipient,
            reward_name=reward_item.name,
            reward_type=reward_item.type,
            reward_value=reward_item.value,
            points_deducted=0 if is_tracker_reward else required_points,  # No points deducted for tracker rewards
            given_by=admin_user
        )
        
        # Create notification for the user
        if is_tracker_reward:
            # Custom notification message for tracker form rewards (no points deducted)
            notification_content = f'🎉 You are lucky! As a token of appreciation for cooperating and answering the tracker form, you have been chosen to receive a reward. Congratulations! You have been awarded "{reward_item.name}" ({reward_item.value}). No points were deducted - this is a special reward from the admin. Thank you for your participation!'
            notification_subject = '🎁 Token of Appreciation - Tracker Form Response!'
        else:
            # Standard notification message for regular rewards (points deducted)
            notification_content = f'Congratulations! You have been awarded "{reward_item.name}" ({reward_item.value}) for your engagement in the alumni network. {required_points} points have been deducted from your account. Keep up the great work!'
            notification_subject = '🎁 You received a reward!'
        
        notification = Notification.objects.create(
            user=recipient,
            notif_type='Reward',
            subject=notification_subject,
            notifi_content=notification_content,
            notif_date=timezone.now(),
            is_read=False
        )
        
        # Broadcast notification in real-time
        try:
            from apps.messaging.notification_broadcaster import broadcast_notification
            broadcast_notification(notification)
        except Exception as e:
            logger.error(f"Error broadcasting reward notification: {e}")
        
        if is_tracker_reward:
            logger.info(f"Admin {admin_user.full_name} gave tracker reward '{reward_item.name}' to {recipient.full_name} (no points deducted)")
        else:
            logger.info(f"Admin {admin_user.full_name} gave reward '{reward_item.name}' to {recipient.full_name}, {required_points} points deducted")
        
        return JsonResponse({
            'success': True,
            'message': f'Reward "{reward_item.name}" successfully given to {recipient.full_name}',
            'notification_created': True,
            'points_deducted': 0 if is_tracker_reward else required_points,
            'user_remaining_points': user_points.total_points
        })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"give_reward_view error: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=500)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def reward_history_view(request):
    """
    GET: List all reward history (admin only)
    Returns list of rewards given to users with user details
    """
    try:
        # Check if user is admin
        user = request.user
        if not hasattr(user, 'account_type') or not user.account_type.admin:
            return JsonResponse({
                'success': False,
                'message': 'Admin access required'
            }, status=403)
        
        # Get limit parameter (default to 50)
        limit = int(request.GET.get('limit', 50))
        
        # Get filter parameter for tracker rewards (points_deducted = 0)
        tracker_only = request.GET.get('tracker_only', 'false').lower() == 'true'
        
        # Fetch reward history
        if tracker_only:
            # Filter for tracker rewards: points_deducted = 0 AND given_by is an admin
            # Tracker rewards are rewards given by admin for answering tracker form (no points deducted)
            history = RewardHistory.objects.select_related('user', 'given_by').filter(
                points_deducted=0,
                given_by__isnull=False
            ).order_by('-given_at')[:limit]
        else:
            history = RewardHistory.objects.select_related('user', 'given_by').all().order_by('-given_at')[:limit]
        
        history_data = []
        for entry in history:
            try:
                # Get user profile pic
                profile_pic = None
                try:
                    user_profile = UserProfile.objects.filter(user=entry.user).first()
                    if user_profile and user_profile.profile_pic:
                        profile_pic = user_profile.profile_pic.url if user_profile.profile_pic else None
                except Exception as e:
                    logger.warning(f"Error getting profile pic for user {entry.user.user_id}: {e}")
                
                # Get user academic info
                program = None
                year_graduated = None
                try:
                    academic_info = AcademicInfo.objects.filter(user=entry.user).first()
                    if academic_info:
                        program = academic_info.program
                        year_graduated = academic_info.year_graduated
                except Exception as e:
                    logger.warning(f"Error getting academic info for user {entry.user.user_id}: {e}")
                
                history_data.append({
                    'id': entry.history_id,
                    'user_id': entry.user.user_id,
                    'user_name': entry.user.full_name,
                    'profile_pic': profile_pic,
                    'program': program,
                    'year_graduated': year_graduated,
                    'reward_name': entry.reward_name,
                    'reward_type': entry.reward_type,
                    'reward_value': entry.reward_value,
                    'points_deducted': entry.points_deducted,
                    'given_by': entry.given_by.full_name if entry.given_by else 'System',
                    'given_at': entry.given_at.isoformat()
                })
            except Exception as e:
                logger.error(f"Error processing reward history entry {entry.history_id}: {e}")
                continue
        
        return JsonResponse({
            'success': True,
            'history': history_data,
            'count': len(history_data)
        })
    
    except Exception as e:
        import traceback
        logger.error(f"reward_history_view error: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=500)


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def request_reward_view(request):
    """
    User requests a reward (self-service redemption)
    Creates a pending request WITHOUT deducting points or inventory
    Points and inventory will be deducted when user actually claims after admin approval
    """
    try:
        user = request.user
        data = json.loads(request.body)
        reward_id = data.get('reward_id')
        
        if not reward_id:
            return JsonResponse({
                'success': False,
                'message': 'Reward ID is required'
            }, status=400)
        
        # Get reward item
        try:
            reward_item = RewardInventoryItem.objects.get(item_id=reward_id)
        except RewardInventoryItem.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Reward item not found'
            }, status=404)
        
        # Check if item has stock
        if reward_item.quantity <= 0:
            return JsonResponse({
                'success': False,
                'message': 'Reward item is out of stock'
            }, status=400)
        
        # Extract point value from reward item (e.g., "10 pts" -> 10)
        import re
        points_match = re.search(r'(\d+)', reward_item.value)
        required_points = int(points_match.group(1)) if points_match else 0
        
        # Get user points
        user_points, created = UserPoints.objects.get_or_create(user=user)
        
        # Check if user has enough points (but don't deduct yet)
        if user_points.total_points < required_points:
            return JsonResponse({
                'success': False,
                'message': f'Insufficient points. Required: {required_points}, Available: {user_points.total_points}'
            }, status=400)
        
        # Check if user has already requested a reward this month (limit: 1 per month)
        now = timezone.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Count reward requests in current month (any status)
        monthly_requests = RewardRequest.objects.filter(
            user=user,
            requested_at__gte=start_of_month
        ).count()
        
        if monthly_requests >= 1:
            return JsonResponse({
                'success': False,
                'message': 'You can only request 1 reward per month. Please wait until next month to request another reward.'
            }, status=400)
        
        # Create pending reward request (NO points or inventory deduction yet)
        reward_request = RewardRequest.objects.create(
            user=user,
            reward_item=reward_item,
            status='pending',
            points_cost=required_points
        )
        
        # Determine message based on reward type
        is_voucher = reward_item.type.lower() in ['voucher', 'gift card', 'giftcard', 'coupon']
        is_merchandise = reward_item.type.lower() in ['merchandise', 'merch', 'item', 'product']
        
        confirmation_message = ""
        if is_voucher:
            confirmation_message = "Please expect a reply from us regarding your reward request."
        elif is_merchandise:
            confirmation_message = "Please note that this reward must be claimed in person at the CTU office."
        else:
            confirmation_message = "Your reward request has been submitted and is pending approval."
        
        # Create notification for admin
        try:
            admin_users = User.objects.filter(account_type__admin=True)
            for admin in admin_users:
                notification = Notification.objects.create(
                    user=admin,
                    notif_type='Reward Request',
                    subject=f'🎁 New Reward Request',
                    notifi_content=f'{user.full_name} has requested to claim "{reward_item.name}" ({reward_item.value}). Points required: {required_points}. Please review and approve.',
                    notif_date=timezone.now(),
                    is_read=False
                )
                # Broadcast notification in real-time
                try:
                    from apps.messaging.notification_broadcaster import broadcast_notification
                    broadcast_notification(notification)
                except Exception as e:
                    logger.error(f"Error broadcasting reward request notification: {e}")
        except Exception as e:
            logger.error(f"Error creating admin notifications: {e}")
        
        return JsonResponse({
            'success': True,
            'message': confirmation_message,
            'request_id': reward_request.request_id,
            'points_required': required_points,
            'remaining_points': user_points.total_points
        })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"request_reward_view error: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=500)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def reward_requests_list_view(request):
    """
    GET: List reward requests (admin only - all requests, user - their own requests)
    """
    try:
        user = request.user
        is_admin = hasattr(user, 'account_type') and user.account_type.admin
        
        if is_admin:
            # Admin sees all requests
            # Query from RewardRequest model which uses 'shared_rewardrequest' table
            status_filter = request.GET.get('status', None)
            
            # First get all requests without filter to debug
            all_requests = RewardRequest.objects.all()
            total_all = all_requests.count()
            logger.info(f"DEBUG: Total reward requests in DB (no filter): {total_all}")
            
            # Check status distribution
            from django.db.models import Count
            status_counts = RewardRequest.objects.values('status').annotate(count=Count('status'))
            logger.info(f"DEBUG: Status distribution: {list(status_counts)}")
            
            queryset = RewardRequest.objects.select_related('user', 'reward_item', 'approved_by').all()
            
            if status_filter:
                queryset = queryset.filter(status=status_filter)
                logger.info(f"DEBUG: Filtering by status='{status_filter}'")
            
            requests_data = []
            total_requests = queryset.count()
            # Log to confirm we're querying the shared_rewardrequest table
            logger.info(f"Admin {user.full_name} fetching reward requests from 'shared_rewardrequest' table. Status filter: {status_filter}. Total matching filter: {total_requests}")
            
            for req in queryset.order_by('-requested_at'):
                try:
                    # Get user profile pic
                    profile_pic = None
                    try:
                        user_profile = UserProfile.objects.filter(user=req.user).first()
                        if user_profile and user_profile.profile_pic:
                            profile_pic = user_profile.profile_pic.url if user_profile.profile_pic else None
                    except Exception as e:
                        logger.warning(f"Error getting profile pic for request {req.request_id}: {e}")
                    
                    requests_data.append({
                        'request_id': req.request_id,
                        'user_id': req.user.user_id,
                        'user_name': req.user.full_name,
                        'profile_pic': profile_pic,
                        'reward_id': req.reward_item.item_id,
                        'reward_name': req.reward_item.name,
                        'reward_type': req.reward_item.type,
                        'reward_value': req.reward_item.value,
                        'status': req.status,
                        'points_cost': req.points_cost,
                        'voucher_code': req.voucher_code,
                        'voucher_file': req.voucher_file.url if req.voucher_file else None,
                        'requested_at': req.requested_at.isoformat(),
                        'approved_at': req.approved_at.isoformat() if req.approved_at else None,
                        'approved_by': req.approved_by.full_name if req.approved_by else None,
                        'expires_at': req.expires_at.isoformat() if req.expires_at else None,
                        'notes': req.notes
                    })
                except Exception as e:
                    import traceback
                    logger.error(f"Error processing reward request {req.request_id}: {e}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    continue
            
            logger.info(f"Returning {len(requests_data)} reward requests (filtered from {total_requests} total)")
            
            # If we have requests in DB but none in response, log warning
            if total_requests > 0 and len(requests_data) == 0:
                logger.warning(f"WARNING: Found {total_requests} requests in DB matching filter, but none processed successfully. Check for serialization errors above.")
            
            return JsonResponse({
                'success': True,
                'requests': requests_data,
                'count': len(requests_data),
                'total_in_db': total_requests  # Include for debugging
            })
        else:
            # User sees their own requests
            requests = RewardRequest.objects.filter(user=user).select_related('reward_item', 'approved_by').order_by('-requested_at')
            requests_data = []
            for req in requests:
                requests_data.append({
                    'request_id': req.request_id,
                    'reward_id': req.reward_item.item_id,
                    'reward_name': req.reward_item.name,
                    'reward_type': req.reward_item.type,
                    'reward_value': req.reward_item.value,
                    'status': req.status,
                    'points_cost': req.points_cost,
                    'voucher_code': req.voucher_code,
                    'voucher_file': req.voucher_file.url if req.voucher_file else None,
                    'requested_at': req.requested_at.isoformat(),
                    'approved_at': req.approved_at.isoformat() if req.approved_at else None,
                    'expires_at': req.expires_at.isoformat() if req.expires_at else None,
                    'notes': req.notes
                })
            
            return JsonResponse({
                'success': True,
                'requests': requests_data,
                'count': len(requests_data)
            })
    
    except Exception as e:
        logger.error(f"reward_requests_list_view error: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=500)


def get_business_days_after(start_date, days):
    """
    Calculate expiration date excluding weekends and holidays.
    Returns a datetime that is 'days' business days after start_date.
    """
    from datetime import date
    
    # Philippine holidays (common national holidays)
    # Format: (month, day) - year-specific holidays would need to be updated annually
    philippine_holidays = [
        # Fixed holidays
        (1, 1),   # New Year's Day
        (2, 25),  # EDSA Revolution Anniversary
        (4, 9),   # Day of Valor (Araw ng Kagitingan)
        (5, 1),   # Labor Day
        (6, 12),  # Independence Day
        (8, 21),  # Ninoy Aquino Day
        (8, 26),  # National Heroes Day (last Monday of August, but fixed as 26th for simplicity)
        (11, 30), # Bonifacio Day
        (12, 25), # Christmas Day
        (12, 30), # Rizal Day
        # Add more holidays as needed
    ]
    
    # Extract date from timezone-aware or naive datetime
    if hasattr(start_date, 'date'):
        current_date = start_date.date()
        original_time = start_date.time()
        is_timezone_aware = timezone.is_aware(start_date)
    else:
        current_date = start_date
        original_time = datetime.min.time()
        is_timezone_aware = False
    
    business_days_added = 0
    check_date = current_date
    
    while business_days_added < days:
        check_date += timedelta(days=1)
        
        # Skip weekends (Saturday = 5, Sunday = 6)
        if check_date.weekday() >= 5:
            continue
        
        # Skip holidays
        is_holiday = (check_date.month, check_date.day) in philippine_holidays
        if is_holiday:
            continue
        
        business_days_added += 1
    
    # Convert back to datetime, preserving timezone awareness
    result_datetime = datetime.combine(check_date, original_time)
    if is_timezone_aware:
        result_datetime = timezone.make_aware(result_datetime)
    
    return result_datetime


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def approve_reward_request_view(request, request_id):
    """
    Admin approves a reward request
    Admin can add instructions/notes on how to claim the voucher
    For vouchers: can upload voucher code/file, sets 5-day expiration
    For merchandise: marks as ready for pickup
    Status changes to 'approved' but points/inventory NOT deducted yet
    """
    try:
        # Check if user is admin
        admin_user = request.user
        if not hasattr(admin_user, 'account_type') or not admin_user.account_type.admin:
            return JsonResponse({
                'success': False,
                'message': 'Admin access required'
            }, status=403)
        
        # Get reward request
        try:
            reward_request = RewardRequest.objects.get(request_id=request_id)
        except RewardRequest.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Reward request not found'
            }, status=404)
        
        if reward_request.status != 'pending':
            return JsonResponse({
                'success': False,
                'message': f'Request is already {reward_request.status}'
            }, status=400)
        
        data = json.loads(request.body) if request.body else {}
        is_voucher = reward_request.reward_item.type.lower() in ['voucher', 'gift card', 'giftcard', 'coupon']
        is_merchandise = reward_request.reward_item.type.lower() in ['merchandise', 'merch', 'item', 'product']
        
        # Update request status to 'approved' (ready for user to claim)
        reward_request.status = 'approved' if is_voucher else 'ready_for_pickup'
        reward_request.approved_at = timezone.now()
        reward_request.approved_by = admin_user
        
        # Handle voucher expiration (5 business days, excluding weekends and holidays)
        if is_voucher:
            approval_date = timezone.now()
            reward_request.expires_at = get_business_days_after(approval_date, 1)
            voucher_code = data.get('voucher_code')
            if voucher_code:
                reward_request.voucher_code = voucher_code
        
        # Admin can add instructions/notes on how to claim
        notes = data.get('notes') or data.get('instructions')
        if notes:
            reward_request.notes = notes
        
        reward_request.save()
        
        # Get admin profile picture for notification
        admin_profile_pic = None
        try:
            admin_profile = UserProfile.objects.filter(user=admin_user).first()
            if admin_profile and admin_profile.profile_pic:
                admin_profile_pic = admin_profile.profile_pic.url
        except Exception as e:
            logger.warning(f"Error getting admin profile pic for notification: {e}")
        
        # Create notification for user (with instructions if provided)
        notification_content = f'Your request for "{reward_request.reward_item.name}" has been {"approved" if is_voucher else "processed"}. '
        if notes:
            notification_content += f'\n\nInstructions: {notes}\n\n'
        if reward_request.voucher_code:
            notification_content += f'Voucher code: {reward_request.voucher_code}. '
        if is_voucher:
            notification_content += f'Please claim it within 5 business days (expires: {reward_request.expires_at.strftime("%Y-%m-%d")}). Click "Claim" to redeem your reward.'
        else:
            notification_content += 'Your merchandise is ready for pickup. An admin will release it when you collect it in person at the CTU office.'
        
        # Add admin info to notification content for profile picture display
        notification_content += f'<!--AUTHOR_ID:{admin_user.user_id}-->'
        notification_content += f'<!--AUTHOR_NAME:{admin_user.full_name}-->'
        if admin_profile_pic:
            notification_content += f'<!--AUTHOR_PIC:{admin_profile_pic}-->'
        # Add reward request ID for direct navigation to reward details
        notification_content += f'<!--REQUEST_ID:{request_id}-->'
        
        notification = Notification.objects.create(
            user=reward_request.user,
            notif_type='Reward',
            subject=f'🎁 Your reward request has been {"approved" if is_voucher else "processed"}!',
            notifi_content=notification_content,
            notif_date=timezone.now(),
            is_read=False
        )
        
        # Broadcast notification
        try:
            from apps.messaging.notification_broadcaster import broadcast_notification
            broadcast_notification(notification)
        except Exception as e:
            logger.error(f"Error broadcasting notification: {e}")
        
        logger.info(f"Admin {admin_user.full_name} approved reward request {request_id} for {reward_request.user.full_name}")
        
        return JsonResponse({
            'success': True,
            'message': f'Reward request {"approved" if is_voucher else "marked as ready for pickup"}. User will receive notification with instructions.',
            'status': reward_request.status,
            'expires_at': reward_request.expires_at.isoformat() if reward_request.expires_at else None
        })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"approve_reward_request_view error: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=500)


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def claim_reward_request_view(request, request_id):
    """
    User claims a reward after admin approval, OR admin releases merchandise
    THIS is where points and inventory get deducted
    
    For vouchers: User clicks "Claim" after admin approval
    For merchandise: Admin clicks "Release" after marking as ready_for_pickup
    """
    try:
        user = request.user
        
        # Get reward request
        try:
            reward_request = RewardRequest.objects.get(request_id=request_id)
        except RewardRequest.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Reward request not found'
            }, status=404)
        
        # Check if user is admin releasing merchandise
        is_admin = hasattr(user, 'account_type') and user.account_type.admin
        is_merchandise = reward_request.reward_item.type.lower() in ['merchandise', 'merch', 'item', 'product']
        
        # Verify this request belongs to the user, OR admin is releasing merchandise
        if not is_admin or not is_merchandise:
            if reward_request.user.user_id != user.user_id:
                return JsonResponse({
                    'success': False,
                    'message': 'Unauthorized access'
                }, status=403)
        
        # Check if request is approved or ready for pickup
        if reward_request.status not in ['approved', 'ready_for_pickup']:
            return JsonResponse({
                'success': False,
                'message': f'Reward request is not ready to claim. Current status: {reward_request.status}'
            }, status=400)
        
        # Check if already claimed
        if reward_request.status == 'claimed':
            return JsonResponse({
                'success': False,
                'message': 'Reward has already been claimed'
            }, status=400)
        
        # Check if expired (for vouchers)
        if reward_request.expires_at and timezone.now() > reward_request.expires_at:
            reward_request.status = 'expired'
            reward_request.save()
            return JsonResponse({
                'success': False,
                'message': 'Reward has expired'
            }, status=400)
        
        # Check if reward item still has stock
        reward_item = reward_request.reward_item
        if reward_item.quantity <= 0:
            return JsonResponse({
                'success': False,
                'message': 'Reward item is out of stock'
            }, status=400)
        
        # For admin releasing merchandise, use the reward request user's points
        # For regular users claiming, use their own points
        reward_user = reward_request.user if (is_admin and is_merchandise) else user
        
        # Get user points and verify they still have enough
        user_points, created = UserPoints.objects.get_or_create(user=reward_user)
        if user_points.total_points < reward_request.points_cost:
            return JsonResponse({
                'success': False,
                'message': f'Insufficient points. Required: {reward_request.points_cost}, Available: {user_points.total_points}'
            }, status=400)
        
        # NOW deduct points and inventory
        user_points.total_points -= reward_request.points_cost
        user_points.save()
        
        reward_item.quantity -= 1
        reward_item.save()
        
        # Update request status to claimed
        reward_request.status = 'claimed'
        reward_request.save()
        
        # Create reward history entry (this is what appears in reward history)
        # Use approved_by if available, otherwise use the admin who approved (or system)
        reward_history = RewardHistory.objects.create(
            user=reward_user,
            reward_name=reward_item.name,
            reward_type=reward_item.type,
            reward_value=reward_item.value,
            points_deducted=reward_request.points_cost,
            given_by=reward_request.approved_by if reward_request.approved_by else user  # Admin who approved/released
        )
        
        logger.info(f"Reward history entry created: {reward_history.history_id} for user {reward_user.full_name} - {reward_item.name}")
        
        # Create notification for the reward user (not the admin)
        notification_message = f'Congratulations! '
        if is_admin and is_merchandise:
            notification_message += f'Your merchandise "{reward_item.name}" has been released by admin. '
        else:
            notification_message += f'You have successfully claimed "{reward_item.name}". '
        notification_message += f'{reward_request.points_cost} points have been deducted from your account. '
        if reward_request.voucher_code:
            notification_message += f'Voucher code: {reward_request.voucher_code}. '
        if reward_request.notes:
            notification_message += reward_request.notes
        # Add reward request ID for direct navigation to reward details
        notification_message += f'<!--REQUEST_ID:{request_id}-->'
        
        notification = Notification.objects.create(
            user=reward_user,
            notif_type='Reward',
            subject=f'🎉 Reward {"Released" if (is_admin and is_merchandise) else "Claimed"} Successfully!',
            notifi_content=notification_message,
            notif_date=timezone.now(),
            is_read=False
        )
        
        # Broadcast notification
        try:
            from apps.messaging.notification_broadcaster import broadcast_notification
            broadcast_notification(notification)
        except Exception as e:
            logger.error(f"Error broadcasting notification: {e}")
        
        if is_admin and is_merchandise:
            logger.info(f"Admin {user.full_name} released merchandise reward request {request_id} for user {reward_user.full_name}")
        else:
            logger.info(f"User {user.full_name} claimed reward request {request_id}")
        
        return JsonResponse({
            'success': True,
            'message': f'Reward "{reward_item.name}" {"released" if (is_admin and is_merchandise) else "claimed"} successfully!',
            'points_deducted': reward_request.points_cost,
            'remaining_points': user_points.total_points,
            'voucher_code': reward_request.voucher_code if reward_request.voucher_code else None
        })
    
    except Exception as e:
        logger.error(f"claim_reward_request_view error: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=500)


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def upload_voucher_file_view(request, request_id):
    """
    Admin uploads voucher file for a reward request
    """
    try:
        # Check if user is admin
        admin_user = request.user
        if not hasattr(admin_user, 'account_type') or not admin_user.account_type.admin:
            return JsonResponse({
                'success': False,
                'message': 'Admin access required'
            }, status=403)
        
        # Get reward request
        try:
            reward_request = RewardRequest.objects.get(request_id=request_id)
        except RewardRequest.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Reward request not found'
            }, status=404)
        
        # Check if file is provided
        if 'voucher_file' not in request.FILES:
            return JsonResponse({
                'success': False,
                'message': 'Voucher file is required'
            }, status=400)
        
        voucher_file = request.FILES['voucher_file']
        
        # Save voucher file
        reward_request.voucher_file = voucher_file
        reward_request.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Voucher file uploaded successfully',
            'voucher_file_url': reward_request.voucher_file.url
        })
    
    except Exception as e:
        logger.error(f"upload_voucher_file_view error: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=500)