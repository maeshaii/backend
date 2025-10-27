import os
import django
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, TrackerData
from django.utils import timezone

def fix_existing_alumni():
    """Create TrackerData records for alumni who don't have them"""
    print("=== Fixing Existing Alumni TrackerData ===")
    
    # Find alumni without TrackerData
    alumni_without_tracker = User.objects.filter(
        account_type__user=True
    ).exclude(
        tracker_data__isnull=False
    )
    
    print(f"Found {alumni_without_tracker.count()} alumni without TrackerData records")
    
    created_count = 0
    for alumni in alumni_without_tracker:
        try:
            TrackerData.objects.create(
                user=alumni,
                q_employment_status='pending',
                submitted_at=timezone.now()
            )
            created_count += 1
            print(f"  Created TrackerData for: {alumni.f_name} {alumni.l_name} (CTU ID: {alumni.acc_username})")
        except Exception as e:
            print(f"  Error creating TrackerData for {alumni.acc_username}: {e}")
    
    print(f"\nSuccessfully created {created_count} TrackerData records")
    print("These alumni should now appear in the 'Pending' category of the bar graph")

if __name__ == "__main__":
    fix_existing_alumni()






































