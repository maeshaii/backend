#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.api.views import ojt_by_year_view
from django.test import RequestFactory
from django.contrib.auth import get_user_model

User = get_user_model()

# Create a test request
rf = RequestFactory()
request = rf.get('/api/ojt/by-year/?year=2025&section=4-C')

# Get an OJT user for authentication
ojt_user = User.objects.filter(account_type__ojt=True).first()
if ojt_user:
    request.user = ojt_user
    print(f"Testing with user: {ojt_user.acc_username}")
    
    try:
        response = ojt_by_year_view(request)
        print(f"Response status: {response.status_code}")
        if response.status_code == 200:
            response.render()
            print(f"Response content: {response.content.decode()}")
        else:
            print(f"Error response: {response.status_code}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
else:
    print("No OJT user found")


