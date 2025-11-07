"""
Rate limiting for REST API endpoints to prevent spam and abuse.

This module provides rate limiting for social media actions like:
- Likes
- Comments
- Reposts
- Forum interactions
- Donation interactions
"""

import logging
import time
from typing import Dict, Optional, Tuple
from functools import wraps
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone

logger = logging.getLogger(__name__)


class APIRateLimiter:
    """
    Rate limiter for REST API endpoints.
    
    Features:
    - Per-user rate limiting
    - Per-action type rate limiting
    - Sliding window algorithm
    - Configurable limits
    """
    
    # Rate limit configurations (actions per minute)
    DEFAULT_LIKE_RATE = 60  # 60 likes per minute
    DEFAULT_COMMENT_RATE = 30  # 30 comments per minute
    DEFAULT_REPOST_RATE = 20  # 20 reposts per minute
    
    # Cache key prefixes
    LIKE_RATE_PREFIX = "api_rate_like:"
    COMMENT_RATE_PREFIX = "api_rate_comment:"
    REPOST_RATE_PREFIX = "api_rate_repost:"
    
    # TTL values (in seconds)
    RATE_LIMIT_TTL = 60  # 1 minute window
    
    def __init__(self):
        self.like_rate = self.DEFAULT_LIKE_RATE
        self.comment_rate = self.DEFAULT_COMMENT_RATE
        self.repost_rate = self.DEFAULT_REPOST_RATE
    
    def check_rate_limit(self, user_id: int, action_type: str, target_id: Optional[int] = None) -> Tuple[bool, Dict[str, any]]:
        """
        Check if user can perform an action based on rate limits.
        
        Args:
            user_id: User ID
            action_type: Type of action ('like', 'comment', 'repost')
            target_id: Optional target ID (post_id, comment_id, etc.) for per-target limiting
            
        Returns:
            Tuple of (allowed, rate_limit_info)
        """
        try:
            now = time.time()
            
            # Determine rate limit based on action type
            if action_type == 'like':
                rate_limit = self.like_rate
                prefix = self.LIKE_RATE_PREFIX
            elif action_type == 'comment':
                rate_limit = self.comment_rate
                prefix = self.COMMENT_RATE_PREFIX
            elif action_type == 'repost':
                rate_limit = self.repost_rate
                prefix = self.REPOST_RATE_PREFIX
            else:
                # Default rate limit for unknown actions
                rate_limit = 30
                prefix = f"api_rate_{action_type}:"
            
            # Per-user rate limiting
            user_key = f"{prefix}user:{user_id}"
            user_requests = self._get_request_times(user_key, now - self.RATE_LIMIT_TTL)
            
            if len(user_requests) >= rate_limit:
                oldest_request = user_requests[0] if user_requests else now
                retry_after = int(oldest_request + self.RATE_LIMIT_TTL - now)
                if retry_after < 0:
                    retry_after = 1
                
                return False, {
                    'allowed': False,
                    'reason': f'{action_type}_rate_limit_exceeded',
                    'limit': rate_limit,
                    'window': self.RATE_LIMIT_TTL,
                    'retry_after': retry_after,
                    'action': action_type
                }
            
            # Optional: Per-target rate limiting (prevent spam on same post/comment)
            if target_id:
                target_key = f"{prefix}target:{target_id}:user:{user_id}"
                target_requests = self._get_request_times(target_key, now - self.RATE_LIMIT_TTL)
                # More strict limit for same target (e.g., max 5 likes per post per minute)
                target_limit = min(5, rate_limit // 4)
                
                if len(target_requests) >= target_limit:
                    oldest_request = target_requests[0] if target_requests else now
                    retry_after = int(oldest_request + self.RATE_LIMIT_TTL - now)
                    if retry_after < 0:
                        retry_after = 1
                    
                    return False, {
                        'allowed': False,
                        'reason': f'{action_type}_target_rate_limit_exceeded',
                        'limit': target_limit,
                        'window': self.RATE_LIMIT_TTL,
                        'retry_after': retry_after,
                        'action': action_type,
                        'target_id': target_id
                    }
            
            # Record the request
            self._record_request(user_key, now)
            if target_id:
                target_key = f"{prefix}target:{target_id}:user:{user_id}"
                self._record_request(target_key, now)
            
            return True, {
                'allowed': True,
                'limit': rate_limit,
                'remaining': rate_limit - len(user_requests) - 1,
                'action': action_type
            }
            
        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            # On error, allow the request (fail open)
            return True, {'allowed': True, 'error': str(e)}
    
    def _get_request_times(self, key: str, window_start: float) -> list:
        """Get request times within the window."""
        try:
            request_times = cache.get(key, [])
            # Filter out old requests outside the window
            request_times = [t for t in request_times if t >= window_start]
            return request_times
        except Exception as e:
            logger.error(f"Error getting request times: {e}")
            return []
    
    def _record_request(self, key: str, timestamp: float):
        """Record a request timestamp."""
        try:
            request_times = cache.get(key, [])
            request_times.append(timestamp)
            # Keep only requests within the window
            window_start = timestamp - self.RATE_LIMIT_TTL
            request_times = [t for t in request_times if t >= window_start]
            cache.set(key, request_times, self.RATE_LIMIT_TTL + 10)  # Extra 10s buffer
        except Exception as e:
            logger.error(f"Error recording request: {e}")


# Global rate limiter instance
api_rate_limiter = APIRateLimiter()


def rate_limit_action(action_type: str, get_target_id=None):
    """
    Decorator to rate limit API endpoints.
    
    Args:
        action_type: Type of action ('like', 'comment', 'repost')
        get_target_id: Optional function to extract target ID from request/kwargs
    
    Usage:
        @rate_limit_action('like', lambda request, **kwargs: kwargs.get('post_id'))
        def post_like_view(request, post_id):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Skip rate limiting for non-POST requests (GET, DELETE, etc.)
            if request.method not in ['POST', 'PUT']:
                return view_func(request, *args, **kwargs)
            
            # Skip rate limiting for unauthenticated users (they'll be caught by auth)
            if not hasattr(request, 'user') or not request.user or not request.user.is_authenticated:
                return view_func(request, *args, **kwargs)
            
            user_id = request.user.user_id
            
            # Extract target ID if function provided
            target_id = None
            if get_target_id:
                try:
                    target_id = get_target_id(request, *args, **kwargs)
                except Exception as e:
                    logger.warning(f"Error extracting target ID: {e}")
            
            # Check rate limit
            allowed, rate_info = api_rate_limiter.check_rate_limit(user_id, action_type, target_id)
            
            if not allowed:
                logger.warning(f"Rate limit exceeded for user {user_id}, action: {action_type}, reason: {rate_info.get('reason')}")
                return JsonResponse({
                    'success': False,
                    'error': 'Rate limit exceeded',
                    'message': f'Too many {action_type}s. Please slow down and try again in {rate_info.get("retry_after", 1)} seconds.',
                    'retry_after': rate_info.get('retry_after', 1),
                    'limit': rate_info.get('limit'),
                    'action': action_type
                }, status=429)
            
            # Add rate limit headers to response
            response = view_func(request, *args, **kwargs)
            if isinstance(response, JsonResponse):
                response['X-RateLimit-Limit'] = str(rate_info.get('limit', 0))
                response['X-RateLimit-Remaining'] = str(rate_info.get('remaining', 0))
                response['X-RateLimit-Action'] = action_type
            
            return response
        
        return wrapper
    return decorator




