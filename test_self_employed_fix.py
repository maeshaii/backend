"""
Test script to verify self-employed fix is working correctly.

Usage: python test_self_employed_fix.py <user_first_name>

Example: python test_self_employed_fix.py Alvin
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, TrackerData, EmploymentHistory


def check_self_employed_status(first_name):
    """Check if a user's self-employed status is correctly set."""
    try:
        # Find user
        user = User.objects.get(f_name__icontains=first_name, account_type__user=True)
        print(f"\n✅ Found user: {user.f_name} {user.l_name} (ID: {user.user_id})")
        
        # Check if they have tracker data
        try:
            tracker = user.tracker_data
            employment_type = tracker.q_employment_type or "N/A"
            print(f"\n📋 Tracker Data:")
            print(f"   - Employment Type (Q23): {employment_type}")
            print(f"   - Employment Status (Q21): {tracker.q_employment_status or 'N/A'}")
            print(f"   - Submitted At: {tracker.tracker_submitted_at or 'Not submitted'}")
        except TrackerData.DoesNotExist:
            print(f"\n❌ No tracker data found for {first_name}")
            return False
        
        # Check employment history
        try:
            employment = user.employment
            print(f"\n💼 Employment History:")
            print(f"   - Company: {employment.company_name_current or 'N/A'}")
            print(f"   - Position: {employment.position_current or 'N/A'}")
            print(f"   - Self Employed Boolean: {employment.self_employed}")
            print(f"   - High Position: {employment.high_position}")
            print(f"   - Absorbed: {employment.absorbed}")
        except EmploymentHistory.DoesNotExist:
            print(f"\n❌ No employment history found for {first_name}")
            return False
        
        # Verify the fix
        employment_type_lower = employment_type.lower()
        is_self_employed = 'self-employed' in employment_type_lower or 'self employed' in employment_type_lower
        
        print(f"\n🔍 Verification:")
        print(f"   - Expected self_employed: {is_self_employed}")
        print(f"   - Actual self_employed: {employment.self_employed}")
        
        if is_self_employed == employment.self_employed:
            print(f"\n✅ SUCCESS! Self-employed status is correct!")
            return True
        else:
            print(f"\n❌ MISMATCH! Self-employed status is incorrect!")
            print(f"\n💡 Possible causes:")
            print(f"   1. Server needs restart to load new code")
            print(f"   2. Tracker form was submitted before the fix")
            print(f"   3. Need to resubmit tracker form")
            return False
            
    except User.DoesNotExist:
        print(f"\n❌ User with first name '{first_name}' not found")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def list_all_self_employed():
    """List all users who should be marked as self-employed."""
    print("\n" + "="*60)
    print("CHECKING ALL SELF-EMPLOYED USERS IN THE SYSTEM")
    print("="*60)
    
    # Find users with self-employed in tracker
    users_with_tracker = TrackerData.objects.filter(
        q_employment_type__iregex=r'self[\s\-]*employ'
    ).select_related('user', 'user__employment')
    
    # Find users with self-employed in employment
    users_with_employment = EmploymentHistory.objects.filter(
        self_employed=True
    ).select_related('user', 'user__tracker_data')
    
    print(f"\n📊 Users with 'self-employed' in tracker: {users_with_tracker.count()}")
    for tracker in users_with_tracker:
        user = tracker.user
        emp = user.employment if hasattr(user, 'employment') else None
        print(f"   - {user.f_name} {user.l_name}")
        print(f"     Tracker Type: {tracker.q_employment_type}")
        print(f"     Employment Boolean: {emp.self_employed if emp else 'N/A'}")
    
    print(f"\n📊 Users with self_employed=True in employment: {users_with_employment.count()}")
    for emp in users_with_employment:
        user = emp.user
        tracker = user.tracker_data if hasattr(user, 'tracker_data') else None
        print(f"   - {user.f_name} {user.l_name}")
        print(f"     Employment Boolean: {emp.self_employed}")
        print(f"     Tracker Type: {tracker.q_employment_type if tracker else 'N/A'}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_self_employed_fix.py <user_first_name>")
        print("\nOr to list all self-employed users:")
        print("python test_self_employed_fix.py --list")
        sys.exit(1)
    
    if sys.argv[1] == "--list":
        list_all_self_employed()
    else:
        first_name = sys.argv[1]
        success = check_self_employed_status(first_name)
        sys.exit(0 if success else 1)


