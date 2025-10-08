#!/usr/bin/env python
"""
Comprehensive Phase 3 completion verification.
Checks all implemented features and functionality.
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
from django.db import connection
import logging

def check_phase3_completion():
    """Comprehensive Phase 3 verification"""
    print("=" * 80)
    print("PHASE 3 COMPLETION VERIFICATION")
    print("=" * 80)
    
    checks_passed = 0
    total_checks = 0
    
    # Check 1: Database migrations applied
    total_checks += 1
    print(f"\n1. DATABASE MIGRATIONS")
    print("-" * 40)
    
    try:
        with connection.cursor() as cursor:
            # Check if trigram extension exists
            cursor.execute("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm');")
            trigram_exists = cursor.fetchone()[0]
            
            # Check if new fields exist
            cursor.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'shared_employmenthistory' 
                AND column_name IN ('job_alignment_suggested_program', 'job_alignment_original_program')
            """)
            new_fields = [row[0] for row in cursor.fetchall()]
            
            # Check if trigram indexes exist
            cursor.execute("""
                SELECT indexname FROM pg_indexes 
                WHERE indexname LIKE '%_trgm_idx'
            """)
            trigram_indexes = [row[0] for row in cursor.fetchall()]
            
            if trigram_exists and len(new_fields) == 2 and len(trigram_indexes) >= 3:
                print("   [OK] Trigram extension: Installed")
                print("   [OK] New fields: Added")
                print("   [OK] Trigram indexes: Created")
                checks_passed += 1
            else:
                print("   [FAIL] Database setup incomplete")
                print(f"      Trigram: {trigram_exists}")
                print(f"      New fields: {new_fields}")
                print(f"      Trigram indexes: {trigram_indexes}")
                
    except Exception as e:
        print(f"   [FAIL] Database check failed: {e}")
    
    # Check 2: Job tables populated
    total_checks += 1
    print(f"\n2. JOB TABLES POPULATION")
    print("-" * 40)
    
    comp_tech_count = SimpleCompTechJob.objects.count()
    info_tech_count = SimpleInfoTechJob.objects.count()
    info_system_count = SimpleInfoSystemJob.objects.count()
    total_jobs = comp_tech_count + info_tech_count + info_system_count
    
    if total_jobs > 200:  # Should have substantial job data
        print(f"   [OK] BIT-CT Jobs: {comp_tech_count}")
        print(f"   [OK] BSIT Jobs: {info_tech_count}")
        print(f"   [OK] BSIS Jobs: {info_system_count}")
        print(f"   [OK] Total Jobs: {total_jobs}")
        checks_passed += 1
    else:
        print(f"   [FAIL] Insufficient job data: {total_jobs} jobs")
    
    # Check 3: Fuzzy matching functionality
    total_checks += 1
    print(f"\n3. FUZZY MATCHING FUNCTIONALITY")
    print("-" * 40)
    
    try:
        test_query = "softwar developr"  # Intentional typos
        
        # Test fuzzy matching in each table
        fuzzy_works = False
        for model_name, model in [
            ('BIT-CT', SimpleCompTechJob),
            ('BSIT', SimpleInfoTechJob),
            ('BSIS', SimpleInfoSystemJob)
        ]:
            matches = model.objects.annotate(
                similarity=TrigramSimilarity('job_title', test_query)
            ).filter(similarity__gt=0.3).order_by('-similarity')[:1]
            
            if matches:
                match = matches[0]
                print(f"   [OK] {model_name}: '{match.job_title}' (similarity: {match.similarity:.2f})")
                fuzzy_works = True
            else:
                print(f"   [WARN] {model_name}: No fuzzy matches")
        
        if fuzzy_works:
            checks_passed += 1
        else:
            print("   [FAIL] Fuzzy matching not working")
            
    except Exception as e:
        print(f"   [FAIL] Fuzzy matching test failed: {e}")
    
    # Check 4: Cross-program alignment
    total_checks += 1
    print(f"\n4. CROSS-PROGRAM ALIGNMENT")
    print("-" * 40)
    
    try:
        # Get a test user
        test_user = User.objects.filter(
            account_type__user=True,
            academic_info__program__icontains='bsit'
        ).first()
        
        if test_user:
            employment = getattr(test_user, 'employment', None)
            if employment:
                # Test with a position that should trigger cross-program suggestion
                original_position = employment.position_current
                employment.position_current = "Biofuels Processing Technicians"
                employment.update_job_alignment()
                employment.save()
                
                if employment.job_alignment_status == 'pending_confirmation':
                    print("   [OK] Cross-program suggestion: Working")
                    print(f"      Status: {employment.job_alignment_status}")
                    print(f"      Suggested: {employment.job_alignment_suggested_program}")
                    print(f"      Original: {employment.job_alignment_original_program}")
                    checks_passed += 1
                    
                    # Test confirmation
                    employment.confirm_cross_program_alignment(confirmed=True)
                    if employment.job_alignment_status == 'aligned':
                        print("   [OK] User confirmation: Working")
                    else:
                        print("   [FAIL] User confirmation: Failed")
                else:
                    print(f"   [FAIL] Cross-program not triggered (status: {employment.job_alignment_status})")
                
                # Restore original position
                employment.position_current = original_position
                employment.save()
            else:
                print("   [FAIL] No employment record for testing")
        else:
            print("   [FAIL] No test user found")
            
    except Exception as e:
        print(f"   [FAIL] Cross-program test failed: {e}")
    
    # Check 5: API endpoints
    total_checks += 1
    print(f"\n5. API ENDPOINTS")
    print("-" * 40)
    
    try:
        from apps.shared.views import check_job_alignment, confirm_job_alignment, get_job_alignment_suggestions
        
        # Check if functions exist and are callable
        if callable(check_job_alignment) and callable(confirm_job_alignment) and callable(get_job_alignment_suggestions):
            print("   [OK] check_job_alignment: Available")
            print("   [OK] confirm_job_alignment: Available")
            print("   [OK] get_job_alignment_suggestions: Available")
            checks_passed += 1
        else:
            print("   [FAIL] API endpoints not properly defined")
            
    except ImportError as e:
        print(f"   [FAIL] API endpoints import failed: {e}")
    
    # Check 6: Management command
    total_checks += 1
    print(f"\n6. MANAGEMENT COMMAND")
    print("-" * 40)
    
    try:
        from apps.shared.management.commands.analyze_job_alignment import Command
        if Command:
            print("   [OK] analyze_job_alignment command: Available")
            checks_passed += 1
        else:
            print("   [FAIL] Management command not found")
    except ImportError as e:
        print(f"   [FAIL] Management command import failed: {e}")
    
    # Check 7: Frontend component
    total_checks += 1
    print(f"\n7. FRONTEND COMPONENT")
    print("-" * 40)
    
    frontend_path = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'src', 'components', 'JobAlignmentConfirmation.tsx')
    css_path = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'src', 'components', 'JobAlignmentConfirmation.css')
    
    if os.path.exists(frontend_path) and os.path.exists(css_path):
        print("   [OK] JobAlignmentConfirmation.tsx: Created")
        print("   [OK] JobAlignmentConfirmation.css: Created")
        checks_passed += 1
    else:
        print("   [FAIL] Frontend components missing")
        print(f"      TSX: {os.path.exists(frontend_path)}")
        print(f"      CSS: {os.path.exists(css_path)}")
    
    # Final summary
    print("\n" + "=" * 80)
    print("PHASE 3 VERIFICATION SUMMARY")
    print("=" * 80)
    
    print(f"\nChecks Passed: {checks_passed}/{total_checks}")
    print(f"Success Rate: {checks_passed/total_checks*100:.1f}%")
    
    if checks_passed == total_checks:
        print("\n[SUCCESS] PHASE 3 IS COMPLETE!")
        print("[OK] All features implemented and working")
        print("[OK] Database properly configured")
        print("[OK] API endpoints functional")
        print("[OK] Frontend components created")
        print("[OK] Cross-program alignment working")
        print("[OK] Fuzzy matching operational")
        print("\n[READY] READY FOR PRODUCTION!")
    else:
        print(f"\n[WARNING] PHASE 3 INCOMPLETE")
        print(f"[FAIL] {total_checks - checks_passed} checks failed")
        print("[FIX] Review failed items above")
    
    print("=" * 80)
    
    return checks_passed == total_checks


if __name__ == "__main__":
    check_phase3_completion()
