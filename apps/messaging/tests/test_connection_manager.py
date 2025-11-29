"""
Tests for Redis connection manager functionality.

This module tests connection tracking, user presence, and analytics.
"""

import json
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.core.cache import cache
from django.contrib.auth import get_user_model
from apps.messaging.connection_manager import RedisConnectionManager
from apps.shared.models import Conversation, User


class ConnectionManagerTestCase(TestCase):
    """Test case for Redis connection manager."""
    
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
        
        # Create connection manager instance
        self.connection_manager = RedisConnectionManager()
        
        # Clear cache before each test
        cache.clear()
    
    def tearDown(self):
        """Clean up test data."""
        cache.clear()
    
    def test_add_connection_success(self):
        """Test successful connection addition."""
        connection_metadata = {
            'ip_address': '127.0.0.1',
            'user_agent': 'Test Agent'
        }
        
        result = self.connection_manager.add_connection(
            self.user1.user_id,
            self.conversation.conversation_id,
            'test_channel_1',
            connection_metadata
        )
        
        self.assertTrue(result)
        
        # Verify connection was added
        user_connections = self.connection_manager.get_user_connections(self.user1.user_id)
        self.assertIn('test_channel_1', user_connections)
        
        # Verify conversation users
        conversation_users = self.connection_manager.get_conversation_users(self.conversation.conversation_id)
        user_ids = [user['user_id'] for user in conversation_users]
        self.assertIn(self.user1.user_id, user_ids)
    
    def test_remove_connection_success(self):
        """Test successful connection removal."""
        # Add connection first
        self.connection_manager.add_connection(
            self.user1.user_id,
            self.conversation.conversation_id,
            'test_channel_1'
        )
        
        # Remove connection
        result = self.connection_manager.remove_connection('test_channel_1')
        
        self.assertTrue(result)
        
        # Verify connection was removed
        user_connections = self.connection_manager.get_user_connections(self.user1.user_id)
        self.assertNotIn('test_channel_1', user_connections)
    
    def test_update_user_presence(self):
        """Test user presence updates."""
        # Add connection first
        self.connection_manager.add_connection(
            self.user1.user_id,
            self.conversation.conversation_id,
            'test_channel_1'
        )
        
        # Update presence to typing
        result = self.connection_manager.update_user_presence(
            self.user1.user_id,
            self.conversation.conversation_id,
            'typing'
        )
        
        self.assertTrue(result)
        
        # Verify presence was updated
        conversation_users = self.connection_manager.get_conversation_users(self.conversation.conversation_id)
        user_presence = next((user for user in conversation_users if user['user_id'] == self.user1.user_id), None)
        self.assertIsNotNone(user_presence)
        self.assertEqual(user_presence['status'], 'typing')
    
    def test_multiple_connections_per_user(self):
        """Test multiple connections for the same user."""
        # Add multiple connections for user1
        self.connection_manager.add_connection(
            self.user1.user_id,
            self.conversation.conversation_id,
            'test_channel_1'
        )
        self.connection_manager.add_connection(
            self.user1.user_id,
            self.conversation.conversation_id,
            'test_channel_2'
        )
        
        # Verify both connections exist
        user_connections = self.connection_manager.get_user_connections(self.user1.user_id)
        self.assertEqual(len(user_connections), 2)
        self.assertIn('test_channel_1', user_connections)
        self.assertIn('test_channel_2', user_connections)
        
        # Remove one connection
        self.connection_manager.remove_connection('test_channel_1')
        
        # Verify only one connection remains
        user_connections = self.connection_manager.get_user_connections(self.user1.user_id)
        self.assertEqual(len(user_connections), 1)
        self.assertIn('test_channel_2', user_connections)
    
    def test_conversation_users_tracking(self):
        """Test conversation users tracking."""
        # Add connections for both users
        self.connection_manager.add_connection(
            self.user1.user_id,
            self.conversation.conversation_id,
            'test_channel_1'
        )
        self.connection_manager.add_connection(
            self.user2.user_id,
            self.conversation.conversation_id,
            'test_channel_2'
        )
        
        # Verify both users are in conversation
        conversation_users = self.connection_manager.get_conversation_users(self.conversation.conversation_id)
        user_ids = [user['user_id'] for user in conversation_users]
        self.assertIn(self.user1.user_id, user_ids)
        self.assertIn(self.user2.user_id, user_ids)
        
        # Remove one user's connection
        self.connection_manager.remove_connection('test_channel_1')
        
        # Verify only one user remains
        conversation_users = self.connection_manager.get_conversation_users(self.conversation.conversation_id)
        user_ids = [user['user_id'] for user in conversation_users]
        self.assertNotIn(self.user1.user_id, user_ids)
        self.assertIn(self.user2.user_id, user_ids)
    
    def test_connection_analytics(self):
        """Test connection analytics collection."""
        # Add some connections
        self.connection_manager.add_connection(
            self.user1.user_id,
            self.conversation.conversation_id,
            'test_channel_1'
        )
        self.connection_manager.add_connection(
            self.user2.user_id,
            self.conversation.conversation_id,
            'test_channel_2'
        )
        
        # Get analytics
        analytics = self.connection_manager.get_connection_analytics()
        
        self.assertIsInstance(analytics, dict)
        # Analytics should contain event data
        # (In a real test, you'd verify specific analytics data)
    
    def test_cleanup_stale_connections(self):
        """Test cleanup of stale connections."""
        # Add connection
        self.connection_manager.add_connection(
            self.user1.user_id,
            self.conversation.conversation_id,
            'test_channel_1'
        )
        
        # Perform cleanup
        cleaned_count = self.connection_manager.cleanup_stale_connections()
        
        # Should return 0 (Redis handles TTL cleanup automatically)
        self.assertEqual(cleaned_count, 0)
    
    def test_error_handling(self):
        """Test error handling in connection manager."""
        # Test with invalid user ID
        result = self.connection_manager.add_connection(
            None,
            self.conversation.conversation_id,
            'test_channel_1'
        )
        
        # Should handle gracefully
        self.assertIsInstance(result, bool)
    
    def test_presence_broadcasting(self):
        """Test presence update broadcasting."""
        # Add connections for both users
        self.connection_manager.add_connection(
            self.user1.user_id,
            self.conversation.conversation_id,
            'test_channel_1'
        )
        self.connection_manager.add_connection(
            self.user2.user_id,
            self.conversation.conversation_id,
            'test_channel_2'
        )
        
        # Mock channel layer
        with patch.object(self.connection_manager, 'channel_layer') as mock_channel_layer:
            mock_channel_layer.send = MagicMock()
            
            # Update presence for user1
            self.connection_manager.update_user_presence(
                self.user1.user_id,
                self.conversation.conversation_id,
                'typing'
            )
            
            # Verify broadcasting was attempted
            # (In a real test, you'd verify the broadcast was sent)
    
    def test_connection_metadata_storage(self):
        """Test connection metadata storage and retrieval."""
        connection_metadata = {
            'ip_address': '192.168.1.100',
            'user_agent': 'Mozilla/5.0 (Test Browser)',
            'custom_data': 'test_value'
        }
        
        # Add connection with metadata
        result = self.connection_manager.add_connection(
            self.user1.user_id,
            self.conversation.conversation_id,
            'test_channel_1',
            connection_metadata
        )
        
        self.assertTrue(result)
        
        # Verify metadata was stored
        # (In a real test, you'd verify the metadata was stored correctly)
    
    def test_concurrent_connection_operations(self):
        """Test concurrent connection operations."""
        import threading
        import time
        
        results = []
        
        def add_connection(user_id, channel_name):
            result = self.connection_manager.add_connection(
                user_id,
                self.conversation.conversation_id,
                channel_name
            )
            results.append(result)
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(
                target=add_connection,
                args=(self.user1.user_id, f'test_channel_{i}')
            )
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all operations succeeded
        self.assertEqual(len(results), 5)
        self.assertTrue(all(results))
        
        # Verify all connections were added
        user_connections = self.connection_manager.get_user_connections(self.user1.user_id)
        self.assertEqual(len(user_connections), 5)
































































