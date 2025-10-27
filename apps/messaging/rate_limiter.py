"""
WebSocket rate limiting and connection pooling system.

This module provides rate limiting for WebSocket connections and messages
to prevent abuse and ensure fair usage across all users.
"""

import logging
import time
from typing import Dict, List, Optional, Tuple
from django.core.cache import cache
from django.utils import timezone
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class WebSocketRateLimiter:
    """
    Rate limiter for WebSocket connections and message sending.
    
    Features:
    - Per-user rate limiting
    - Per-conversation rate limiting
    - Connection rate limiting
    - Sliding window algorithm
    - Burst protection
    """
    
    # Rate limit configurations
    DEFAULT_MESSAGE_RATE = 30  # messages per minute
    DEFAULT_CONNECTION_RATE = 10  # connections per minute
    DEFAULT_TYPING_RATE = 60  # typing events per minute
    
    # Cache key prefixes
    MESSAGE_RATE_PREFIX = "ws_rate_msg:"
    CONNECTION_RATE_PREFIX = "ws_rate_conn:"
    TYPING_RATE_PREFIX = "ws_rate_typing:"
    USER_CONNECTIONS_PREFIX = "ws_user_conns:"
    
    # TTL values (in seconds)
    RATE_LIMIT_TTL = 3600  # 1 hour
    CONNECTION_TTL = 300   # 5 minutes
    
    def __init__(self):
        self.message_rate = self.DEFAULT_MESSAGE_RATE
        self.connection_rate = self.DEFAULT_CONNECTION_RATE
        self.typing_rate = self.DEFAULT_TYPING_RATE
    
    def check_message_rate_limit(self, user_id: int, conversation_id: int) -> Tuple[bool, Dict[str, any]]:
        """
        Check if user can send a message based on rate limits.
        
        Args:
            user_id: User ID
            conversation_id: Conversation ID
            
        Returns:
            Tuple of (allowed, rate_limit_info)
        """
        try:
            now = time.time()
            window_start = now - 60  # 1 minute window
            
            # Per-user rate limiting
            user_key = f"{self.MESSAGE_RATE_PREFIX}user:{user_id}"
            user_requests = self._get_request_times(user_key, window_start)
            
            if len(user_requests) >= self.message_rate:
                return False, {
                    'allowed': False,
                    'reason': 'user_rate_limit_exceeded',
                    'limit': self.message_rate,
                    'window': 60,
                    'retry_after': int(user_requests[0] + 60 - now) if user_requests else 60
                }
            
            # Per-conversation rate limiting (more lenient)
            conv_key = f"{self.MESSAGE_RATE_PREFIX}conv:{conversation_id}"
            conv_requests = self._get_request_times(conv_key, window_start)
            conv_limit = self.message_rate * 2  # Allow more messages per conversation
            
            if len(conv_requests) >= conv_limit:
                return False, {
                    'allowed': False,
                    'reason': 'conversation_rate_limit_exceeded',
                    'limit': conv_limit,
                    'window': 60,
                    'retry_after': int(conv_requests[0] + 60 - now) if conv_requests else 60
                }
            
            # Record the request
            self._record_request(user_key, now)
            self._record_request(conv_key, now)
            
            return True, {
                'allowed': True,
                'user_requests': len(user_requests) + 1,
                'user_limit': self.message_rate,
                'conv_requests': len(conv_requests) + 1,
                'conv_limit': conv_limit
            }
            
        except Exception as e:
            logger.error(f"Failed to check message rate limit: {e}")
            # Allow request on error to avoid blocking legitimate users
            return True, {'allowed': True, 'error': str(e)}
    
    def check_connection_rate_limit(self, user_id: int, ip_address: Optional[str] = None) -> Tuple[bool, Dict[str, any]]:
        """
        Check if user can establish a new WebSocket connection.
        
        Args:
            user_id: User ID
            ip_address: Optional IP address for additional limiting
            
        Returns:
            Tuple of (allowed, rate_limit_info)
        """
        try:
            now = time.time()
            window_start = now - 60  # 1 minute window
            
            # Per-user connection rate limiting
            user_key = f"{self.CONNECTION_RATE_PREFIX}user:{user_id}"
            user_connections = self._get_request_times(user_key, window_start)
            
            if len(user_connections) >= self.connection_rate:
                return False, {
                    'allowed': False,
                    'reason': 'connection_rate_limit_exceeded',
                    'limit': self.connection_rate,
                    'window': 60,
                    'retry_after': int(user_connections[0] + 60 - now) if user_connections else 60
                }
            
            # Per-IP connection rate limiting (if IP provided)
            if ip_address:
                ip_key = f"{self.CONNECTION_RATE_PREFIX}ip:{ip_address}"
                ip_connections = self._get_request_times(ip_key, window_start)
                ip_limit = self.connection_rate * 3  # More lenient for IP
                
                if len(ip_connections) >= ip_limit:
                    return False, {
                        'allowed': False,
                        'reason': 'ip_connection_rate_limit_exceeded',
                        'limit': ip_limit,
                        'window': 60,
                        'retry_after': int(ip_connections[0] + 60 - now) if ip_connections else 60
                    }
                
                self._record_request(ip_key, now)
            
            # Record the connection
            self._record_request(user_key, now)
            
            return True, {
                'allowed': True,
                'user_connections': len(user_connections) + 1,
                'user_limit': self.connection_rate
            }
            
        except Exception as e:
            logger.error(f"Failed to check connection rate limit: {e}")
            return True, {'allowed': True, 'error': str(e)}
    
    def check_typing_rate_limit(self, user_id: int, conversation_id: int) -> Tuple[bool, Dict[str, any]]:
        """
        Check if user can send typing indicators.
        
        Args:
            user_id: User ID
            conversation_id: Conversation ID
            
        Returns:
            Tuple of (allowed, rate_limit_info)
        """
        try:
            now = time.time()
            window_start = now - 60  # 1 minute window
            
            # Per-user typing rate limiting
            user_key = f"{self.TYPING_RATE_PREFIX}user:{user_id}"
            user_typing = self._get_request_times(user_key, window_start)
            
            if len(user_typing) >= self.typing_rate:
                return False, {
                    'allowed': False,
                    'reason': 'typing_rate_limit_exceeded',
                    'limit': self.typing_rate,
                    'window': 60,
                    'retry_after': int(user_typing[0] + 60 - now) if user_typing else 60
                }
            
            # Record the typing event
            self._record_request(user_key, now)
            
            return True, {
                'allowed': True,
                'typing_events': len(user_typing) + 1,
                'limit': self.typing_rate
            }
            
        except Exception as e:
            logger.error(f"Failed to check typing rate limit: {e}")
            return True, {'allowed': True, 'error': str(e)}
    
    def get_user_rate_limit_status(self, user_id: int) -> Dict[str, any]:
        """
        Get current rate limit status for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with rate limit status
        """
        try:
            now = time.time()
            window_start = now - 60
            
            # Get message rate status
            msg_key = f"{self.MESSAGE_RATE_PREFIX}user:{user_id}"
            msg_requests = self._get_request_times(msg_key, window_start)
            
            # Get connection rate status
            conn_key = f"{self.CONNECTION_RATE_PREFIX}user:{user_id}"
            conn_requests = self._get_request_times(conn_key, window_start)
            
            # Get typing rate status
            typing_key = f"{self.TYPING_RATE_PREFIX}user:{user_id}"
            typing_requests = self._get_request_times(typing_key, window_start)
            
            return {
                'user_id': user_id,
                'timestamp': now,
                'message_rate': {
                    'current': len(msg_requests),
                    'limit': self.message_rate,
                    'remaining': max(0, self.message_rate - len(msg_requests)),
                    'reset_in': int(msg_requests[0] + 60 - now) if msg_requests else 0
                },
                'connection_rate': {
                    'current': len(conn_requests),
                    'limit': self.connection_rate,
                    'remaining': max(0, self.connection_rate - len(conn_requests)),
                    'reset_in': int(conn_requests[0] + 60 - now) if conn_requests else 0
                },
                'typing_rate': {
                    'current': len(typing_requests),
                    'limit': self.typing_rate,
                    'remaining': max(0, self.typing_rate - len(typing_requests)),
                    'reset_in': int(typing_requests[0] + 60 - now) if typing_requests else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get user rate limit status: {e}")
            return {'error': str(e)}
    
    def _get_request_times(self, key: str, window_start: float) -> List[float]:
        """Get request times within the sliding window."""
        try:
            cached_data = cache.get(key, [])
            if not isinstance(cached_data, list):
                return []
            
            # Filter out old requests
            recent_requests = [t for t in cached_data if t >= window_start]
            
            # Update cache with filtered data
            if len(recent_requests) != len(cached_data):
                cache.set(key, recent_requests, timeout=self.RATE_LIMIT_TTL)
            
            return recent_requests
            
        except Exception as e:
            logger.error(f"Failed to get request times for {key}: {e}")
            return []
    
    def _record_request(self, key: str, timestamp: float) -> None:
        """Record a request timestamp."""
        try:
            cached_data = cache.get(key, [])
            if not isinstance(cached_data, list):
                cached_data = []
            
            cached_data.append(timestamp)
            cache.set(key, cached_data, timeout=self.RATE_LIMIT_TTL)
            
        except Exception as e:
            logger.error(f"Failed to record request for {key}: {e}")
    
    def cleanup_old_requests(self) -> int:
        """
        Clean up old rate limit data.
        
        Returns:
            Number of keys cleaned up
        """
        try:
            # This is a simplified cleanup - in production you might want to use
            # Redis SCAN to iterate through all rate limit keys
            # For now, we rely on TTL to handle cleanup automatically
            
            logger.debug("Rate limit cleanup completed")
            return 0  # Redis handles TTL cleanup automatically
            
        except Exception as e:
            logger.error(f"Failed to cleanup old requests: {e}")
            return 0


class ConnectionPool:
    """
    WebSocket connection pool manager.
    
    Features:
    - Connection pooling per user
    - Maximum connection limits
    - Connection cleanup
    - Pool statistics
    """
    
    # Configuration
    MAX_CONNECTIONS_PER_USER = 50
    MAX_TOTAL_CONNECTIONS = 1000
    CONNECTION_CLEANUP_INTERVAL = 300  # 5 minutes
    
    def __init__(self):
        self.rate_limiter = WebSocketRateLimiter()
    
    def can_create_connection(self, user_id: int) -> Tuple[bool, Dict[str, any]]:
        """
        Check if a new connection can be created for the user.
        
        Args:
            user_id: User ID
            
        Returns:
            Tuple of (allowed, pool_info)
        """
        try:
            # Check rate limiting first
            rate_allowed, rate_info = self.rate_limiter.check_connection_rate_limit(user_id)
            if not rate_allowed:
                return False, rate_info
            
            # Check per-user connection limit
            user_connections = self._get_user_connections(user_id)
            if len(user_connections) >= self.MAX_CONNECTIONS_PER_USER:
                return False, {
                    'allowed': False,
                    'reason': 'max_connections_per_user_exceeded',
                    'current': len(user_connections),
                    'limit': self.MAX_CONNECTIONS_PER_USER
                }
            
            # Check total connection limit
            total_connections = self._get_total_connections()
            if total_connections >= self.MAX_TOTAL_CONNECTIONS:
                return False, {
                    'allowed': False,
                    'reason': 'max_total_connections_exceeded',
                    'current': total_connections,
                    'limit': self.MAX_TOTAL_CONNECTIONS
                }
            
            return True, {
                'allowed': True,
                'user_connections': len(user_connections),
                'user_limit': self.MAX_CONNECTIONS_PER_USER,
                'total_connections': total_connections,
                'total_limit': self.MAX_TOTAL_CONNECTIONS
            }
            
        except Exception as e:
            logger.error(f"Failed to check connection pool: {e}")
            return True, {'allowed': True, 'error': str(e)}
    
    def add_connection(self, user_id: int, connection_id: str) -> bool:
        """
        Add a connection to the pool.
        
        Args:
            user_id: User ID
            connection_id: Unique connection identifier
            
        Returns:
            bool: True if connection was added successfully
        """
        try:
            # Add to user's connections
            user_key = f"{self.rate_limiter.USER_CONNECTIONS_PREFIX}{user_id}"
            user_connections = cache.get(user_key, set())
            if not isinstance(user_connections, set):
                user_connections = set()
            
            user_connections.add(connection_id)
            cache.set(user_key, user_connections, timeout=self.rate_limiter.CONNECTION_TTL)
            
            # Add to global connection tracking
            global_key = "ws_pool:global"
            global_connections = cache.get(global_key, set())
            if not isinstance(global_connections, set):
                global_connections = set()
            
            global_connections.add(connection_id)
            cache.set(global_key, global_connections, timeout=self.rate_limiter.CONNECTION_TTL)
            
            logger.debug(f"Added connection {connection_id} for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add connection to pool: {e}")
            return False
    
    def remove_connection(self, user_id: int, connection_id: str) -> bool:
        """
        Remove a connection from the pool.
        
        Args:
            user_id: User ID
            connection_id: Unique connection identifier
            
        Returns:
            bool: True if connection was removed successfully
        """
        try:
            # Remove from user's connections
            user_key = f"{self.rate_limiter.USER_CONNECTIONS_PREFIX}{user_id}"
            user_connections = cache.get(user_key, set())
            if isinstance(user_connections, set):
                user_connections.discard(connection_id)
                if user_connections:
                    cache.set(user_key, user_connections, timeout=self.rate_limiter.CONNECTION_TTL)
                else:
                    cache.delete(user_key)
            
            # Remove from global connection tracking
            global_key = "ws_pool:global"
            global_connections = cache.get(global_key, set())
            if isinstance(global_connections, set):
                global_connections.discard(connection_id)
                if global_connections:
                    cache.set(global_key, global_connections, timeout=self.rate_limiter.CONNECTION_TTL)
                else:
                    cache.delete(global_key)
            
            logger.debug(f"Removed connection {connection_id} for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove connection from pool: {e}")
            return False
    
    def _get_user_connections(self, user_id: int) -> List[str]:
        """Get all connections for a user."""
        try:
            user_key = f"{self.rate_limiter.USER_CONNECTIONS_PREFIX}{user_id}"
            connections = cache.get(user_key, set())
            return list(connections) if isinstance(connections, set) else []
        except Exception:
            return []
    
    def _get_total_connections(self) -> int:
        """Get total number of active connections."""
        try:
            global_key = "ws_pool:global"
            connections = cache.get(global_key, set())
            return len(connections) if isinstance(connections, set) else 0
        except Exception:
            return 0
    
    def get_pool_statistics(self) -> Dict[str, any]:
        """
        Get connection pool statistics.
        
        Returns:
            Dictionary with pool statistics
        """
        try:
            total_connections = self._get_total_connections()
            
            # Get user connection distribution
            user_connection_counts = defaultdict(int)
            # This would require scanning all user keys in production
            
            return {
                'total_connections': total_connections,
                'max_total_connections': self.MAX_TOTAL_CONNECTIONS,
                'max_connections_per_user': self.MAX_CONNECTIONS_PER_USER,
                'utilization_percentage': (total_connections / self.MAX_TOTAL_CONNECTIONS) * 100,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get pool statistics: {e}")
            return {'error': str(e)}


# Global instances
rate_limiter = WebSocketRateLimiter()
connection_pool = ConnectionPool()





















