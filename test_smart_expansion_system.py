#!/usr/bin/env python
"""
Test script for the Smart Job Database Expansion System.
Tests the new behavior: radio button first, then cross-course checking and database expansion.
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, EmploymentHistory, SimpleCompTechJob, SimpleInfoTechJob, SimpleInfoSystemJob


def test_smart_expansion_system():
    """Test the smart job database expansion system"""
    print("=" * 80)
    print("SMART JOB DATABASE EXPANSION SYSTEM TEST")
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
    
    # Test 1: Job that exists in BSIS but not BSIT
    test_position = "Biofuels Processing Technicians"
    
    print(f"\n" + "="*60)
    print("TEST 1: CROSS-COURSE JOB EXPANSION")
    print("="*60)
    
    print(f"Position: '{test_position}'")
    print(f"User Program: {bsit_user.academic_info.program}")
    
    # Check if job exists in BSIS
    bsis_job = SimpleInfoSystemJob.objects.filter(job_title__iexact=test_position).first()
    if bsis_job:
        print(f"Found in BSIS table: YES")
    else:
        print(f"Found in BSIS table: NO")
    
    # Check if job exists in BSIT
    bsit_job = SimpleInfoTechJob.objects.filter(job_title__iexact=test_position).first()
    if bsit_job:
        print(f"Found in BSIT table: YES")
    else:
        print(f"Found in BSIT table: NO")
    
    # Update position and check alignment
    employment.position_current = test_position
    employment.update_job_alignment()
    employment.save()
    
    print(f"\nAlignment Result:")
    print(f"  Status: {employment.job_alignment_status}")
    print(f"  Category: {employment.job_alignment_category}")
    print(f"  Title: {employment.job_alignment_title}")
    
    if employment.job_alignment_status == 'pending_user_confirmation':
        print(f"  [OK] Radio button should be shown!")
        print(f"  Question: Is '{test_position}' aligned to your {bsit_user.academic_info.program} program?")
        
        # Simulate user saying YES
        print(f"\nUser selects: YES")
        employment.confirm_job_alignment(confirmed=True)
        employment.save()
        
        print(f"\nAfter confirmation:")
        print(f"  Status: {employment.job_alignment_status}")
        print(f"  Category: {employment.job_alignment_category}")
        print(f"  Title: {employment.job_alignment_title}")
        
        # Check if job was added to BSIT table
        bsit_job_after = SimpleInfoTechJob.objects.filter(job_title__iexact=test_position).first()
        if bsit_job_after:
            print(f"  [OK] Job added to BSIT table!")
        else:
            print(f"  [FAIL] Job NOT added to BSIT table")
        
        # Test 2: Future BSIT user should get automatic alignment
        print(f"\n" + "="*60)
        print("TEST 2: FUTURE USER AUTOMATIC ALIGNMENT")
        print("="*60)
        
        # Get another BSIT user
        bsit_user2 = User.objects.filter(
            account_type__user=True,
            academic_info__program__icontains='bsit'
        ).exclude(user_id=bsit_user.user_id).first()
        
        if bsit_user2:
            employment2 = getattr(bsit_user2, 'employment', None)
            if employment2:
                print(f"Future User: {bsit_user2.full_name} ({bsit_user2.academic_info.program})")
                
                # Test same position
                employment2.position_current = test_position
                employment2.update_job_alignment()
                employment2.save()
                
                print(f"Position: '{test_position}'")
                print(f"Alignment Status: {employment2.job_alignment_status}")
                
                if employment2.job_alignment_status == 'aligned':
                    print(f"  [OK] Automatic alignment working! No radio button needed.")
                else:
                    print(f"  [FAIL] Automatic alignment failed")
        
        # Test 3: User says NO
        print(f"\n" + "="*60)
        print("TEST 3: USER REJECTS ALIGNMENT")
        print("="*60)
        
        # Reset and test NO response
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
    
    else:
        print(f"  [FAIL] Expected 'pending_user_confirmation' but got '{employment.job_alignment_status}'")
    
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
    
    if final_info_tech > initial_info_tech:
        print(f"  [OK] BSIT table expanded by {final_info_tech - initial_info_tech} jobs!")
    else:
        print(f"  [FAIL] BSIT table did not expand")
    
    print("\n" + "=" * 80)
    print("SMART EXPANSION SYSTEM TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    test_smart_expansion_system()
