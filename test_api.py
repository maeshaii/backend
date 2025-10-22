import requests
import json

try:
    # Test the coordinator requests list endpoint
    url = "http://127.0.0.1:8000/api/ojt/coordinator-requests/list/"
    response = requests.get(url)
    
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Success! Response: {json.dumps(data, indent=2)}")
    else:
        print(f"Error Response: {response.text}")
        
except Exception as e:
    print(f"Request failed: {e}")
    import traceback
    traceback.print_exc()















