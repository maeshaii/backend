"""
Caching decorators for statistics views
Uses Django's built-in cache framework (local memory by default, Redis-ready)
"""
from functools import wraps
from django.core.cache import cache
import hashlib
import json


def cache_statistics(timeout=300):
    """
    Cache statistics view results for specified timeout (default 5 minutes).
    
    Cache key based on: view name, year, program, type parameters
    Cache invalidation: Automatic after timeout or manual via cache.delete()
    
    Args:
        timeout: Cache duration in seconds (default 300 = 5 minutes)
    
    Usage:
        @cache_statistics(timeout=600)  # 10 minutes
        @api_view(["GET"])
        def my_stats_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Build cache key from request parameters
            year = request.GET.get('year', 'ALL')
            program = request.GET.get('program', 'ALL')
            stats_type = request.GET.get('type', 'ALL')
            status = request.GET.get('status', 'ALL')
            course = request.GET.get('course', 'ALL')
            
            # Create unique cache key
            cache_params = f"{view_func.__name__}:{year}:{program}:{stats_type}:{status}:{course}"
            cache_key = f"stats:{hashlib.md5(cache_params.encode()).hexdigest()}"
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                # Return cached response
                from django.http import JsonResponse
                return JsonResponse(cached_result)
            
            # Not in cache, call the actual view
            response = view_func(request, *args, **kwargs)
            
            # Cache the result if successful
            if response.status_code == 200:
                try:
                    result_data = json.loads(response.content)
                    cache.set(cache_key, result_data, timeout)
                except (json.JSONDecodeError, AttributeError):
                    pass  # Don't cache if response isn't JSON
            
            return response
        
        return wrapper
    return decorator


def invalidate_statistics_cache():
    """
    Invalidate all statistics caches.
    Call this when user data is updated (e.g., after tracker form submission)
    
    Usage:
        from apps.alumni_stats.decorators import invalidate_statistics_cache
        invalidate_statistics_cache()
    """
    # Clear all cache keys starting with 'stats:'
    # Note: This requires cache backend to support pattern deletion
    # For local memory cache, we can't pattern-delete, so we clear all
    try:
        cache.clear()
    except:
        pass  # Silently fail if cache backend doesn't support clearing



