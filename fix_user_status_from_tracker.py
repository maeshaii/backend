"""
Fix user_status field for all alumni based on their tracker responses.

ISSUE: Some alumni have incorrect user_status values (e.g., 'Absorbed', 'active')
when they should have 'Employed', 'Unemployed', or 'Pending' based on their
tracker responses.

SOLUTION: Re-run the user_status update logic for all alumni with tracker data.
"""
import os
import django
import sys

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.db import transaction
from apps.shared.models import User, TrackerData, TrackerResponse, EmploymentHistory

def fix_user_status():
    """Fix user_status for all alumni based on their tracker data"""
    
    print("=" * 70)
    print("FIXING USER_STATUS FOR ALL ALUMNI")
    print("=" * 70)
    
    # Get all alumni users
    alumni_users = User.objects.filter(account_type__user=True)
    total_alumni = alumni_users.count()
    print(f"\nFound {total_alumni} alumni users")
    
    fixed_count = 0
    no_tracker_count = 0
    error_count = 0
    
    for user in alumni_users:
        try:
            # Get their tracker data
            tracker_data = TrackerData.objects.filter(user=user).first()
            employment = EmploymentHistory.objects.filter(user=user).first()
            
            if not tracker_data or not tracker_data.q_employment_status:
                # No tracker data - set to Pending
                if user.user_status != 'Pending':
                    old_status = user.user_status
                    user.user_status = 'Pending'
                    user.save(update_fields=['user_status'])
                    print(f"✓ {user.acc_username}: {old_status} → Pending (no tracker)")
                    fixed_count += 1
                else:
                    no_tracker_count += 1
                continue
            
            # Determine correct user_status based on tracker data
            employment_status = str(tracker_data.q_employment_status).lower()
            old_status = user.user_status
            new_status = user.user_status
            
            if employment_status == 'yes':
                # Check if absorbed
                if employment and employment.absorbed:
                    new_status = 'Absorbed'
                else:
                    new_status = 'Employed'
            elif employment_status == 'no':
                new_status = 'Unemployed'
            else:
                new_status = 'Pending'
            
            # Update if changed
            if old_status != new_status:
                with transaction.atomic():
                    user.user_status = new_status
                    user.save(update_fields=['user_status'])
                print(f"✓ {user.acc_username}: {old_status} → {new_status}")
                fixed_count += 1
            
        except Exception as e:
            print(f"✗ Error processing {user.acc_username}: {e}")
            error_count += 1
            continue
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total alumni: {total_alumni}")
    print(f"Fixed: {fixed_count}")
    print(f"No tracker data: {no_tracker_count}")
    print(f"Errors: {error_count}")
    print("=" * 70)
    
    # Show current status distribution
    print("\n" + "=" * 70)
    print("CURRENT STATUS DISTRIBUTION")
    print("=" * 70)
    from collections import Counter
    status_counts = Counter(User.objects.filter(account_type__user=True).values_list('user_status', flat=True))
    for status, count in status_counts.most_common():
        print(f"{status}: {count}")
    print("=" * 70)

if __name__ == '__main__':
    try:
        fix_user_status()
        print("\n✅ Script completed successfully!")
    except Exception as e:
        print(f"\n❌ Script failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

