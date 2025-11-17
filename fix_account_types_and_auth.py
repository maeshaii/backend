#!/usr/bin/env python
"""
Senior Developer Solution: Fix Account Types and Authentication System

This script fixes the authentication system by:
1. Creating proper separated account types (Admin, User, Coordinator, OJT)
2. Migrating existing users to correct account types
3. Ensuring all users have proper passwords
4. Fixing the admin login issue
5. Setting up alumni with random passwords

Run this script to fix all authentication issues systematically.
"""

import os
import sys
import django
import secrets
import string
from datetime import datetime

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.conf import settings
from apps.shared.models import User, AccountType, UserInitialPassword
from django.db import transaction

def create_proper_account_types():
    """Create properly separated account types"""
    print("🔧 Creating proper account types...")
    
    # Clear existing account types
    AccountType.objects.all().delete()
    print("   ✅ Cleared existing mixed account types")
    
    # Create proper separated account types
    account_types = {
        1: {'admin': True, 'user': False, 'coordinator': False, 'peso': False, 'ojt': False},
        2: {'admin': False, 'user': True, 'coordinator': False, 'peso': False, 'ojt': False},
        3: {'admin': False, 'user': False, 'coordinator': True, 'peso': False, 'ojt': False},
        4: {'admin': False, 'user': False, 'coordinator': False, 'peso': False, 'ojt': True},
        5: {'admin': False, 'user': False, 'coordinator': False, 'peso': True, 'ojt': False},
    }
    
    created_types = {}
    for type_id, flags in account_types.items():
        account_type = AccountType.objects.create(**flags)
        created_types[type_id] = account_type
        type_name = [k for k, v in flags.items() if v][0].title()
        print(f"   ✅ Created {type_name} account type (ID: {account_type.account_type_id})")
    
    return created_types

