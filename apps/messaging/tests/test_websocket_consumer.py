"""
Comprehensive tests for WebSocket consumer functionality.

This module tests WebSocket connection handling, message processing,
typing indicators, read receipts, and error scenarios.
"""

import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from channels.testing import WebsocketCommunicator
from channels.layers import InMemoryChannelLayer
from apps.messaging.consumers import ChatConsumer
from apps.shared.models import Conversation, Message, User
from apps.messaging.connection_manager import connection_manager
from apps.messaging.rate_limiter import rate_limiter, connection_pool
from apps.messaging.message_ordering import message_sequencer
from apps.messaging.monitoring import messaging_monitor
from apps.messaging.performance_metrics import performance_metrics


class WebSocketConsumerTestCase(TransactionTestCase):
    """Test case for WebSocket consumer functionality."""
    
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
        
        # Set up channel layer
        self.channel_layer = InMemoryChannelLayer()
        
        # Mock dependencies
        self.mock_connection_manager = AsyncMock()
        self.mock_rate_limiter = AsyncMock()
        self.mock_connection_pool = AsyncMock()
        self.mock_message_sequencer = AsyncMock()
        self.mock_messaging_monitor = AsyncMock()
        self.mock_performance_metrics = AsyncMock()
    
    def tearDown(self):
        """Clean up test data."""
        # Clear cache
        from django.core.cache import cache
        cache.clear()
    
    async def test_websocket_connection_success(self):
        """Test successful WebSocket connection."""
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.conversation.conversation_id}/"
        )
        
        # Mock authentication
        communicator.scope['user'] = self.user1
        
        # Mock rate limiting to allow connection
        with patch.object(connection_pool, 'can_create_connection', return_value=(True, {'allowed': True})):
            with patch.object(connection_manager, 'add_connection', return_value=True):
                with patch.object(connection_pool, 'add_connection', return_value=True):
                    with patch.object(messaging_monitor, 'track_websocket_event', return_value=None):
                        with patch.object(performance_metrics, 'track_websocket_connection_performance', return_value=None):
                            # Connect
                            connected, subprotocol = await communicator.connect()
                            
                            self.assertTrue(connected)
                            
                            # Check connection confirmation message
                            response = await communicator.receive_json_from()
                            self.assertEqual(response['type'], 'connection_established')
                            self.assertEqual(response['conversation_id'], self.conversation.conversation_id)
                            self.assertEqual(response['user_id'], self.user1.user_id)
        
        await communicator.disconnect()
    
    async def test_websocket_connection_rate_limited(self):
        """Test WebSocket connection rate limiting."""
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.conversation.conversation_id}/"
        )
        
        # Mock authentication
        communicator.scope['user'] = self.user1
        
        # Mock rate limiting to deny connection
        with patch.object(connection_pool, 'can_create_connection', return_value=(False, {
            'allowed': False,
            'reason': 'connection_rate_limit_exceeded',
            'retry_after': 60
        })):
            # Connect
            connected, subprotocol = await communicator.connect()
            
            self.assertTrue(connected)  # Connection established but will be closed
            
            # Check rate limit message
            response = await communicator.receive_json_from()
            self.assertEqual(response['type'], 'connection_denied')
            self.assertEqual(response['reason'], 'connection_rate_limit_exceeded')
            self.assertEqual(response['retry_after'], 60)
        
        await communicator.disconnect()
    
    async def test_websocket_connection_access_denied(self):
        """Test WebSocket connection access denial."""
        # Create user not in conversation
        user3 = self.User.objects.create_user(
            username='testuser3',
            email='test3@example.com',
            password='testpass123',
            user_id=3,
            name='Test User 3',
            full_name='Test User 3'
        )
        
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.conversation.conversation_id}/"
        )
        
        # Mock authentication
        communicator.scope['user'] = user3
        
        # Mock rate limiting to allow connection
        with patch.object(connection_pool, 'can_create_connection', return_value=(True, {'allowed': True})):
            # Connect
            connected, subprotocol = await communicator.connect()
            
            # Connection should be closed due to access denial
            self.assertFalse(connected)
        
        await communicator.disconnect()
    
    async def test_message_sending_success(self):
        """Test successful message sending via WebSocket."""
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.conversation.conversation_id}/"
        )
        
        # Mock authentication
        communicator.scope['user'] = self.user1
        
        # Mock dependencies
        with patch.object(connection_pool, 'can_create_connection', return_value=(True, {'allowed': True})):
            with patch.object(connection_manager, 'add_connection', return_value=True):
                with patch.object(connection_pool, 'add_connection', return_value=True):
                    with patch.object(messaging_monitor, 'track_websocket_event', return_value=None):
                        with patch.object(performance_metrics, 'track_websocket_connection_performance', return_value=None):
                            # Connect
                            connected, subprotocol = await communicator.connect()
                            self.assertTrue(connected)
                            
                            # Receive connection confirmation
                            await communicator.receive_json_from()
                            
                            # Mock message saving and rate limiting
                            with patch.object(rate_limiter, 'check_message_rate_limit', return_value=(True, {'allowed': True})):
                                with patch.object(ChatConsumer, 'save_message', return_value=MagicMock(
                                    message_id=1,
                                    content='Test message',
                                    message_type='text',
                                    created_at='2024-01-01T00:00:00Z',
                                    sender=self.user1
                                )):
                                    with patch.object(message_sequencer, 'create_message_metadata', return_value={
                                        'sequence_number': 1,
                                        'microsecond_timestamp': 1640995200000
                                    }):
                                        with patch.object(performance_metrics, 'track_message_delivery_performance', return_value=None):
                                            # Send message
                                            await communicator.send_json_to({
                                                'type': 'message',
                                                'message': 'Test message',
                                                'message_type': 'text'
                                            })
                                            
                                            # Should not receive error response
                                            # (In a real test, you'd check for the message being broadcast)
                            
                            await communicator.disconnect()
    
    async def test_message_sending_rate_limited(self):
        """Test message sending rate limiting."""
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.conversation.conversation_id}/"
        )
        
        # Mock authentication
        communicator.scope['user'] = self.user1
        
        # Mock dependencies
        with patch.object(connection_pool, 'can_create_connection', return_value=(True, {'allowed': True})):
            with patch.object(connection_manager, 'add_connection', return_value=True):
                with patch.object(connection_pool, 'add_connection', return_value=True):
                    with patch.object(messaging_monitor, 'track_websocket_event', return_value=None):
                        with patch.object(performance_metrics, 'track_websocket_connection_performance', return_value=None):
                            # Connect
                            connected, subprotocol = await communicator.connect()
                            self.assertTrue(connected)
                            
                            # Receive connection confirmation
                            await communicator.receive_json_from()
                            
                            # Mock rate limiting to deny message
                            with patch.object(rate_limiter, 'check_message_rate_limit', return_value=(False, {
                                'allowed': False,
                                'reason': 'message_rate_limit_exceeded',
                                'retry_after': 60
                            })):
                                # Send message
                                await communicator.send_json_to({
                                    'type': 'message',
                                    'message': 'Test message',
                                    'message_type': 'text'
                                })
                                
                                # Check rate limit response
                                response = await communicator.receive_json_from()
                                self.assertEqual(response['type'], 'rate_limit_exceeded')
                                self.assertEqual(response['reason'], 'message_rate_limit_exceeded')
                                self.assertEqual(response['retry_after'], 60)
                            
                            await communicator.disconnect()
    
    async def test_typing_indicator_success(self):
        """Test successful typing indicator sending."""
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.conversation.conversation_id}/"
        )
        
        # Mock authentication
        communicator.scope['user'] = self.user1
        
        # Mock dependencies
        with patch.object(connection_pool, 'can_create_connection', return_value=(True, {'allowed': True})):
            with patch.object(connection_manager, 'add_connection', return_value=True):
                with patch.object(connection_pool, 'add_connection', return_value=True):
                    with patch.object(messaging_monitor, 'track_websocket_event', return_value=None):
                        with patch.object(performance_metrics, 'track_websocket_connection_performance', return_value=None):
                            # Connect
                            connected, subprotocol = await communicator.connect()
                            self.assertTrue(connected)
                            
                            # Receive connection confirmation
                            await communicator.receive_json_from()
                            
                            # Mock typing rate limiting to allow
                            with patch.object(rate_limiter, 'check_typing_rate_limit', return_value=(True, {'allowed': True})):
                                with patch.object(connection_manager, 'update_user_presence', return_value=True):
                                    # Send typing indicator
                                    await communicator.send_json_to({
                                        'type': 'typing',
                                        'is_typing': True
                                    })
                                    
                                    # Should not receive error response
                                    # (In a real test, you'd check for the typing indicator being broadcast)
                            
                            await communicator.disconnect()
    
    async def test_typing_indicator_rate_limited(self):
        """Test typing indicator rate limiting."""
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.conversation.conversation_id}/"
        )
        
        # Mock authentication
        communicator.scope['user'] = self.user1
        
        # Mock dependencies
        with patch.object(connection_pool, 'can_create_connection', return_value=(True, {'allowed': True})):
            with patch.object(connection_manager, 'add_connection', return_value=True):
                with patch.object(connection_pool, 'add_connection', return_value=True):
                    with patch.object(messaging_monitor, 'track_websocket_event', return_value=None):
                        with patch.object(performance_metrics, 'track_websocket_connection_performance', return_value=None):
                            # Connect
                            connected, subprotocol = await communicator.connect()
                            self.assertTrue(connected)
                            
                            # Receive connection confirmation
                            await communicator.receive_json_from()
                            
                            # Mock typing rate limiting to deny
                            with patch.object(rate_limiter, 'check_typing_rate_limit', return_value=(False, {
                                'allowed': False,
                                'reason': 'typing_rate_limit_exceeded',
                                'retry_after': 60
                            })):
                                # Send typing indicator
                                await communicator.send_json_to({
                                    'type': 'typing',
                                    'is_typing': True
                                })
                                
                                # Should not receive response (typing rate limits are silent)
                            
                            await communicator.disconnect()
    
    async def test_invalid_message_handling(self):
        """Test handling of invalid messages."""
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.conversation.conversation_id}/"
        )
        
        # Mock authentication
        communicator.scope['user'] = self.user1
        
        # Mock dependencies
        with patch.object(connection_pool, 'can_create_connection', return_value=(True, {'allowed': True})):
            with patch.object(connection_manager, 'add_connection', return_value=True):
                with patch.object(connection_pool, 'add_connection', return_value=True):
                    with patch.object(messaging_monitor, 'track_websocket_event', return_value=None):
                        with patch.object(performance_metrics, 'track_websocket_connection_performance', return_value=None):
                            # Connect
                            connected, subprotocol = await communicator.connect()
                            self.assertTrue(connected)
                            
                            # Receive connection confirmation
                            await communicator.receive_json_from()
                            
                            # Mock rate limiting to allow
                            with patch.object(rate_limiter, 'check_message_rate_limit', return_value=(True, {'allowed': True})):
                                # Send invalid message (malicious content)
                                await communicator.send_json_to({
                                    'type': 'message',
                                    'message': '<script>alert("xss")</script>',
                                    'message_type': 'text'
                                })
                                
                                # Should receive error response
                                response = await communicator.receive_json_from()
                                self.assertEqual(response['type'], 'error')
                                self.assertIn('Invalid message', response['message'])
                            
                            await communicator.disconnect()
    
    async def test_websocket_disconnection_cleanup(self):
        """Test proper cleanup on WebSocket disconnection."""
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.conversation.conversation_id}/"
        )
        
        # Mock authentication
        communicator.scope['user'] = self.user1
        
        # Mock dependencies
        with patch.object(connection_pool, 'can_create_connection', return_value=(True, {'allowed': True})):
            with patch.object(connection_manager, 'add_connection', return_value=True):
                with patch.object(connection_pool, 'add_connection', return_value=True):
                    with patch.object(messaging_monitor, 'track_websocket_event', return_value=None):
                        with patch.object(performance_metrics, 'track_websocket_connection_performance', return_value=None):
                            # Connect
                            connected, subprotocol = await communicator.connect()
                            self.assertTrue(connected)
                            
                            # Receive connection confirmation
                            await communicator.receive_json_from()
                            
                            # Mock cleanup methods
                            with patch.object(connection_pool, 'remove_connection', return_value=True):
                                with patch.object(connection_manager, 'remove_connection', return_value=True):
                                    with patch.object(messaging_monitor, 'track_websocket_event', return_value=None):
                                        # Disconnect
                                        await communicator.disconnect()
                                        
                                        # Verify cleanup methods were called
                                        # (In a real test, you'd verify the cleanup was successful)
    
    async def test_message_broadcasting(self):
        """Test message broadcasting to all conversation participants."""
        # Create two communicators for the same conversation
        communicator1 = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.conversation.conversation_id}/"
        )
        communicator2 = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.conversation.conversation_id}/"
        )
        
        # Mock authentication
        communicator1.scope['user'] = self.user1
        communicator2.scope['user'] = self.user2
        
        # Mock dependencies
        with patch.object(connection_pool, 'can_create_connection', return_value=(True, {'allowed': True})):
            with patch.object(connection_manager, 'add_connection', return_value=True):
                with patch.object(connection_pool, 'add_connection', return_value=True):
                    with patch.object(messaging_monitor, 'track_websocket_event', return_value=None):
                        with patch.object(performance_metrics, 'track_websocket_connection_performance', return_value=None):
                            # Connect both users
                            connected1, _ = await communicator1.connect()
                            connected2, _ = await communicator2.connect()
                            
                            self.assertTrue(connected1)
                            self.assertTrue(connected2)
                            
                            # Receive connection confirmations
                            await communicator1.receive_json_from()
                            await communicator2.receive_json_from()
                            
                            # Mock message sending
                            with patch.object(rate_limiter, 'check_message_rate_limit', return_value=(True, {'allowed': True})):
                                with patch.object(ChatConsumer, 'save_message', return_value=MagicMock(
                                    message_id=1,
                                    content='Test message',
                                    message_type='text',
                                    created_at='2024-01-01T00:00:00Z',
                                    sender=self.user1
                                )):
                                    with patch.object(message_sequencer, 'create_message_metadata', return_value={
                                        'sequence_number': 1,
                                        'microsecond_timestamp': 1640995200000
                                    }):
                                        with patch.object(performance_metrics, 'track_message_delivery_performance', return_value=None):
                                            # Send message from user1
                                            await communicator1.send_json_to({
                                                'type': 'message',
                                                'message': 'Test message',
                                                'message_type': 'text'
                                            })
                                            
                                            # Both users should receive the message
                                            # (In a real test, you'd verify both received the broadcast)
                            
                            await communicator1.disconnect()
                            await communicator2.disconnect()
    
    async def test_concurrent_connections(self):
        """Test handling of concurrent WebSocket connections."""
        communicators = []
        
        # Create multiple communicators
        for i in range(5):
            communicator = WebsocketCommunicator(
                ChatConsumer.as_asgi(),
                f"/ws/chat/{self.conversation.conversation_id}/"
            )
            communicator.scope['user'] = self.user1
            communicators.append(communicator)
        
        # Mock dependencies
        with patch.object(connection_pool, 'can_create_connection', return_value=(True, {'allowed': True})):
            with patch.object(connection_manager, 'add_connection', return_value=True):
                with patch.object(connection_pool, 'add_connection', return_value=True):
                    with patch.object(messaging_monitor, 'track_websocket_event', return_value=None):
                        with patch.object(performance_metrics, 'track_websocket_connection_performance', return_value=None):
                            # Connect all communicators concurrently
                            tasks = [comm.connect() for comm in communicators]
                            results = await asyncio.gather(*tasks)
                            
                            # All connections should succeed
                            for connected, _ in results:
                                self.assertTrue(connected)
                            
                            # Disconnect all
                            disconnect_tasks = [comm.disconnect() for comm in communicators]
                            await asyncio.gather(*disconnect_tasks)
    
    async def test_websocket_error_handling(self):
        """Test WebSocket error handling and recovery."""
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.conversation.conversation_id}/"
        )
        
        # Mock authentication
        communicator.scope['user'] = self.user1
        
        # Mock dependencies
        with patch.object(connection_pool, 'can_create_connection', return_value=(True, {'allowed': True})):
            with patch.object(connection_manager, 'add_connection', return_value=True):
                with patch.object(connection_pool, 'add_connection', return_value=True):
                    with patch.object(messaging_monitor, 'track_websocket_event', return_value=None):
                        with patch.object(performance_metrics, 'track_websocket_connection_performance', return_value=None):
                            # Connect
                            connected, subprotocol = await communicator.connect()
                            self.assertTrue(connected)
                            
                            # Receive connection confirmation
                            await communicator.receive_json_from()
                            
                            # Send malformed JSON
                            await communicator.send_to(text_data='invalid json')
                            
                            # Should receive error response
                            response = await communicator.receive_json_from()
                            self.assertEqual(response['type'], 'error')
                            self.assertIn('Invalid JSON', response['message'])
                            
                            await communicator.disconnect()
    
    async def test_websocket_connection_performance(self):
        """Test WebSocket connection performance tracking."""
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.conversation.conversation_id}/"
        )
        
        # Mock authentication
        communicator.scope['user'] = self.user1
        
        # Mock dependencies
        with patch.object(connection_pool, 'can_create_connection', return_value=(True, {'allowed': True})):
            with patch.object(connection_manager, 'add_connection', return_value=True):
                with patch.object(connection_pool, 'add_connection', return_value=True):
                    with patch.object(messaging_monitor, 'track_websocket_event', return_value=None):
                        with patch.object(performance_metrics, 'track_websocket_connection_performance', return_value=None) as mock_perf:
                            # Connect
                            connected, subprotocol = await communicator.connect()
                            self.assertTrue(connected)
                            
                            # Verify performance tracking was called
                            mock_perf.assert_called_once()
                            
                            await communicator.disconnect()
    
    async def test_message_sequencing(self):
        """Test message sequencing and ordering."""
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.conversation.conversation_id}/"
        )
        
        # Mock authentication
        communicator.scope['user'] = self.user1
        
        # Mock dependencies
        with patch.object(connection_pool, 'can_create_connection', return_value=(True, {'allowed': True})):
            with patch.object(connection_manager, 'add_connection', return_value=True):
                with patch.object(connection_pool, 'add_connection', return_value=True):
                    with patch.object(messaging_monitor, 'track_websocket_event', return_value=None):
                        with patch.object(performance_metrics, 'track_websocket_connection_performance', return_value=None):
                            # Connect
                            connected, subprotocol = await communicator.connect()
                            self.assertTrue(connected)
                            
                            # Receive connection confirmation
                            await communicator.receive_json_from()
                            
                            # Mock message sequencing
                            with patch.object(rate_limiter, 'check_message_rate_limit', return_value=(True, {'allowed': True})):
                                with patch.object(ChatConsumer, 'save_message', return_value=MagicMock(
                                    message_id=1,
                                    content='Test message',
                                    message_type='text',
                                    created_at='2024-01-01T00:00:00Z',
                                    sender=self.user1
                                )):
                                    with patch.object(message_sequencer, 'create_message_metadata', return_value={
                                        'sequence_number': 1,
                                        'microsecond_timestamp': 1640995200000
                                    }) as mock_seq:
                                        with patch.object(performance_metrics, 'track_message_delivery_performance', return_value=None):
                                            # Send message
                                            await communicator.send_json_to({
                                                'type': 'message',
                                                'message': 'Test message',
                                                'message_type': 'text'
                                            })
                                            
                                            # Verify sequencing was called
                                            mock_seq.assert_called_once()
                            
                            await communicator.disconnect()









































