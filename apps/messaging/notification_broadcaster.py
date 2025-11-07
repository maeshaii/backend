"""
Real-time notification broadcasting service.
Handles WebSocket broadcasting of notifications to connected users.
"""

import logging
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone
from apps.shared.models import Notification
from apps.shared.models import User
import time

logger = logging.getLogger(__name__)

class NotificationBroadcaster:
    """
    Service for broadcasting notifications in real-time via WebSocket.
    """
    
    def __init__(self):
        self.channel_layer = get_channel_layer()
    
    def broadcast_notification(self, notification):
        """
        Broadcast a single notification to the user's notification channel.
        
        Args:
            notification: Notification instance to broadcast
        """
        try:
            if not self.channel_layer:
                logger.warning("Channel layer not available for notification broadcasting")
                return
            
            # Prepare notification data
            notification_data = {
                'id': notification.notification_id,
                'type': notification.notif_type,
                'subject': notification.subject or 'Notification',
                'content': notification.notifi_content,
                'date': notification.notif_date.strftime('%Y-%m-%d %H:%M:%S'),
                'is_read': notification.is_read,
                'timestamp': timezone.now().isoformat()
            }
            # Prepare notification data
            
            # Broadcast to user's notification channel
            group_name = f"notifications_{notification.user.user_id}"
            logger.info(f"Broadcasting notification {notification.notification_id} to group: {group_name}")
            logger.info(f"Notification data: {notification_data}")
            print(f"🔔 BROADCASTING NOTIFICATION: {notification.notification_id} to user {notification.user.user_id}")
            print(f"📊 Group: {group_name}")
            print(f"📝 Data: {notification_data}")
            
            async_to_sync(self.channel_layer.group_send)(
                group_name,
                {
                    'type': 'notification_update',
                    'notification': notification_data
                }
            )
            
            logger.info(f"Successfully broadcasted notification {notification.notification_id} to user {notification.user.user_id}")
            
        except Exception as e:
            logger.error(f"Error broadcasting notification {notification.notification_id}: {e}")
    
    def broadcast_notification_count(self, user_id, count):
        """
        Broadcast notification count update to user.
        
        Args:
            user_id: User ID to broadcast to
            count: New notification count
        """
        try:
            if not self.channel_layer:
                logger.warning("Channel layer not available for count broadcasting")
                return
            
            # Broadcast count update
            async_to_sync(self.channel_layer.group_send)(
                f"notifications_{user_id}",
                {
                    'type': 'notification_count_update',
                    'count': count
                }
            )
            
            logger.info(f"Broadcasted notification count {count} to user {user_id}")
            
        except Exception as e:
            logger.error(f"Error broadcasting notification count to user {user_id}: {e}")
    
    def broadcast_points_update(self, user_id, points_data):
        """
        Broadcast points update to user.
        
        Args:
            user_id: User ID to broadcast to
            points_data: Points data dictionary
        """
        try:
            if not self.channel_layer:
                logger.warning("Channel layer not available for points broadcasting")
                return
            
            # Broadcast points update
            async_to_sync(self.channel_layer.group_send)(
                f"notifications_{user_id}",
                {
                    'type': 'points_update',
                    'points': points_data
                }
            )
            
            logger.info(f"Broadcasted points update to user {user_id}")
            
        except Exception as e:
            logger.error(f"Error broadcasting points update to user {user_id}: {e}")
    
    def broadcast_multiple_notifications(self, notifications):
        """
        Broadcast multiple notifications to their respective users.
        
        Args:
            notifications: List of Notification instances
        """
        try:
            for notification in notifications:
                self.broadcast_notification(notification)
        except Exception as e:
            logger.error(f"Error broadcasting multiple notifications: {e}")


# Global instance
notification_broadcaster = NotificationBroadcaster()


def broadcast_notification(notification):
    """
    Convenience function to broadcast a single notification.
    
    Args:
        notification: Notification instance
    """
    notification_broadcaster.broadcast_notification(notification)


def broadcast_notification_count(user_id, count):
    """
    Convenience function to broadcast notification count.
    
    Args:
        user_id: User ID
        count: Notification count
    """
    notification_broadcaster.broadcast_notification_count(user_id, count)


def broadcast_points_update(user_id, points_data):
    """
    Convenience function to broadcast points update.
    
    Args:
        user_id: User ID
        points_data: Points data dictionary
    """
    notification_broadcaster.broadcast_points_update(user_id, points_data)
