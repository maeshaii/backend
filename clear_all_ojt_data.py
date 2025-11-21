#!/usr/bin/env python
"""
Clear All OJT Data Script

This script deletes ALL OJT-related data from the database, allowing you to re-import fresh data.

WHAT IT DELETES:
- All OJT users (account_type.ojt=True)
- All OJT information records
- All OJT company profiles
- All academic information for OJT users
- All user profiles for OJT users
- All employment history for OJT users
- All initial passwords for OJT users
- All OJT import records
- All scheduled send dates (both processed and unprocessed)

⚠️ WARNING: This action is IRREVERSIBLE!
⚠️ Make sure you have a backup before running this script!

Usage:
    python backend/clear_all_ojt_data.py
"""

import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.db import transaction
from apps.shared.models import (
    User, OJTImport, OJTInfo, AcademicInfo, OJTCompanyProfile,
    UserProfile, EmploymentHistory, UserInitialPassword, SendDate
)


def clear_all_ojt_data():
    """Clear all OJT-related data from the database."""
    
    print("\n" + "="*70)
    print("⚠️  CLEAR ALL OJT DATA")
    print("="*70)
    
    # Count existing data
    ojt_users = User.objects.filter(account_type__ojt=True)
    user_count = ojt_users.count()
    
    if user_count == 0:
        print("\n✅ No OJT data found in the database. Nothing to clear.")
        return
    
    print(f"\n📊 Current OJT Data:")
    print(f"   - OJT Users: {user_count}")
    print(f"   - OJT Info Records: {OJTInfo.objects.filter(user__in=ojt_users).count()}")
    print(f"   - Company Profiles: {OJTCompanyProfile.objects.filter(user__in=ojt_users).count()}")
    print(f"   - Academic Records: {AcademicInfo.objects.filter(user__in=ojt_users).count()}")
    print(f"   - Import Records: {OJTImport.objects.all().count()}")
    print(f"   - Send Date Schedules: {SendDate.objects.all().count()}")
    
    print("\n⚠️  WARNING: This will PERMANENTLY DELETE all the above data!")
    print("⚠️  This action CANNOT be undone!")
    
    # Confirmation prompts
    print("\n" + "-"*70)
    confirm1 = input("Type 'DELETE' to confirm you want to delete all OJT data: ")
    
    if confirm1 != "DELETE":
        print("\n❌ Operation cancelled. No data was deleted.")
        return
    
    confirm2 = input("Type 'YES' to confirm again: ")
    
    if confirm2 != "YES":
        print("\n❌ Operation cancelled. No data was deleted.")
        return
    
    # Proceed with deletion
    print("\n🗑️  Deleting all OJT data...")
    
    try:
        with transaction.atomic():
            # Delete all related data
            ojt_info_count = OJTInfo.objects.filter(user__in=ojt_users).delete()[0]
            print(f"   ✓ Deleted {ojt_info_count} OJT info records")
            
            ojt_company_count = OJTCompanyProfile.objects.filter(user__in=ojt_users).delete()[0]
            print(f"   ✓ Deleted {ojt_company_count} company profiles")
            
            academic_count = AcademicInfo.objects.filter(user__in=ojt_users).delete()[0]
            print(f"   ✓ Deleted {academic_count} academic records")
            
            profile_count = UserProfile.objects.filter(user__in=ojt_users).delete()[0]
            print(f"   ✓ Deleted {profile_count} user profiles")
            
            employment_count = EmploymentHistory.objects.filter(user__in=ojt_users).delete()[0]
            print(f"   ✓ Deleted {employment_count} employment records")
            
            password_count = UserInitialPassword.objects.filter(user__in=ojt_users).delete()[0]
            print(f"   ✓ Deleted {password_count} initial passwords")
            
            # Delete the OJT users themselves
            deleted_users = ojt_users.delete()[0]
            print(f"   ✓ Deleted {deleted_users} OJT users")
            
            # Remove import history
            import_count = OJTImport.objects.all().delete()[0]
            print(f"   ✓ Deleted {import_count} import records")
            
            # Clear all scheduled send dates
            send_date_count = SendDate.objects.all().delete()[0]
            print(f"   ✓ Deleted {send_date_count} send date schedules")
        
        print("\n" + "="*70)
        print("✅ SUCCESS! All OJT data has been permanently deleted.")
        print("="*70)
        print(f"\nDeleted:")
        print(f"  - {user_count} OJT users")
        print(f"  - {ojt_info_count} OJT info records")
        print(f"  - {ojt_company_count} company profiles")
        print(f"  - {academic_count} academic records")
        print(f"  - {profile_count} user profiles")
        print(f"  - {employment_count} employment records")
        print(f"  - {password_count} passwords")
        print(f"  - {import_count} import records")
        print(f"  - {send_date_count} send date schedules")
        print("\n✅ The database is now clean. You can re-import OJT data.\n")
        
    except Exception as e:
        print(f"\n❌ ERROR: Failed to clear OJT data")
        print(f"   Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    clear_all_ojt_data()

