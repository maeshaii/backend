#!/usr/bin/env python
"""
Script to get OJT user password from the database
"""
import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, UserInitialPassword

def get_ojt_passwords():
    """Get passwords for all OJT users"""
    
    # Find all OJT users
    ojt_users = User.objects.filter(account_type__ojt=True)
    
    if not ojt_users.exists():
        print("No OJT users found in the database")
        return
    
    print(f"Found {ojt_users.count()} OJT user(s):")
    print("=" * 50)
    
    for user in ojt_users:
        print(f"User ID: {user.user_id}")
        print(f"Username: {user.acc_username}")
        print(f"Name: {user.f_name} {user.l_name}")
        print(f"Status: {user.user_status}")
        
        # Try to get the stored password
        try:
            initial_password = UserInitialPassword.objects.get(user=user)
            if initial_password.is_active:
                password = initial_password.get_plaintext()
                print(f"Password: {password}")
            else:
                print("Password: Not available (inactive)")
        except UserInitialPassword.DoesNotExist:
            print("Password: Not stored in UserInitialPassword")
        except Exception as e:
            print(f"Password: Error retrieving - {e}")
        
        print("-" * 30)

if __name__ == "__main__":
    try:
        get_ojt_passwords()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
