"""
Redis-based message caching for improved performance.

This module provides caching for frequently accessed messages, conversation metadata,
and user presence data to reduce database load and improve response times.
"""

import json
import logging
from typing import List, Dict, Optional, Any
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class MessageCache:
    """
    Redis-based caching for messages and conversation data.
    
    Features:
    - Message caching with TTL
    - Conversation metadata caching
    - User presence caching
    - Cache invalidation strategies
    - Performance metrics
    """
    
    # Cache key prefixes
    MESSAGE_PREFIX = "msg:"
    CONVERSATION_PREFIX = "conv:"
    USER_PRESENCE_PREFIX = "presence:"
    CONVERSATION_MESSAGES_PREFIX = "conv_msgs:"
    USER_CONVERSATIONS_PREFIX = "user_convs:"
    
    # TTL values (in seconds)
    MESSAGE_TTL = 3600  # 1 hour
    CONVERSATION_TTL = 1800  # 30 minutes
    PRESENCE_TTL = 300  # 5 minutes
    CONVERSATION_MESSAGES_TTL = 600  # 10 minutes
    USER_CONVERSATIONS_TTL = 900  # 15 minutes
    
    @classmethod
    def cache_message(cls, message_data: Dict[str, Any]) -> bool:
        """
        Cache a single message.
        
        Args:
            message_data: Message data dictionary
            
        Returns:
            bool: True if message was cached successfully
        """
        try:
            message_id = message_data.get('message_id')
            if not message_id:
                return False
            
            cache_key = f"{cls.MESSAGE_PREFIX}{message_id}"
            cache.set(cache_key, json.dumps(message_data), timeout=cls.MESSAGE_TTL)
            
            logger.debug(f"Cached message {message_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache message: {e}")
            return False
    
    @classmethod
    def get_message(cls, message_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a cached message.
        
        Args:
            message_id: Message ID
            
        Returns:
            Message data dictionary or None if not found
        """
        try:
            cache_key = f"{cls.MESSAGE_PREFIX}{message_id}"
            cached_data = cache.get(cache_key)
            
            if cached_data:
                return json.loads(cached_data)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get cached message {message_id}: {e}")
            return None
    
    @classmethod
    def cache_conversation_messages(cls, conversation_id: int, messages: List[Dict[str, Any]], 
                                  cursor: Optional[str] = None) -> bool:
        """
        Cache a list of messages for a conversation.
        
        Args:
            conversation_id: Conversation ID
            messages: List of message data dictionaries
            cursor: Optional cursor for pagination
            
        Returns:
            bool: True if messages were cached successfully
        """
        try:
            cache_key = f"{cls.CONVERSATION_MESSAGES_PREFIX}{conversation_id}"
            if cursor:
                cache_key += f":{cursor}"
            
            cache_data = {
                'messages': messages,
                'cached_at': timezone.now().isoformat(),
                'count': len(messages),
                'cursor': cursor,
            }
            
            cache.set(cache_key, json.dumps(cache_data), timeout=cls.CONVERSATION_MESSAGES_TTL)
            
            logger.debug(f"Cached {len(messages)} messages for conversation {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache conversation messages: {e}")
            return False
    
    @classmethod
    def get_conversation_messages(cls, conversation_id: int, cursor: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached messages for a conversation.
        
        Args:
            conversation_id: Conversation ID
            cursor: Optional cursor for pagination
            
        Returns:
            List of message data dictionaries or None if not found
        """
        try:
            cache_key = f"{cls.CONVERSATION_MESSAGES_PREFIX}{conversation_id}"
            if cursor:
                cache_key += f":{cursor}"
            
            cached_data = cache.get(cache_key)
            if cached_data:
                data = json.loads(cached_data)
                return data.get('messages', [])
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get cached conversation messages: {e}")
            return None
    
    @classmethod
    def cache_conversation_metadata(cls, conversation_id: int, metadata: Dict[str, Any]) -> bool:
        """
        Cache conversation metadata.
        
        Args:
            conversation_id: Conversation ID
            metadata: Conversation metadata dictionary
            
        Returns:
            bool: True if metadata was cached successfully
        """
        try:
            cache_key = f"{cls.CONVERSATION_PREFIX}{conversation_id}"
            metadata['cached_at'] = timezone.now().isoformat()
            
            cache.set(cache_key, json.dumps(metadata), timeout=cls.CONVERSATION_TTL)
            
            logger.debug(f"Cached metadata for conversation {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache conversation metadata: {e}")
            return False
    
    @classmethod
    def get_conversation_metadata(cls, conversation_id: int) -> Optional[Dict[str, Any]]:
        """
        Get cached conversation metadata.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            Conversation metadata dictionary or None if not found
        """
        try:
            cache_key = f"{cls.CONVERSATION_PREFIX}{conversation_id}"
            cached_data = cache.get(cache_key)
            
            if cached_data:
                return json.loads(cached_data)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get cached conversation metadata: {e}")
            return None
    
    @classmethod
    def cache_user_conversations(cls, user_id: int, conversations: List[Dict[str, Any]]) -> bool:
        """
        Cache user's conversations list.
        
        Args:
            user_id: User ID
            conversations: List of conversation data dictionaries
            
        Returns:
            bool: True if conversations were cached successfully
        """
        try:
            cache_key = f"{cls.USER_CONVERSATIONS_PREFIX}{user_id}"
            cache_data = {
                'conversations': conversations,
                'cached_at': timezone.now().isoformat(),
                'count': len(conversations),
            }
            
            cache.set(cache_key, json.dumps(cache_data), timeout=cls.USER_CONVERSATIONS_TTL)
            
            logger.debug(f"Cached {len(conversations)} conversations for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache user conversations: {e}")
            return False
    
    @classmethod
    def get_user_conversations(cls, user_id: int) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached user conversations.
        
        Args:
            user_id: User ID
            
        Returns:
            List of conversation data dictionaries or None if not found
        """
        try:
            cache_key = f"{cls.USER_CONVERSATIONS_PREFIX}{user_id}"
            cached_data = cache.get(cache_key)
            
            if cached_data:
                data = json.loads(cached_data)
                return data.get('conversations', [])
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get cached user conversations: {e}")
            return None
    
    @classmethod
    def invalidate_message(cls, message_id: int) -> bool:
        """
        Invalidate a cached message.
        
        Args:
            message_id: Message ID
            
        Returns:
            bool: True if message was invalidated successfully
        """
        try:
            cache_key = f"{cls.MESSAGE_PREFIX}{message_id}"
            cache.delete(cache_key)
            
            logger.debug(f"Invalidated cached message {message_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to invalidate message {message_id}: {e}")
            return False
    
    @classmethod
    def invalidate_conversation_messages(cls, conversation_id: int) -> bool:
        """
        Invalidate all cached messages for a conversation.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            bool: True if messages were invalidated successfully
        """
        try:
            # In a production environment, you might want to use Redis SCAN
            # to find all keys with the conversation prefix
            # For now, we'll invalidate the most common patterns
            
            patterns = [
                f"{cls.CONVERSATION_MESSAGES_PREFIX}{conversation_id}",
                f"{cls.CONVERSATION_MESSAGES_PREFIX}{conversation_id}:*",
            ]
            
            for pattern in patterns:
                cache.delete(pattern)
            
            logger.debug(f"Invalidated cached messages for conversation {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to invalidate conversation messages: {e}")
            return False
    
    @classmethod
    def invalidate_conversation_metadata(cls, conversation_id: int) -> bool:
        """
        Invalidate cached conversation metadata.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            bool: True if metadata was invalidated successfully
        """
        try:
            cache_key = f"{cls.CONVERSATION_PREFIX}{conversation_id}"
            cache.delete(cache_key)
            
            logger.debug(f"Invalidated cached metadata for conversation {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to invalidate conversation metadata: {e}")
            return False
    
    @classmethod
    def invalidate_user_conversations(cls, user_id: int) -> bool:
        """
        Invalidate cached user conversations.
        
        Args:
            user_id: User ID
            
        Returns:
            bool: True if conversations were invalidated successfully
        """
        try:
            cache_key = f"{cls.USER_CONVERSATIONS_PREFIX}{user_id}"
            cache.delete(cache_key)
            
            logger.debug(f"Invalidated cached conversations for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to invalidate user conversations: {e}")
            return False
    
    @classmethod
    def get_cache_stats(cls) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        try:
            # This is a simplified version - in production you might want to
            # use Redis INFO command to get detailed cache statistics
            
            stats = {
                'timestamp': timezone.now().isoformat(),
                'message_cache_ttl': cls.MESSAGE_TTL,
                'conversation_cache_ttl': cls.CONVERSATION_TTL,
                'presence_cache_ttl': cls.PRESENCE_TTL,
                'conversation_messages_ttl': cls.CONVERSATION_MESSAGES_TTL,
                'user_conversations_ttl': cls.USER_CONVERSATIONS_TTL,
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {}


# Global instance
message_cache = MessageCache()





































































