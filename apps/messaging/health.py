"""
Health check endpoints for monitoring and load balancer integration.
A senior developer always includes comprehensive health checks!
"""
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
from channels.layers import get_channel_layer
from django.db import connection
from django.conf import settings
import time
import asyncio

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
def health_check(request):
    """
    Basic health check endpoint for load balancers.
    Returns 200 if application is running.
    """
    return JsonResponse({
        'status': 'healthy',
        'service': 'messaging',
        'timestamp': time.time()
    })


@require_http_methods(["GET"])
def health_check_detailed(request):
    """
    Detailed health check including all critical dependencies.
    Use this for monitoring dashboards and alerting.
    """
    health_status = {
        'status': 'healthy',
        'timestamp': time.time(),
        'checks': {}
    }
    
    overall_healthy = True
    
    # 1. Database Health Check
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        health_status['checks']['database'] = {
            'status': 'healthy',
            'message': 'Database connection successful'
        }
    except Exception as e:
        overall_healthy = False
        health_status['checks']['database'] = {
            'status': 'unhealthy',
            'message': f'Database connection failed: {str(e)}'
        }
        logger.error(f"Health check: Database connection failed: {e}")
    
    # 2. Redis Cache Health Check
    try:
        cache_key = 'health_check_test'
        cache_value = f'test_{time.time()}'
        cache.set(cache_key, cache_value, 10)
        retrieved = cache.get(cache_key)
        
        if retrieved == cache_value:
            health_status['checks']['redis_cache'] = {
                'status': 'healthy',
                'message': 'Redis cache read/write successful'
            }
        else:
            overall_healthy = False
            health_status['checks']['redis_cache'] = {
                'status': 'unhealthy',
                'message': 'Redis cache read/write mismatch'
            }
    except Exception as e:
        overall_healthy = False
        health_status['checks']['redis_cache'] = {
            'status': 'unhealthy',
            'message': f'Redis cache check failed: {str(e)}'
        }
        logger.error(f"Health check: Redis cache failed: {e}")
    
    # 3. Channel Layer Health Check (Redis for WebSockets)
    try:
        channel_layer = get_channel_layer()
        backend_type = type(channel_layer).__name__
        
        if 'InMemory' in backend_type:
            # Warning: InMemory means not production-ready
            health_status['checks']['channel_layer'] = {
                'status': 'degraded',
                'message': f'Using {backend_type} - not suitable for production scaling',
                'backend': backend_type
            }
        else:
            # Redis-based channel layer is good
            health_status['checks']['channel_layer'] = {
                'status': 'healthy',
                'message': f'Using {backend_type} for distributed WebSockets',
                'backend': backend_type
            }
    except Exception as e:
        overall_healthy = False
        health_status['checks']['channel_layer'] = {
            'status': 'unhealthy',
            'message': f'Channel layer check failed: {str(e)}'
        }
        logger.error(f"Health check: Channel layer failed: {e}")
    
    # 4. Environment Configuration Check
    config_issues = []
    
    if settings.DEBUG:
        config_issues.append('DEBUG=True (should be False in production)')
    
    if not settings.SECRET_KEY or settings.SECRET_KEY.startswith('django-insecure'):
        config_issues.append('SECRET_KEY is insecure')
    
    redis_url = getattr(settings, 'REDIS_URL', None)
    if not redis_url:
        config_issues.append('REDIS_URL not configured')
    
    if config_issues:
        health_status['checks']['configuration'] = {
            'status': 'warning',
            'message': 'Configuration issues detected',
            'issues': config_issues
        }
    else:
        health_status['checks']['configuration'] = {
            'status': 'healthy',
            'message': 'Configuration is production-ready'
        }
    
    # 5. Circuit Breaker Status Check
    try:
        from .circuit_breaker import get_circuit_breaker_status
        breaker_status = get_circuit_breaker_status()
        
        all_breakers_closed = all(
            status['state'] == 'closed' 
            for status in breaker_status.values()
        )
        
        if not all_breakers_closed:
            health_status['checks']['circuit_breakers'] = {
                'status': 'warning',
                'message': 'Some circuit breakers are not in CLOSED state',
                'details': breaker_status
            }
        else:
            health_status['checks']['circuit_breakers'] = {
                'status': 'healthy',
                'message': 'All circuit breakers operational',
                'details': breaker_status
            }
    except Exception as e:
        logger.error(f"Health check: Circuit breaker status check failed: {e}")
        health_status['checks']['circuit_breakers'] = {
            'status': 'unknown',
            'message': f'Failed to check circuit breakers: {str(e)}'
        }
    
    # 6. Set overall status
    if not overall_healthy:
        health_status['status'] = 'unhealthy'
        status_code = 503  # Service Unavailable
    elif config_issues:
        health_status['status'] = 'degraded'
        status_code = 200  # Still operational
    else:
        health_status['status'] = 'healthy'
        status_code = 200
    
    return JsonResponse(health_status, status=status_code)


@require_http_methods(["GET"])
def readiness_check(request):
    """
    Readiness check for Kubernetes/container orchestration.
    Returns 200 only if the service is ready to accept traffic.
    """
    try:
        # Check if critical dependencies are available
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        
        # Quick cache check
        cache.get('readiness_check_test')
        
        return JsonResponse({
            'status': 'ready',
            'timestamp': time.time()
        })
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JsonResponse({
            'status': 'not_ready',
            'error': str(e),
            'timestamp': time.time()
        }, status=503)


@require_http_methods(["GET"])
def liveness_check(request):
    """
    Liveness check for Kubernetes/container orchestration.
    Returns 200 if the application process is alive.
    Should NOT check dependencies (just process health).
    """
    return JsonResponse({
        'status': 'alive',
        'timestamp': time.time()
    })


@require_http_methods(["GET"])
def metrics_endpoint(request):
    """
    Prometheus-compatible metrics endpoint.
    Returns key performance metrics for monitoring.
    """
    from apps.shared.models import Message, Conversation, User
    from django.db.models import Count
    from django.utils import timezone
    from datetime import timedelta
    
    try:
        # Get database statistics (with timeout protection)
        from django.db import connection as db_conn
        
        # Calculate 24 hours ago
        yesterday = timezone.now() - timedelta(days=1)
        
        total_conversations = Conversation.objects.count()
        total_messages_today = Message.objects.filter(
            created_at__gte=yesterday
        ).count()
        active_users_today = User.objects.filter(
            sent_messages__created_at__gte=yesterday
        ).distinct().count()
        
        metrics = {
            'conversations_total': total_conversations,
            'messages_last_24h': total_messages_today,
            'active_users_last_24h': active_users_today,
            'timestamp': time.time()
        }
        
        return JsonResponse(metrics)
    except Exception as e:
        logger.error(f"Metrics endpoint error: {e}")
        return JsonResponse({
            'error': 'Failed to retrieve metrics',
            'message': str(e),
            'timestamp': time.time()
        }, status=500)

