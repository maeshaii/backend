"""
Tests for rate limiting functionality.

This module tests message rate limiting, connection rate limiting,
and typing rate limiting with various scenarios.
"""

import time
from unittest.mock import patch
from django.test import TestCase
from django.core.cache import cache
from django.contrib.auth import get_user_model
from apps.messaging.rate_limiter import WebSocketRateLimiter, ConnectionPool
from apps.shared.models import Conversation, User


class RateLimiterTestCase(TestCase):
    """Test case for rate limiting functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.User = get_user_model()
        
        # Create test users
        self.user1 = self.User.objects.create_user(
            username='testuser1',
            email='test1@example.com',
            password='testpass123',
            user_id=1,
            name='Test User 1',
            full_name='Test User 1'
        )
        
        self.user2 = self.User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123',
            user_id=2,
            name='Test User 2',
            full_name='Test User 2'
        )
        
        # Create test conversation
        self.conversation = Conversation.objects.create()
        self.conversation.participants.add(self.user1, self.user2)
        
        # Create rate limiter and connection pool instances
        self.rate_limiter = WebSocketRateLimiter()
        self.connection_pool = ConnectionPool()
        
        # Clear cache before each test
        cache.clear()
    
    def tearDown(self):
        """Clean up test data."""
        cache.clear()
    
    def test_message_rate_limit_success(self):
        """Test successful message rate limit check."""
        can_send, rate_info = self.rate_limiter.check_message_rate_limit(
            self.user1.user_id,
            self.conversation.conversation_id
        )
        
        self.assertTrue(can_send)
        self.assertTrue(rate_info['allowed'])
        self.assertEqual(rate_info['user_requests'], 1)
        self.assertEqual(rate_info['user_limit'], self.rate_limiter.message_rate)
    
    def test_message_rate_limit_exceeded(self):
        """Test message rate limit exceeded."""
        # Send messages up to the limit
        for i in range(self.rate_limiter.message_rate):
            can_send, rate_info = self.rate_limiter.check_message_rate_limit(
                self.user1.user_id,
                self.conversation.conversation_id
            )
            self.assertTrue(can_send)
        
        # Next message should be rate limited
        can_send, rate_info = self.rate_limiter.check_message_rate_limit(
            self.user1.user_id,
            self.conversation.conversation_id
        )
        
        self.assertFalse(can_send)
        self.assertFalse(rate_info['allowed'])
        self.assertEqual(rate_info['reason'], 'user_rate_limit_exceeded')
        self.assertIn('retry_after', rate_info)
    
    def test_connection_rate_limit_success(self):
        """Test successful connection rate limit check."""
        can_connect, rate_info = self.rate_limiter.check_connection_rate_limit(
            self.user1.user_id,
            '127.0.0.1'
        )
        
        self.assertTrue(can_connect)
        self.assertTrue(rate_info['allowed'])
        self.assertEqual(rate_info['user_connections'], 1)
        self.assertEqual(rate_info['user_limit'], self.rate_limiter.connection_rate)
    
    def test_connection_rate_limit_exceeded(self):
        """Test connection rate limit exceeded."""
        # Create connections up to the limit
        for i in range(self.rate_limiter.connection_rate):
            can_connect, rate_info = self.rate_limiter.check_connection_rate_limit(
                self.user1.user_id,
                '127.0.0.1'
            )
            self.assertTrue(can_connect)
        
        # Next connection should be rate limited
        can_connect, rate_info = self.rate_limiter.check_connection_rate_limit(
            self.user1.user_id,
            '127.0.0.1'
        )
        
        self.assertFalse(can_connect)
        self.assertFalse(rate_info['allowed'])
        self.assertEqual(rate_info['reason'], 'connection_rate_limit_exceeded')
        self.assertIn('retry_after', rate_info)
    
    def test_typing_rate_limit_success(self):
        """Test successful typing rate limit check."""
        can_type, rate_info = self.rate_limiter.check_typing_rate_limit(
            self.user1.user_id,
            self.conversation.conversation_id
        )
        
        self.assertTrue(can_type)
        self.assertTrue(rate_info['allowed'])
        self.assertEqual(rate_info['typing_events'], 1)
        self.assertEqual(rate_info['limit'], self.rate_limiter.typing_rate)
    
    def test_typing_rate_limit_exceeded(self):
        """Test typing rate limit exceeded."""
        # Send typing events up to the limit
        for i in range(self.rate_limiter.typing_rate):
            can_type, rate_info = self.rate_limiter.check_typing_rate_limit(
                self.user1.user_id,
                self.conversation.conversation_id
            )
            self.assertTrue(can_type)
        
        # Next typing event should be rate limited
        can_type, rate_info = self.rate_limiter.check_typing_rate_limit(
            self.user1.user_id,
            self.conversation.conversation_id
        )
        
        self.assertFalse(can_type)
        self.assertFalse(rate_info['allowed'])
        self.assertEqual(rate_info['reason'], 'typing_rate_limit_exceeded')
        self.assertIn('retry_after', rate_info)
    
    def test_ip_connection_rate_limit(self):
        """Test IP-based connection rate limiting."""
        # Create connections from same IP up to the limit
        ip_limit = self.rate_limiter.connection_rate * 3  # More lenient for IP
        
        for i in range(ip_limit):
            can_connect, rate_info = self.rate_limiter.check_connection_rate_limit(
                self.user1.user_id,
                '192.168.1.100'  # Same IP
            )
            self.assertTrue(can_connect)
        
        # Next connection from same IP should be rate limited
        can_connect, rate_info = self.rate_limiter.check_connection_rate_limit(
            self.user1.user_id,
            '192.168.1.100'
        )
        
        self.assertFalse(can_connect)
        self.assertFalse(rate_info['allowed'])
        self.assertEqual(rate_info['reason'], 'ip_connection_rate_limit_exceeded')
    
    def test_rate_limit_status(self):
        """Test rate limit status retrieval."""
        # Send some messages
        for i in range(5):
            self.rate_limiter.check_message_rate_limit(
                self.user1.user_id,
                self.conversation.conversation_id
            )
        
        # Get status
        status = self.rate_limiter.get_user_rate_limit_status(self.user1.user_id)
        
        self.assertIsInstance(status, dict)
        self.assertEqual(status['user_id'], self.user1.user_id)
        self.assertIn('message_rate', status)
        self.assertIn('connection_rate', status)
        self.assertIn('typing_rate', status)
        
        # Check message rate status
        msg_rate = status['message_rate']
        self.assertEqual(msg_rate['current'], 5)
        self.assertEqual(msg_rate['limit'], self.rate_limiter.message_rate)
        self.assertEqual(msg_rate['remaining'], self.rate_limiter.message_rate - 5)
    
    def test_connection_pool_limits(self):
        """Test connection pool limits."""
        # Test per-user connection limit
        for i in range(self.connection_pool.MAX_CONNECTIONS_PER_USER):
            can_create, pool_info = self.connection_pool.can_create_connection(self.user1.user_id)
            self.assertTrue(can_create)
            self.assertTrue(pool_info['allowed'])
        
        # Next connection should exceed per-user limit
        can_create, pool_info = self.connection_pool.can_create_connection(self.user1.user_id)
        self.assertFalse(can_create)
        self.assertFalse(pool_info['allowed'])
        self.assertEqual(pool_info['reason'], 'max_connections_per_user_exceeded')
    
    def test_connection_pool_add_remove(self):
        """Test connection pool add and remove operations."""
        # Add connection
        result = self.connection_pool.add_connection(
            self.user1.user_id,
            'test_connection_1'
        )
        self.assertTrue(result)
        
        # Remove connection
        result = self.connection_pool.remove_connection(
            self.user1.user_id,
            'test_connection_1'
        )
        self.assertTrue(result)
    
    def test_connection_pool_statistics(self):
        """Test connection pool statistics."""
        # Add some connections
        self.connection_pool.add_connection(self.user1.user_id, 'test_connection_1')
        self.connection_pool.add_connection(self.user2.user_id, 'test_connection_2')
        
        # Get statistics
        stats = self.connection_pool.get_pool_statistics()
        
        self.assertIsInstance(stats, dict)
        self.assertIn('total_connections', stats)
        self.assertIn('max_total_connections', stats)
        self.assertIn('utilization_percentage', stats)
        self.assertEqual(stats['total_connections'], 2)
    
    def test_rate_limit_cleanup(self):
        """Test rate limit data cleanup."""
        # Add some rate limit data
        self.rate_limiter.check_message_rate_limit(
            self.user1.user_id,
            self.conversation.conversation_id
        )
        
        # Perform cleanup
        cleaned_count = self.rate_limiter.cleanup_old_requests()
        
        # Should return 0 (Redis handles TTL cleanup automatically)
        self.assertEqual(cleaned_count, 0)
    
    def test_conversation_rate_limit(self):
        """Test conversation-specific rate limiting."""
        # Send messages to conversation up to the limit
        conv_limit = self.rate_limiter.message_rate * 2  # More lenient for conversation
        
        for i in range(conv_limit):
            can_send, rate_info = self.rate_limiter.check_message_rate_limit(
                self.user1.user_id,
                self.conversation.conversation_id
            )
            self.assertTrue(can_send)
        
        # Next message should be rate limited at conversation level
        can_send, rate_info = self.rate_limiter.check_message_rate_limit(
            self.user1.user_id,
            self.conversation.conversation_id
        )
        
        self.assertFalse(can_send)
        self.assertFalse(rate_info['allowed'])
        self.assertEqual(rate_info['reason'], 'conversation_rate_limit_exceeded')
    
    def test_rate_limit_time_window(self):
        """Test rate limit time window behavior."""
        # Send messages up to limit
        for i in range(self.rate_limiter.message_rate):
            can_send, rate_info = self.rate_limiter.check_message_rate_limit(
                self.user1.user_id,
                self.conversation.conversation_id
            )
            self.assertTrue(can_send)
        
        # Should be rate limited
        can_send, rate_info = self.rate_limiter.check_message_rate_limit(
            self.user1.user_id,
            self.conversation.conversation_id
        )
        self.assertFalse(can_send)
        
        # Wait for time window to pass (simulate by clearing cache)
        cache.clear()
        
        # Should be allowed again
        can_send, rate_info = self.rate_limiter.check_message_rate_limit(
            self.user1.user_id,
            self.conversation.conversation_id
        )
        self.assertTrue(can_send)
    
    def test_error_handling(self):
        """Test error handling in rate limiter."""
        # Test with invalid user ID
        can_send, rate_info = self.rate_limiter.check_message_rate_limit(
            None,
            self.conversation.conversation_id
        )
        
        # Should handle gracefully
        self.assertIsInstance(can_send, bool)
        self.assertIsInstance(rate_info, dict)
    
    def test_concurrent_rate_limit_checks(self):
        """Test concurrent rate limit checks."""
        import threading
        import time
        
        results = []
        
        def check_rate_limit(user_id, conversation_id):
            can_send, rate_info = self.rate_limiter.check_message_rate_limit(
                user_id,
                conversation_id
            )
            results.append((can_send, rate_info))
        
        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(
                target=check_rate_limit,
                args=(self.user1.user_id, self.conversation.conversation_id)
            )
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all operations completed
        self.assertEqual(len(results), 10)
        
        # Some should be allowed, some should be rate limited
        allowed_count = sum(1 for can_send, _ in results if can_send)
        self.assertGreater(allowed_count, 0)
        self.assertLessEqual(allowed_count, self.rate_limiter.message_rate)






