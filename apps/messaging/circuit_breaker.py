"""
Circuit Breaker Pattern for Redis and Channel Layer failures.
A senior developer implements graceful degradation!

The circuit breaker has 3 states:
- CLOSED: Normal operation (requests go through)
- OPEN: Failures detected (fail fast, no requests)
- HALF_OPEN: Testing if service recovered (limited requests)
"""
import time
import logging
from typing import Callable, Any, Optional
from functools import wraps
from django.core.cache import cache
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


class CircuitBreakerState:
    """Circuit breaker states"""
    CLOSED = 'closed'  # Normal operation
    OPEN = 'open'      # Failing - don't make requests
    HALF_OPEN = 'half_open'  # Testing recovery


class CircuitBreaker:
    """
    Circuit breaker implementation for resilient service calls.
    
    Usage:
        breaker = CircuitBreaker(
            name='redis_cache',
            failure_threshold=5,
            recovery_timeout=30,
            expected_exception=Exception
        )
        
        @breaker
        def risky_redis_call():
            cache.get('key')
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        expected_exception: type = Exception
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        # State tracking (in-memory for simplicity)
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.last_success_time = None
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator to wrap function with circuit breaker"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)
        return wrapper
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function through circuit breaker"""
        
        # Check if we should attempt the call
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                logger.info(f"Circuit breaker '{self.name}' entering HALF_OPEN state")
            else:
                # Fail fast - don't even try
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Service unavailable. Retry after {self.recovery_timeout}s"
                )
        
        try:
            # Attempt the call
            result = func(*args, **kwargs)
            
            # Success! Reset failure count
            self._on_success()
            return result
            
        except self.expected_exception as e:
            # Expected failure - track it
            self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try recovery"""
        if self.last_failure_time is None:
            return True
        return (time.time() - self.last_failure_time) >= self.recovery_timeout
    
    def _on_success(self):
        """Handle successful call"""
        if self.state == CircuitBreakerState.HALF_OPEN:
            logger.info(f"Circuit breaker '{self.name}' recovered - moving to CLOSED")
        
        self.failure_count = 0
        self.last_success_time = time.time()
        self.state = CircuitBreakerState.CLOSED
    
    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            if self.state != CircuitBreakerState.OPEN:
                logger.error(
                    f"Circuit breaker '{self.name}' OPEN after {self.failure_count} failures. "
                    f"Failing fast for {self.recovery_timeout}s"
                )
                self.state = CircuitBreakerState.OPEN
        else:
            logger.warning(
                f"Circuit breaker '{self.name}' failure {self.failure_count}/{self.failure_threshold}"
            )
    
    def reset(self):
        """Manually reset the circuit breaker"""
        logger.info(f"Circuit breaker '{self.name}' manually reset")
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


# Global circuit breakers for different services
redis_cache_breaker = CircuitBreaker(
    name='redis_cache',
    failure_threshold=5,
    recovery_timeout=30,
    expected_exception=Exception
)

channel_layer_breaker = CircuitBreaker(
    name='channel_layer',
    failure_threshold=5,
    recovery_timeout=30,
    expected_exception=Exception
)


def safe_cache_get(key: str, default: Any = None) -> Any:
    """
    Safe cache get with circuit breaker and fallback.
    Returns default value if cache is unavailable.
    """
    try:
        return redis_cache_breaker.call(cache.get, key)
    except CircuitBreakerOpenError:
        logger.warning(f"Cache circuit breaker OPEN - returning default for key: {key}")
        return default
    except Exception as e:
        logger.error(f"Cache get failed for key {key}: {e}")
        return default


def safe_cache_set(key: str, value: Any, timeout: int = 300) -> bool:
    """
    Safe cache set with circuit breaker.
    Returns True if successful, False otherwise.
    """
    try:
        redis_cache_breaker.call(cache.set, key, value, timeout)
        return True
    except CircuitBreakerOpenError:
        logger.warning(f"Cache circuit breaker OPEN - skipping set for key: {key}")
        return False
    except Exception as e:
        logger.error(f"Cache set failed for key {key}: {e}")
        return False


async def safe_channel_send(channel: str, message: dict, fallback: Optional[Callable] = None) -> bool:
    """
    Safe channel layer send with circuit breaker.
    Returns True if successful, False otherwise.
    
    Args:
        channel: Channel name to send to
        message: Message dict to send
        fallback: Optional fallback function to call if channel layer fails
    """
    try:
        channel_layer = get_channel_layer()
        await channel_layer_breaker.call(channel_layer.send, channel, message)
        return True
    except CircuitBreakerOpenError:
        logger.warning(f"Channel layer circuit breaker OPEN - message not sent to {channel}")
        if fallback:
            try:
                await fallback(channel, message)
            except Exception as e:
                logger.error(f"Fallback failed for channel {channel}: {e}")
        return False
    except Exception as e:
        logger.error(f"Channel layer send failed for {channel}: {e}")
        if fallback:
            try:
                await fallback(channel, message)
            except Exception as e:
                logger.error(f"Fallback failed for channel {channel}: {e}")
        return False


async def safe_channel_group_send(group: str, message: dict) -> bool:
    """
    Safe channel layer group send with circuit breaker.
    Returns True if successful, False otherwise.
    """
    try:
        channel_layer = get_channel_layer()
        await channel_layer_breaker.call(channel_layer.group_send, group, message)
        return True
    except CircuitBreakerOpenError:
        logger.warning(f"Channel layer circuit breaker OPEN - message not sent to group {group}")
        return False
    except Exception as e:
        logger.error(f"Channel layer group send failed for {group}: {e}")
        return False


def get_circuit_breaker_status() -> dict:
    """
    Get status of all circuit breakers.
    Useful for monitoring and health checks.
    """
    return {
        'redis_cache': {
            'state': redis_cache_breaker.state,
            'failure_count': redis_cache_breaker.failure_count,
            'last_failure': redis_cache_breaker.last_failure_time,
            'last_success': redis_cache_breaker.last_success_time,
        },
        'channel_layer': {
            'state': channel_layer_breaker.state,
            'failure_count': channel_layer_breaker.failure_count,
            'last_failure': channel_layer_breaker.last_failure_time,
            'last_success': channel_layer_breaker.last_success_time,
        }
    }

