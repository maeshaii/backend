"""
Load Testing Script for CTU Alumni Messaging System
Uses Locust for distributed load testing

Installation:
    pip install locust

Usage:
    # Start Locust web UI
    locust -f locustfile.py --host=http://localhost:8000

    # Or run headless
    locust -f locustfile.py --host=http://localhost:8000 --users 100 --spawn-rate 10 --run-time 5m --headless

Test Scenarios:
    1. Basic API load testing (conversations, messages)
    2. WebSocket connection simulation
    3. Concurrent message sending
    4. Health check monitoring
"""
from locust import HttpUser, task, between, events
import json
import logging

logger = logging.getLogger(__name__)


class MessagingUser(HttpUser):
    """
    Simulates a user interacting with the messaging system.
    Each user will authenticate, load conversations, and send messages.
    """
    
    # Wait between 1-5 seconds between tasks (realistic user behavior)
    wait_time = between(1, 5)
    
    def on_start(self):
        """
        Called when a simulated user starts.
        Authenticate and get token.
        """
        # For testing, you'll need to create test users or use existing ones
        # This is a placeholder - adjust based on your authentication
        self.token = None
        self.conversation_id = None
        
        # Try to login (adjust credentials as needed)
        try:
            response = self.client.post(
                "/api/auth/login/",
                json={"username": "test_user", "password": "test_password"},
                name="/api/auth/login [AUTH]"
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data.get('access_token') or data.get('token')
                logger.info(f"User authenticated: {self.token[:20]}...")
        except Exception as e:
            logger.warning(f"Authentication failed (expected if no test users): {e}")
    
    def get_headers(self):
        """Get headers with authentication token"""
        if self.token:
            return {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
        return {"Content-Type": "application/json"}
    
    @task(10)
    def health_check(self):
        """Test health check endpoint (high frequency)"""
        self.client.get(
            "/api/messaging/health/",
            name="/api/messaging/health [HEALTH]"
        )
    
    @task(5)
    def list_conversations(self):
        """Test listing conversations"""
        response = self.client.get(
            "/api/messaging/conversations/",
            headers=self.get_headers(),
            name="/api/messaging/conversations [LIST]"
        )
        
        # Store first conversation ID for message testing
        if response.status_code == 200:
            try:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    self.conversation_id = data[0].get('conversation_id')
            except Exception:
                pass
    
    @task(8)
    def list_messages(self):
        """Test listing messages in a conversation"""
        if not self.conversation_id:
            # Skip if no conversation available
            return
        
        self.client.get(
            f"/api/messaging/conversations/{self.conversation_id}/messages/",
            headers=self.get_headers(),
            name="/api/messaging/conversations/:id/messages [LIST]"
        )
    
    @task(3)
    def send_message(self):
        """Test sending a message"""
        if not self.conversation_id:
            # Skip if no conversation available
            return
        
        self.client.post(
            f"/api/messaging/conversations/{self.conversation_id}/messages/",
            headers=self.get_headers(),
            json={
                "content": f"Load test message at {self.environment.runner.stats.total.start_time}",
                "message_type": "text"
            },
            name="/api/messaging/conversations/:id/messages [CREATE]"
        )
    
    @task(2)
    def mark_conversation_read(self):
        """Test marking conversation as read"""
        if not self.conversation_id:
            return
        
        self.client.post(
            f"/api/messaging/conversations/{self.conversation_id}/read/",
            headers=self.get_headers(),
            name="/api/messaging/conversations/:id/read [UPDATE]"
        )
    
    @task(1)
    def get_messaging_stats(self):
        """Test getting messaging statistics"""
        self.client.get(
            "/api/messaging/stats/",
            headers=self.get_headers(),
            name="/api/messaging/stats [STATS]"
        )
    
    @task(1)
    def search_users(self):
        """Test user search"""
        self.client.get(
            "/api/messaging/users/search/?q=test",
            headers=self.get_headers(),
            name="/api/messaging/users/search [SEARCH]"
        )


class AnonymousUser(HttpUser):
    """
    Simulates anonymous users hitting public endpoints.
    Tests rate limiting and DDoS protection.
    """
    
    wait_time = between(0.1, 1)  # Aggressive testing
    
    @task
    def health_check_spam(self):
        """Test health check under load"""
        self.client.get("/api/messaging/health/")


# Event hooks for custom metrics
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when the test starts"""
    print("\n" + "="*80)
    print("🚀 LOAD TEST STARTING")
    print("="*80)
    print(f"Host: {environment.host}")
    print(f"Users: {environment.runner.target_user_count if hasattr(environment.runner, 'target_user_count') else 'N/A'}")
    print("="*80 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when the test stops"""
    print("\n" + "="*80)
    print("🏁 LOAD TEST COMPLETE")
    print("="*80)
    
    stats = environment.runner.stats
    print(f"Total Requests: {stats.total.num_requests}")
    print(f"Failed Requests: {stats.total.num_failures}")
    print(f"Success Rate: {((stats.total.num_requests - stats.total.num_failures) / stats.total.num_requests * 100):.2f}%" if stats.total.num_requests > 0 else "N/A")
    print(f"Avg Response Time: {stats.total.avg_response_time:.2f}ms")
    print(f"Max Response Time: {stats.total.max_response_time:.2f}ms")
    print(f"Requests/sec: {stats.total.total_rps:.2f}")
    print("="*80 + "\n")

