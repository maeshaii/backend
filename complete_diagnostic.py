"""
Complete diagnostic - Check EVERYTHING
"""
import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, OJTInfo, AcademicInfo
from datetime import date

print("="*70)
print("COMPLETE DIAGNOSTIC - OJT STATUS ISSUE")
print("="*70)

batch_year = 2026
today = date.today()

print(f"\n📅 Current Date: {today}")
print(f"🎓 Checking Batch: {batch_year}\n")

# Get all students
students = User.objects.filter(
    account_type__ojt=True,
    academic_info__year_graduated=batch_year
).select_related('ojt_info', 'academic_info', 'ojt_company_profile', 'profile').order_by('l_name')

print(f"Found {students.count()} students\n")
print("="*70)

# Check each student
issues_found = []

for student in students:
    print(f"\n👤 {student.f_name} {student.m_name or ''} {student.l_name}")
    print(f"   CTU ID: {student.acc_username}")
    
    # Check OJT Info
    if hasattr(student, 'ojt_info') and student.ojt_info:
        ojt = student.ojt_info
        print(f"   ✓ OJT Info exists")
        print(f"   └─ ojtstatus (DB field): '{ojt.ojtstatus}'")
        print(f"   └─ is_sent_to_admin: {ojt.is_sent_to_admin}")
        print(f"   └─ ojt_end_date: {ojt.ojt_end_date}")
        print(f"   └─ ojt_start_date: {ojt.ojt_start_date}")
        
        # Check what API will return
        api_status = ojt.ojtstatus or 'Pending'
        print(f"   └─ API will send 'ojt_status': '{api_status}'")
        
        # Check if status is correct
        if not ojt.is_sent_to_admin and ojt.ojt_end_date and today > ojt.ojt_end_date:
            if ojt.ojtstatus in ['Completed', 'Ongoing']:
                print(f"   ❌ PROBLEM: Should be Incomplete but is '{ojt.ojtstatus}'")
                issues_found.append(f"{student.f_name} {student.l_name}: {ojt.ojtstatus} should be Incomplete")
            else:
                print(f"   ✓ Status correct: Incomplete")
        elif ojt.is_sent_to_admin:
            print(f"   ✓ Status correct: Sent to admin (will show PENDING)")
        else:
            print(f"   ✓ Status OK")
    else:
        print(f"   ❌ No OJT Info found!")
        issues_found.append(f"{student.f_name} {student.l_name}: No OJT Info")
    
    # Check Company Profile
    if hasattr(student, 'ojt_company_profile') and student.ojt_company_profile:
        print(f"   ✓ Company Profile exists: {student.ojt_company_profile.company_name}")
    else:
        print(f"   ⚠️ No Company Profile")

print("\n" + "="*70)
print("SUMMARY")
print("="*70)

if issues_found:
    print(f"\n❌ Found {len(issues_found)} issue(s):")
    for issue in issues_found:
        print(f"   - {issue}")
    print("\nFixing issues now...")
    
    # Fix the issues
    fixed = 0
    for student in students:
        if hasattr(student, 'ojt_info') and student.ojt_info:
            ojt = student.ojt_info
            if not ojt.is_sent_to_admin and ojt.ojt_end_date and today > ojt.ojt_end_date:
                if ojt.ojtstatus in ['Completed', 'Ongoing']:
                    old = ojt.ojtstatus
                    ojt.ojtstatus = 'Incomplete'
                    ojt.save()
                    print(f"   ✅ Fixed: {student.f_name} {student.l_name}: {old} → Incomplete")
                    fixed += 1
    
    print(f"\n✅ Fixed {fixed} student(s)")
else:
    print("\n✅ No issues found - all statuses are correct!")

print("\n" + "="*70)
print("WHAT THE API RETURNS")
print("="*70)

print("\nSimulated API Response:")
for student in students.select_related('ojt_info'):
    if hasattr(student, 'ojt_info') and student.ojt_info:
        ojt_status = student.ojt_info.ojtstatus or 'Pending'
        is_sent = student.ojt_info.is_sent_to_admin
        print(f"  {student.f_name} {student.l_name}:")
        print(f"    'ojt_status': '{ojt_status}'")
        print(f"    'is_sent_to_admin': {is_sent}")
        
        # What frontend should display
        if is_sent:
            print(f"    → Frontend should show: PENDING")
        elif ojt_status == 'Incomplete':
            print(f"    → Frontend should show: INCOMPLETE")
        elif ojt_status == 'Completed':
            print(f"    → Frontend should show: COMPLETED (dropdown)")
        else:
            print(f"    → Frontend should show: {ojt_status} (dropdown)")
        print()

print("="*70)
print("✅ Diagnostic Complete")
print("="*70)
print("\nIf frontend still shows wrong status:")
print("1. Close browser completely")
print("2. Reopen and navigate to the page")
print("3. Or press Ctrl+Shift+Delete and clear cache")

