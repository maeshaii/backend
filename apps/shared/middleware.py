"""
Advanced middleware for performance monitoring, health checks, and system optimization.
Senior Developer: Comprehensive system monitoring and performance tracking.
"""
import time
import logging
import json
from django.http import JsonResponse
from django.core.cache import cache
from django.db import connection
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
import psutil
import os


logger = logging.getLogger('apps.shared.middleware')


class PerformanceMonitoringMiddleware(MiddlewareMixin):
    """
    SENIOR DEV: Advanced performance monitoring middleware.
    Tracks response times, database queries, memory usage, and system health.
    """
    
    def process_request(self, request):
        """Start performance tracking for each request"""
        request._start_time = time.time()
        request._start_queries = len(connection.queries)
        request._start_memory = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024  # MB
        
        # Track API endpoints
        if request.path.startswith('/api/'):
            request._is_api_request = True
            self._log_api_request_start(request)
        else:
            request._is_api_request = False
    
    def process_response(self, request, response):
        """End performance tracking and log metrics"""
        if hasattr(request, '_start_time'):
            # Calculate metrics
            response_time = time.time() - request._start_time
            query_count = len(connection.queries) - request._start_queries
            memory_used = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024 - request._start_memory
            
            # Add performance headers
            response['X-Response-Time'] = f"{response_time:.3f}s"
            response['X-Query-Count'] = str(query_count)
            response['X-Memory-Used'] = f"{memory_used:.2f}MB"
            
            # Log performance metrics
            self._log_performance_metrics(request, response, response_time, query_count, memory_used)
            
            # Cache performance data for dashboard
            self._cache_performance_data(request, response_time, query_count, memory_used)
        
        return response
    
    def _log_api_request_start(self, request):
        """Log API request start for monitoring"""
        logger.info(f"API Request: {request.method} {request.path} - User: {getattr(request.user, 'user_id', 'Anonymous')}")
    
    def _log_performance_metrics(self, request, response, response_time, query_count, memory_used):
        """Log detailed performance metrics"""
        # Log slow requests
        if response_time > 2.0:  # 2 seconds threshold
            logger.warning(f"SLOW REQUEST: {request.method} {request.path} - {response_time:.3f}s - {query_count} queries")
        
        # Log high query count
        if query_count > 10:
            logger.warning(f"HIGH QUERY COUNT: {request.method} {request.path} - {query_count} queries")
        
        # Log memory spikes
        if memory_used > 50:  # 50MB threshold
            logger.warning(f"HIGH MEMORY USAGE: {request.method} {request.path} - {memory_used:.2f}MB")
        
        # Log API performance
        if request._is_api_request:
            logger.info(f"API Performance: {request.path} - {response_time:.3f}s - {query_count} queries - {memory_used:.2f}MB")
    
    def _cache_performance_data(self, request, response_time, query_count, memory_used):
        """Cache performance data for real-time dashboard"""
        try:
            # Get current performance data
            perf_data = cache.get('system_performance', {
                'requests': [],
                'avg_response_time': 0,
                'total_requests': 0,
                'slow_requests': 0,
                'high_query_requests': 0
            })
            
            # Add current request data
            request_data = {
                'timestamp': time.time(),
                'method': request.method,
                'path': request.path,
                'response_time': response_time,
                'query_count': query_count,
                'memory_used': memory_used,
                'status_code': getattr(request, '_response_status', 200)
            }
            
            perf_data['requests'].append(request_data)
            
            # Keep only last 100 requests
            if len(perf_data['requests']) > 100:
                perf_data['requests'] = perf_data['requests'][-100:]
            
            # Update statistics
            perf_data['total_requests'] += 1
            if response_time > 2.0:
                perf_data['slow_requests'] += 1
            if query_count > 10:
                perf_data['high_query_requests'] += 1
            
            # Calculate average response time
            recent_requests = perf_data['requests'][-50:]  # Last 50 requests
            if recent_requests:
                perf_data['avg_response_time'] = sum(r['response_time'] for r in recent_requests) / len(recent_requests)
            
            # Cache for 5 minutes
            cache.set('system_performance', perf_data, 300)
            
        except Exception as e:
            logger.error(f"Failed to cache performance data: {e}")


