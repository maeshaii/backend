"""
Advanced performance metrics collection for messaging system.

This module provides detailed performance metrics for message delivery,
WebSocket connections, and system performance with real-time monitoring.
"""

import time
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.cache import cache
from collections import defaultdict, deque
import json

logger = logging.getLogger(__name__)


class PerformanceMetricsCollector:
    """
    Advanced performance metrics collector for messaging system.
    
    Features:
    - Real-time performance tracking
    - Message delivery latency metrics
    - WebSocket connection performance
    - System resource utilization
    - Performance trend analysis
    - Alerting and threshold monitoring
    """
    
    def __init__(self):
        self.metrics_cache_prefix = "perf_metrics:"
        self.metrics_ttl = 7200  # 2 hours
        self.alert_thresholds = {
            'message_delivery_latency': 1000,  # 1 second
            'websocket_connection_time': 5000,  # 5 seconds
            'database_query_time': 100,  # 100ms
            'cache_hit_ratio': 0.8,  # 80%
            'error_rate': 0.05,  # 5%
        }
    
    def track_message_delivery_performance(self, message_id: int, 
                                         delivery_stages: Dict[str, float],
                                         user_id: Optional[int] = None,
                                         conversation_id: Optional[int] = None):
        """
        Track detailed message delivery performance across all stages.
        
        Args:
            message_id: Message ID
            delivery_stages: Dictionary of stage names to timestamps
            user_id: User ID
            conversation_id: Conversation ID
        """
        try:
            # Calculate stage durations
            stages = sorted(delivery_stages.items(), key=lambda x: x[1])
            stage_durations = {}
            
            for i, (stage, timestamp) in enumerate(stages):
                if i > 0:
                    prev_stage, prev_timestamp = stages[i-1]
                    stage_durations[f"{prev_stage}_to_{stage}"] = timestamp - prev_timestamp
                stage_durations[f"{stage}_duration"] = timestamp - stages[0][1]
            
            # Calculate total delivery time
            total_delivery_time = stages[-1][1] - stages[0][1] if len(stages) > 1 else 0
            
            # Store detailed metrics
            metrics_data = {
                'message_id': message_id,
                'user_id': user_id,
                'conversation_id': conversation_id,
                'total_delivery_time': total_delivery_time,
                'stage_durations': stage_durations,
                'delivery_stages': delivery_stages,
                'timestamp': timezone.now().isoformat(),
            }
            
            # Cache metrics
            cache_key = f"{self.metrics_cache_prefix}message_delivery:{message_id}"
            cache.set(cache_key, json.dumps(metrics_data), timeout=self.metrics_ttl)
            
            # Update aggregated metrics
            self._update_message_delivery_aggregates(total_delivery_time, stage_durations)
            
            # Check for performance alerts
            self._check_message_delivery_alerts(total_delivery_time, stage_durations)
            
            logger.debug(f"Tracked message delivery performance for {message_id}: {total_delivery_time:.3f}ms")
            
        except Exception as e:
            logger.error(f"Failed to track message delivery performance: {e}")
    
    def track_websocket_connection_performance(self, connection_id: str,
                                             connection_stages: Dict[str, float],
                                             user_id: Optional[int] = None):
        """
        Track WebSocket connection performance across all stages.
        
        Args:
            connection_id: Unique connection identifier
            connection_stages: Dictionary of stage names to timestamps
            user_id: User ID
        """
        try:
            # Calculate stage durations
            stages = sorted(connection_stages.items(), key=lambda x: x[1])
            stage_durations = {}
            
            for i, (stage, timestamp) in enumerate(stages):
                if i > 0:
                    prev_stage, prev_timestamp = stages[i-1]
                    stage_durations[f"{prev_stage}_to_{stage}"] = timestamp - prev_timestamp
                stage_durations[f"{stage}_duration"] = timestamp - stages[0][1]
            
            # Calculate total connection time
            total_connection_time = stages[-1][1] - stages[0][1] if len(stages) > 1 else 0
            
            # Store detailed metrics
            metrics_data = {
                'connection_id': connection_id,
                'user_id': user_id,
                'total_connection_time': total_connection_time,
                'stage_durations': stage_durations,
                'connection_stages': connection_stages,
                'timestamp': timezone.now().isoformat(),
            }
            
            # Cache metrics
            cache_key = f"{self.metrics_cache_prefix}websocket_connection:{connection_id}"
            cache.set(cache_key, json.dumps(metrics_data), timeout=self.metrics_ttl)
            
            # Update aggregated metrics
            self._update_websocket_connection_aggregates(total_connection_time, stage_durations)
            
            # Check for performance alerts
            self._check_websocket_connection_alerts(total_connection_time, stage_durations)
            
            logger.debug(f"Tracked WebSocket connection performance for {connection_id}: {total_connection_time:.3f}ms")
            
        except Exception as e:
            logger.error(f"Failed to track WebSocket connection performance: {e}")
    
    def track_database_performance(self, operation: str, duration: float,
                                 query_count: int = 1, cache_hit: bool = False):
        """
        Track database operation performance.
        
        Args:
            operation: Database operation name
            duration: Operation duration in milliseconds
            query_count: Number of queries executed
            cache_hit: Whether this was a cache hit
        """
        try:
            # Store operation metrics
            metrics_data = {
                'operation': operation,
                'duration': duration,
                'query_count': query_count,
                'cache_hit': cache_hit,
                'timestamp': timezone.now().isoformat(),
            }
            
            # Cache metrics
            cache_key = f"{self.metrics_cache_prefix}db_operation:{operation}:{int(time.time())}"
            cache.set(cache_key, json.dumps(metrics_data), timeout=self.metrics_ttl)
            
            # Update aggregated metrics
            self._update_database_aggregates(operation, duration, query_count, cache_hit)
            
            # Check for performance alerts
            self._check_database_alerts(operation, duration, query_count)
            
            logger.debug(f"Tracked database performance for {operation}: {duration:.3f}ms")
            
        except Exception as e:
            logger.error(f"Failed to track database performance: {e}")
    
    def track_cache_performance(self, operation: str, cache_key: str,
                              hit: bool, duration: float):
        """
        Track cache operation performance.
        
        Args:
            operation: Cache operation name (get, set, delete)
            cache_key: Cache key used
            hit: Whether this was a cache hit
            duration: Operation duration in milliseconds
        """
        try:
            # Store cache metrics
            metrics_data = {
                'operation': operation,
                'cache_key': cache_key,
                'hit': hit,
                'duration': duration,
                'timestamp': timezone.now().isoformat(),
            }
            
            # Cache metrics
            cache_key_metrics = f"{self.metrics_cache_prefix}cache_operation:{operation}:{int(time.time())}"
            cache.set(cache_key_metrics, json.dumps(metrics_data), timeout=self.metrics_ttl)
            
            # Update aggregated metrics
            self._update_cache_aggregates(operation, hit, duration)
            
            logger.debug(f"Tracked cache performance for {operation}: {duration:.3f}ms, hit: {hit}")
            
        except Exception as e:
            logger.error(f"Failed to track cache performance: {e}")
    
    def get_performance_summary(self, time_window_minutes: int = 60) -> Dict[str, Any]:
        """
        Get comprehensive performance summary for the specified time window.
        
        Args:
            time_window_minutes: Time window in minutes
            
        Returns:
            Dictionary with performance summary
        """
        try:
            cutoff_time = timezone.now() - timedelta(minutes=time_window_minutes)
            
            summary = {
                'time_window_minutes': time_window_minutes,
                'timestamp': timezone.now().isoformat(),
                'message_delivery': self._get_message_delivery_summary(cutoff_time),
                'websocket_connections': self._get_websocket_connection_summary(cutoff_time),
                'database_operations': self._get_database_summary(cutoff_time),
                'cache_operations': self._get_cache_summary(cutoff_time),
                'system_health': self._get_system_health_summary(),
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to get performance summary: {e}")
            return {'error': str(e)}
    
    def get_performance_trends(self, metric_name: str, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get performance trends for a specific metric over time.
        
        Args:
            metric_name: Name of the metric
            hours: Number of hours to look back
            
        Returns:
            List of metric values over time
        """
        try:
            trends = []
            current_time = timezone.now()
            
            for i in range(hours):
                hour_start = current_time - timedelta(hours=i+1)
                hour_end = current_time - timedelta(hours=i)
                
                # Get metrics for this hour
                hour_metrics = self._get_metrics_for_time_range(metric_name, hour_start, hour_end)
                trends.append({
                    'timestamp': hour_start.isoformat(),
                    'value': hour_metrics.get('average', 0),
                    'count': hour_metrics.get('count', 0),
                    'min': hour_metrics.get('min', 0),
                    'max': hour_metrics.get('max', 0),
                })
            
            return list(reversed(trends))  # Return in chronological order
            
        except Exception as e:
            logger.error(f"Failed to get performance trends: {e}")
            return []
    
    def _update_message_delivery_aggregates(self, total_time: float, stage_durations: Dict[str, float]):
        """Update aggregated message delivery metrics."""
        try:
            # Update total delivery time aggregates
            total_key = f"{self.metrics_cache_prefix}msg_delivery_total"
            self._update_aggregate_metric(total_key, total_time)
            
            # Update stage duration aggregates
            for stage, duration in stage_durations.items():
                stage_key = f"{self.metrics_cache_prefix}msg_delivery_stage:{stage}"
                self._update_aggregate_metric(stage_key, duration)
                
        except Exception as e:
            logger.error(f"Failed to update message delivery aggregates: {e}")
    
    def _update_websocket_connection_aggregates(self, total_time: float, stage_durations: Dict[str, float]):
        """Update aggregated WebSocket connection metrics."""
        try:
            # Update total connection time aggregates
            total_key = f"{self.metrics_cache_prefix}ws_connection_total"
            self._update_aggregate_metric(total_key, total_time)
            
            # Update stage duration aggregates
            for stage, duration in stage_durations.items():
                stage_key = f"{self.metrics_cache_prefix}ws_connection_stage:{stage}"
                self._update_aggregate_metric(stage_key, duration)
                
        except Exception as e:
            logger.error(f"Failed to update WebSocket connection aggregates: {e}")
    
    def _update_database_aggregates(self, operation: str, duration: float, query_count: int, cache_hit: bool):
        """Update aggregated database metrics."""
        try:
            # Update operation duration aggregates
            duration_key = f"{self.metrics_cache_prefix}db_duration:{operation}"
            self._update_aggregate_metric(duration_key, duration)
            
            # Update query count aggregates
            count_key = f"{self.metrics_cache_prefix}db_queries:{operation}"
            self._update_aggregate_metric(count_key, query_count)
            
            # Update cache hit ratio
            hit_key = f"{self.metrics_cache_prefix}db_cache_hits:{operation}"
            miss_key = f"{self.metrics_cache_prefix}db_cache_misses:{operation}"
            
            if cache_hit:
                self._update_aggregate_metric(hit_key, 1)
            else:
                self._update_aggregate_metric(miss_key, 1)
                
        except Exception as e:
            logger.error(f"Failed to update database aggregates: {e}")
    
    def _update_cache_aggregates(self, operation: str, hit: bool, duration: float):
        """Update aggregated cache metrics."""
        try:
            # Update operation duration aggregates
            duration_key = f"{self.metrics_cache_prefix}cache_duration:{operation}"
            self._update_aggregate_metric(duration_key, duration)
            
            # Update hit/miss ratios
            if hit:
                hit_key = f"{self.metrics_cache_prefix}cache_hits:{operation}"
                self._update_aggregate_metric(hit_key, 1)
            else:
                miss_key = f"{self.metrics_cache_prefix}cache_misses:{operation}"
                self._update_aggregate_metric(miss_key, 1)
                
        except Exception as e:
            logger.error(f"Failed to update cache aggregates: {e}")
    
    def _update_aggregate_metric(self, key: str, value: float):
        """Update an aggregate metric with count, sum, min, max."""
        try:
            # Get current aggregate data
            aggregate_data = cache.get(key, {'count': 0, 'sum': 0, 'min': float('inf'), 'max': 0})
            
            # Update aggregates
            aggregate_data['count'] += 1
            aggregate_data['sum'] += value
            aggregate_data['min'] = min(aggregate_data['min'], value)
            aggregate_data['max'] = max(aggregate_data['max'], value)
            aggregate_data['average'] = aggregate_data['sum'] / aggregate_data['count']
            
            # Cache updated data
            cache.set(key, aggregate_data, timeout=self.metrics_ttl)
            
        except Exception as e:
            logger.error(f"Failed to update aggregate metric {key}: {e}")
    
    def _check_message_delivery_alerts(self, total_time: float, stage_durations: Dict[str, float]):
        """Check for message delivery performance alerts."""
        try:
            threshold = self.alert_thresholds.get('message_delivery_latency', 1000)
            
            if total_time > threshold:
                logger.warning(f"Message delivery latency alert: {total_time:.3f}ms exceeds threshold {threshold}ms")
                
                # Log slow stages
                for stage, duration in stage_durations.items():
                    if duration > threshold * 0.5:  # Stage taking more than 50% of threshold
                        logger.warning(f"Slow message delivery stage: {stage} took {duration:.3f}ms")
                        
        except Exception as e:
            logger.error(f"Failed to check message delivery alerts: {e}")
    
    def _check_websocket_connection_alerts(self, total_time: float, stage_durations: Dict[str, float]):
        """Check for WebSocket connection performance alerts."""
        try:
            threshold = self.alert_thresholds.get('websocket_connection_time', 5000)
            
            if total_time > threshold:
                logger.warning(f"WebSocket connection time alert: {total_time:.3f}ms exceeds threshold {threshold}ms")
                
                # Log slow stages
                for stage, duration in stage_durations.items():
                    if duration > threshold * 0.5:  # Stage taking more than 50% of threshold
                        logger.warning(f"Slow WebSocket connection stage: {stage} took {duration:.3f}ms")
                        
        except Exception as e:
            logger.error(f"Failed to check WebSocket connection alerts: {e}")
    
    def _check_database_alerts(self, operation: str, duration: float, query_count: int):
        """Check for database performance alerts."""
        try:
            threshold = self.alert_thresholds.get('database_query_time', 100)
            
            if duration > threshold:
                logger.warning(f"Database query time alert: {operation} took {duration:.3f}ms exceeds threshold {threshold}ms")
                
            if query_count > 10:  # N+1 query alert
                logger.warning(f"High query count alert: {operation} executed {query_count} queries")
                
        except Exception as e:
            logger.error(f"Failed to check database alerts: {e}")
    
    def _get_message_delivery_summary(self, cutoff_time) -> Dict[str, Any]:
        """Get message delivery performance summary."""
        try:
            # This is a simplified version - in production you might want to
            # scan all message delivery keys and aggregate them
            return {
                'average_delivery_time': cache.get(f"{self.metrics_cache_prefix}msg_delivery_total", {}).get('average', 0),
                'total_messages': cache.get(f"{self.metrics_cache_prefix}msg_delivery_total", {}).get('count', 0),
                'slow_messages': 0,  # Would need to calculate based on threshold
            }
        except Exception as e:
            logger.error(f"Failed to get message delivery summary: {e}")
            return {}
    
    def _get_websocket_connection_summary(self, cutoff_time) -> Dict[str, Any]:
        """Get WebSocket connection performance summary."""
        try:
            return {
                'average_connection_time': cache.get(f"{self.metrics_cache_prefix}ws_connection_total", {}).get('average', 0),
                'total_connections': cache.get(f"{self.metrics_cache_prefix}ws_connection_total", {}).get('count', 0),
                'slow_connections': 0,  # Would need to calculate based on threshold
            }
        except Exception as e:
            logger.error(f"Failed to get WebSocket connection summary: {e}")
            return {}
    
    def _get_database_summary(self, cutoff_time) -> Dict[str, Any]:
        """Get database performance summary."""
        try:
            return {
                'average_query_time': 0,  # Would need to aggregate all operations
                'total_queries': 0,  # Would need to aggregate all operations
                'cache_hit_ratio': 0,  # Would need to calculate from hits/misses
            }
        except Exception as e:
            logger.error(f"Failed to get database summary: {e}")
            return {}
    
    def _get_cache_summary(self, cutoff_time) -> Dict[str, Any]:
        """Get cache performance summary."""
        try:
            return {
                'average_operation_time': 0,  # Would need to aggregate all operations
                'total_operations': 0,  # Would need to aggregate all operations
                'hit_ratio': 0,  # Would need to calculate from hits/misses
            }
        except Exception as e:
            logger.error(f"Failed to get cache summary: {e}")
            return {}
    
    def _get_system_health_summary(self) -> Dict[str, Any]:
        """Get system health summary."""
        try:
            return {
                'status': 'healthy',
                'alerts': [],
                'recommendations': [],
            }
        except Exception as e:
            logger.error(f"Failed to get system health summary: {e}")
            return {}
    
    def _get_metrics_for_time_range(self, metric_name: str, start_time, end_time) -> Dict[str, Any]:
        """Get metrics for a specific time range."""
        try:
            # This is a simplified version - in production you might want to
            # scan all metric keys and filter by timestamp
            return {
                'average': 0,
                'count': 0,
                'min': 0,
                'max': 0,
            }
        except Exception as e:
            logger.error(f"Failed to get metrics for time range: {e}")
            return {}


# Global performance metrics collector
performance_metrics = PerformanceMetricsCollector()


# Context manager for performance tracking
class PerformanceTracker:
    """Context manager for tracking performance of code blocks."""
    
    def __init__(self, operation_name: str, context: Optional[Dict[str, Any]] = None):
        self.operation_name = operation_name
        self.context = context or {}
        self.start_time = None
        self.stages = {}
    
    def __enter__(self):
        self.start_time = time.time()
        self.stages['start'] = self.start_time
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            end_time = time.time()
            self.stages['end'] = end_time
            
            duration = (end_time - self.start_time) * 1000  # Convert to milliseconds
            
            # Track the performance
            if 'message_delivery' in self.operation_name:
                performance_metrics.track_message_delivery_performance(
                    self.context.get('message_id', 0),
                    self.stages,
                    self.context.get('user_id'),
                    self.context.get('conversation_id')
                )
            elif 'websocket_connection' in self.operation_name:
                performance_metrics.track_websocket_connection_performance(
                    self.context.get('connection_id', 'unknown'),
                    self.stages,
                    self.context.get('user_id')
                )
            else:
                # Generic performance tracking
                logger.info(f"Performance: {self.operation_name} took {duration:.3f}ms")
    
    def mark_stage(self, stage_name: str):
        """Mark a performance stage."""
        self.stages[stage_name] = time.time()


# Decorator for automatic performance tracking
def track_performance(operation_name: str):
    """Decorator to automatically track performance of functions."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with PerformanceTracker(operation_name):
                return func(*args, **kwargs)
        return wrapper
    return decorator































