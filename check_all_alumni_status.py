#!/usr/bin/env python
"""
Quick check of all alumni and their tracker status
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, TrackerData, TrackerResponse

print("=" * 80)
print("ALUMNI TRACKER STATUS CHECK")
print("=" * 80)

alumni_users = User.objects.filter(account_type__user=True)
print(f"\nTotal Alumni: {alumni_users.count()}")

print("\n" + "=" * 80)
print("DETAILED STATUS:")
print("=" * 80)

for idx, user in enumerate(alumni_users, 1):
    print(f"\n{idx}. {user.full_name} (ID: {user.user_id})")
    
    # Check TrackerResponse
    has_response = TrackerResponse.objects.filter(user=user).exists()
    print(f"   - Has TrackerResponse: {has_response}")
    
    # Check TrackerData
    try:
        tracker_data = user.tracker_data
        print(f"   - Has TrackerData: Yes")
        print(f"   - Employment Status: {tracker_data.q_employment_status}")
        print(f"   - Employment Type: {tracker_data.q_employment_type}")
        print(f"   - Company: {tracker_data.q_company_name}")
    except:
        print(f"   - Has TrackerData: No")
    
    if has_response and not tracker_data.q_employment_status:
        print(f"   ⚠️  WARNING: Has response but TrackerData is empty!")
        print(f"   ➡️  Need to run fix_tracker_data_migration.py")

print("\n" + "=" * 80)

