import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, AcademicInfo, TrackerData
from django.utils import timezone

def check_and_fix_2020():
    """Check and fix Class of 2020 alumni data"""
    print("=== Checking Class of 2020 Alumni ===")
    
    # Find all alumni users
    all_alumni = User.objects.filter(account_type__user=True)
    print(f"Total alumni users: {all_alumni.count()}")
    
    # Check recent alumni (likely the imported ones)
    recent_alumni = all_alumni.order_by('-user_id')[:20]  # Last 20 created
    
    print(f"\n=== Recent Alumni (Last 20) ===")
    alumni_without_academic = []
    alumni_without_tracker = []
    
    for alumni in recent_alumni:
        has_academic = hasattr(alumni, 'academic_info') and alumni.academic_info
        has_tracker = TrackerData.objects.filter(user=alumni).exists()
        
        year = alumni.academic_info.year_graduated if has_academic else 'No Year'
        course = alumni.academic_info.course if has_academic else 'No Course'
        
        print(f"  {alumni.f_name} {alumni.l_name} (CTU: {alumni.acc_username})")
        print(f"    Year: {year}, Course: {course}")
        print(f"    Has AcademicInfo: {has_academic}, Has TrackerData: {has_tracker}")
        
        if not has_academic:
            alumni_without_academic.append(alumni)
        if not has_tracker:
            alumni_without_tracker.append(alumni)
        print()
    
    # Fix missing AcademicInfo records
    if alumni_without_academic:
        print(f"=== Fixing {len(alumni_without_academic)} alumni without AcademicInfo ===")
        
        # Get or create default values (you can modify these)
        default_year = 2020  # Change this to match your import
        default_course = 'BSIT'  # Change this to match your import
        
        for alumni in alumni_without_academic:
            try:
                AcademicInfo.objects.create(
                    user=alumni,
                    year_graduated=default_year,
                    course=default_course
                )
                print(f"  Created AcademicInfo for: {alumni.f_name} {alumni.l_name}")
            except Exception as e:
                print(f"  Error creating AcademicInfo for {alumni.acc_username}: {e}")
    
    # Fix missing TrackerData records
    if alumni_without_tracker:
        print(f"\n=== Fixing {len(alumni_without_tracker)} alumni without TrackerData ===")
        
        for alumni in alumni_without_tracker:
            try:
                TrackerData.objects.create(
                    user=alumni,
                    q_employment_status='pending',
                    submitted_at=timezone.now()
                )
                print(f"  Created TrackerData for: {alumni.f_name} {alumni.l_name}")
            except Exception as e:
                print(f"  Error creating TrackerData for {alumni.acc_username}: {e}")
    
    # Check final counts
    print(f"\n=== Final Check ===")
    year_counts = {}
    for alumni in User.objects.filter(account_type__user=True).select_related('academic_info'):
        year = alumni.academic_info.year_graduated if alumni.academic_info else 'No Year'
        year_counts[year] = year_counts.get(year, 0) + 1
    
    print("Alumni by year:")
    for year, count in sorted(year_counts.items(), reverse=True):
        print(f"  {year}: {count} alumni")

if __name__ == "__main__":
    check_and_fix_2020()




