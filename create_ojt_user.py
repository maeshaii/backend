#!/usr/bin/env python
"""
Script to create a single OJT user
"""
import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, AccountType, UserProfile, AcademicInfo, TrackerData, OJTInfo
from django.contrib.auth.hashers import make_password
import secrets
import string

def create_ojt_user():
    """Create a single OJT user"""
    
    # Get or create OJT account type
    ojt_account_type, created = AccountType.objects.get_or_create(
        ojt=True,
        admin=False,
        peso=False,
        user=False,
        coordinator=False
    )
    
    if created:
        print("Created OJT account type")
    else:
        print("Using existing OJT account type")
    
    # Generate a random password
    password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
    
    # Create OJT user
    ojt_user = User.objects.create(
        acc_username='ojt001',
        user_status='active',
        f_name='John',
        m_name='Doe',
        l_name='Smith',
        gender='M',
        account_type=ojt_account_type
    )
    ojt_user.set_password(password)
    ojt_user.save()
    
    # Create related models
    UserProfile.objects.create(user=ojt_user)
    AcademicInfo.objects.create(user=ojt_user)
    TrackerData.objects.create(user=ojt_user)
    OJTInfo.objects.create(
        user=ojt_user,
        ojtstatus='Active',
        company_name='Sample Company',
        position='OJT Trainee'
    )
    
    print(f"✅ OJT User created successfully!")
    print(f"Username: {ojt_user.acc_username}")
    print(f"Password: {password}")
    print(f"Name: {ojt_user.f_name} {ojt_user.l_name}")
    print(f"User ID: {ojt_user.user_id}")
    
    return ojt_user

if __name__ == "__main__":
    try:
        user = create_ojt_user()
        print(f"\nOJT user created with ID: {user.user_id}")
    except Exception as e:
        print(f"Error creating OJT user: {e}")
        sys.exit(1)
