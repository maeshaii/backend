#!/usr/bin/env python
"""
Test script for cross-program job alignment system.
Demonstrates the Yes/No radio button confirmation workflow.
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, EmploymentHistory, SimpleCompTechJob, SimpleInfoTechJob, SimpleInfoSystemJob
from django.contrib.postgres.search import TrigramSimilarity


def test_cross_program_alignment():
    """Test the cross-program alignment system"""
    print("=" * 70)
    print("CROSS-PROGRAM JOB ALIGNMENT TEST")
    print("=" * 70)
    
    # Get a test user (BSIT graduate)
    test_user = User.objects.filter(
        account_type__user=True,
        academic_info__program__icontains='bsit'
    ).first()
    
    if not test_user:
        print("No BSIT test user found")
        return
    
    print(f"Test User: {test_user.full_name} ({test_user.academic_info.program})")
    
    # Get employment record
    employment = getattr(test_user, 'employment', None)
    if not employment:
        print("No employment record found")
        return
    
    # Test case 1: Position that matches in another program
    test_position = "Software Developer"  # This should match in BSIS or BIT-CT
    
    print(f"\nTesting position: '{test_position}'")
    print(f"   Original program: {test_user.academic_info.program}")
    
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
        
        # Simulate user confirmation (Yes)
        print(f"\nUser Question: Is '{employment.job_alignment_title}' aligned to your {employment.job_alignment_original_program} program?")
        print(f"   User Answer: YES")
        
        employment.confirm_cross_program_alignment(confirmed=True)
        print(f"   Alignment confirmed! Status: {employment.job_alignment_status}")
        
    elif employment.job_alignment_status == 'aligned':
        print(f"   Direct alignment found in original program")
    else:
        print(f"   No alignment found")
    
    # Test case 2: Position that doesn't match anywhere
    test_position2 = "Completely Unknown Job Title XYZ"
    
    print(f"\nTesting position: '{test_position2}'")
    employment.position_current = test_position2
    employment.update_job_alignment()
    employment.save()
    
    print(f"\nAlignment Result:")
    print(f"   Status: {employment.job_alignment_status}")
    
    if employment.job_alignment_status == 'not_aligned':
        print(f"   No alignment found (expected for unknown position)")
    
    print("\n" + "=" * 70)
    print("CROSS-PROGRAM ALIGNMENT TEST COMPLETE")
    print("=" * 70)


def show_job_table_coverage():
    """Show current job table coverage"""
    print("\nJOB TABLE COVERAGE:")
    print("-" * 40)
    
    comp_tech_count = SimpleCompTechJob.objects.count()
    info_tech_count = SimpleInfoTechJob.objects.count()
    info_system_count = SimpleInfoSystemJob.objects.count()
    
    print(f"BIT-CT Jobs:     {comp_tech_count}")
    print(f"BSIT Jobs:       {info_tech_count}")
    print(f"BSIS Jobs:       {info_system_count}")
    print(f"Total Jobs:      {comp_tech_count + info_tech_count + info_system_count}")
    
    # Show some sample jobs
    print(f"\nSample Jobs:")
    if comp_tech_count > 0:
        sample = SimpleCompTechJob.objects.first()
        print(f"   BIT-CT: {sample.job_title}")
    if info_tech_count > 0:
        sample = SimpleInfoTechJob.objects.first()
        print(f"   BSIT:   {sample.job_title}")
    if info_system_count > 0:
        sample = SimpleInfoSystemJob.objects.first()
        print(f"   BSIS:   {sample.job_title}")


def test_fuzzy_matching():
    """Test fuzzy matching capabilities"""
    print(f"\nFUZZY MATCHING TEST:")
    print("-" * 40)
    
    # Test with a slightly misspelled job title
    test_query = "softwar developr"  # Missing 'e' in software, missing 'e' in developer
    
    print(f"Query: '{test_query}'")
    
    # Test in each job table
    for model_name, model in [
        ('BIT-CT', SimpleCompTechJob),
        ('BSIT', SimpleInfoTechJob),
        ('BSIS', SimpleInfoSystemJob)
    ]:
        try:
            matches = model.objects.annotate(
                similarity=TrigramSimilarity('job_title', test_query)
            ).filter(similarity__gt=0.3).order_by('-similarity')[:3]
            
            if matches:
                print(f"   {model_name}:")
                for match in matches:
                    print(f"     '{match.job_title}' (similarity: {match.similarity:.2f})")
            else:
                print(f"   {model_name}: No fuzzy matches")
        except Exception as e:
            print(f"   {model_name}: Error - {e}")


if __name__ == "__main__":
    show_job_table_coverage()
    test_fuzzy_matching()
    test_cross_program_alignment()
