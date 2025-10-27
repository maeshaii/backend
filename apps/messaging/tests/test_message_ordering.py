"""
Tests for message ordering and sequencing functionality.

This module tests message sequencing, race condition handling,
and chronological ordering logic.
"""

import json
from unittest.mock import patch
from django.test import TestCase
from django.core.cache import cache
from django.contrib.auth import get_user_model
from apps.messaging.message_ordering import MessageSequencer
from apps.shared.models import Conversation, User


class MessageOrderingTestCase(TestCase):
    """Test case for message ordering and sequencing."""
    
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
        
        # Create message sequencer instance
        self.message_sequencer = MessageSequencer()
        
        # Clear cache before each test
        cache.clear()
    
    def tearDown(self):
        """Clean up test data."""
        cache.clear()
    
    def test_sequence_number_generation(self):
        """Test sequence number generation."""
        # Generate sequence numbers
        seq1 = self.message_sequencer.generate_sequence_number(
            self.conversation.conversation_id,
            self.user1.user_id
        )
        seq2 = self.message_sequencer.generate_sequence_number(
            self.conversation.conversation_id,
            self.user1.user_id
        )
        seq3 = self.message_sequencer.generate_sequence_number(
            self.conversation.conversation_id,
            self.user1.user_id
        )
        
        # Sequence numbers should be incremental
        self.assertEqual(seq1, 1)
        self.assertEqual(seq2, 2)
        self.assertEqual(seq3, 3)
        
        # Sequence numbers should be unique
        self.assertNotEqual(seq1, seq2)
        self.assertNotEqual(seq2, seq3)
    
    def test_message_metadata_creation(self):
        """Test message metadata creation with sequencing."""
        message_metadata = self.message_sequencer.create_message_metadata(
            message_id=1,
            conversation_id=self.conversation.conversation_id,
            user_id=self.user1.user_id,
            content='Test message',
            message_type='text'
        )
        
        self.assertIsInstance(message_metadata, dict)
        self.assertEqual(message_metadata['message_id'], 1)
        self.assertEqual(message_metadata['conversation_id'], self.conversation.conversation_id)
        self.assertEqual(message_metadata['user_id'], self.user1.user_id)
        self.assertEqual(message_metadata['content'], 'Test message')
        self.assertEqual(message_metadata['message_type'], 'text')
        self.assertIn('sequence_number', message_metadata)
        self.assertIn('timestamp', message_metadata)
        self.assertIn('microsecond_timestamp', message_metadata)
    
    def test_message_ordering_by_sequence(self):
        """Test message ordering by sequence number."""
        # Create messages with different sequence numbers
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
        ordered_messages = self.message_sequencer.order_messages(messages)
        
        # Messages should be ordered by sequence number
        self.assertEqual(len(ordered_messages), 3)
        self.assertEqual(ordered_messages[0]['sequence_number'], 1)
        self.assertEqual(ordered_messages[1]['sequence_number'], 2)
        self.assertEqual(ordered_messages[2]['sequence_number'], 3)
    
    def test_message_ordering_by_timestamp_fallback(self):
        """Test message ordering by timestamp when sequence numbers are missing."""
        # Create messages without sequence numbers
        messages = [
            {
                'message_id': 1,
                'content': 'Third message',
                'created_at': '2024-01-01T00:00:03Z',
                'microsecond_timestamp': 1640995203000
            },
            {
                'message_id': 2,
                'content': 'First message',
                'created_at': '2024-01-01T00:00:01Z',
                'microsecond_timestamp': 1640995201000
            },
            {
                'message_id': 3,
                'content': 'Second message',
                'created_at': '2024-01-01T00:00:02Z',
                'microsecond_timestamp': 1640995202000
            }
        ]
        
        # Order messages
        ordered_messages = self.message_sequencer.order_messages(messages)
        
        # Messages should be ordered by timestamp
        self.assertEqual(len(ordered_messages), 3)
        self.assertEqual(ordered_messages[0]['message_id'], 2)  # First message
        self.assertEqual(ordered_messages[1]['message_id'], 3)  # Second message
        self.assertEqual(ordered_messages[2]['message_id'], 1)  # Third message
    
    def test_race_condition_handling(self):
        """Test race condition handling between REST and WebSocket."""
        # Simulate race condition scenario
        message_data = {
            'message_id': 1,
            'sequence_number': 1,
            'content': 'Test message',
            'user_id': self.user1.user_id,
            'conversation_id': self.conversation.conversation_id
        }
        
        # First check should be ready
        race_info = self.message_sequencer.handle_race_condition(
            self.conversation.conversation_id,
            message_data
        )
        
        self.assertEqual(race_info['status'], 'ready')
        self.assertEqual(race_info['action'], 'accept')
        
        # Second check with same sequence should be duplicate
        race_info = self.message_sequencer.handle_race_condition(
            self.conversation.conversation_id,
            message_data
        )
        
        self.assertEqual(race_info['status'], 'duplicate')
        self.assertEqual(race_info['action'], 'reject')
    
    def test_sequence_gap_detection(self):
        """Test sequence gap detection."""
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
                'sequence_number': 4,  # Gap: missing 2 and 3
                'content': 'Fourth message',
                'created_at': '2024-01-01T00:00:04Z'
            },
            {
                'message_id': 3,
                'sequence_number': 6,  # Gap: missing 5
                'content': 'Sixth message',
                'created_at': '2024-01-01T00:00:06Z'
            }
        ]
        
        # Order messages (should detect gaps)
        ordered_messages = self.message_sequencer.order_messages(messages)
        
        # Messages should still be ordered correctly
        self.assertEqual(len(ordered_messages), 3)
        self.assertEqual(ordered_messages[0]['sequence_number'], 1)
        self.assertEqual(ordered_messages[1]['sequence_number'], 4)
        self.assertEqual(ordered_messages[2]['sequence_number'], 6)
    
    def test_sequence_gap_resolution(self):
        """Test sequence gap resolution."""
        # Try to resolve a gap
        missing_messages = self.message_sequencer.resolve_sequence_gap(
            self.conversation.conversation_id,
            2  # Expected sequence number
        )
        
        # Should return empty list (no missing messages found)
        self.assertIsInstance(missing_messages, list)
        self.assertEqual(len(missing_messages), 0)
    
    def test_duplicate_message_detection(self):
        """Test duplicate message detection."""
        # Create message data
        message_data = {
            'message_id': 1,
            'sequence_number': 1,
            'content': 'Test message',
            'user_id': self.user1.user_id,
            'conversation_id': self.conversation.conversation_id
        }
        
        # First message should not be duplicate
        race_info = self.message_sequencer.handle_race_condition(
            self.conversation.conversation_id,
            message_data
        )
        self.assertEqual(race_info['status'], 'ready')
        
        # Same message should be detected as duplicate
        race_info = self.message_sequencer.handle_race_condition(
            self.conversation.conversation_id,
            message_data
        )
        self.assertEqual(race_info['status'], 'duplicate')
    
    def test_pending_message_handling(self):
        """Test pending message handling."""
        # Create message with higher sequence number
        message_data = {
            'message_id': 1,
            'sequence_number': 3,  # Higher sequence number
            'content': 'Test message',
            'user_id': self.user1.user_id,
            'conversation_id': self.conversation.conversation_id
        }
        
        # Should detect pending messages
        race_info = self.message_sequencer.handle_race_condition(
            self.conversation.conversation_id,
            message_data
        )
        
        # Should queue the message due to sequence gap
        self.assertEqual(race_info['status'], 'sequence_gap')
        self.assertEqual(race_info['action'], 'queue')
        self.assertTrue(race_info['gap_detected'])
    
    def test_cleanup_old_sequences(self):
        """Test cleanup of old sequence data."""
        # Generate some sequence numbers
        for i in range(5):
            self.message_sequencer.generate_sequence_number(
                self.conversation.conversation_id,
                self.user1.user_id
            )
        
        # Perform cleanup
        cleaned_count = self.message_sequencer.cleanup_old_sequences(
            self.conversation.conversation_id,
            keep_last=2
        )
        
        # Should return 0 (Redis handles TTL cleanup automatically)
        self.assertEqual(cleaned_count, 0)
    
    def test_error_handling(self):
        """Test error handling in message sequencer."""
        # Test with invalid conversation ID
        sequence_number = self.message_sequencer.generate_sequence_number(
            None,
            self.user1.user_id
        )
        
        # Should handle gracefully (fallback to timestamp-based)
        self.assertIsInstance(sequence_number, int)
        self.assertGreater(sequence_number, 0)
    
    def test_concurrent_sequence_generation(self):
        """Test concurrent sequence number generation."""
        import threading
        import time
        
        sequence_numbers = []
        
        def generate_sequence():
            seq = self.message_sequencer.generate_sequence_number(
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
    
    def test_message_ordering_mixed_sequence_timestamp(self):
        """Test message ordering with mixed sequence numbers and timestamps."""
        # Create messages with some having sequence numbers, some not
        messages = [
            {
                'message_id': 1,
                'sequence_number': 2,
                'content': 'Second message',
                'created_at': '2024-01-01T00:00:02Z',
                'microsecond_timestamp': 1640995202000
            },
            {
                'message_id': 2,
                'content': 'First message (no sequence)',
                'created_at': '2024-01-01T00:00:01Z',
                'microsecond_timestamp': 1640995201000
            },
            {
                'message_id': 3,
                'sequence_number': 1,
                'content': 'First message (with sequence)',
                'created_at': '2024-01-01T00:00:01Z',
                'microsecond_timestamp': 1640995201000
            }
        ]
        
        # Order messages
        ordered_messages = self.message_sequencer.order_messages(messages)
        
        # Messages with sequence numbers should be ordered first
        self.assertEqual(len(ordered_messages), 3)
        self.assertEqual(ordered_messages[0]['sequence_number'], 1)
        self.assertEqual(ordered_messages[1]['sequence_number'], 2)
        # Message without sequence number should be last
        self.assertNotIn('sequence_number', ordered_messages[2])
    
    def test_sequence_number_persistence(self):
        """Test sequence number persistence across operations."""
        # Generate sequence numbers
        seq1 = self.message_sequencer.generate_sequence_number(
            self.conversation.conversation_id,
            self.user1.user_id
        )
        seq2 = self.message_sequencer.generate_sequence_number(
            self.conversation.conversation_id,
            self.user1.user_id
        )
        
        # Create new sequencer instance
        new_sequencer = MessageSequencer()
        
        # Generate next sequence number
        seq3 = new_sequencer.generate_sequence_number(
            self.conversation.conversation_id,
            self.user1.user_id
        )
        
        # Sequence should continue from where it left off
        self.assertEqual(seq1, 1)
        self.assertEqual(seq2, 2)
        self.assertEqual(seq3, 3)
    
    def test_message_metadata_validation(self):
        """Test message metadata validation."""
        # Test with invalid message type
        with self.assertRaises(Exception):
            self.message_sequencer.create_message_metadata(
                message_id=1,
                conversation_id=self.conversation.conversation_id,
                user_id=self.user1.user_id,
                content='Test message',
                message_type='invalid_type'
            )
    
    def test_performance_under_load(self):
        """Test performance under load."""
        import time
        
        start_time = time.time()
        
        # Generate many sequence numbers
        for i in range(100):
            self.message_sequencer.generate_sequence_number(
                self.conversation.conversation_id,
                self.user1.user_id
            )
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete within reasonable time (less than 1 second)
        self.assertLess(duration, 1.0)
        
        # Verify sequence numbers are correct
        last_seq = self.message_sequencer.generate_sequence_number(
            self.conversation.conversation_id,
            self.user1.user_id
        )
        self.assertEqual(last_seq, 101)




























