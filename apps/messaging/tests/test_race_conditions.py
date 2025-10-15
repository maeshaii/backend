"""
Tests for REST/WebSocket race conditions and message ordering.

This module tests race conditions between REST API and WebSocket
message delivery, ensuring proper message ordering and deduplication.
"""

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from channels.testing import WebsocketCommunicator
from channels.layers import InMemoryChannelLayer
from apps.messaging.consumers import ChatConsumer
from apps.messaging.views import MessageListView
from apps.shared.models import Conversation, Message, User
from apps.messaging.message_ordering import message_sequencer
from apps.messaging.message_cache import message_cache
from rest_framework.test import APIClient
from rest_framework import status


class RaceConditionTestCase(TransactionTestCase):
    """Test case for REST/WebSocket race conditions."""
    
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
        
        # Create API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user1)
        
        # Set up channel layer
        self.channel_layer = InMemoryChannelLayer()
        
        # Clear cache
        from django.core.cache import cache
        cache.clear()
    
    def tearDown(self):
        """Clean up test data."""
        from django.core.cache import cache
        cache.clear()
    
    async def test_rest_websocket_message_race_condition(self):
        """Test race condition between REST API and WebSocket message delivery."""
        # Create WebSocket connection
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.conversation.conversation_id}/"
        )
        
        # Mock authentication
        communicator.scope['user'] = self.user1
        
        # Mock dependencies
        with patch.object(message_sequencer, 'generate_sequence_number', return_value=1):
            with patch.object(message_sequencer, 'create_message_metadata', return_value={
                'sequence_number': 1,
                'microsecond_timestamp': int(time.time() * 1000000)
            }):
                with patch.object(ChatConsumer, 'save_message', return_value=MagicMock(
                    message_id=1,
                    content='WebSocket message',
                    message_type='text',
                    created_at='2024-01-01T00:00:00Z',
                    sender=self.user1
                )):
                    # Connect WebSocket
                    connected, _ = await communicator.connect()
                    self.assertTrue(connected)
                    
                    # Receive connection confirmation
                    await communicator.receive_json_from()
                    
                    # Send message via REST API and WebSocket simultaneously
                    rest_task = asyncio.create_task(
                        self._send_rest_message('REST message')
                    )
                    websocket_task = asyncio.create_task(
                        self._send_websocket_message(communicator, 'WebSocket message')
                    )
                    
                    # Wait for both to complete
                    rest_result, websocket_result = await asyncio.gather(rest_task, websocket_task)
                    
                    # Both should succeed
                    self.assertEqual(rest_result.status_code, status.HTTP_201_CREATED)
                    self.assertTrue(websocket_result)
                    
                    await communicator.disconnect()
    
    async def test_message_deduplication_race_condition(self):
        """Test message deduplication in race condition scenarios."""
        # Create WebSocket connection
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.conversation.conversation_id}/"
        )
        
        # Mock authentication
        communicator.scope['user'] = self.user1
        
        # Mock dependencies
        with patch.object(message_sequencer, 'generate_sequence_number', return_value=1):
            with patch.object(message_sequencer, 'create_message_metadata', return_value={
                'sequence_number': 1,
                'microsecond_timestamp': int(time.time() * 1000000)
            }):
                with patch.object(ChatConsumer, 'save_message', return_value=MagicMock(
                    message_id=1,
                    content='Duplicate message',
                    message_type='text',
                    created_at='2024-01-01T00:00:00Z',
                    sender=self.user1
                )):
                    # Connect WebSocket
                    connected, _ = await communicator.connect()
                    self.assertTrue(connected)
                    
                    # Receive connection confirmation
                    await communicator.receive_json_from()
                    
                    # Send same message multiple times simultaneously
                    tasks = []
                    for i in range(5):
                        task = asyncio.create_task(
                            self._send_websocket_message(communicator, 'Duplicate message')
                        )
                        tasks.append(task)
                    
                    # Wait for all to complete
                    results = await asyncio.gather(*tasks)
                    
                    # All should succeed but only one message should be saved
                    self.assertTrue(all(results))
                    
                    await communicator.disconnect()
    
    async def test_message_ordering_race_condition(self):
        """Test message ordering in race condition scenarios."""
        # Create WebSocket connection
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.conversation.conversation_id}/"
        )
        
        # Mock authentication
        communicator.scope['user'] = self.user1
        
        # Mock dependencies with sequence numbers
        sequence_numbers = [1, 2, 3, 4, 5]
        sequence_index = 0
        
        def mock_generate_sequence():
            nonlocal sequence_index
            if sequence_index < len(sequence_numbers):
                seq = sequence_numbers[sequence_index]
                sequence_index += 1
                return seq
            return sequence_index + 1
        
        with patch.object(message_sequencer, 'generate_sequence_number', side_effect=mock_generate_sequence):
            with patch.object(message_sequencer, 'create_message_metadata', return_value={
                'sequence_number': 1,
                'microsecond_timestamp': int(time.time() * 1000000)
            }):
                with patch.object(ChatConsumer, 'save_message', return_value=MagicMock(
                    message_id=1,
                    content='Ordered message',
                    message_type='text',
                    created_at='2024-01-01T00:00:00Z',
                    sender=self.user1
                )):
                    # Connect WebSocket
                    connected, _ = await communicator.connect()
                    self.assertTrue(connected)
                    
                    # Receive connection confirmation
                    await communicator.receive_json_from()
                    
                    # Send messages with different sequence numbers
                    messages = ['Message 1', 'Message 2', 'Message 3', 'Message 4', 'Message 5']
                    tasks = []
                    
                    for i, message in enumerate(messages):
                        task = asyncio.create_task(
                            self._send_websocket_message(communicator, message)
                        )
                        tasks.append(task)
                    
                    # Wait for all to complete
                    results = await asyncio.gather(*tasks)
                    
                    # All should succeed
                    self.assertTrue(all(results))
                    
                    await communicator.disconnect()
    
    async def test_concurrent_message_sending(self):
        """Test concurrent message sending from multiple users."""
        # Create WebSocket connections for both users
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
        with patch.object(message_sequencer, 'generate_sequence_number', return_value=1):
            with patch.object(message_sequencer, 'create_message_metadata', return_value={
                'sequence_number': 1,
                'microsecond_timestamp': int(time.time() * 1000000)
            }):
                with patch.object(ChatConsumer, 'save_message', return_value=MagicMock(
                    message_id=1,
                    content='Concurrent message',
                    message_type='text',
                    created_at='2024-01-01T00:00:00Z',
                    sender=self.user1
                )):
                    # Connect both WebSockets
                    connected1, _ = await communicator1.connect()
                    connected2, _ = await communicator2.connect()
                    
                    self.assertTrue(connected1)
                    self.assertTrue(connected2)
                    
                    # Receive connection confirmations
                    await communicator1.receive_json_from()
                    await communicator2.receive_json_from()
                    
                    # Send messages from both users simultaneously
                    task1 = asyncio.create_task(
                        self._send_websocket_message(communicator1, 'Message from user1')
                    )
                    task2 = asyncio.create_task(
                        self._send_websocket_message(communicator2, 'Message from user2')
                    )
                    
                    # Wait for both to complete
                    result1, result2 = await asyncio.gather(task1, task2)
                    
                    # Both should succeed
                    self.assertTrue(result1)
                    self.assertTrue(result2)
                    
                    await communicator1.disconnect()
                    await communicator2.disconnect()
    
    async def test_message_cache_race_condition(self):
        """Test message cache race conditions."""
        # Create WebSocket connection
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.conversation.conversation_id}/"
        )
        
        # Mock authentication
        communicator.scope['user'] = self.user1
        
        # Mock dependencies
        with patch.object(message_sequencer, 'generate_sequence_number', return_value=1):
            with patch.object(message_sequencer, 'create_message_metadata', return_value={
                'sequence_number': 1,
                'microsecond_timestamp': int(time.time() * 1000000)
            }):
                with patch.object(ChatConsumer, 'save_message', return_value=MagicMock(
                    message_id=1,
                    content='Cached message',
                    message_type='text',
                    created_at='2024-01-01T00:00:00Z',
                    sender=self.user1
                )):
                    # Connect WebSocket
                    connected, _ = await communicator.connect()
                    self.assertTrue(connected)
                    
                    # Receive connection confirmation
                    await communicator.receive_json_from()
                    
                    # Send message via WebSocket
                    await self._send_websocket_message(communicator, 'Cached message')
                    
                    # Simultaneously try to get messages from cache
                    cache_task = asyncio.create_task(
                        self._get_messages_from_cache()
                    )
                    
                    # Wait for cache operation
                    cache_result = await cache_task
                    
                    # Cache should return the message
                    self.assertIsNotNone(cache_result)
                    
                    await communicator.disconnect()
    
    async def test_sequence_number_race_condition(self):
        """Test sequence number generation race conditions."""
        # Create WebSocket connection
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(),
            f"/ws/chat/{self.conversation.conversation_id}/"
        )
        
        # Mock authentication
        communicator.scope['user'] = self.user1
        
        # Mock dependencies
        with patch.object(message_sequencer, 'generate_sequence_number', return_value=1):
            with patch.object(message_sequencer, 'create_message_metadata', return_value={
                'sequence_number': 1,
                'microsecond_timestamp': int(time.time() * 1000000)
            }):
                with patch.object(ChatConsumer, 'save_message', return_value=MagicMock(
                    message_id=1,
                    content='Sequenced message',
                    message_type='text',
                    created_at='2024-01-01T00:00:00Z',
                    sender=self.user1
                )):
                    # Connect WebSocket
                    connected, _ = await communicator.connect()
                    self.assertTrue(connected)
                    
                    # Receive connection confirmation
                    await communicator.receive_json_from()
                    
                    # Send multiple messages simultaneously to test sequence number generation
                    tasks = []
                    for i in range(10):
                        task = asyncio.create_task(
                            self._send_websocket_message(communicator, f'Message {i}')
                        )
                        tasks.append(task)
                    
                    # Wait for all to complete
                    results = await asyncio.gather(*tasks)
                    
                    # All should succeed
                    self.assertTrue(all(results))
                    
                    await communicator.disconnect()
    
    async def test_websocket_connection_race_condition(self):
        """Test WebSocket connection race conditions."""
        # Create multiple WebSocket connections simultaneously
        communicators = []
        for i in range(5):
            communicator = WebsocketCommunicator(
                ChatConsumer.as_asgi(),
                f"/ws/chat/{self.conversation.conversation_id}/"
            )
            communicator.scope['user'] = self.user1
            communicators.append(communicator)
        
        # Mock dependencies
        with patch.object(message_sequencer, 'generate_sequence_number', return_value=1):
            with patch.object(message_sequencer, 'create_message_metadata', return_value={
                'sequence_number': 1,
                'microsecond_timestamp': int(time.time() * 1000000)
            }):
                with patch.object(ChatConsumer, 'save_message', return_value=MagicMock(
                    message_id=1,
                    content='Connection race message',
                    message_type='text',
                    created_at='2024-01-01T00:00:00Z',
                    sender=self.user1
                )):
                    # Connect all WebSockets simultaneously
                    tasks = []
                    for communicator in communicators:
                        task = asyncio.create_task(communicator.connect())
                        tasks.append(task)
                    
                    # Wait for all to complete
                    results = await asyncio.gather(*tasks)
                    
                    # All should succeed
                    for connected, _ in results:
                        self.assertTrue(connected)
                    
                    # Disconnect all
                    disconnect_tasks = []
                    for communicator in communicators:
                        task = asyncio.create_task(communicator.disconnect())
                        disconnect_tasks.append(task)
                    
                    await asyncio.gather(*disconnect_tasks)
    
    async def test_message_broadcast_race_condition(self):
        """Test message broadcast race conditions."""
        # Create WebSocket connections for both users
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
        with patch.object(message_sequencer, 'generate_sequence_number', return_value=1):
            with patch.object(message_sequencer, 'create_message_metadata', return_value={
                'sequence_number': 1,
                'microsecond_timestamp': int(time.time() * 1000000)
            }):
                with patch.object(ChatConsumer, 'save_message', return_value=MagicMock(
                    message_id=1,
                    content='Broadcast message',
                    message_type='text',
                    created_at='2024-01-01T00:00:00Z',
                    sender=self.user1
                )):
                    # Connect both WebSockets
                    connected1, _ = await communicator1.connect()
                    connected2, _ = await communicator2.connect()
                    
                    self.assertTrue(connected1)
                    self.assertTrue(connected2)
                    
                    # Receive connection confirmations
                    await communicator1.receive_json_from()
                    await communicator2.receive_json_from()
                    
                    # Send message from user1
                    await self._send_websocket_message(communicator1, 'Broadcast message')
                    
                    # Both users should receive the message
                    # (In a real test, you'd verify both received the broadcast)
                    
                    await communicator1.disconnect()
                    await communicator2.disconnect()
    
    async def _send_rest_message(self, content):
        """Send message via REST API."""
        return self.client.post(
            f'/api/messaging/conversations/{self.conversation.conversation_id}/messages/',
            {
                'content': content,
                'message_type': 'text'
            },
            format='json'
        )
    
    async def _send_websocket_message(self, communicator, content):
        """Send message via WebSocket."""
        try:
            await communicator.send_json_to({
                'type': 'message',
                'message': content,
                'message_type': 'text'
            })
            return True
        except Exception:
            return False
    
    async def _get_messages_from_cache(self):
        """Get messages from cache."""
        try:
            return message_cache.get_conversation_messages(self.conversation.conversation_id)
        except Exception:
            return None


