"""
Advanced caching manager with Redis integration and intelligent cache strategies.
Senior Developer: Comprehensive caching system with performance optimization.
"""
import json
import hashlib
import logging
from django.core.cache import cache
from django.conf import settings
from functools import wraps
import time

logger = logging.getLogger('apps.shared.cache_manager')


class AdvancedCacheManager:
    """
    SENIOR DEV: Advanced caching manager with intelligent strategies.
    Provides multi-level caching, cache invalidation, and performance optimization.
    """
    
    def __init__(self):
        self.default_timeout = 300  # 5 minutes
        self.long_timeout = 3600    # 1 hour
        self.short_timeout = 60     # 1 minute
    
    def get_cache_key(self, prefix, *args, **kwargs):
        """Generate consistent cache keys"""
        # Create a hash of the arguments
        key_data = f"{args}:{sorted(kwargs.items())}"
        key_hash = hashlib.md5(key_data.encode()).hexdigest()[:8]
        return f"{prefix}:{key_hash}"
    
    def get_or_set(self, key, callable_func, timeout=None, version=None):
        """Enhanced get_or_set with better error handling"""
        try:
            return cache.get_or_set(key, callable_func, timeout or self.default_timeout, version)
        except Exception as e:
            logger.error(f"Cache get_or_set failed for key {key}: {e}")
            # Fallback to direct execution
            return callable_func()
    
    def set_many(self, data, timeout=None, version=None):
        """Set multiple cache entries efficiently"""
        try:
            cache.set_many(data, timeout or self.default_timeout, version)
        except Exception as e:
            logger.error(f"Cache set_many failed: {e}")
    
    def get_many(self, keys, version=None):
        """Get multiple cache entries efficiently"""
        try:
            return cache.get_many(keys, version)
        except Exception as e:
            logger.error(f"Cache get_many failed: {e}")
            return {}
    
    def delete_pattern(self, pattern):
        """Delete cache entries matching a pattern (Redis-specific)"""
        try:
            # This works with Redis backend
            if hasattr(cache, 'delete_pattern'):
                cache.delete_pattern(pattern)
            else:
                # Fallback for other backends
                logger.warning("delete_pattern not supported by current cache backend")
        except Exception as e:
            logger.error(f"Cache delete_pattern failed for pattern {pattern}: {e}")
    
    def invalidate_statistics_cache(self, user_id=None, program=None):
        """Intelligent cache invalidation for statistics"""
        patterns = [
            'stats:*',
            'dashboard:*',
            'analytics:*'
        ]
        
        if user_id:
            patterns.append(f'user:{user_id}:*')
        
        if program:
            patterns.append(f'program:{program}:*')
        
        for pattern in patterns:
            self.delete_pattern(pattern)
        
        logger.info(f"Invalidated statistics cache for user_id={user_id}, program={program}")
    
    def cache_statistics(self, timeout=300):
        """Advanced statistics caching decorator"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key
                cache_key = self.get_cache_key(
                    f"stats:{func.__name__}",
                    *args,
                    **kwargs
                )
                
                # Try to get from cache
                try:
                    cached_result = cache.get(cache_key)
                    if cached_result is not None:
                        logger.debug(f"Cache hit for {cache_key}")
                        return cached_result
                except Exception as e:
                    logger.error(f"Cache get failed for {cache_key}: {e}")
                
                # Execute function and cache result
                try:
                    result = func(*args, **kwargs)
                    cache.set(cache_key, result, timeout)
                    logger.debug(f"Cached result for {cache_key}")
                    return result
                except Exception as e:
                    logger.error(f"Function execution failed for {func.__name__}: {e}")
                    raise
            
            return wrapper
        return decorator
    
    def cache_with_invalidation(self, invalidate_on=None, timeout=300):
        """Cache with automatic invalidation triggers"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                cache_key = self.get_cache_key(
                    f"cache_inv:{func.__name__}",
                    *args,
                    **kwargs
                )
                
                # Check if cache should be invalidated
                if invalidate_on:
                    invalidation_key = f"invalidate:{func.__name__}"
                    if cache.get(invalidation_key):
                        cache.delete(cache_key)
                        cache.delete(invalidation_key)
                        logger.info(f"Cache invalidated for {cache_key}")
                
                # Get or set cache
                return self.get_or_set(cache_key, lambda: func(*args, **kwargs), timeout)
            
            return wrapper
        return decorator
    
    def warm_cache(self, functions_with_args):
        """Warm up cache with frequently accessed data"""
        logger.info("Starting cache warming...")
        
        for func, args, kwargs in functions_with_args:
            try:
                cache_key = self.get_cache_key(
                    f"warm:{func.__name__}",
                    *args,
                    **kwargs
                )
                
                # Execute and cache
                result = func(*args, **kwargs)
                cache.set(cache_key, result, self.long_timeout)
                logger.debug(f"Warmed cache for {cache_key}")
                
            except Exception as e:
                logger.error(f"Cache warming failed for {func.__name__}: {e}")
        
        logger.info("Cache warming completed")
    
    def get_cache_stats(self):
        """Get cache statistics and health"""
        try:
            stats = {
                'backend': cache.__class__.__name__,
                'default_timeout': self.default_timeout,
                'timestamp': time.time()
            }
            
            # Try to get Redis-specific stats
            if hasattr(cache, 'get_stats'):
                redis_stats = cache.get_stats()
                stats.update(redis_stats)
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {'error': str(e)}


# Global cache manager instance
cache_manager = AdvancedCacheManager()


def smart_cache(timeout=300, invalidate_on=None):
    """
    SENIOR DEV: Smart caching decorator with intelligent invalidation.
    Usage: @smart_cache(timeout=600, invalidate_on='user_update')
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return cache_manager.cache_with_invalidation(
                invalidate_on=invalidate_on,
                timeout=timeout
            )(func)(*args, **kwargs)
        return wrapper
    return decorator


def cache_statistics(timeout=300):
    """
    SENIOR DEV: Statistics-specific caching decorator.
    Usage: @cache_statistics(timeout=600)
    """
    return cache_manager.cache_statistics(timeout=timeout)


def invalidate_user_cache(user_id):
    """Invalidate all cache entries for a specific user"""
    cache_manager.invalidate_statistics_cache(user_id=user_id)


def invalidate_program_cache(program):
    """Invalidate all cache entries for a specific program"""
    cache_manager.invalidate_statistics_cache(program=program)


def warm_system_cache():
    """Warm up system cache with frequently accessed data"""
    from apps.shared.models import User, EmploymentHistory
    from apps.alumni_stats.views import alumni_statistics_view
    
    functions_to_warm = [
        # Statistics functions
        (alumni_statistics_view, [], {}),
        
        # Model counts
        (lambda: User.objects.filter(account_type__user=True).count(), [], {}),
        (lambda: EmploymentHistory.objects.count(), [], {}),
    ]
    
    cache_manager.warm_cache(functions_to_warm)


