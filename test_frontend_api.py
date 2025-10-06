#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from apps.shared.models import User, AccountType
import json

def test_frontend_api():
    """Test the actual API endpoint that the frontend calls"""
    
    print("🔍 Testing frontend API endpoint...")
    
    # Create a test coordinator user
    User = get_user_model()
    
    # Get or create coordinator account type
    coord_type, _ = AccountType.objects.get_or_create(
        coordinator=True,
        defaults={'admin': False, 'peso': False, 'user': False, 'ojt': False}
    )
    
    # Create test coordinator
    coordinator, _ = User.objects.get_or_create(
        acc_username='test_coordinator',
        defaults={
            'account_type': coord_type,
            'f_name': 'Test',
            'l_name': 'Coordinator',
            'user_status': 'active'
        }
    )
    
    # Create a test client
    client = Client()
    
    # Login the coordinator
    client.force_login(coordinator)
    
    # Test the ojt/by-year endpoint
    response = client.get('/api/ojt/by-year/?year=2023&coordinator=test_coordinator')
    
    print(f"Response status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response success: {data.get('success')}")
        
        ojt_data = data.get('ojt_data', [])
        print(f"Number of OJT records: {len(ojt_data)}")
        
        for user in ojt_data:
            print(f"\n📋 User: {user.get('name')}")
            print(f"   ID: {user.get('id')}")
            print(f"   OJT Status: {user.get('ojt_status')}")
            print(f"   Is Sent to Admin: {user.get('is_sent_to_admin')}")
    else:
        print(f"Error response: {response.content}")

if __name__ == "__main__":
    test_frontend_api()
