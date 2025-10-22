#!/usr/bin/env python
"""
Test the complete notification flow from backend to frontend
"""
import os
import sys
import django
import asyncio
import json
import time
from channels.testing import WebsocketCommunicator

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, Notification
from django.utils import timezone
from apps.messaging.notification_broadcaster import broadcast_notification
from apps.messaging.consumers import NotificationConsumer

async def test_complete_notification_flow():
    """Test complete notification flow with WebSocket"""
    print("🧪 Testing Complete Notification Flow")
    print("=" * 50)
    
    # Get test users
    users = User.objects.all()[:2]
    if len(users) < 2:
        print("❌ Need at least 2 users for testing")
        return False
    
    sender = users[0]
    receiver = users[1]
    
    print(f"👤 Sender: {sender.f_name} {sender.l_name} (ID: {sender.user_id})")
    print(f"👤 Receiver: {receiver.f_name} {receiver.l_name} (ID: {receiver.user_id})")
    
    # Create WebSocket connection for receiver
    print("\n🔌 Creating WebSocket connection for receiver...")
    communicator = WebsocketCommunicator(
        NotificationConsumer.as_asgi(), 
        '/ws/notifications/',
        headers=[(b'authorization', b'Bearer fake-token')]
    )
    communicator.scope['user'] = receiver
    
    connected, subprotocol = await communicator.connect()
    if not connected:
        print("❌ Failed to connect WebSocket")
        return False
    
    print("✅ WebSocket connected successfully")
    
    # Create notification (simulating a comment)
    print("\n📝 Creating notification...")
    notification = Notification.objects.create(
        user=receiver,
        notif_type='comment',
        subject='Post Commented',
        notifi_content=f'{sender.f_name} {sender.l_name} commented on your post<!--POST_ID:123-->',
        notif_date=timezone.now()
    )
    
    print(f"✅ Created notification ID: {notification.notification_id}")
    
    # Broadcast notification
    print("\n📡 Broadcasting notification...")
    broadcast_notification(notification)
    print("✅ Notification broadcasted")
    
    # Wait for WebSocket message
    print("\n⏳ Waiting for WebSocket message...")
    try:
        message = await asyncio.wait_for(communicator.receive_json_from(), timeout=10.0)
        print(f"✅ Received WebSocket message: {json.dumps(message, indent=2)}")
        
        if message.get('type') == 'notification_update':
            print("🎉 SUCCESS: Real-time notification received!")
            print(f"📋 Notification content: {message['notification']['content']}")
            success = True
        else:
            print(f"❌ Unexpected message type: {message.get('type')}")
            success = False
    except asyncio.TimeoutError:
        print("❌ Timeout waiting for WebSocket message")
        success = False
    except Exception as e:
        print(f"❌ Error receiving message: {e}")
        success = False
    
    # Clean up
    print("\n🧹 Cleaning up...")
    notification.delete()
    await communicator.disconnect()
    
    return success

async def test_multiple_notifications():
    """Test multiple notifications in sequence"""
    print("\n🔄 Testing Multiple Notifications")
    print("=" * 30)
    
    user = User.objects.first()
    if not user:
        print("❌ No users found")
        return False
    
    # Create WebSocket connection
    communicator = WebsocketCommunicator(
        NotificationConsumer.as_asgi(), 
        '/ws/notifications/',
        headers=[(b'authorization', b'Bearer fake-token')]
    )
    communicator.scope['user'] = user
    
    connected, subprotocol = await communicator.connect()
    if not connected:
        print("❌ Failed to connect WebSocket")
        return False
    
    print("✅ WebSocket connected")
    
    # Send multiple notifications
    notifications = []
    for i in range(3):
        notification = Notification.objects.create(
            user=user,
            notif_type='test',
            subject=f'Test Notification {i+1}',
            notifi_content=f'This is test notification number {i+1}',
            notif_date=timezone.now()
        )
        notifications.append(notification)
        broadcast_notification(notification)
        print(f"📡 Sent notification {i+1}")
        await asyncio.sleep(0.5)  # Small delay between notifications
    
    # Wait for all messages
    received_count = 0
    try:
        for i in range(3):
            message = await asyncio.wait_for(communicator.receive_json_from(), timeout=5.0)
            if message.get('type') == 'notification_update':
                received_count += 1
                print(f"✅ Received notification {received_count}: {message['notification']['content']}")
    except asyncio.TimeoutError:
        print(f"⚠️ Timeout - received {received_count}/3 notifications")
    
    # Clean up
    for notification in notifications:
        notification.delete()
    await communicator.disconnect()
    
    return received_count == 3

async def main():
    """Run all tests"""
    print("🚀 Starting Complete Notification Flow Tests")
    print("=" * 60)
    
    tests = [
        ("Complete Notification Flow", await test_complete_notification_flow()),
        ("Multiple Notifications", await test_multiple_notifications())
    ]
    
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in tests:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {test_name}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    if all_passed:
        print("🎉 ALL TESTS PASSED! Backend notification system is working perfectly.")
        print("The issue is likely in the frontend WebSocket connection.")
    else:
        print("⚠️ SOME TESTS FAILED! Check the backend configuration.")
    
    return all_passed

if __name__ == "__main__":
    asyncio.run(main())
