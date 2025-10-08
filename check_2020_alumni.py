import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, AcademicInfo, TrackerData

def check_2020_alumni():
    """Check what alumni exist for 2020 batch and their status"""
    print("=== Checking Class of 2020 Alumni ===")
    
    # Get all alumni with batch year 2020
    alumni_2020 = User.objects.filter(
        account_type__user=True,
        academic_info__year_graduated=2020
    ).select_related('academic_info', 'tracker_data')
    
    print(f"Total alumni with batch year 2020: {alumni_2020.count()}")
    
    if alumni_2020.count() == 0:
        print("No alumni found for 2020!")
        
        # Check all alumni years
        print("\n=== All Available Batch Years ===")
        all_years = User.objects.filter(account_type__user=True).select_related('academic_info')
        year_counts = {}
        for alumni in all_years:
            year = alumni.academic_info.year_graduated if alumni.academic_info else 'No Year'
            year_counts[year] = year_counts.get(year, 0) + 1
        
        for year, count in sorted(year_counts.items()):
            print(f"  {year}: {count} alumni")
        
        return
    
    # Check each 2020 alumni
    print(f"\n=== Class of 2020 Alumni Details ===")
    for alumni in alumni_2020:
        tracker_status = "No Tracker Data"
        if hasattr(alumni, 'tracker_data') and alumni.tracker_data:
            tracker_status = alumni.tracker_data.q_employment_status or "Unknown"
        
        course = alumni.academic_info.course if alumni.academic_info else "No Course"
        
        print(f"  - {alumni.f_name} {alumni.l_name} (CTU ID: {alumni.acc_username})")
        print(f"    Course: {course}")
        print(f"    Tracker Status: {tracker_status}")
        print()
    
    # Check tracker data for 2020 alumni
    print("=== Tracker Data Status for 2020 Alumni ===")
    tracker_data_2020 = TrackerData.objects.filter(
        user__account_type__user=True,
        user__academic_info__year_graduated=2020
    )
    
    print(f"TrackerData records for 2020 alumni: {tracker_data_2020.count()}")
    
    for tracker in tracker_data_2020:
        user = tracker.user
        print(f"  - {user.f_name} {user.l_name}: {tracker.q_employment_status}")

if __name__ == "__main__":
    check_2020_alumni()
