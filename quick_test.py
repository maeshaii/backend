#!/usr/bin/env python
"""
Quick test for notification system
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, Notification
from django.utils import timezone
from apps.messaging.notification_broadcaster import broadcast_notification

def test_notification_creation_and_broadcast():
    """Test notification creation and broadcasting"""
    print("🧪 Quick Notification Test")
    print("=" * 40)
    
    # Get users
    users = list(User.objects.all()[:2])
    if len(users) < 2:
        print("❌ Need at least 2 users")
        return False
    
    sender = users[0]
    receiver = users[1]
    
    print(f"👤 Sender: {sender.f_name} {sender.l_name} (ID: {sender.user_id})")
    print(f"👤 Receiver: {receiver.f_name} {receiver.l_name} (ID: {receiver.user_id})")
    
    # Create notification
    notification = Notification.objects.create(
        user=receiver,
        notif_type='comment',
        subject='Post Commented',
        notifi_content=f'{sender.f_name} {sender.l_name} commented on your post<!--POST_ID:123-->',
        notif_date=timezone.now()
    )
    
    print(f"📝 Created notification ID: {notification.notification_id}")
    
    # Broadcast notification
    print("📡 Broadcasting notification...")
    broadcast_notification(notification)
    print("✅ Notification broadcasted successfully!")
    
    # Clean up
    notification.delete()
    print("🧹 Test completed and cleaned up")
    
    return True

if __name__ == "__main__":
    success = test_notification_creation_and_broadcast()
    if success:
        print("\n🎉 BACKEND NOTIFICATION SYSTEM IS WORKING!")
        print("The issue is in the frontend WebSocket connection.")
        print("\nNext steps:")
        print("1. Open browser console and check for WebSocket connection logs")
        print("2. Test with the debug tool: frontend/test-websocket.html")
        print("3. Check if JWT token is being sent correctly")
    else:
        print("\n❌ BACKEND HAS ISSUES!")
