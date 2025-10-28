#!/usr/bin/env python
import os
import sys
import django
from datetime import datetime

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, AccountType

def create_coordinator_account():
    try:
        # Check if coordinator account type exists, if not create it
        coordinator_account_type, created = AccountType.objects.get_or_create(
            coordinator=True,
            defaults={
                'admin': False,
                'peso': False,
                'user': False,
                'ojt': False
            }
        )
        
        if created:
            print(f"✅ Created new coordinator account type")
        else:
            print(f"✅ Using existing coordinator account type")
        
        # Check if user already exists
        username = 'coordinator'
        existing_user = User.objects.filter(acc_username=username).first()
        
        if existing_user:
            print(f"ℹ️ Coordinator account already exists!")
            print(f"   Username: {username}")
            print(f"   Password: coordiwherenayou2025")
            print(f"   Status: {existing_user.user_status}")
            print(f"\n✅ You can login with these credentials.")
            return
        
        # Create the coordinator user with requested password
        coordinator_password = 'coordiwherenayou2025'
        
        coordinator_user = User.objects.create(
            account_type=coordinator_account_type,
            acc_username=username,
            user_status='active',
            f_name='Coordinator',
            l_name='User',
            gender='N/A'  # keep within max_length=10
        )
        coordinator_user.set_password(coordinator_password)
        coordinator_user.save()
        
        print(f"✅ Successfully created coordinator account!")
        print(f"   Username: {coordinator_user.acc_username}")
        print(f"   Password: {coordinator_password} (securely hashed)")
        print(f"   Account Type: Coordinator")
        print(f"   Status: {coordinator_user.user_status}")
        
    except Exception as e:
        print(f"❌ Error creating coordinator account: {e}")

if __name__ == '__main__':
    create_coordinator_account() 