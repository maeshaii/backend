import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, AcademicInfo, TrackerData, AccountType
from django.utils import timezone
from collections import Counter

def fix_2020_alumni_complete():
    """Complete fix for 2020 alumni visibility issue"""
    print("=" * 60)
    print("COMPLETE FIX FOR CLASS OF 2020 ALUMNI")
    print("=" * 60)
    
    # Step 1: Check current state
    print("\n1. CURRENT DATABASE STATE:")
    print("-" * 30)
    
    all_alumni = User.objects.filter(account_type__user=True)
    print(f"Total alumni users: {all_alumni.count()}")
    
    # Check AcademicInfo distribution
    year_counts = Counter()
    alumni_without_academic = []
    alumni_without_tracker = []
    
    for alumni in all_alumni:
        # Check AcademicInfo
        if hasattr(alumni, 'academic_info') and alumni.academic_info:
            year = alumni.academic_info.year_graduated
            if year:
                year_counts[year] += 1
        else:
            alumni_without_academic.append(alumni)
        
        # Check TrackerData
        if not TrackerData.objects.filter(user=alumni).exists():
            alumni_without_tracker.append(alumni)
    
    print(f"Years found: {dict(year_counts)}")
    print(f"Alumni without AcademicInfo: {len(alumni_without_academic)}")
    print(f"Alumni without TrackerData: {len(alumni_without_tracker)}")
    
    # Step 2: Fix missing AcademicInfo records
    if alumni_without_academic:
        print(f"\n2. FIXING {len(alumni_without_academic)} MISSING ACADEMIC INFO RECORDS:")
        print("-" * 50)
        
        # Get the most recent alumni (likely the imported ones)
        recent_alumni = sorted(alumni_without_academic, key=lambda x: x.user_id, reverse=True)[:10]
        
        for alumni in recent_alumni:
            try:
                # Create AcademicInfo with 2020 as default (you can change this)
                AcademicInfo.objects.create(
                    user=alumni,
                    year_graduated=2020,
                    course='BSIT'  # You can change this to match your import
                )
                print(f"  ✓ Created AcademicInfo for: {alumni.f_name} {alumni.l_name} (CTU: {alumni.acc_username})")
            except Exception as e:
                print(f"  ✗ Error creating AcademicInfo for {alumni.acc_username}: {e}")
    
    # Step 3: Fix missing TrackerData records
    if alumni_without_tracker:
        print(f"\n3. FIXING {len(alumni_without_tracker)} MISSING TRACKER DATA RECORDS:")
        print("-" * 50)
        
        for alumni in alumni_without_tracker:
            try:
                TrackerData.objects.create(
                    user=alumni,
                    q_employment_status='pending',
                    submitted_at=timezone.now()
                )
                print(f"  ✓ Created TrackerData for: {alumni.f_name} {alumni.l_name} (CTU: {alumni.acc_username})")
            except Exception as e:
                print(f"  ✗ Error creating TrackerData for {alumni.acc_username}: {e}")
    
    # Step 4: Verify the fix
    print(f"\n4. VERIFICATION AFTER FIX:")
    print("-" * 30)
    
    # Recheck AcademicInfo distribution
    year_counts_after = Counter()
    all_alumni_after = User.objects.filter(account_type__user=True)
    
    for alumni in all_alumni_after:
        if hasattr(alumni, 'academic_info') and alumni.academic_info:
            year = alumni.academic_info.year_graduated
            if year:
                year_counts_after[year] += 1
    
    print(f"Years found after fix: {dict(year_counts_after)}")
    
    # Check TrackerData distribution
    status_counts = Counter()
    tracker_records = TrackerData.objects.filter(user__account_type__user=True)
    for tracker in tracker_records:
        status = tracker.q_employment_status
        if status:
            status_counts[status] += 1
    
    print(f"TrackerData status distribution: {dict(status_counts)}")
    
    # Step 5: Test the statistics endpoint logic
    print(f"\n5. TESTING STATISTICS ENDPOINT LOGIC:")
    print("-" * 35)
    
    # This is the exact logic from alumni_statistics_view
    year_values = (
        User.objects
        .filter(account_type__user=True)
        .values_list('academic_info__year_graduated', flat=True)
    )
    year_counts_result = Counter([y for y in year_values if y is not None])
    
    years_list = [
        {'year': year, 'count': count}
        for year, count in sorted(year_counts_result.items(), reverse=True)
    ]
    
    print("Years list that will be returned to frontend:")
    for year_data in years_list:
        print(f"  {year_data}")
    
    # Step 6: Summary
    print(f"\n6. SUMMARY:")
    print("-" * 15)
    
    if 2020 in year_counts_result:
        print(f"✓ Class of 2020 is now visible with {year_counts_result[2020]} alumni")
        print("✓ The View Statistics page should now show a 2020 card")
        print("✓ The statistics bar graph should show pending alumni")
    else:
        print("✗ Class of 2020 is still not visible")
        print("  This might mean:")
        print("  - No alumni were actually imported")
        print("  - The import failed silently")
        print("  - The alumni have a different year set")
    
    print(f"\nTotal alumni in database: {all_alumni_after.count()}")
    print(f"Total TrackerData records: {tracker_records.count()}")

if __name__ == "__main__":
    fix_2020_alumni_complete()





























































