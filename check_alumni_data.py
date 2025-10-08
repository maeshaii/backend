import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, AcademicInfo, TrackerData

def check_alumni_data():
    """Check all alumni data to see what's in the database"""
    print("=== All Alumni in Database ===")
    
    # Get all alumni
    all_alumni = User.objects.filter(account_type__user=True).select_related('academic_info')
    
    print(f"Total alumni: {all_alumni.count()}")
    
    # Group by batch year
    year_counts = {}
    for alumni in all_alumni:
        year = alumni.academic_info.year_graduated if alumni.academic_info else 'No Year'
        year_counts[year] = year_counts.get(year, 0) + 1
    
    print("\nAlumni by batch year:")
    for year, count in sorted(year_counts.items()):
        print(f"  {year}: {count} alumni")
    
    # Check which alumni have TrackerData
    print(f"\nAlumni with TrackerData: {TrackerData.objects.filter(user__account_type__user=True).count()}")
    
    # Show recent alumni (last 10 created)
    print(f"\n=== Recent Alumni (Last 10) ===")
    recent_alumni = all_alumni.order_by('-user_id')[:10]
    for alumni in recent_alumni:
        year = alumni.academic_info.year_graduated if alumni.academic_info else 'No Year'
        course = alumni.academic_info.course if alumni.academic_info else 'No Course'
        has_tracker = TrackerData.objects.filter(user=alumni).exists()
        print(f"  {alumni.f_name} {alumni.l_name} (CTU: {alumni.acc_username}) - Year: {year}, Course: {course}, Has TrackerData: {has_tracker}")

if __name__ == "__main__":
    check_alumni_data()
