"""
Check current absorbed status and fix with new logic.
This will show which alumni are marked as absorbed and why,
then recalculate with the corrected logic.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, EmploymentHistory
from django.db import transaction

print("=" * 80)
print("CHECKING AND FIXING ABSORBED STATUS")
print("=" * 80)
print()

# First, check current state
print("📊 CURRENT STATE:")
print("-" * 80)
absorbed_employments = EmploymentHistory.objects.filter(absorbed=True).select_related('user', 'user__ojt_company_profile')
absorbed_count = absorbed_employments.count()

print(f"Total alumni marked as absorbed: {absorbed_count}")
print()

if absorbed_count > 0:
    print("🔍 DETAILED ANALYSIS:")
    print("-" * 80)
    
    for employment in absorbed_employments:
        user = employment.user
        ojt_profile = getattr(user, 'ojt_company_profile', None)
        
        ojt_company = getattr(ojt_profile, 'company_name', None) if ojt_profile else None
        current_company = employment.company_name_current
        
        print(f"\n👤 User: {user.acc_username} ({user.f_name} {user.l_name})")
        print(f"   Current Company: {current_company or 'N/A'}")
        print(f"   OJT Company: {ojt_company or 'N/A'}")
        
        # Check if they should actually be absorbed
        if not current_company:
            print(f"   ❌ Should NOT be absorbed (no current company)")
        elif not ojt_company:
            print(f"   ❌ Should NOT be absorbed (no OJT company)")
        else:
            # Use the same normalization as the model
            def normalize_for_comparison(company):
                if not company:
                    return ''
                normalized = company.upper().strip()
                suffixes_to_remove = [
                    ' INCORPORATED', ' INC.', ' CORPORATION', ' CORP.',
                    ' LIMITED', ' LTD.', ' COMPANY', ' CO.', ' LLC',
                    ' INC', ' CORP', ' LTD', ' CO',
                ]
                for suffix in suffixes_to_remove:
                    if normalized.endswith(suffix):
                        normalized = normalized[:-len(suffix)].strip()
                        break
                return ' '.join(normalized.split())
            
            current_norm = normalize_for_comparison(current_company)
            ojt_norm = normalize_for_comparison(ojt_company)
            
            if current_norm == ojt_norm:
                print(f"   ✅ CORRECTLY absorbed (companies match after normalization)")
                print(f"      Normalized: '{current_norm}' == '{ojt_norm}'")
            else:
                print(f"   ❌ INCORRECTLY absorbed (companies don't match)")
                print(f"      Normalized Current: '{current_norm}'")
                print(f"      Normalized OJT: '{ojt_norm}'")

print("\n" + "=" * 80)
print("🛠️  FIXING WITH NEW LOGIC...")
print("=" * 80)
print()

# Now fix with new logic
fixed_count = 0
correct_count = 0
no_employment_count = 0

all_alumni = User.objects.filter(account_type__user=True)
total_alumni = all_alumni.count()

for user in all_alumni:
    try:
        employment = EmploymentHistory.objects.filter(user=user).first()
        if not employment:
            no_employment_count += 1
            continue
        
        old_absorbed = employment.absorbed
        
        # Re-run job alignment with corrected logic
        with transaction.atomic():
            employment.update_job_alignment()
            employment.save()
        
        employment.refresh_from_db()
        new_absorbed = employment.absorbed
        
        if old_absorbed != new_absorbed:
            status_change = "True → False" if old_absorbed else "False → True"
            print(f"✓ Fixed: {user.acc_username} ({user.f_name} {user.l_name})")
            print(f"  absorbed: {status_change}")
            fixed_count += 1
            
            # Update user_status if needed
            if new_absorbed:
                if user.user_status != 'Absorbed':
                    user.user_status = 'Absorbed'
                    user.save(update_fields=['user_status'])
            elif user.user_status == 'Absorbed':
                user.user_status = 'Employed'
                user.save(update_fields=['user_status'])
        elif new_absorbed:
            correct_count += 1
            print(f"✓ Correct: {user.acc_username} ({user.f_name} {user.l_name})")
            print(f"  OJT: {getattr(getattr(user, 'ojt_company_profile', None), 'company_name', 'N/A')}")
            print(f"  Current: {employment.company_name_current}")
    
    except Exception as e:
        print(f"✗ Error processing {user.acc_username}: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 80)
print("📈 SUMMARY")
print("=" * 80)
print(f"Total alumni: {total_alumni}")
print(f"Fixed (changed): {fixed_count}")
print(f"Correct (already accurate): {correct_count}")
print(f"No employment data: {no_employment_count}")
print()

# Final count
final_absorbed = EmploymentHistory.objects.filter(absorbed=True, user__account_type__user=True).count()
print(f"✅ Final absorbed count: {final_absorbed}")
print("=" * 80)

