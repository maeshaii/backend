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

def create_peso_account():
    try:
        # Check if peso account type exists, if not create it
        peso_account_type, created = AccountType.objects.get_or_create(
            peso=True,
            defaults={
                'admin': False,
                'user': False,
                'coordinator': False,
                'ojt': False
            }
        )
        
        if created:
            print(f"✅ Created new peso account type")
        else:
            print(f"✅ Using existing peso account type")
        
        # Delete existing peso user if present
        User.objects.filter(acc_username='peso').delete()
        
        # Check if user already exists
        username = 'peso'
        if User.objects.filter(acc_username=username).exists():
            print(f"❌ User with username '{username}' already exists!")
            return
        
        # Create the peso user with requested password
        peso_password = 'pesopassword2025'
        
        peso_user = User.objects.create(
            account_type=peso_account_type,
            acc_username=username,
            user_status='active',
            f_name='CTU',
            l_name='PESO',
            gender='N/A'  # keep within max_length=10
        )
        peso_user.set_password(peso_password)
        peso_user.save()
        
        print(f"✅ Successfully created peso account!")
        print(f"   Username: {peso_user.acc_username}")
        print(f"   Password: {peso_password} (securely hashed)")
        print(f"   Account Type: Peso")
        print(f"   Status: {peso_user.user_status}")
        
    except Exception as e:
        print(f"❌ Error creating peso account: {e}")

if __name__ == '__main__':
    create_peso_account()
