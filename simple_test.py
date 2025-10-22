#!/usr/bin/env python
"""
Simple test for notification system
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

def test_basic_notification():
    """Test basic notification creation and broadcasting"""
    print("🧪 Testing Basic Notification System")
    print("=" * 40)
    
    # Check if we have users
    users = User.objects.all()
    print(f"👥 Found {users.count()} users in database")
    
    if users.count() == 0:
        print("❌ No users found. Please create a user first.")
        return False
    
    # Get first user
    user = users.first()
    print(f"👤 Using user: {user.f_name} {user.l_name} (ID: {user.user_id})")
    
    # Create notification
    print("📝 Creating test notification...")
    notification = Notification.objects.create(
        user=user,
        notif_type='system_test',
        notifi_content='This is a test notification to verify the system is working',
        notif_date=timezone.now()
    )
    print(f"✅ Created notification ID: {notification.notification_id}")
    
    # Test broadcasting
    print("📡 Broadcasting notification...")
    try:
        broadcast_notification(notification)
        print("✅ Notification broadcasted successfully!")
        print("🔔 Check if you see the broadcast messages in the console above")
    except Exception as e:
        print(f"❌ Broadcasting failed: {e}")
        return False
    
    # Clean up
    print("🧹 Cleaning up test notification...")
    notification.delete()
    print("✅ Test completed successfully!")
    
    return True

if __name__ == "__main__":
    success = test_basic_notification()
    if success:
        print("\n🎉 NOTIFICATION SYSTEM IS WORKING!")
        print("The issue might be with WebSocket connections or frontend setup.")
    else:
        print("\n❌ NOTIFICATION SYSTEM HAS ISSUES!")
