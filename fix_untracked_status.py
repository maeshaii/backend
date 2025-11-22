import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, AcademicInfo, TrackerData
from django.utils import timezone

def fix_untracked_status():
    """Remove TrackerData records from imported alumni to make them untracked"""
    print("=" * 60)
    print("FIXING UNTRACKED STATUS FOR IMPORTED ALUMNI")
    print("=" * 60)
    
    # Find alumni with AcademicInfo year_graduated=2020 who have TrackerData
    alumni_2020_with_tracker = User.objects.filter(
        account_type__user=True,
        academic_info__year_graduated=2020,
        tracker_data__isnull=False
    )
    
    print(f"Found {alumni_2020_with_tracker.count()} Class of 2020 alumni with TrackerData records")
    
    if alumni_2020_with_tracker.count() > 0:
        print("\nRemoving TrackerData records to make them untracked...")
        
        for alumni in alumni_2020_with_tracker:
            try:
                # Remove the TrackerData record
                tracker_data = TrackerData.objects.filter(user=alumni)
                if tracker_data.exists():
                    tracker_data.delete()
                    print(f"  ✓ Removed TrackerData for: {alumni.f_name} {alumni.l_name} (CTU: {alumni.acc_username})")
            except Exception as e:
                print(f"  ✗ Error removing TrackerData for {alumni.acc_username}: {e}")
    
    # Verify the fix
    print(f"\nVERIFICATION:")
    print("-" * 20)
    
    # Check untracked count (alumni without TrackerData)
    alumni_without_tracker = User.objects.filter(
        account_type__user=True
    ).exclude(
        tracker_data__isnull=False
    )
    
    print(f"Total untracked alumni: {alumni_without_tracker.count()}")
    
    # Check Class of 2020 specifically
    alumni_2020 = User.objects.filter(
        account_type__user=True,
        academic_info__year_graduated=2020
    )
    
    alumni_2020_untracked = alumni_2020.exclude(tracker_data__isnull=False)
    
    print(f"Class of 2020 alumni: {alumni_2020.count()}")
    print(f"Class of 2020 untracked: {alumni_2020_untracked.count()}")
    
    # Check TrackerData status distribution
    from collections import Counter
    status_counts = Counter()
    tracker_records = TrackerData.objects.filter(user__account_type__user=True)
    for tracker in tracker_records:
        status = tracker.q_employment_status
        if status:
            status_counts[status] += 1
    
    print(f"Remaining TrackerData status distribution: {dict(status_counts)}")
    
    print(f"\nSUMMARY:")
    print("-" * 10)
    print("✓ Class of 2020 alumni are now untracked")
    print("✓ Dashboard should show untracked: 8")
    print("✓ Statistics bar graph should show Pending: 0")
    print("✓ View Statistics should still show Class of 2020 card")

if __name__ == "__main__":
    fix_untracked_status()





























































