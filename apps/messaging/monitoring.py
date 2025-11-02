"""
Comprehensive monitoring and error tracking system.

This module provides production-grade monitoring, error tracking, and performance
metrics for the messaging system using Sentry and custom metrics.
"""

import logging
import time
import json
from typing import Dict, Any, Optional, List
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

# Sentry integration
try:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False

logger = logging.getLogger(__name__)


class MessagingMonitor:
    """
    Comprehensive monitoring system for messaging functionality.
    
    Features:
    - Error tracking with Sentry
    - Performance metrics collection
    - WebSocket connection monitoring
    - Message delivery tracking
    - Custom business metrics
    """
    
    def __init__(self):
        self.sentry_enabled = SENTRY_AVAILABLE and getattr(settings, 'SENTRY_DSN', None)
        self.metrics_cache_prefix = "messaging_metrics:"
        self.metrics_ttl = 3600  # 1 hour
        
        if self.sentry_enabled:
            self._initialize_sentry()
    
    def _initialize_sentry(self):
        """Initialize Sentry SDK with proper configuration."""
        try:
            sentry_sdk.init(
                dsn=getattr(settings, 'SENTRY_DSN', None),
                integrations=[
                    DjangoIntegration(
                        transaction_style='url',
                        middleware_spans=True,
                        signals_spans=True,
                    ),
                    RedisIntegration(),
                    LoggingIntegration(
                        level=logging.INFO,
                        event_level=logging.ERROR
                    ),
                ],
                traces_sample_rate=getattr(settings, 'SENTRY_TRACES_SAMPLE_RATE', 0.1),
                profiles_sample_rate=getattr(settings, 'SENTRY_PROFILES_SAMPLE_RATE', 0.1),
                environment=getattr(settings, 'SENTRY_ENVIRONMENT', 'development'),
                release=getattr(settings, 'SENTRY_RELEASE', None),
                before_send=self._before_send_filter,
            )
            
            logger.info("Sentry monitoring initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Sentry: {e}")
            self.sentry_enabled = False
    
    def _before_send_filter(self, event, hint):
        """Filter events before sending to Sentry."""
        try:
            # Filter out sensitive information
            if 'request' in event and 'data' in event['request']:
                sensitive_fields = ['password', 'token', 'secret', 'key']
                for field in sensitive_fields:
                    if field in event['request']['data']:
                        event['request']['data'][field] = '[FILTERED]'
            
            # Add custom tags
            event['tags'] = event.get('tags', {})
            event['tags']['component'] = 'messaging'
            
            return event
            
        except Exception as e:
            logger.error(f"Error in Sentry before_send filter: {e}")
            return event
    
    def track_error(self, error: Exception, context: Optional[Dict[str, Any]] = None, 
                   level: str = 'error', user_id: Optional[int] = None):
        """
        Track an error with Sentry and custom logging.
        
        Args:
            error: The exception that occurred
            context: Additional context information
            level: Error level (error, warning, info)
            user_id: User ID for user context
        """
        try:
            # Log the error
            log_level = getattr(logging, level.upper(), logging.ERROR)
            logger.log(log_level, f"Messaging error: {str(error)}", exc_info=True, extra=context)
            
            # Send to Sentry if enabled
            if self.sentry_enabled:
                with sentry_sdk.push_scope() as scope:
                    # Add user context
                    if user_id:
                        scope.user = {'id': user_id}
                    
                    # Add custom context
                    if context:
                        for key, value in context.items():
                            scope.set_extra(key, value)
                    
                    # Add component tag
                    scope.set_tag('component', 'messaging')
                    
                    # Capture the exception
                    sentry_sdk.capture_exception(error)
            
            # Update error metrics
            self._update_error_metrics(level, context)
            
        except Exception as e:
            logger.error(f"Failed to track error: {e}")
    
    def track_performance(self, operation: str, duration: float, 
                         context: Optional[Dict[str, Any]] = None):
        """
        Track performance metrics for operations.
        
        Args:
            operation: Name of the operation
            duration: Duration in seconds
            context: Additional context information
        """
        try:
            # Log performance metric
            logger.info(f"Performance: {operation} took {duration:.3f}s", extra=context)
            
            # Send to Sentry if enabled
            if self.sentry_enabled:
                with sentry_sdk.push_scope() as scope:
                    scope.set_tag('operation', operation)
                    scope.set_tag('component', 'messaging')
                    
                    if context:
                        for key, value in context.items():
                            scope.set_extra(key, value)
                    
                    # Add performance data
                    scope.set_measurement(f"{operation}_duration", duration)
                    
                    # Send as transaction
                    sentry_sdk.capture_message(
                        f"Performance: {operation}",
                        level='info'
                    )
            
            # Update performance metrics
            self._update_performance_metrics(operation, duration, context)
            
        except Exception as e:
            logger.error(f"Failed to track performance: {e}")
    
    def track_websocket_event(self, event_type: str, user_id: Optional[int] = None,
                            conversation_id: Optional[int] = None,
                            context: Optional[Dict[str, Any]] = None):
        """
        Track WebSocket events and connections.
        
        Args:
            event_type: Type of WebSocket event
            user_id: User ID
            conversation_id: Conversation ID
            context: Additional context
        """
        try:
            # Log WebSocket event
            logger.info(f"WebSocket event: {event_type}", extra={
                'user_id': user_id,
                'conversation_id': conversation_id,
                **(context or {})
            })
            
            # Send to Sentry if enabled
            if self.sentry_enabled:
                with sentry_sdk.push_scope() as scope:
                    scope.set_tag('event_type', event_type)
                    scope.set_tag('component', 'websocket')
                    
                    if user_id:
                        scope.user = {'id': user_id}
                    
                    if conversation_id:
                        scope.set_extra('conversation_id', conversation_id)
                    
                    if context:
                        for key, value in context.items():
                            scope.set_extra(key, value)
                    
                    sentry_sdk.capture_message(
                        f"WebSocket: {event_type}",
                        level='info'
                    )
            
            # Update WebSocket metrics
            self._update_websocket_metrics(event_type, user_id, conversation_id)
            
        except Exception as e:
            logger.error(f"Failed to track WebSocket event: {e}")
    
    def track_message_delivery(self, message_id: int, delivery_status: str,
                             user_id: Optional[int] = None,
                             conversation_id: Optional[int] = None,
                             context: Optional[Dict[str, Any]] = None):
        """
        Track message delivery status and performance.
        
        Args:
            message_id: Message ID
            delivery_status: Status (sent, delivered, failed, etc.)
            user_id: User ID
            conversation_id: Conversation ID
            context: Additional context
        """
        try:
            # Log message delivery
            logger.info(f"Message delivery: {message_id} - {delivery_status}", extra={
                'message_id': message_id,
                'user_id': user_id,
                'conversation_id': conversation_id,
                **(context or {})
            })
            
            # Send to Sentry if enabled
            if self.sentry_enabled:
                with sentry_sdk.push_scope() as scope:
                    scope.set_tag('message_id', message_id)
                    scope.set_tag('delivery_status', delivery_status)
                    scope.set_tag('component', 'message_delivery')
                    
                    if user_id:
                        scope.user = {'id': user_id}
                    
                    if conversation_id:
                        scope.set_extra('conversation_id', conversation_id)
                    
                    if context:
                        for key, value in context.items():
                            scope.set_extra(key, value)
                    
                    # Set appropriate level based on status
                    level = 'error' if delivery_status == 'failed' else 'info'
                    sentry_sdk.capture_message(
                        f"Message delivery: {delivery_status}",
                        level=level
                    )
            
            # Update message delivery metrics
            self._update_message_delivery_metrics(message_id, delivery_status, user_id, conversation_id)
            
        except Exception as e:
            logger.error(f"Failed to track message delivery: {e}")
    
    def track_business_metric(self, metric_name: str, value: float,
                            tags: Optional[Dict[str, str]] = None,
                            context: Optional[Dict[str, Any]] = None):
        """
        Track custom business metrics.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            tags: Metric tags
            context: Additional context
        """
        try:
            # Log business metric
            logger.info(f"Business metric: {metric_name} = {value}", extra={
                'metric_name': metric_name,
                'metric_value': value,
                'tags': tags,
                **(context or {})
            })
            
            # Send to Sentry if enabled
            if self.sentry_enabled:
                with sentry_sdk.push_scope() as scope:
                    scope.set_tag('metric_name', metric_name)
                    scope.set_tag('component', 'business_metrics')
                    
                    if tags:
                        for key, value in tags.items():
                            scope.set_tag(key, value)
                    
                    if context:
                        for key, value in context.items():
                            scope.set_extra(key, value)
                    
                    # Add measurement
                    scope.set_measurement(metric_name, value)
                    
                    sentry_sdk.capture_message(
                        f"Business metric: {metric_name}",
                        level='info'
                    )
            
            # Update business metrics
            self._update_business_metrics(metric_name, value, tags)
            
        except Exception as e:
            logger.error(f"Failed to track business metric: {e}")
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all collected metrics.
        
        Returns:
            Dictionary with metrics summary
        """
        try:
            summary = {
                'timestamp': timezone.now().isoformat(),
                'sentry_enabled': self.sentry_enabled,
                'error_metrics': self._get_error_metrics(),
                'performance_metrics': self._get_performance_metrics(),
                'websocket_metrics': self._get_websocket_metrics(),
                'message_delivery_metrics': self._get_message_delivery_metrics(),
                'business_metrics': self._get_business_metrics(),
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to get metrics summary: {e}")
            return {'error': str(e)}
    
    def _update_error_metrics(self, level: str, context: Optional[Dict[str, Any]]):
        """Update error metrics in cache."""
        try:
            key = f"{self.metrics_cache_prefix}errors:{level}"
            current_count = cache.get(key, 0)
            cache.set(key, current_count + 1, timeout=self.metrics_ttl)
            
            # Update total errors
            total_key = f"{self.metrics_cache_prefix}errors:total"
            total_count = cache.get(total_key, 0)
            cache.set(total_key, total_count + 1, timeout=self.metrics_ttl)
            
        except Exception as e:
            logger.error(f"Failed to update error metrics: {e}")
    
    def _update_performance_metrics(self, operation: str, duration: float, 
                                  context: Optional[Dict[str, Any]]):
        """Update performance metrics in cache."""
        try:
            # Update operation count
            count_key = f"{self.metrics_cache_prefix}perf:{operation}:count"
            current_count = cache.get(count_key, 0)
            cache.set(count_key, current_count + 1, timeout=self.metrics_ttl)
            
            # Update total duration
            duration_key = f"{self.metrics_cache_prefix}perf:{operation}:duration"
            current_duration = cache.get(duration_key, 0)
            cache.set(duration_key, current_duration + duration, timeout=self.metrics_ttl)
            
            # Update average duration
            avg_key = f"{self.metrics_cache_prefix}perf:{operation}:avg"
            avg_duration = (current_duration + duration) / (current_count + 1)
            cache.set(avg_key, avg_duration, timeout=self.metrics_ttl)
            
        except Exception as e:
            logger.error(f"Failed to update performance metrics: {e}")
    
    def _update_websocket_metrics(self, event_type: str, user_id: Optional[int],
                                conversation_id: Optional[int]):
        """Update WebSocket metrics in cache."""
        try:
            # Update event count
            event_key = f"{self.metrics_cache_prefix}ws:{event_type}:count"
            current_count = cache.get(event_key, 0)
            cache.set(event_key, current_count + 1, timeout=self.metrics_ttl)
            
            # Update active connections
            if event_type == 'connected':
                conn_key = f"{self.metrics_cache_prefix}ws:active_connections"
                current_conn = cache.get(conn_key, 0)
                cache.set(conn_key, current_conn + 1, timeout=self.metrics_ttl)
            elif event_type == 'disconnected':
                conn_key = f"{self.metrics_cache_prefix}ws:active_connections"
                current_conn = cache.get(conn_key, 0)
                cache.set(conn_key, max(0, current_conn - 1), timeout=self.metrics_ttl)
            
        except Exception as e:
            logger.error(f"Failed to update WebSocket metrics: {e}")
    
    def _update_message_delivery_metrics(self, message_id: int, status: str,
                                       user_id: Optional[int], conversation_id: Optional[int]):
        """Update message delivery metrics in cache."""
        try:
            # Update status count
            status_key = f"{self.metrics_cache_prefix}msg:{status}:count"
            current_count = cache.get(status_key, 0)
            cache.set(status_key, current_count + 1, timeout=self.metrics_ttl)
            
            # Update total messages
            total_key = f"{self.metrics_cache_prefix}msg:total"
            total_count = cache.get(total_key, 0)
            cache.set(total_key, total_count + 1, timeout=self.metrics_ttl)
            
        except Exception as e:
            logger.error(f"Failed to update message delivery metrics: {e}")
    
    def _update_business_metrics(self, metric_name: str, value: float,
                               tags: Optional[Dict[str, str]]):
        """Update business metrics in cache."""
        try:
            # Update metric value
            metric_key = f"{self.metrics_cache_prefix}business:{metric_name}"
            current_value = cache.get(metric_key, 0)
            cache.set(metric_key, current_value + value, timeout=self.metrics_ttl)
            
        except Exception as e:
            logger.error(f"Failed to update business metrics: {e}")
    
    def _get_error_metrics(self) -> Dict[str, Any]:
        """Get error metrics from cache."""
        try:
            return {
                'total_errors': cache.get(f"{self.metrics_cache_prefix}errors:total", 0),
                'error_levels': {
                    'error': cache.get(f"{self.metrics_cache_prefix}errors:error", 0),
                    'warning': cache.get(f"{self.metrics_cache_prefix}errors:warning", 0),
                    'info': cache.get(f"{self.metrics_cache_prefix}errors:info", 0),
                }
            }
        except Exception as e:
            logger.error(f"Failed to get error metrics: {e}")
            return {}
    
    def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics from cache."""
        try:
            # This is a simplified version - in production you might want to
            # scan all performance keys and aggregate them
            return {
                'message_send_avg': cache.get(f"{self.metrics_cache_prefix}perf:message_send:avg", 0),
                'websocket_connect_avg': cache.get(f"{self.metrics_cache_prefix}perf:websocket_connect:avg", 0),
            }
        except Exception as e:
            logger.error(f"Failed to get performance metrics: {e}")
            return {}
    
    def _get_websocket_metrics(self) -> Dict[str, Any]:
        """Get WebSocket metrics from cache."""
        try:
            return {
                'active_connections': cache.get(f"{self.metrics_cache_prefix}ws:active_connections", 0),
                'connection_events': {
                    'connected': cache.get(f"{self.metrics_cache_prefix}ws:connected:count", 0),
                    'disconnected': cache.get(f"{self.metrics_cache_prefix}ws:disconnected:count", 0),
                }
            }
        except Exception as e:
            logger.error(f"Failed to get WebSocket metrics: {e}")
            return {}
    
    def _get_message_delivery_metrics(self) -> Dict[str, Any]:
        """Get message delivery metrics from cache."""
        try:
            return {
                'total_messages': cache.get(f"{self.metrics_cache_prefix}msg:total", 0),
                'delivery_status': {
                    'sent': cache.get(f"{self.metrics_cache_prefix}msg:sent:count", 0),
                    'delivered': cache.get(f"{self.metrics_cache_prefix}msg:delivered:count", 0),
                    'failed': cache.get(f"{self.metrics_cache_prefix}msg:failed:count", 0),
                }
            }
        except Exception as e:
            logger.error(f"Failed to get message delivery metrics: {e}")
            return {}
    
    def _get_business_metrics(self) -> Dict[str, Any]:
        """Get business metrics from cache."""
        try:
            # This is a simplified version - in production you might want to
            # scan all business metric keys and return them
            return {
                'active_conversations': cache.get(f"{self.metrics_cache_prefix}business:active_conversations", 0),
                'messages_per_hour': cache.get(f"{self.metrics_cache_prefix}business:messages_per_hour", 0),
            }
        except Exception as e:
            logger.error(f"Failed to get business metrics: {e}")
            return {}


# Global monitoring instance
messaging_monitor = MessagingMonitor()


# Decorator for automatic performance tracking
def track_performance(operation_name: str):
    """Decorator to automatically track performance of functions."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                messaging_monitor.track_performance(
                    operation_name,
                    duration,
                    {'function': func.__name__}
                )
                return result
            except Exception as e:
                duration = time.time() - start_time
                messaging_monitor.track_error(
                    e,
                    {'operation': operation_name, 'duration': duration},
                    'error'
                )
                raise
        return wrapper
    return decorator


# Context manager for performance tracking
class PerformanceTracker:
    """Context manager for tracking performance of code blocks."""
    
    def __init__(self, operation_name: str, context: Optional[Dict[str, Any]] = None):
        self.operation_name = operation_name
        self.context = context or {}
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            
            if exc_type:
                messaging_monitor.track_error(
                    exc_val,
                    {'operation': self.operation_name, 'duration': duration, **self.context},
                    'error'
                )
            else:
                messaging_monitor.track_performance(
                    self.operation_name,
                    duration,
                    self.context
                )







































