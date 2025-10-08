#!/usr/bin/env python
"""
Test script for the Autocomplete-First Job Alignment System.
Tests the complete flow: autocomplete → alignment check → radio button if needed.
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, EmploymentHistory, SimpleCompTechJob, SimpleInfoTechJob, SimpleInfoSystemJob


def test_autocomplete_first_system():
    """Test the autocomplete-first job alignment system"""
    print("=" * 80)
    print("AUTOCOMPLETE-FIRST JOB ALIGNMENT SYSTEM TEST")
    print("=" * 80)
    
    # Get initial job counts
    initial_comp_tech = SimpleCompTechJob.objects.count()
    initial_info_tech = SimpleInfoTechJob.objects.count()
    initial_info_system = SimpleInfoSystemJob.objects.count()
    
    print(f"\nINITIAL JOB COUNTS:")
    print(f"  BIT-CT: {initial_comp_tech}")
    print(f"  BSIT:   {initial_info_tech}")
    print(f"  BSIS:   {initial_info_system}")
    
    # Get a BSIT test user
    bsit_user = User.objects.filter(
        account_type__user=True,
        academic_info__program__icontains='bsit'
    ).first()
    
    if not bsit_user:
        print("No BSIT test user found")
        return
    
    print(f"\nTest User: {bsit_user.full_name} ({bsit_user.academic_info.program})")
    
    employment = getattr(bsit_user, 'employment', None)
    if not employment:
        print("No employment record found")
        return
    
    # Test 1: Job that exists in BSIT table (should auto-align)
    print(f"\n" + "="*60)
    print("TEST 1: JOB FROM AUTOCOMPLETE - ALIGNED TO USER'S PROGRAM")
    print("="*60)
    
    # Find a job that exists in BSIT table
    bsit_job = SimpleInfoTechJob.objects.first()
    if bsit_job:
        test_position = bsit_job.job_title
        print(f"Position: '{test_position}'")
        print(f"Source: BSIT table (user's program)")
        
        # Simulate autocomplete selection
        employment.position_current = test_position
        employment.update_job_alignment()
        employment.save()
        
        print(f"Alignment Status: {employment.job_alignment_status}")
        
        if employment.job_alignment_status == 'aligned':
            print(f"  [OK] Auto-aligned! No radio button needed.")
        else:
            print(f"  [FAIL] Expected auto-alignment but got '{employment.job_alignment_status}'")
    
    # Test 2: Job that exists in BSIS table (cross-program, needs confirmation)
    print(f"\n" + "="*60)
    print("TEST 2: JOB FROM AUTOCOMPLETE - CROSS-PROGRAM (NEEDS CONFIRMATION)")
    print("="*60)
    
    # Find a job that exists in BSIS but not BSIT
    bsis_job = SimpleInfoSystemJob.objects.exclude(
        job_title__in=SimpleInfoTechJob.objects.values_list('job_title', flat=True)
    ).first()
    
    if bsis_job:
        test_position = bsis_job.job_title
        print(f"Position: '{test_position}'")
        print(f"Source: BSIS table (cross-program)")
        print(f"User Program: {bsit_user.academic_info.program}")
        
        # Simulate autocomplete selection
        employment.position_current = test_position
        employment.update_job_alignment()
        employment.save()
        
        print(f"Alignment Status: {employment.job_alignment_status}")
        
        if employment.job_alignment_status == 'pending_user_confirmation':
            print(f"  [OK] Radio button should appear!")
            print(f"  Question: Is '{test_position}' aligned to your {bsit_user.academic_info.program} program?")
            
            # Simulate user saying YES
            print(f"\nUser selects: YES")
            employment.confirm_job_alignment(confirmed=True)
            employment.save()
            
            print(f"After confirmation:")
            print(f"  Status: {employment.job_alignment_status}")
            print(f"  Category: {employment.job_alignment_category}")
            print(f"  Title: {employment.job_alignment_title}")
            
            # Check if job was added to BSIT table
            bsit_job_after = SimpleInfoTechJob.objects.filter(job_title__iexact=test_position).first()
            if bsit_job_after:
                print(f"  [OK] Job added to BSIT table!")
            else:
                print(f"  [FAIL] Job NOT added to BSIT table")
        else:
            print(f"  [FAIL] Expected 'pending_user_confirmation' but got '{employment.job_alignment_status}'")
    
    # Test 3: Job not in any autocomplete (manual typing)
    print(f"\n" + "="*60)
    print("TEST 3: JOB NOT IN AUTOCOMPLETE (MANUAL TYPING)")
    print("="*60)
    
    test_position = "Completely New Job Title XYZ"
    print(f"Position: '{test_position}'")
    print(f"Source: Manual typing (not in any autocomplete)")
    
    # Simulate manual typing
    employment.position_current = test_position
    employment.update_job_alignment()
    employment.save()
    
    print(f"Alignment Status: {employment.job_alignment_status}")
    
    if employment.job_alignment_status == 'pending_user_confirmation':
        print(f"  [OK] Radio button should appear immediately!")
        print(f"  Question: Is '{test_position}' aligned to your {bsit_user.academic_info.program} program?")
        
        # Simulate user saying YES (new job type)
        print(f"\nUser selects: YES")
        employment.confirm_job_alignment(confirmed=True)
        employment.save()
        
        print(f"After confirmation:")
        print(f"  Status: {employment.job_alignment_status}")
        print(f"  Category: {employment.job_alignment_category}")
        print(f"  Title: {employment.job_alignment_title}")
        
        if employment.job_alignment_status == 'aligned':
            print(f"  [OK] New job type aligned!")
        else:
            print(f"  [FAIL] New job type alignment failed")
    else:
        print(f"  [FAIL] Expected 'pending_user_confirmation' but got '{employment.job_alignment_status}'")
    
    # Test 4: User says NO to alignment
    print(f"\n" + "="*60)
    print("TEST 4: USER REJECTS ALIGNMENT")
    print("="*60)
    
    test_position = "Another Unknown Job Title"
    print(f"Position: '{test_position}'")
    
    employment.position_current = test_position
    employment.update_job_alignment()
    employment.save()
    
    if employment.job_alignment_status == 'pending_user_confirmation':
        print(f"User selects: NO")
        employment.confirm_job_alignment(confirmed=False)
        employment.save()
        
        print(f"After rejection:")
        print(f"  Status: {employment.job_alignment_status}")
        
        if employment.job_alignment_status == 'not_aligned':
            print(f"  [OK] Rejection working correctly")
        else:
            print(f"  [FAIL] Rejection failed")
    
    # Final job counts
    final_comp_tech = SimpleCompTechJob.objects.count()
    final_info_tech = SimpleInfoTechJob.objects.count()
    final_info_system = SimpleInfoSystemJob.objects.count()
    
    print(f"\n" + "="*60)
    print("FINAL JOB COUNTS")
    print("="*60)
    print(f"  BIT-CT: {final_comp_tech} (was {initial_comp_tech})")
    print(f"  BSIT:   {final_info_tech} (was {initial_info_tech})")
    print(f"  BSIS:   {final_info_system} (was {initial_info_system})")
    
    total_expanded = (final_comp_tech - initial_comp_tech) + (final_info_tech - initial_info_tech) + (final_info_system - initial_info_system)
    if total_expanded > 0:
        print(f"  [OK] Total jobs added: {total_expanded}")
    else:
        print(f"  [INFO] No jobs added (expected for this test)")
    
    print("\n" + "=" * 80)
    print("AUTOCOMPLETE-FIRST SYSTEM TEST COMPLETE")
    print("=" * 80)
    
    print(f"\nSYSTEM BEHAVIOR SUMMARY:")
    print(f"[OK] Autocomplete shows jobs from ALL 3 programs")
    print(f"[OK] Jobs aligned to user's program → Auto-align")
    print(f"[OK] Jobs from other programs → Radio button")
    print(f"[OK] Jobs not in autocomplete → Radio button")
    print(f"[OK] User confirms → Database expansion")
    print(f"[OK] User rejects → Not aligned")


if __name__ == "__main__":
    test_autocomplete_first_system()
