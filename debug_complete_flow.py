import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, AcademicInfo, TrackerData, AccountType
from collections import Counter

def debug_complete_flow():
    """Comprehensive debugging of the entire import to statistics flow"""
    print("=" * 60)
    print("COMPREHENSIVE ALUMNI DATA DEBUG")
    print("=" * 60)
    
    # 1. Check all users by account type
    print("\n1. ALL USERS BY ACCOUNT TYPE:")
    print("-" * 30)
    all_users = User.objects.all()
    print(f"Total users: {all_users.count()}")
    
    for user in all_users[:5]:  # Show first 5 users
        print(f"  User ID: {user.user_id}, Username: {user.acc_username}, Name: {user.f_name} {user.l_name}")
        if hasattr(user, 'account_type') and user.account_type:
            print(f"    Account Type: user={user.account_type.user}, admin={user.account_type.admin}, ojt={user.account_type.ojt}")
    
    # 2. Check alumni users specifically
    print("\n2. ALUMNI USERS (account_type.user=True):")
    print("-" * 40)
    alumni_users = User.objects.filter(account_type__user=True)
    print(f"Total alumni users: {alumni_users.count()}")
    
    for user in alumni_users:
        print(f"  {user.f_name} {user.l_name} (CTU: {user.acc_username})")
        print(f"    User ID: {user.user_id}")
        print(f"    Created: {user.date_created if hasattr(user, 'date_created') else 'Unknown'}")
        
        # Check AcademicInfo
        if hasattr(user, 'academic_info') and user.academic_info:
            print(f"    AcademicInfo: Year={user.academic_info.year_graduated}, Course={user.academic_info.course}")
        else:
            print(f"    AcademicInfo: MISSING")
        
        # Check TrackerData
        tracker_count = TrackerData.objects.filter(user=user).count()
        print(f"    TrackerData records: {tracker_count}")
        
        if tracker_count > 0:
            tracker = TrackerData.objects.filter(user=user).first()
            print(f"    Latest TrackerData status: {tracker.q_employment_status if tracker else 'None'}")
        print()
    
    # 3. Check AcademicInfo records
    print("\n3. ACADEMIC INFO RECORDS:")
    print("-" * 30)
    academic_records = AcademicInfo.objects.all()
    print(f"Total AcademicInfo records: {academic_records.count()}")
    
    year_counts = Counter()
    for record in academic_records:
        year = record.year_graduated
        course = record.course
        print(f"  User: {record.user.acc_username}, Year: {year}, Course: {course}")
        if year:
            year_counts[year] += 1
    
    print(f"\nYears distribution: {dict(year_counts)}")
    
    # 4. Check TrackerData records
    print("\n4. TRACKER DATA RECORDS:")
    print("-" * 30)
    tracker_records = TrackerData.objects.all()
    print(f"Total TrackerData records: {tracker_records.count()}")
    
    status_counts = Counter()
    for record in tracker_records:
        status = record.q_employment_status
        user = record.user
        print(f"  User: {user.acc_username}, Status: {status}")
        if status:
            status_counts[status] += 1
    
    print(f"\nStatus distribution: {dict(status_counts)}")
    
    # 5. Simulate the alumni_statistics_view logic
    print("\n5. SIMULATING ALUMNI STATISTICS VIEW:")
    print("-" * 40)
    
    # This is the exact logic from alumni_statistics_view
    year_values = (
        User.objects
        .filter(account_type__user=True)
        .values_list('academic_info__year_graduated', flat=True)
    )
    year_counts_result = Counter([y for y in year_values if y is not None])
    
    print(f"Years found by statistics view: {dict(year_counts_result)}")
    
    years_list = [
        {'year': year, 'count': count}
        for year, count in sorted(year_counts_result.items(), reverse=True)
    ]
    
    print("Years list that would be returned to frontend:")
    for year_data in years_list:
        print(f"  {year_data}")
    
    # 6. Check recent imports (last 10 users created)
    print("\n6. RECENT USERS (LAST 10 CREATED):")
    print("-" * 35)
    recent_users = User.objects.order_by('-user_id')[:10]
    for user in recent_users:
        account_type = "Alumni" if user.account_type and user.account_type.user else "Other"
        print(f"  {user.user_id}: {user.f_name} {user.l_name} ({account_type}) - {user.acc_username}")

if __name__ == "__main__":
    debug_complete_flow()




