import requests
import time

# Wait a moment for server to start
time.sleep(2)

try:
    # Test if server is running
    response = requests.get("http://127.0.0.1:8000/api/ojt/coordinator-requests/list/", timeout=5)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except requests.exceptions.ConnectionError:
    print("Server is not running or not accessible")
except requests.exceptions.Timeout:
    print("Server timeout")
except Exception as e:
    print(f"Error: {e}")

















