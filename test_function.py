import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from apps.api.views import coordinator_requests_list_view

print('=== Testing coordinator_requests_list_view function directly ===')

try:
    # Create a mock request
    factory = RequestFactory()
    request = factory.get('/api/ojt/coordinator-requests/list/')
    
    # Mock authentication - create a simple user object
    class MockUser:
        is_authenticated = True
        id = 1
        username = 'test'
    
    request.user = MockUser()
    
    print('Calling coordinator_requests_list_view...')
    response = coordinator_requests_list_view(request)
    
    print(f'Response status: {response.status_code}')
    if response.status_code == 200:
        print('SUCCESS! Function executed without errors')
        # Try to get the content
        try:
            content = response.content.decode('utf-8')
            print(f'Response content: {content}')
        except Exception as e:
            print(f'Could not decode content: {e}')
    else:
        print(f'Error status: {response.status_code}')
        try:
            content = response.content.decode('utf-8')
            print(f'Error content: {content}')
        except Exception as e:
            print(f'Could not decode error content: {e}')
            
except Exception as e:
    print(f'Function call failed: {e}')
    import traceback
    traceback.print_exc()

















