"""
Script to fix coordinator assignments for OJT students.

This script ensures that all OJT students have the correct coordinator
assigned in their OJTCompanyProfile based on OJTImport records.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, OJTCompanyProfile, OJTImport, AcademicInfo
from django.db.models import Q

def fix_coordinator_assignments():
    """Fix coordinator assignments for all OJT students"""
    print("=" * 70)
    print("Fixing Coordinator Assignments for OJT Students")
    print("=" * 70)
    
    # Get all OJT students
    ojt_students = User.objects.filter(account_type__ojt=True).select_related(
        'academic_info', 'ojt_company_profile'
    )
    
    print(f"\nFound {ojt_students.count()} OJT students")
    
    fixed_count = 0
    created_count = 0
    no_year_section_count = 0
    
    for student in ojt_students:
        academic_info = getattr(student, 'academic_info', None)
        if not academic_info:
            no_year_section_count += 1
            continue
            
        year = getattr(academic_info, 'year_graduated', None)
        section = (getattr(academic_info, 'section', '') or '').strip()
        
        if not year:
            no_year_section_count += 1
            continue
        
        # Find the coordinator who imported this student's batch_year and section
        imports = OJTImport.objects.filter(
            batch_year=year,
            section=section
        ).order_by('-import_date')
        
        if not imports.exists():
            # Try without section
            imports = OJTImport.objects.filter(
                batch_year=year
            ).order_by('-import_date')
        
        if imports.exists():
            # Get or create OJTCompanyProfile
            profile, created = OJTCompanyProfile.objects.get_or_create(
                user=student
            )
            
            # IMPORTANT: Only set coordinator if it's not already set
            # This prevents overwriting correct assignments when multiple coordinators
            # import students into the same section
            if not profile.coordinator or profile.coordinator == '':
                # Use the most recent import's coordinator only if not set
                coordinator = imports.first().coordinator
                profile.coordinator = coordinator
                profile.save()
                if created:
                    created_count += 1
                    print(f"✓ Created profile for {student.f_name} {student.l_name} ({student.acc_username}) - Coordinator: {coordinator}")
                else:
                    fixed_count += 1
                    print(f"✓ Set coordinator for {student.f_name} {student.l_name} ({student.acc_username}) - Coordinator: {coordinator}")
            else:
                # Coordinator already set - preserve it (don't overwrite)
                print(f"✓ Preserved existing coordinator '{profile.coordinator}' for {student.f_name} {student.l_name} ({student.acc_username})")
        else:
            no_year_section_count += 1
            print(f"⚠ No import record found for {student.f_name} {student.l_name} ({student.acc_username}) - Year: {year}, Section: {section}")
    
    print("\n" + "=" * 70)
    print(f"Summary:")
    print(f"  - Fixed/Updated: {fixed_count}")
    print(f"  - Created profiles: {created_count}")
    print(f"  - No year/section/import: {no_year_section_count}")
    print("=" * 70)

if __name__ == "__main__":
    fix_coordinator_assignments()

