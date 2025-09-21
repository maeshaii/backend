#!/usr/bin/env python
"""
Complete Admin Account Diagnostic and Fix Script

This script will:
1. Check current admin account status
2. Diagnose any issues
3. Fix admin account if needed
4. Verify the fix works
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, AccountType
from django.db import transaction

def check_admin_account():
    """Check current admin account status"""
    print("🔍 CHECKING ADMIN ACCOUNT STATUS")
    print("=" * 40)
    
    try:
        admin = User.objects.get(acc_username='admin')
        print(f"✅ Admin user exists")
        print(f"   Username: {admin.acc_username}")
        print(f"   Name: {admin.f_name} {admin.l_name}")
        print(f"   Status: {admin.user_status}")
        print(f"   Account Type ID: {admin.account_type.account_type_id}")
        print(f"   Account Type Flags: Admin={admin.account_type.admin}, User={admin.account_type.user}")
        print(f"   Password Set: {bool(admin.acc_password)}")
        
        # Test password
        password_works = admin.check_password('wherenayou2025')
        print(f"   Password 'wherenayou2025' works: {password_works}")
        
        return admin, password_works
        
    except User.DoesNotExist:
        print("❌ Admin user does not exist!")
        return None, False
    except Exception as e:
        print(f"❌ Error checking admin: {e}")
        return None, False

def check_account_types():
    """Check current account types"""
    print("\n🔍 CHECKING ACCOUNT TYPES")
    print("=" * 40)
    
    account_types = AccountType.objects.all()
    print(f"Total account types: {account_types.count()}")
    
    for at in account_types:
        flags = []
        if at.admin: flags.append("Admin")
        if at.user: flags.append("User")
        if at.coordinator: flags.append("Coordinator")
        if at.peso: flags.append("PESO")
        if at.ojt: flags.append("OJT")
        
        print(f"   ID {at.account_type_id}: {', '.join(flags) if flags else 'No flags'}")
    
    return account_types

def fix_admin_account():
    """Fix admin account"""
    print("\n🔧 FIXING ADMIN ACCOUNT")
    print("=" * 40)
    
    # Get or create admin account type
    admin_type, created = AccountType.objects.get_or_create(
        admin=True,
        defaults={
            'user': False,
            'coordinator': False,
            'peso': False,
            'ojt': False
        }
    )
    
    if created:
        print(f"✅ Created admin account type (ID: {admin_type.account_type_id})")
    else:
        print(f"✅ Using existing admin account type (ID: {admin_type.account_type_id})")
    
    # Delete existing admin if exists
    User.objects.filter(acc_username='admin').delete()
    print("✅ Cleared existing admin user")
    
    # Create new admin user
    admin_user = User.objects.create(
        acc_username='admin',
        f_name='System',
        l_name='Administrator',
        gender='Other',
        user_status='active',
        account_type=admin_type,
    )
    
    # Set password
    admin_user.set_password('wherenayou2025')
    admin_user.save()
    
    print("✅ Created new admin user")
    print(f"   Username: admin")
    print(f"   Password: wherenayou2025")
    print(f"   Account Type: Admin only")
    
    return admin_user

def verify_fix():
    """Verify the fix works"""
    print("\n🔍 VERIFYING FIX")
    print("=" * 40)
    
    try:
        admin = User.objects.get(acc_username='admin')
        password_works = admin.check_password('wherenayou2025')
        
        print(f"✅ Admin user exists: {admin is not None}")
        print(f"✅ Password works: {password_works}")
        print(f"✅ Account type: Admin={admin.account_type.admin}, User={admin.account_type.user}")
        print(f"✅ Status: {admin.user_status}")
        
        if password_works and admin.account_type.admin and not admin.account_type.user:
            print("\n🎉 ADMIN ACCOUNT FIXED SUCCESSFULLY!")
            print("You can now log in with:")
            print("   Username: admin")
            print("   Password: wherenayou2025")
            return True
        else:
            print("\n❌ Fix verification failed!")
            return False
            
    except Exception as e:
        print(f"❌ Verification error: {e}")
        return False

def main():
    """Main function"""
    print("🚀 ADMIN ACCOUNT DIAGNOSTIC AND FIX")
    print("=" * 50)
    
    # Step 1: Check current status
    admin, password_works = check_admin_account()
    
    # Step 2: Check account types
    account_types = check_account_types()
    
    # Step 3: Fix if needed
    if not admin or not password_works:
        print("\n🔧 Admin account needs fixing...")
        with transaction.atomic():
            admin_user = fix_admin_account()
            
            # Step 4: Verify fix
            success = verify_fix()
            
            if success:
                print("\n✅ All done! Admin account is working.")
            else:
                print("\n❌ Fix failed. Please check the errors above.")
    else:
        print("\n✅ Admin account is already working correctly!")
        print("You can log in with:")
        print("   Username: admin")
        print("   Password: wherenayou2025")

if __name__ == "__main__":
    main()
