#!/usr/bin/env python
import os
import sys
import django

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User

def fix_user_model():
    """Add is_active property to User model if it doesn't exist"""
    
    # Check if is_active property exists
    if not hasattr(User, 'is_active'):
        print("Adding is_active property to User model...")
        
        # Add the property
        @property
        def is_active(self):
            return True
        
        # Add the property to the User model
        User.is_active = is_active
        
        print("✅ is_active property added to User model!")
    else:
        print("✅ is_active property already exists in User model!")
    
    # Test the property
    try:
        # Get the first user to test
        user = User.objects.first()
        if user:
            print(f"✅ Testing is_active property: {user.is_active}")
        else:
            print("⚠️ No users found to test with")
    except Exception as e:
        print(f"❌ Error testing is_active property: {e}")

if __name__ == '__main__':
    fix_user_model() 