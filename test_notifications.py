#!/usr/bin/env python
"""
Test script for notification system components
"""
import os
import sys
import django
import asyncio
from channels.testing import WebsocketCommunicator

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.messaging.consumers import NotificationConsumer
from apps.messaging.notification_broadcaster import broadcast_notification
from apps.shared.models import User, Notification
from django.utils import timezone
from channels.layers import get_channel_layer

async def test_websocket_consumer():
    """Test WebSocket consumer connection"""
    print("🔌 Testing WebSocket Consumer...")
    try:
        # Mock user in scope for authentication
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.first()
        
        communicator = WebsocketCommunicator(
            NotificationConsumer.as_asgi(), 
            '/ws/notifications/',
            headers=[(b'authorization', b'Bearer fake-token')]
        )
        
        # Mock the user in the scope
        communicator.scope['user'] = user
        
        connected, subprotocol = await communicator.connect()
        print(f"✅ WebSocket connected: {connected}")
        
        if connected:
            # Test ping
            await communicator.send_json_to({'type': 'ping'})
            response = await communicator.receive_json_from()
            print(f"✅ Ping response: {response}")
        
        await communicator.disconnect()
        print("✅ WebSocket test completed successfully")
        return True
    except Exception as e:
        print(f"❌ WebSocket test failed: {e}")
        return False

async def test_notification_broadcasting():
    """Test notification broadcasting"""
    print("\n📡 Testing Notification Broadcasting...")
    try:
        # Get a test user
        user = User.objects.first()
        if not user:
            print("❌ No users found in database")
            return False
            
        print(f"👤 Using test user: {user.f_name} {user.l_name} (ID: {user.user_id})")
        
        # Create test notification
        notification = Notification.objects.create(
            user=user,
            notif_type='test',
            notifi_content='Test notification for system verification',
            notif_date=timezone.now()
        )
        
        print(f"📝 Created notification ID: {notification.notification_id}")
        
        # Broadcast notification using sync_to_async
        from asgiref.sync import sync_to_async
        await sync_to_async(broadcast_notification)(notification)
        print("✅ Notification broadcast completed")
        
        # Clean up test notification
        notification.delete()
        print("🧹 Test notification cleaned up")
        
        return True
    except Exception as e:
        print(f"❌ Broadcasting test failed: {e}")
        return False

async def test_channel_layer():
    """Test channel layer connectivity"""
    print("\n🔗 Testing Channel Layer...")
    try:
        channel_layer = get_channel_layer()
        print(f"✅ Channel layer type: {type(channel_layer).__name__}")
        
        # Test group send
        await channel_layer.group_send(
            'test_group',
            {
                'type': 'test_message',
                'content': 'Test message'
            }
        )
        print("✅ Group send test completed")
        
        return True
    except Exception as e:
        print(f"❌ Channel layer test failed: {e}")
        return False

async def test_full_notification_flow():
    """Test complete notification flow"""
    print("\n🔄 Testing Full Notification Flow...")
    try:
        # Get test user
        user = User.objects.first()
        if not user:
            print("❌ No users found")
            return False
            
        # Create WebSocket connection with user in scope
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
            
        # Create and broadcast notification
        notification = Notification.objects.create(
            user=user,
            notif_type='integration_test',
            notifi_content='Integration test notification',
            notif_date=timezone.now()
        )
        
        print(f"📝 Created notification for user {user.user_id}")
        
        # Broadcast notification using sync_to_async
        from asgiref.sync import sync_to_async
        await sync_to_async(broadcast_notification)(notification)
        print("📡 Notification broadcasted")
        
        # Wait for WebSocket message
        try:
            message = await asyncio.wait_for(communicator.receive_json_from(), timeout=5.0)
            print(f"✅ Received WebSocket message: {message}")
            
            if message.get('type') == 'notification_update':
                print("✅ Notification update received successfully!")
                success = True
            else:
                print(f"❌ Unexpected message type: {message.get('type')}")
                success = False
        except asyncio.TimeoutError:
            print("❌ Timeout waiting for WebSocket message")
            success = False
        
        # Clean up
        notification.delete()
        await communicator.disconnect()
        
        return success
        
    except Exception as e:
        print(f"❌ Full flow test failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("🧪 Starting Notification System Tests\n")
    print("=" * 50)
    
    tests = [
        ("Channel Layer", await test_channel_layer()),
        ("Notification Broadcasting", await test_notification_broadcasting()),
        ("WebSocket Consumer", await test_websocket_consumer()),
        ("Full Notification Flow", await test_full_notification_flow())
    ]
    
    results = []
    for test_name, test_result in tests:
        try:
            results.append((test_name, test_result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("📊 TEST RESULTS")
    print("=" * 50)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {test_name}")
        if not passed:
            all_passed = False
    
    print("=" * 50)
    if all_passed:
        print("🎉 ALL TESTS PASSED! Notification system is working correctly.")
    else:
        print("⚠️  SOME TESTS FAILED! Check the issues above.")
    
    return all_passed

if __name__ == "__main__":
    asyncio.run(main())