class HealthCheckMiddleware(MiddlewareMixin):
    """
    SENIOR DEV: System health check middleware.
    Provides real-time system health monitoring and alerts.
    """
    
    def process_request(self, request):
        """Handle health check requests"""
        if request.path == '/health/':
            return self._health_check_response(request)
        elif request.path == '/health/detailed/':
            return self._detailed_health_check(request)
    
    def _health_check_response(self, request):
        """Basic health check response"""
        try:
            # Check database connection
            from django.db import connection
            connection.ensure_connection()
            db_status = 'healthy'
        except Exception:
            db_status = 'unhealthy'
        
        # Check cache
        try:
            cache.set('health_check', 'ok', 10)
            cache_status = 'healthy' if cache.get('health_check') == 'ok' else 'unhealthy'
        except Exception:
            cache_status = 'unhealthy'
        
        # Check system resources
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory_percent = psutil.virtual_memory().percent
        disk_percent = psutil.disk_usage('/').percent
        
        # Determine overall health
        overall_health = 'healthy'
        if db_status != 'healthy' or cache_status != 'healthy':
            overall_health = 'unhealthy'
        elif cpu_percent > 80 or memory_percent > 85 or disk_percent > 90:
            overall_health = 'warning'
        
        return JsonResponse({
            'status': overall_health,
            'timestamp': time.time(),
            'services': {
                'database': db_status,
                'cache': cache_status
            },
            'resources': {
                'cpu_percent': cpu_percent,
                'memory_percent': memory_percent,
                'disk_percent': disk_percent
            }
        })
    
    def _detailed_health_check(self, request):
        """Detailed health check with comprehensive metrics"""
        try:
            # System metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Database metrics
            from django.db import connection
            db_queries = len(connection.queries)
            
            # Cache metrics
            cache_stats = cache.get('system_performance', {})
            
            # Job alignment metrics
            from apps.shared.models import EmploymentHistory
            total_employment = EmploymentHistory.objects.count()
            aligned_jobs = EmploymentHistory.objects.filter(job_alignment_status='aligned').count()
            alignment_rate = (aligned_jobs / total_employment * 100) if total_employment > 0 else 0
            
            return JsonResponse({
                'status': 'healthy',
                'timestamp': time.time(),
                'system': {
                    'cpu_percent': cpu_percent,
                    'memory': {
                        'total_gb': round(memory.total / 1024 / 1024 / 1024, 2),
                        'used_gb': round(memory.used / 1024 / 1024 / 1024, 2),
                        'percent': memory.percent
                    },
                    'disk': {
                        'total_gb': round(disk.total / 1024 / 1024 / 1024, 2),
                        'used_gb': round(disk.used / 1024 / 1024 / 1024, 2),
                        'percent': round(disk.used / disk.total * 100, 2)
                    }
                },
                'database': {
                    'queries_executed': db_queries,
                    'connection_status': 'healthy'
                },
                'performance': {
                    'avg_response_time': cache_stats.get('avg_response_time', 0),
                    'total_requests': cache_stats.get('total_requests', 0),
                    'slow_requests': cache_stats.get('slow_requests', 0)
                },
                'business_metrics': {
                    'total_employment_records': total_employment,
                    'aligned_jobs': aligned_jobs,
                    'alignment_rate_percent': round(alignment_rate, 2)
                }
            })
            
        except Exception as e:
            logger.error(f"Detailed health check failed: {e}")
            return JsonResponse({
                'status': 'error',
                'error': str(e),
                'timestamp': time.time()
            }, status=500)


class SecurityEnhancementMiddleware(MiddlewareMixin):
    """
    SENIOR DEV: Security enhancement middleware.
    Implements rate limiting, security headers, and request validation.
    """
    
    def process_request(self, request):
        """Apply security enhancements to requests"""
        # Rate limiting for API endpoints
        if request.path.startswith('/api/'):
            self._apply_rate_limiting(request)
        
        # Security headers
        self._add_security_headers(request)
    
    def process_response(self, request, response):
        """Add security headers to responses"""
        # Security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Remove server information
        if 'Server' in response:
            del response['Server']
        
        return response
    
    def _apply_rate_limiting(self, request):
        """Apply rate limiting to API requests"""
        try:
            # Get client IP
            client_ip = self._get_client_ip(request)
            
            # Create rate limit key
            rate_limit_key = f"rate_limit:{client_ip}"
            
            # Get current request count
            current_requests = cache.get(rate_limit_key, 0)
            
            # Check rate limit (100 requests per minute)
            if current_requests >= 100:
                logger.warning(f"Rate limit exceeded for IP: {client_ip}")
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'message': 'Too many requests. Please try again later.'
                }, status=429)
            
            # Increment request count
            cache.set(rate_limit_key, current_requests + 1, 60)  # 1 minute TTL
            
        except Exception as e:
            logger.error(f"Rate limiting failed: {e}")
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _add_security_headers(self, request):
        """Add security headers to request context"""
        request._security_headers_added = True