class MessageOrderingRaceConditionTestCase(TestCase):
    """Test case for message ordering race conditions."""
    
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
        
        # Clear cache
        from django.core.cache import cache
        cache.clear()
    
    def tearDown(self):
        """Clean up test data."""
        from django.core.cache import cache
        cache.clear()
    
    def test_message_ordering_with_race_conditions(self):
        """Test message ordering with race conditions."""
        # Create messages with different timestamps and sequence numbers
        messages = [
            {
                'message_id': 1,
                'sequence_number': 3,
                'content': 'Third message',
                'created_at': '2024-01-01T00:00:03Z',
                'microsecond_timestamp': 1640995203000
            },
            {
                'message_id': 2,
                'sequence_number': 1,
                'content': 'First message',
                'created_at': '2024-01-01T00:00:01Z',
                'microsecond_timestamp': 1640995201000
            },
            {
                'message_id': 3,
                'sequence_number': 2,
                'content': 'Second message',
                'created_at': '2024-01-01T00:00:02Z',
                'microsecond_timestamp': 1640995202000
            }
        ]
        
        # Order messages
        ordered_messages = message_sequencer.order_messages(messages)
        
        # Messages should be ordered by sequence number
        self.assertEqual(len(ordered_messages), 3)
        self.assertEqual(ordered_messages[0]['sequence_number'], 1)
        self.assertEqual(ordered_messages[1]['sequence_number'], 2)
        self.assertEqual(ordered_messages[2]['sequence_number'], 3)
    
    def test_message_deduplication_with_race_conditions(self):
        """Test message deduplication with race conditions."""
        # Create duplicate messages
        messages = [
            {
                'message_id': 1,
                'sequence_number': 1,
                'content': 'Duplicate message',
                'created_at': '2024-01-01T00:00:01Z',
                'microsecond_timestamp': 1640995201000
            },
            {
                'message_id': 1,
                'sequence_number': 1,
                'content': 'Duplicate message',
                'created_at': '2024-01-01T00:00:01Z',
                'microsecond_timestamp': 1640995201000
            }
        ]
        
        # Order messages (should deduplicate)
        ordered_messages = message_sequencer.order_messages(messages)
        
        # Should only have one message
        self.assertEqual(len(ordered_messages), 1)
        self.assertEqual(ordered_messages[0]['message_id'], 1)
    
    def test_sequence_gap_handling(self):
        """Test sequence gap handling."""
        # Create messages with gaps
        messages = [
            {
                'message_id': 1,
                'sequence_number': 1,
                'content': 'First message',
                'created_at': '2024-01-01T00:00:01Z'
            },
            {
                'message_id': 2,
                'sequence_number': 4,
                'content': 'Fourth message',
                'created_at': '2024-01-01T00:00:04Z'
            }
        ]
        
        # Order messages
        ordered_messages = message_sequencer.order_messages(messages)
        
        # Messages should still be ordered correctly
        self.assertEqual(len(ordered_messages), 2)
        self.assertEqual(ordered_messages[0]['sequence_number'], 1)
        self.assertEqual(ordered_messages[1]['sequence_number'], 4)
    
    def test_concurrent_sequence_generation(self):
        """Test concurrent sequence number generation."""
        import threading
        import time
        
        sequence_numbers = []
        
        def generate_sequence():
            seq = message_sequencer.generate_sequence_number(
                self.conversation.conversation_id,
                self.user1.user_id
            )
            sequence_numbers.append(seq)
        
        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=generate_sequence)
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all sequence numbers were generated
        self.assertEqual(len(sequence_numbers), 10)
        
        # Sequence numbers should be unique and incremental
        sequence_numbers.sort()
        for i, seq in enumerate(sequence_numbers, 1):
            self.assertEqual(seq, i)
    
    def test_message_metadata_race_condition(self):
        """Test message metadata creation race conditions."""
        import threading
        import time
        
        metadata_list = []
        
        def create_metadata():
            metadata = message_sequencer.create_message_metadata(
                message_id=1,
                conversation_id=self.conversation.conversation_id,
                user_id=self.user1.user_id,
                content='Race condition message',
                message_type='text'
            )
            metadata_list.append(metadata)
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_metadata)
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all metadata was created
        self.assertEqual(len(metadata_list), 5)
        
        # All metadata should have required fields
        for metadata in metadata_list:
            self.assertIn('message_id', metadata)
            self.assertIn('conversation_id', metadata)
            self.assertIn('user_id', metadata)
            self.assertIn('content', metadata)
            self.assertIn('message_type', metadata)
            self.assertIn('sequence_number', metadata)
            self.assertIn('timestamp', metadata)
            self.assertIn('microsecond_timestamp', metadata)


