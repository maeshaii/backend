"""
Re-run job alignment for all employed alumni to fix absorbed status.
NOW with the CORRECT logic: absorbed = OJT company matches current company
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, EmploymentHistory
from django.db import transaction

print("=" * 70)
print("FIXING ABSORBED STATUS WITH CORRECT LOGIC")
print("=" * 70)
print("CORRECT: Absorbed = OJT company hired them as full employee")
print("=" * 70)

# Get all alumni with employment history
alumni = User.objects.filter(account_type__user=True)
fixed_count = 0
no_change_count = 0

for user in alumni:
    try:
        employment = EmploymentHistory.objects.filter(user=user).first()
        if not employment:
            continue
        
        old_absorbed = employment.absorbed
        
        # Re-run job alignment with corrected logic
        with transaction.atomic():
            employment.update_job_alignment()
            employment.save()
        
        employment.refresh_from_db()
        new_absorbed = employment.absorbed
        
        if old_absorbed != new_absorbed:
            print(f"✓ {user.acc_username}: absorbed {old_absorbed} → {new_absorbed}")
            fixed_count += 1
            
            # Also update user_status if needed
            if new_absorbed:
                user.user_status = 'Absorbed'
            elif user.user_status == 'Absorbed':
                # Was absorbed, now not - set to Employed
                user.user_status = 'Employed'
            user.save(update_fields=['user_status'])
        else:
            no_change_count += 1
    
    except Exception as e:
        print(f"✗ Error processing {user.acc_username}: {e}")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"Total alumni: {alumni.count()}")
print(f"Fixed: {fixed_count}")
print(f"No change: {no_change_count}")
print("=" * 70)

# Show current absorbed count
absorbed_count = EmploymentHistory.objects.filter(absorbed=True, user__account_type__user=True).count()
print(f"\n✅ Current absorbed alumni: {absorbed_count}")
print("=" * 70)

