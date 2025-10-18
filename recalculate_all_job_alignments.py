#!/usr/bin/env python
"""
Recalculate job alignment for all existing alumni users.
Run this after populating job tables to update alignment status.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, EmploymentHistory
from django.db import transaction

def recalculate_alignments():
    """Recalculate job alignment for all alumni"""
    print("=" * 70)
    print("RECALCULATING JOB ALIGNMENT FOR ALL ALUMNI")
    print("=" * 70)
    
    # Get all alumni users
    alumni_users = User.objects.filter(account_type__user=True).select_related(
        'employment', 'academic_info', 'tracker_data'
    )
    
    total = alumni_users.count()
    print(f"\nFound {total} alumni users")
    
    if total == 0:
        print("[INFO] No alumni users to process")
        return True
    
    # Counters
    processed = 0
    aligned = 0
    not_aligned = 0
    self_employed = 0
    high_position_count = 0
    absorbed_count = 0
    errors = 0
    
    print("\nProcessing users...")
    
    # Process in batches for efficiency
    for user in alumni_users:
        try:
            # Get or create employment history
            employment, created = EmploymentHistory.objects.get_or_create(user=user)
            
            # Store old values
            old_status = employment.job_alignment_status
            old_category = employment.job_alignment_category
            
            # Recalculate
            employment.update_job_alignment()
            employment.save()
            
            # Count statistics
            processed += 1
            
            if employment.job_alignment_status == 'aligned':
                aligned += 1
            else:
                not_aligned += 1
            
            if employment.self_employed:
                self_employed += 1
            
            if employment.high_position:
                high_position_count += 1
            
            if employment.absorbed:
                absorbed_count += 1
            
            # Show progress every 10 users
            if processed % 10 == 0:
                print(f"  Processed {processed}/{total} users...")
            
            # Log changes
            if old_status != employment.job_alignment_status:
                print(f"    Updated: {user.full_name}")
                print(f"      Position: {employment.position_current}")
                print(f"      Program: {user.academic_info.program if hasattr(user, 'academic_info') else 'N/A'}")
                print(f"      Status: {old_status} -> {employment.job_alignment_status}")
                print(f"      Category: {old_category} -> {employment.job_alignment_category}")
            
        except Exception as e:
            errors += 1
            print(f"  [ERROR] Failed for user {user.user_id}: {e}")
            continue
    
    # Summary
    print("\n" + "=" * 70)
    print("[SUCCESS] JOB ALIGNMENT RECALCULATION COMPLETE")
    print("=" * 70)
    print(f"\nResults:")
    print(f"  Total users:      {total}")
    print(f"  Processed:        {processed}")
    print(f"  Errors:           {errors}")
    print(f"\nAlignment Statistics:")
    print(f"  Aligned:          {aligned} ({aligned/total*100:.1f}%)" if total > 0 else "  Aligned:          0")
    print(f"  Not Aligned:      {not_aligned} ({not_aligned/total*100:.1f}%)" if total > 0 else "  Not Aligned:      0")
    print(f"  Self-Employed:    {self_employed} ({self_employed/total*100:.1f}%)" if total > 0 else "  Self-Employed:    0")
    print(f"  High Position:    {high_position_count} ({high_position_count/total*100:.1f}%)" if total > 0 else "  High Position:    0")
    print(f"  Absorbed:         {absorbed_count} ({absorbed_count/total*100:.1f}%)" if total > 0 else "  Absorbed:         0")
    print("=" * 70)
    
    return errors == 0

if __name__ == '__main__':
    success = recalculate_alignments()
    sys.exit(0 if success else 1)



