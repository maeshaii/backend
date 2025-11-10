#!/usr/bin/env python
"""
FIX SCRIPT: Populate TrackerData from existing TrackerResponse records

ISSUE: Alumni submitted tracker forms, but the data is only stored in
TrackerResponse.answers (JSON) and NOT copied to TrackerData model fields.
Statistics queries look at TrackerData fields, so they return 0.

SOLUTION: Re-run update_user_fields() for all TrackerResponse records.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import TrackerResponse, TrackerData, User
from django.db import transaction

print("=" * 80)
print("FIX SCRIPT: Migrating TrackerResponse data to TrackerData")
print("=" * 80)

# Get all TrackerResponse records
tracker_responses = TrackerResponse.objects.all()
total_responses = tracker_responses.count()

print(f"\nFound {total_responses} TrackerResponse records to process")

if total_responses == 0:
    print("\n❌ No TrackerResponse records found. Alumni haven't submitted tracker yet.")
    print("   Please have alumni submit the tracker form first.")
    exit(0)

# Check current state
print("\n📊 BEFORE FIX:")
print("-" * 80)
empty_tracker_data = TrackerData.objects.filter(q_employment_status__isnull=True).count()
total_tracker_data = TrackerData.objects.count()
print(f"TrackerData records with empty q_employment_status: {empty_tracker_data}/{total_tracker_data}")

# Process each TrackerResponse
print("\n🔄 PROCESSING:")
print("-" * 80)
success_count = 0
error_count = 0
errors = []

for idx, tr in enumerate(tracker_responses, 1):
    try:
        print(f"\n[{idx}/{total_responses}] Processing user: {tr.user.full_name} (ID: {tr.user.user_id})")
        
        # Show sample of answers
        if tr.answers:
            employment_status = tr.answers.get('21', 'N/A')
            employment_type = tr.answers.get('23', 'N/A')
            company_name = tr.answers.get('25', 'N/A')
            print(f"   - Q21 (Employment Status): {employment_status}")
            print(f"   - Q23 (Employment Type): {employment_type}")
            print(f"   - Q25 (Company Name): {company_name}")
        
        # Get or create TrackerData BEFORE calling update_user_fields
        tracker_data, created = TrackerData.objects.get_or_create(user=tr.user)
        if created:
            print(f"   ✓ Created new TrackerData record")
        else:
            print(f"   ✓ Found existing TrackerData record")
        
        # Re-run update_user_fields to populate TrackerData
        with transaction.atomic():
            tr.update_user_fields()
        
        # Verify the data was copied
        tracker_data.refresh_from_db()
        if tracker_data.q_employment_status:
            print(f"   ✅ SUCCESS: q_employment_status = {tracker_data.q_employment_status}")
            success_count += 1
        else:
            print(f"   ⚠️  WARNING: q_employment_status still None after update")
            print(f"      This might be normal if Question 21 wasn't answered")
            success_count += 1  # Still count as success since update ran
            
    except Exception as e:
        print(f"   ❌ ERROR: {str(e)}")
        error_count += 1
        errors.append((tr.user.user_id, str(e)))

# Check final state
print("\n\n📊 AFTER FIX:")
print("-" * 80)
empty_tracker_data_after = TrackerData.objects.filter(q_employment_status__isnull=True).count()
total_tracker_data_after = TrackerData.objects.count()
filled_tracker_data = total_tracker_data_after - empty_tracker_data_after

print(f"TrackerData records with employment_status: {filled_tracker_data}/{total_tracker_data_after}")
print(f"TrackerData records still empty: {empty_tracker_data_after}/{total_tracker_data_after}")

# Summary
print("\n" + "=" * 80)
print("SUMMARY:")
print("=" * 80)
print(f"✅ Successfully processed: {success_count}/{total_responses}")
print(f"❌ Errors: {error_count}/{total_responses}")

if error_count > 0:
    print("\nErrors encountered:")
    for user_id, error_msg in errors:
        print(f"  - User {user_id}: {error_msg}")

# Show sample TrackerData
print("\n" + "=" * 80)
print("SAMPLE TrackerData (first 3 records):")
print("=" * 80)
for idx, td in enumerate(TrackerData.objects.all()[:3], 1):
    print(f"\n{idx}. User: {td.user.full_name}")
    print(f"   - q_employment_status: {td.q_employment_status}")
    print(f"   - q_employment_type: {td.q_employment_type}")
    print(f"   - q_company_name: {td.q_company_name}")
    print(f"   - q_current_position: {td.q_current_position}")
    print(f"   - q_sector_current: {td.q_sector_current}")
    print(f"   - q_scope_current: {td.q_scope_current}")

# Test statistics query
print("\n" + "=" * 80)
print("TESTING STATISTICS QUERY:")
print("=" * 80)
from django.db.models import Q, Count

alumni_qs = User.objects.filter(account_type__user=True)
employment_stats = TrackerData.objects.filter(user__in=alumni_qs).aggregate(
    employed=Count('id', filter=Q(q_employment_status__iexact='yes')),
    unemployed=Count('id', filter=Q(q_employment_status__iexact='no'))
)

print(f"Employed: {employment_stats['employed']}")
print(f"Unemployed: {employment_stats['unemployed']}")

if employment_stats['employed'] > 0 or employment_stats['unemployed'] > 0:
    print("\n✅ SUCCESS! Statistics should now show correct values!")
else:
    print("\n⚠️  Statistics still showing 0. Checking reasons...")
    print("\nPossible reasons:")
    print("1. Alumni answered 'No' or other values for employment status")
    print("2. Question 21 mapping might be different")
    print("3. Check the actual values in TrackerResponse.answers")

print("\n" + "=" * 80)
print("FIX COMPLETE!")
print("=" * 80)
print("\nNext steps:")
print("1. Refresh your frontend statistics page")
print("2. If still showing 0, run: python diagnose_tracker_data.py")
print("3. Clear browser cache and try again")

