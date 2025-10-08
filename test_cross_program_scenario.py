#!/usr/bin/env python
"""
Test cross-program alignment scenario.
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, EmploymentHistory, SimpleCompTechJob, SimpleInfoTechJob, SimpleInfoSystemJob


def test_cross_program_scenario():
    """Test a real cross-program scenario"""
    print("=" * 70)
    print("CROSS-PROGRAM ALIGNMENT SCENARIO TEST")
    print("=" * 70)
    
    # Get a BSIT user
    bsit_user = User.objects.filter(
        account_type__user=True,
        academic_info__program__icontains='bsit'
    ).first()
    
    if not bsit_user:
        print("No BSIT user found")
        return
    
    print(f"Test User: {bsit_user.full_name} ({bsit_user.academic_info.program})")
    
    employment = getattr(bsit_user, 'employment', None)
    if not employment:
        print("No employment record found")
        return
    
    # Test with a position that exists in BSIS but not BSIT
    # Let's find a BSIS-specific job
    bsis_job = SimpleInfoSystemJob.objects.exclude(
        job_title__in=SimpleInfoTechJob.objects.values_list('job_title', flat=True)
    ).first()
    
    if not bsis_job:
        print("No BSIS-specific job found for testing")
        return
    
    test_position = bsis_job.job_title
    print(f"\nTesting position: '{test_position}'")
    print(f"   This job exists in BSIS but not in BSIT")
    print(f"   User's program: {bsit_user.academic_info.program}")
    
    # Update position and check alignment
    employment.position_current = test_position
    employment.update_job_alignment()
    employment.save()
    
    print(f"\nAlignment Result:")
    print(f"   Status: {employment.job_alignment_status}")
    print(f"   Category: {employment.job_alignment_category}")
    print(f"   Title: {employment.job_alignment_title}")
    
    if employment.job_alignment_status == 'pending_confirmation':
        print(f"   CROSS-PROGRAM SUGGESTION FOUND!")
        print(f"   Suggested Program: {employment.job_alignment_suggested_program}")
        print(f"   Original Program: {employment.job_alignment_original_program}")
        
        # Show the user question
        print(f"\n" + "="*50)
        print("USER INTERFACE SIMULATION")
        print("="*50)
        print(f"Position: {test_position}")
        print(f"Your Program: {employment.job_alignment_original_program.upper()}")
        print(f"Suggested Match: {employment.job_alignment_title}")
        print(f"From Program: {employment.job_alignment_suggested_program.upper()}")
        print(f"\nQuestion: Is '{employment.job_alignment_title}' aligned to your {employment.job_alignment_original_program} program?")
        print(f"\nRadio Button Options:")
        print(f"   [ ] Yes, this job is aligned to my program")
        print(f"   [ ] No, this job is not aligned to my program")
        
        # Simulate user choosing YES
        print(f"\nUser selects: YES")
        employment.confirm_cross_program_alignment(confirmed=True)
        print(f"Result: Alignment confirmed! Status: {employment.job_alignment_status}")
        
        # Simulate user choosing NO
        print(f"\n" + "-"*50)
        print("Testing NO response:")
        employment.position_current = test_position
        employment.update_job_alignment()
        employment.save()
        
        if employment.job_alignment_status == 'pending_confirmation':
            print(f"User selects: NO")
            employment.confirm_cross_program_alignment(confirmed=False)
            print(f"Result: Alignment rejected! Status: {employment.job_alignment_status}")
        
    else:
        print(f"   No cross-program suggestion (status: {employment.job_alignment_status})")
    
    print("\n" + "=" * 70)
    print("CROSS-PROGRAM SCENARIO TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    test_cross_program_scenario()
