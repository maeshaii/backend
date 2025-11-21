#!/usr/bin/env python
"""
WebSocket Real-Time Testing Script
Tests if WebSocket server is properly configured for real-time messaging
"""

import argparse
import asyncio
import json
import os
import sys

import websockets


def build_ws_url(base_url: str, conversation_id: int) -> str:
    """Return a normalized websocket URL for the conversation."""
    if base_url.startswith("http://"):
        base = "ws://" + base_url[len("http://") :]
    elif base_url.startswith("https://"):
        base = "wss://" + base_url[len("https://") :]
    else:
        base = base_url

    base = base.rstrip("/")
    return f"{base}/ws/chat/{conversation_id}/"


parser = argparse.ArgumentParser(description="Diagnose the messaging WebSocket.")
parser.add_argument(
    "--conversation",
    type=int,
    default=int(os.getenv("WS_CONVERSATION_ID", 1)),
    help="Conversation ID to use for the test (default: %(default)s)",
)
parser.add_argument(
    "--base-url",
    default=os.getenv("WS_BASE_URL", "ws://localhost:8000"),
    help="Base URL for the backend (default: %(default)s)",
)
parser.add_argument(
    "--token",
    default=os.getenv("WS_TOKEN"),
    help="JWT token to append as ?token=... (default: value of WS_TOKEN env var)",
)
parser.add_argument(
    "--full-url",
    default=os.getenv("WS_FULL_URL"),
    help="Optional full websocket URL (overrides --base-url/--conversation)",
)
args = parser.parse_args()

WS_URL = args.full_url or build_ws_url(args.base_url, args.conversation)
TOKEN = args.token


async def next_message(websocket, queued_messages, timeout=5.0):
    """Return the next message, first checking queued ones."""
    if queued_messages:
        return queued_messages.pop(0)
    raw = await asyncio.wait_for(websocket.recv(), timeout=timeout)
    return json.loads(raw)

async def collect_initial_messages(websocket, queued_messages):
    """Drain any immediate server messages (connection established/denied)."""
    while True:
        try:
            raw = await asyncio.wait_for(websocket.recv(), timeout=0.5)
        except asyncio.TimeoutError:
            break
        data = json.loads(raw)
        data_type = data.get("type")
        queued_messages.append(data)
        if data_type == "connection_established":
            print("✅ Server confirmed connection establishment.")
        elif data_type == "connection_denied":
            print("\n❌ Server denied the WebSocket connection:")
            print(f"   Reason : {data.get('reason', 'unknown')}")
            print(f"   Message: {data.get('message', 'No details provided')}")
            return False
    return True


def check_denied_message(data):
    if data.get("type") == "connection_denied":
        print("\n❌ Server denied the WebSocket request mid-test.")
        print(f"   Reason : {data.get('reason', 'unknown')}")
        print(f"   Message: {data.get('message', 'No details provided')}")
        return False
    return True


async def test_websocket_connection():
    """Test WebSocket connection and message broadcasting"""
    
    print("=" * 60)
    print("🔍 WebSocket Real-Time Messaging Test")
    print("=" * 60)
    
    # Test 1: Connection
    print("\n📡 Test 1: Connecting to WebSocket...")
    try:
        uri = f"{WS_URL}?token={TOKEN}" if TOKEN else WS_URL
        async with websockets.connect(uri) as websocket:
            queued_messages = []
            if not await collect_initial_messages(websocket, queued_messages):
                return
            print("✅ WebSocket connected successfully!")
            
            # Test 2: Send ping
            print("\n🏓 Test 2: Sending ping...")
            await websocket.send(json.dumps({
                "type": "ping"
            }))
            
            # Wait for pong
            data = await next_message(websocket, queued_messages)
            if not check_denied_message(data):
                return
            if data.get('type') == 'pong':
                print("✅ Received pong - Server is responsive!")
            else:
                print(f"⚠️ Unexpected response: {data}")
            
            # Test 3: Send test message
            print("\n💬 Test 3: Sending test message...")
            await websocket.send(json.dumps({
                "type": "message",
                "content": "Test message from diagnostic script",
                "message_type": "text"
            }))
            
            # Wait for response
            data = await next_message(websocket, queued_messages)
            if not check_denied_message(data):
                return
            print(f"✅ Received response: {data.get('type', 'unknown')}")
            
            # Test 4: Listen for broadcasts
            print("\n📻 Test 4: Listening for broadcasts (5 seconds)...")
            print("   → Try sending a message from mobile/web now!")
            
            try:
                while True:
                    data = await next_message(websocket, queued_messages)
                    if not check_denied_message(data):
                        return
                    print(f"   📨 Received broadcast: {data.get('type')} - {data.get('content', '')[:50]}")
            except asyncio.TimeoutError:
                print("   ⏱️ No broadcasts received in 5 seconds")
            
            print("\n✅ All tests completed!")
            print("\n" + "=" * 60)
            print("🎉 WebSocket is working correctly!")
            print("=" * 60)
            print("\n📝 Next steps:")
            print("   1. Try sending a message from mobile to web")
            print("   2. It should appear instantly without refresh")
            print("   3. Try the reverse (web to mobile)")
            
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"\n❌ Connection failed with status code: {e.status_code}")
        print("\n🔍 Possible causes:")
        print("   1. Backend not running with ASGI server")
        print("   2. Running with 'python manage.py runserver' (doesn't support WebSocket)")
        print("\n✅ Solution:")
        print("   Stop current server and run:")
        print("   → daphne -b 0.0.0.0 -p 8000 backend.asgi:application")
        print("   or")
        print("   → uvicorn backend.asgi:application --host 0.0.0.0 --port 8000")
        sys.exit(1)
        
    except ConnectionRefusedError:
        print("\n❌ Connection refused!")
        print("\n🔍 Possible causes:")
        print("   1. Backend server is not running")
        print("   2. Wrong port or host")
        print("\n✅ Solution:")
        print("   1. Start backend server:")
        print("   → cd backend")
        print("   → daphne -b 0.0.0.0 -p 8000 backend.asgi:application")
        sys.exit(1)
        
    except asyncio.TimeoutError:
        print("\n⏱️ Connection timeout!")
        print("\n🔍 Possible causes:")
        print("   1. Firewall blocking connection")
        print("   2. Server not responding")
        print("\n✅ Solution:")
        print("   1. Check if port 8000 is accessible")
        print("   2. Try: telnet localhost 8000")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        print(f"\n🔍 Error type: {type(e).__name__}")
        sys.exit(1)

if __name__ == "__main__":
    print("\n⚙️ Configuration:")
    print(f"   WebSocket URL: {WS_URL}")
    if TOKEN:
        print("   Token: Set")
    else:
        print("   Token: Not set (pass via --token or WS_TOKEN env var)")
    print()
    
    # Check if websockets is installed
    try:
        import websockets
    except ImportError:
        print("❌ websockets package not installed!")
        print("\n✅ Install it:")
        print("   pip install websockets")
        sys.exit(1)
    
    # Run async test
    asyncio.run(test_websocket_connection())

