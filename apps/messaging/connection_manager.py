"""
Redis-based WebSocket connection management and tracking.

This module provides connection tracking, user presence, and conversation analytics
using Redis for scalability and persistence across multiple server instances.
"""

import json
import logging
import time
from typing import Dict, List, Set, Optional
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


class RedisConnectionManager:
    """
    Manages WebSocket connections using Redis for scalability.
    
    Features:
    - Connection tracking per user and conversation
    - User presence indicators
    - Connection analytics and monitoring
    - Automatic cleanup of stale connections
    """
    
    # Redis key prefixes
    USER_CONNECTIONS_PREFIX = "ws:user_connections:"
    CONVERSATION_USERS_PREFIX = "ws:conversation_users:"
    USER_PRESENCE_PREFIX = "ws:user_presence:"
    CONNECTION_METADATA_PREFIX = "ws:connection_metadata:"
    ANALYTICS_PREFIX = "ws:analytics:"
    
    # TTL values (in seconds)
    CONNECTION_TTL = 3600  # 1 hour
    PRESENCE_TTL = 300     # 5 minutes
    ANALYTICS_TTL = 86400  # 24 hours
    
    def __init__(self):
        self.channel_layer = get_channel_layer()
    
    def add_connection(self, user_id: int, conversation_id: int, channel_name: str, 
                      connection_metadata: Optional[Dict] = None) -> bool:
        """
        Add a new WebSocket connection to tracking.
        
        Args:
            user_id: User ID
            conversation_id: Conversation ID
            channel_name: WebSocket channel name
            connection_metadata: Optional metadata about the connection
            
        Returns:
            bool: True if connection was added successfully
        """
        try:
            timestamp = timezone.now().isoformat()
            
            # Store connection metadata
            metadata = {
                'user_id': user_id,
                'conversation_id': conversation_id,
                'channel_name': channel_name,
                'connected_at': timestamp,
                'last_activity': timestamp,
                'ip_address': connection_metadata.get('ip_address') if connection_metadata else None,
                'user_agent': connection_metadata.get('user_agent') if connection_metadata else None,
            }
            
            # Store connection metadata
            cache.set(
                f"{self.CONNECTION_METADATA_PREFIX}{channel_name}",
                json.dumps(metadata),
                timeout=self.CONNECTION_TTL
            )
            
            # Add to user's connections set
            user_connections_key = f"{self.USER_CONNECTIONS_PREFIX}{user_id}"
            user_connections = cache.get(user_connections_key, set())
            if not isinstance(user_connections, set):
                user_connections = set()
            user_connections.add(channel_name)
            cache.set(user_connections_key, user_connections, timeout=self.CONNECTION_TTL)
            
            # Add to conversation's users set
            conversation_users_key = f"{self.CONVERSATION_USERS_PREFIX}{conversation_id}"
            conversation_users = cache.get(conversation_users_key, set())
            if not isinstance(conversation_users, set):
                conversation_users = set()
            conversation_users.add(user_id)
            cache.set(conversation_users_key, conversation_users, timeout=self.CONNECTION_TTL)
            
            # Update user presence
            self.update_user_presence(user_id, conversation_id, 'online')
            
            # Update analytics
            self._update_connection_analytics('connection_added', user_id, conversation_id)
            
            logger.info(f"Added WebSocket connection: user {user_id} to conversation {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add WebSocket connection: {e}")
            return False
    
    def remove_connection(self, channel_name: str) -> bool:
        """
        Remove a WebSocket connection from tracking.
        
        Args:
            channel_name: WebSocket channel name
            
        Returns:
            bool: True if connection was removed successfully
        """
        try:
            # Get connection metadata
            metadata_key = f"{self.CONNECTION_METADATA_PREFIX}{channel_name}"
            metadata_json = cache.get(metadata_key)
            
            if not metadata_json:
                logger.warning(f"Connection metadata not found for channel: {channel_name}")
                return False
            
            metadata = json.loads(metadata_json)
            user_id = metadata['user_id']
            conversation_id = metadata['conversation_id']
            
            # Remove from user's connections
            user_connections_key = f"{self.USER_CONNECTIONS_PREFIX}{user_id}"
            user_connections = cache.get(user_connections_key, set())
            if isinstance(user_connections, set):
                user_connections.discard(channel_name)
                if user_connections:
                    cache.set(user_connections_key, user_connections, timeout=self.CONNECTION_TTL)
                else:
                    cache.delete(user_connections_key)
                    # Update user presence to offline if no more connections
                    self.update_user_presence(user_id, conversation_id, 'offline')
            
            # Remove from conversation's users if user has no more connections to this conversation
            if not self._user_has_connections_to_conversation(user_id, conversation_id):
                conversation_users_key = f"{self.CONVERSATION_USERS_PREFIX}{conversation_id}"
                conversation_users = cache.get(conversation_users_key, set())
                if isinstance(conversation_users, set):
                    conversation_users.discard(user_id)
                    if conversation_users:
                        cache.set(conversation_users_key, conversation_users, timeout=self.CONNECTION_TTL)
                    else:
                        cache.delete(conversation_users_key)
            
            # Remove connection metadata
            cache.delete(metadata_key)
            
            # Update analytics
            self._update_connection_analytics('connection_removed', user_id, conversation_id)
            
            logger.info(f"Removed WebSocket connection: user {user_id} from conversation {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove WebSocket connection: {e}")
            return False
    
    def update_user_presence(self, user_id: int, conversation_id: int, status: str) -> bool:
        """
        Update user presence status.
        
        Args:
            user_id: User ID
            conversation_id: Conversation ID
            status: 'online', 'offline', 'typing', 'idle'
            
        Returns:
            bool: True if presence was updated successfully
        """
        try:
            presence_key = f"{self.USER_PRESENCE_PREFIX}{user_id}:{conversation_id}"
            presence_data = {
                'user_id': user_id,
                'conversation_id': conversation_id,
                'status': status,
                'last_seen': timezone.now().isoformat(),
            }
            
            cache.set(presence_key, json.dumps(presence_data), timeout=self.PRESENCE_TTL)
            
            # Broadcast presence update to conversation participants
            self._broadcast_presence_update(user_id, conversation_id, status)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update user presence: {e}")
            return False
    
    def get_conversation_users(self, conversation_id: int) -> List[Dict]:
        """
        Get all users currently connected to a conversation.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            List of user presence data
        """
        try:
            conversation_users_key = f"{self.CONVERSATION_USERS_PREFIX}{conversation_id}"
            user_ids = cache.get(conversation_users_key, set())
            
            if not isinstance(user_ids, set):
                return []
            
            users = []
            for user_id in user_ids:
                presence_key = f"{self.USER_PRESENCE_PREFIX}{user_id}:{conversation_id}"
                presence_json = cache.get(presence_key)
                if presence_json:
                    users.append(json.loads(presence_json))
            
            return users
            
        except Exception as e:
            logger.error(f"Failed to get conversation users: {e}")
            return []
    
    def get_user_connections(self, user_id: int) -> List[str]:
        """
        Get all WebSocket connections for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of channel names
        """
        try:
            user_connections_key = f"{self.USER_CONNECTIONS_PREFIX}{user_id}"
            connections = cache.get(user_connections_key, set())
            return list(connections) if isinstance(connections, set) else []
            
        except Exception as e:
            logger.error(f"Failed to get user connections: {e}")
            return []
    
    def get_connection_analytics(self, conversation_id: Optional[int] = None) -> Dict:
        """
        Get connection analytics data.
        
        Args:
            conversation_id: Optional conversation ID to filter by
            
        Returns:
            Dictionary with analytics data
        """
        try:
            if conversation_id:
                analytics_key = f"{self.ANALYTICS_PREFIX}conversation:{conversation_id}"
            else:
                analytics_key = f"{self.ANALYTICS_PREFIX}global"
            
            analytics = cache.get(analytics_key, {})
            return analytics if isinstance(analytics, dict) else {}
            
        except Exception as e:
            logger.error(f"Failed to get connection analytics: {e}")
            return {}
    
    def cleanup_stale_connections(self) -> int:
        """
        Clean up stale connections that have exceeded TTL.
        
        Returns:
            Number of connections cleaned up
        """
        try:
            # This is a simplified cleanup - in production, you might want to use
            # Redis SCAN to iterate through all connection keys
            # For now, we rely on Redis TTL to handle cleanup automatically
            
            # Update analytics
            self._update_connection_analytics('cleanup_performed', None, None)
            
            return 0  # Redis handles TTL cleanup automatically
            
        except Exception as e:
            logger.error(f"Failed to cleanup stale connections: {e}")
            return 0
    
    def _user_has_connections_to_conversation(self, user_id: int, conversation_id: int) -> bool:
        """Check if user has any connections to a specific conversation."""
        try:
            user_connections = self.get_user_connections(user_id)
            for channel_name in user_connections:
                metadata_key = f"{self.CONNECTION_METADATA_PREFIX}{channel_name}"
                metadata_json = cache.get(metadata_key)
                if metadata_json:
                    metadata = json.loads(metadata_json)
                    if metadata.get('conversation_id') == conversation_id:
                        return True
            return False
        except Exception:
            return False
    
    def _update_connection_analytics(self, event_type: str, user_id: Optional[int], 
                                   conversation_id: Optional[int]) -> None:
        """Update connection analytics."""
        try:
            # Global analytics
            global_key = f"{self.ANALYTICS_PREFIX}global"
            global_analytics = cache.get(global_key, {})
            if not isinstance(global_analytics, dict):
                global_analytics = {}
            
            # Update event counters
            if 'events' not in global_analytics:
                global_analytics['events'] = {}
            if event_type not in global_analytics['events']:
                global_analytics['events'][event_type] = 0
            global_analytics['events'][event_type] += 1
            
            # Update last activity
            global_analytics['last_activity'] = timezone.now().isoformat()
            
            cache.set(global_key, global_analytics, timeout=self.ANALYTICS_TTL)
            
            # Conversation-specific analytics
            if conversation_id:
                conv_key = f"{self.ANALYTICS_PREFIX}conversation:{conversation_id}"
                conv_analytics = cache.get(conv_key, {})
                if not isinstance(conv_analytics, dict):
                    conv_analytics = {}
                
                if 'events' not in conv_analytics:
                    conv_analytics['events'] = {}
                if event_type not in conv_analytics['events']:
                    conv_analytics['events'][event_type] = 0
                conv_analytics['events'][event_type] += 1
                
                conv_analytics['last_activity'] = timezone.now().isoformat()
                
                cache.set(conv_key, conv_analytics, timeout=self.ANALYTICS_TTL)
                
        except Exception as e:
            logger.error(f"Failed to update connection analytics: {e}")
    
    def _broadcast_presence_update(self, user_id: int, conversation_id: int, status: str) -> None:
        """Broadcast presence update to conversation participants."""
        try:
            if not self.channel_layer:
                return
            
            # Get all users in the conversation
            users = self.get_conversation_users(conversation_id)
            
            # Send presence update to each user's connections
            for user_data in users:
                if user_data['user_id'] != user_id:  # Don't send to the user who changed status
                    user_connections = self.get_user_connections(user_data['user_id'])
                    for channel_name in user_connections:
                        async_to_sync(self.channel_layer.send)(
                            channel_name,
                            {
                                'type': 'presence_update',
                                'user_id': user_id,
                                'conversation_id': conversation_id,
                                'status': status,
                                'timestamp': timezone.now().isoformat(),
                            }
                        )
                        
        except Exception as e:
            logger.error(f"Failed to broadcast presence update: {e}")


# Global instance
connection_manager = RedisConnectionManager()



