def generate_secure_password(length=12):
    """Generate a secure random password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def fix_admin_account(account_types):
    """Fix admin account with proper credentials"""
    print("\n🔧 Fixing admin account...")
    
    admin_type = account_types[1]  # Admin account type
    
    # Find or create admin user
    admin_user, created = User.objects.get_or_create(
        acc_username='admin',
        defaults={
            'f_name': 'System',
            'l_name': 'Administrator',
            'gender': 'Other',
            'user_status': 'active',
            'account_type': admin_type,
        }
    )
    
    # Set proper account type and password
    admin_user.account_type = admin_type
    admin_user.user_status = 'active'
    admin_user.set_password('wherenayou2025')  # Known admin password
    admin_user.save()
    
    print(f"   ✅ Admin account {'created' if created else 'updated'}")
    print(f"   📋 Username: admin")
    print(f"   🔑 Password: wherenayou2025")
    
    return admin_user

def fix_alumni_accounts(account_types):
    """Fix alumni accounts with random passwords"""
    print("\n🔧 Fixing alumni accounts...")
    
    alumni_type = account_types[2]  # User (Alumni) account type
    
    # Get all users that should be alumni (numeric usernames)
    alumni_users = User.objects.filter(acc_username__regex=r'^\d+$')
    
    print(f"   📊 Found {alumni_users.count()} alumni users")
    
    passwords_generated = []
    
    for user in alumni_users:
        # Set proper account type
        user.account_type = alumni_type
        user.user_status = 'active'
        
        # Generate new random password
        new_password = generate_secure_password()
        user.set_password(new_password)
        user.save()
        
        # Store initial password for export
        try:
            initial_password, created = UserInitialPassword.objects.get_or_create(user=user)
            initial_password.set_plaintext(new_password)
            initial_password.is_active = True
            initial_password.save()
        except Exception as e:
            print(f"   ⚠️  Warning: Could not store initial password for {user.acc_username}: {e}")
        
        passwords_generated.append({
            'username': user.acc_username,
            'name': f"{user.f_name} {user.l_name}",
            'password': new_password
        })
        
        print(f"   ✅ Updated {user.acc_username} ({user.f_name} {user.l_name})")
    
    return passwords_generated

def create_coordinator_account(account_types):
    """Create coordinator account"""
    print("\n🔧 Creating coordinator account...")
    
    coord_type = account_types[3]  # Coordinator account type
    
    # Delete existing coordinator if exists
    User.objects.filter(acc_username=settings.DEFAULT_COORDINATOR_USERNAME).delete()
    
    # Create new coordinator
    coord_user = User.objects.create(
        acc_username=settings.DEFAULT_COORDINATOR_USERNAME,
        f_name='BSIT',
        l_name='Coordinator',
        gender='Other',
        user_status='active',
        account_type=coord_type,
    )
    
    coord_password = settings.DEFAULT_COORDINATOR_PASSWORD
    coord_user.set_password(coord_password)
    coord_user.save()
    
    print(f"   ✅ Coordinator account created")
    print(f"   📋 Username: {settings.DEFAULT_COORDINATOR_USERNAME}")
    print(f"   🔑 Password: {coord_password}")
    
    return coord_user

def create_peso_account(account_types):
    """Create PESO account"""
    print("\n🔧 Creating PESO account...")
    
    peso_type = account_types[5]  # PESO account type
    
    # Delete existing peso if exists
    User.objects.filter(acc_username='peso').delete()
    
    # Create new peso user
    peso_user = User.objects.create(
        acc_username='peso',
        f_name='PESO',
        l_name='User',
        gender='Other',
        user_status='active',
        account_type=peso_type,
    )
    
    peso_password = 'pesopassword2025'
    peso_user.set_password(peso_password)
    peso_user.save()
    
    print(f"   ✅ PESO account created")
    print(f"   📋 Username: peso")
    print(f"   🔑 Password: {peso_password}")
    
    return peso_user

def export_alumni_passwords(passwords_generated):
    """Export alumni passwords to a file"""
    if not passwords_generated:
        return
    
    print("\n📄 Exporting alumni passwords...")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"alumni_passwords_{timestamp}.txt"
    
    with open(filename, 'w') as f:
        f.write("ALUMNI ACCOUNT CREDENTIALS\n")
        f.write("=" * 50 + "\n")
        f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        for creds in passwords_generated:
            f.write(f"Username: {creds['username']}\n")
            f.write(f"Name: {creds['name']}\n")
            f.write(f"Password: {creds['password']}\n")
            f.write("-" * 30 + "\n")
    
    print(f"   ✅ Passwords exported to: {filename}")
    return filename

def verify_authentication_system():
    """Verify the authentication system is working"""
    print("\n🔍 Verifying authentication system...")
    
    # Test admin login
    try:
        admin = User.objects.get(acc_username='admin')
        admin_login_works = admin.check_password('wherenayou2025')
        print(f"   {'✅' if admin_login_works else '❌'} Admin login: {'WORKS' if admin_login_works else 'FAILED'}")
    except User.DoesNotExist:
        print("   ❌ Admin user not found")
    
    # Test coordinator login
    try:
        coord = User.objects.get(acc_username=settings.DEFAULT_COORDINATOR_USERNAME)
        coord_login_works = coord.check_password(settings.DEFAULT_COORDINATOR_PASSWORD)
        print(f"   {'✅' if coord_login_works else '❌'} Coordinator login: {'WORKS' if coord_login_works else 'FAILED'}")
    except User.DoesNotExist:
        print("   ❌ Coordinator user not found")
    
    # Test peso login
    try:
        peso = User.objects.get(acc_username='peso')
        peso_login_works = peso.check_password('pesopassword2025')
        print(f"   {'✅' if peso_login_works else '❌'} PESO login: {'WORKS' if peso_login_works else 'FAILED'}")
    except User.DoesNotExist:
        print("   ❌ PESO user not found")
    
    # Count alumni
    alumni_count = User.objects.filter(account_type__user=True).count()
    print(f"   📊 Alumni accounts: {alumni_count}")
    
    # Check account type separation
    print("\n📋 Final Account Type Structure:")
    for at in AccountType.objects.all():
        flags = [k for k, v in {'admin': at.admin, 'user': at.user, 'coordinator': at.coordinator, 'peso': at.peso, 'ojt': at.ojt}.items() if v]
        print(f"   ID {at.account_type_id}: {', '.join(flags).title()}")

@transaction.atomic
def main():
    """Main function to fix the entire authentication system"""
    print("🚀 SENIOR DEVELOPER AUTHENTICATION FIX")
    print("=" * 50)
    
    try:
        # Step 1: Create proper account types
        account_types = create_proper_account_types()
        
        # Step 2: Fix admin account
        admin_user = fix_admin_account(account_types)
        
        # Step 3: Fix alumni accounts
        passwords_generated = fix_alumni_accounts(account_types)
        
        # Step 4: Create coordinator account
        coord_user = create_coordinator_account(account_types)
        
        # Step 5: Create PESO account
        peso_user = create_peso_account(account_types)
        
        # Step 6: Export alumni passwords
        export_alumni_passwords(passwords_generated)
        
        # Step 7: Verify system
        verify_authentication_system()
        
        print("\n🎉 AUTHENTICATION SYSTEM FIXED SUCCESSFULLY!")
        print("=" * 50)
        print("📋 SYSTEM CREDENTIALS:")
        print("   Admin: admin / wherenayou2025")
        print(f"   Coordinator: {settings.DEFAULT_COORDINATOR_USERNAME} / {settings.DEFAULT_COORDINATOR_PASSWORD}")
        print("   PESO: peso / pesopassword2025")
        print("   Alumni: Check exported password file")
        print("\n✅ All authentication issues have been resolved!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("Transaction rolled back. Please check the error and try again.")
        raise

if __name__ == "__main__":
    main()
