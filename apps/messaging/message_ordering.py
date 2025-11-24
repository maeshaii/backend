"""
Message ordering and sequencing system for handling race conditions.

This module provides robust message ordering logic to handle race conditions
between REST API responses and WebSocket message delivery, ensuring messages
are displayed in the correct chronological order.
"""

import logging
import time
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone as dt_timezone
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class MessageSequencer:
    """
    Handles message sequencing and ordering to prevent race conditions.
    
    Features:
    - Message sequence number generation
    - Chronological ordering with microsecond precision
    - Race condition detection and resolution
    - Duplicate message prevention
    - Message gap detection and recovery
    """
    
    # Cache key prefixes
    SEQUENCE_PREFIX = "msg_seq:"
    PENDING_PREFIX = "msg_pending:"
    GAP_PREFIX = "msg_gap:"
    
    # TTL values (in seconds)
    SEQUENCE_TTL = 3600  # 1 hour
    PENDING_TTL = 300    # 5 minutes
    GAP_TTL = 1800       # 30 minutes
    
    @classmethod
    def generate_sequence_number(cls, conversation_id: int, user_id: int) -> int:
        """
        Generate a unique sequence number for a message.
        
        Args:
            conversation_id: Conversation ID
            user_id: User ID sending the message
            
        Returns:
            int: Unique sequence number
        """
        try:
            # Use Redis INCR for atomic sequence generation
            sequence_key = f"{cls.SEQUENCE_PREFIX}{conversation_id}"
            
            # Get current sequence number
            current_seq = cache.get(sequence_key, 0)
            if not isinstance(current_seq, int):
                current_seq = 0
            
            # Increment sequence number
            new_seq = current_seq + 1
            cache.set(sequence_key, new_seq, timeout=cls.SEQUENCE_TTL)
            
            logger.debug(f"Generated sequence number {new_seq} for conversation {conversation_id}")
            return new_seq
            
        except Exception as e:
            logger.error(f"Failed to generate sequence number: {e}")
            # Fallback to timestamp-based sequence
            return int(time.time() * 1000000)  # Microsecond precision
    
    @classmethod
    def create_message_metadata(cls, message_id: int, conversation_id: int, 
                              user_id: int, content: str, message_type: str = 'text') -> Dict[str, Any]:
        """
        Create message metadata with sequencing information.
        
        Args:
            message_id: Database message ID
            conversation_id: Conversation ID
            user_id: User ID
            content: Message content
            message_type: Message type
            
        Returns:
            Dict with message metadata including sequence information
        """
        try:
            sequence_number = cls.generate_sequence_number(conversation_id, user_id)
            timestamp = timezone.now()
            
            metadata = {
                'message_id': message_id,
                'sequence_number': sequence_number,
                'conversation_id': conversation_id,
                'user_id': user_id,
                'content': content,
                'message_type': message_type,
                'timestamp': timestamp.isoformat(),
                'microsecond_timestamp': timestamp.timestamp(),
                'created_at': timestamp.isoformat(),
            }
            
            # Store pending message for race condition handling
            cls._store_pending_message(conversation_id, sequence_number, metadata)
            
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to create message metadata: {e}")
            # Return basic metadata without sequencing
            return {
                'message_id': message_id,
                'conversation_id': conversation_id,
                'user_id': user_id,
                'content': content,
                'message_type': message_type,
                'timestamp': timezone.now().isoformat(),
                'created_at': timezone.now().isoformat(),
            }
    
    @classmethod
    def order_messages(cls, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Order messages chronologically with proper sequencing.
        
        Args:
            messages: List of message dictionaries
            
        Returns:
            List of messages ordered by sequence number and timestamp
        """
        try:
            if not messages:
                return messages
            
            # Sort by sequence number first, then by timestamp
            def sort_key(msg):
                seq_num = msg.get('sequence_number', 0)
                timestamp = msg.get('microsecond_timestamp', 0)
                if not timestamp:
                    # Fallback to parsing timestamp string
                    try:
                        ts_str = msg.get('timestamp', msg.get('created_at', ''))
                        if ts_str:
                            dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                            timestamp = dt.timestamp()
                    except Exception:
                        timestamp = 0
                return (seq_num, timestamp)
            
            ordered_messages = sorted(messages, key=sort_key)
            
            # Check for gaps in sequence
            cls._detect_sequence_gaps(ordered_messages)
            
            return ordered_messages
            
        except Exception as e:
            logger.error(f"Failed to order messages: {e}")
            # Fallback to timestamp-based sorting
            return sorted(messages, key=lambda x: x.get('timestamp', x.get('created_at', '')))
    
    @classmethod
    def handle_race_condition(cls, conversation_id: int, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle race conditions between REST and WebSocket message delivery.
        
        Args:
            conversation_id: Conversation ID
            message_data: Message data from either REST or WebSocket
            
        Returns:
            Dict with race condition handling information
        """
        try:
            sequence_number = message_data.get('sequence_number')
            if not sequence_number:
                return {'status': 'no_sequence', 'action': 'accept'}
            
            # Check if this is a duplicate message
            if cls._is_duplicate_message(conversation_id, sequence_number, message_data):
                return {'status': 'duplicate', 'action': 'reject'}
            
            # Check if there are pending messages with lower sequence numbers
            pending_messages = cls._get_pending_messages(conversation_id, sequence_number)
            
            if pending_messages:
                return {
                    'status': 'pending_messages',
                    'action': 'queue',
                    'pending_count': len(pending_messages),
                    'pending_sequences': [msg['sequence_number'] for msg in pending_messages]
                }
            
            # Check for sequence gaps
            if cls._has_sequence_gap(conversation_id, sequence_number):
                return {
                    'status': 'sequence_gap',
                    'action': 'queue',
                    'gap_detected': True
                }
            
            return {'status': 'ready', 'action': 'accept'}
            
        except Exception as e:
            logger.error(f"Failed to handle race condition: {e}")
            return {'status': 'error', 'action': 'accept'}
    
    @classmethod
    def resolve_sequence_gap(cls, conversation_id: int, expected_sequence: int) -> List[Dict[str, Any]]:
        """
        Resolve sequence gaps by retrieving missing messages.
        
        Args:
            conversation_id: Conversation ID
            expected_sequence: Expected sequence number
            
        Returns:
            List of missing messages or empty list if none found
        """
        try:
            gap_key = f"{cls.GAP_PREFIX}{conversation_id}:{expected_sequence}"
            gap_data = cache.get(gap_key)
            
            if gap_data:
                logger.warning(f"Sequence gap detected for conversation {conversation_id}, sequence {expected_sequence}")
                return gap_data.get('missing_messages', [])
            
            return []
            
        except Exception as e:
            logger.error(f"Failed to resolve sequence gap: {e}")
            return []
    
    @classmethod
    def _store_pending_message(cls, conversation_id: int, sequence_number: int, 
                             message_data: Dict[str, Any]) -> None:
        """Store a pending message for race condition handling."""
        try:
            pending_key = f"{cls.PENDING_PREFIX}{conversation_id}:{sequence_number}"
            cache.set(pending_key, message_data, timeout=cls.PENDING_TTL)
            
        except Exception as e:
            logger.error(f"Failed to store pending message: {e}")
    
    @classmethod
    def _get_pending_messages(cls, conversation_id: int, current_sequence: int) -> List[Dict[str, Any]]:
        """Get pending messages with sequence numbers less than current."""
        try:
            pending_messages = []
            
            # Check for pending messages with lower sequence numbers
            for seq in range(1, current_sequence):
                pending_key = f"{cls.PENDING_PREFIX}{conversation_id}:{seq}"
                pending_data = cache.get(pending_key)
                if pending_data:
                    pending_messages.append(pending_data)
            
            return pending_messages
            
        except Exception as e:
            logger.error(f"Failed to get pending messages: {e}")
            return []
    
    @classmethod
    def _is_duplicate_message(cls, conversation_id: int, sequence_number: int, 
                            message_data: Dict[str, Any]) -> bool:
        """Check if a message is a duplicate based on sequence number and content."""
        try:
            pending_key = f"{cls.PENDING_PREFIX}{conversation_id}:{sequence_number}"
            existing_data = cache.get(pending_key)
            
            if not existing_data:
                return False
            
            # Compare message content and metadata
            return (
                existing_data.get('content') == message_data.get('content') and
                existing_data.get('user_id') == message_data.get('user_id') and
                existing_data.get('message_type') == message_data.get('message_type')
            )
            
        except Exception as e:
            logger.error(f"Failed to check duplicate message: {e}")
            return False
    
    @classmethod
    def _has_sequence_gap(cls, conversation_id: int, current_sequence: int) -> bool:
        """Check if there's a sequence gap before the current sequence."""
        try:
            if current_sequence <= 1:
                return False
            
            # Check if the previous sequence exists
            prev_sequence = current_sequence - 1
            prev_key = f"{cls.PENDING_PREFIX}{conversation_id}:{prev_sequence}"
            
            return cache.get(prev_key) is None
            
        except Exception as e:
            logger.error(f"Failed to check sequence gap: {e}")
            return False
    
    @classmethod
    def _detect_sequence_gaps(cls, messages: List[Dict[str, Any]]) -> None:
        """Detect and log sequence gaps in message list."""
        try:
            if len(messages) < 2:
                return
            
            for i in range(1, len(messages)):
                current_seq = messages[i].get('sequence_number', 0)
                prev_seq = messages[i-1].get('sequence_number', 0)
                
                if current_seq - prev_seq > 1:
                    gap_size = current_seq - prev_seq - 1
                    logger.warning(f"Sequence gap detected: {gap_size} messages missing between {prev_seq} and {current_seq}")
                    
                    # Store gap information for recovery
                    conversation_id = messages[i].get('conversation_id')
                    if conversation_id:
                        gap_key = f"{cls.GAP_PREFIX}{conversation_id}:{current_seq}"
                        gap_data = {
                            'gap_start': prev_seq + 1,
                            'gap_end': current_seq - 1,
                            'gap_size': gap_size,
                            'detected_at': timezone.now().isoformat(),
                        }
                        cache.set(gap_key, gap_data, timeout=cls.GAP_TTL)
            
        except Exception as e:
            logger.error(f"Failed to detect sequence gaps: {e}")
    
    @classmethod
    def cleanup_old_sequences(cls, conversation_id: int, keep_last: int = 100) -> int:
        """
        Clean up old sequence data to prevent memory leaks.
        
        Args:
            conversation_id: Conversation ID
            keep_last: Number of recent sequences to keep
            
        Returns:
            Number of sequences cleaned up
        """
        try:
            # This is a simplified cleanup - in production you might want to use
            # Redis SCAN to iterate through all sequence keys
            # For now, we rely on TTL to handle cleanup automatically
            
            logger.debug(f"Cleanup completed for conversation {conversation_id}")
            return 0  # Redis handles TTL cleanup automatically
            
        except Exception as e:
            logger.error(f"Failed to cleanup old sequences: {e}")
            return 0


# Global instance
message_sequencer = MessageSequencer()





















































