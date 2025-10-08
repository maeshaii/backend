#!/usr/bin/env python
"""
Test script to verify Phase 1 optimizations.
Measures query performance and validates functionality.
"""
import os
import sys
import django
import time
from django.db import connection, reset_queries
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, SimpleCompTechJob, SimpleInfoTechJob, SimpleInfoSystemJob

def print_header(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def test_job_tables():
    """Test 1: Verify job tables are populated"""
    print_header("TEST 1: Job Tables Population")
    
    ct_count = SimpleCompTechJob.objects.count()
    it_count = SimpleInfoTechJob.objects.count()
    is_count = SimpleInfoSystemJob.objects.count()
    
    print(f"SimpleCompTechJob (BIT-CT):   {ct_count:4d} jobs")
    print(f"SimpleInfoTechJob (BSIT):     {it_count:4d} jobs")
    print(f"SimpleInfoSystemJob (BSIS):   {is_count:4d} jobs")
    print(f"Total:                         {ct_count + it_count + is_count:4d} jobs")
    
    if ct_count + it_count + is_count == 0:
        print("[FAIL] Job tables are EMPTY!")
        return False
    else:
        print("[PASS] Job tables populated")
        return True

def test_query_optimization():
    """Test 2: Verify select_related() reduces query count"""
    print_header("TEST 2: Query Optimization (select_related)")
    
    # Reset query log
    settings.DEBUG = True
    reset_queries()
    
    # Without select_related (old way)
    print("\nOLD WAY (without select_related):")
    start = time.time()
    alumni = list(User.objects.filter(account_type__user=True)[:10])
    for alum in alumni:
        # Access related models (triggers additional queries)
        _ = alum.profile.email if hasattr(alum, 'profile') else None
        _ = alum.academic_info.program if hasattr(alum, 'academic_info') else None
    old_queries = len(connection.queries)
    old_time = time.time() - start
    print(f"  Queries: {old_queries}")
    print(f"  Time: {old_time:.4f}s")
    
    # Reset for new test
    reset_queries()
    
    # With select_related (new way)
    print("\nNEW WAY (with select_related):")
    start = time.time()
    alumni = list(User.objects.filter(account_type__user=True).select_related(
        'profile', 'academic_info', 'employment'
    )[:10])
    for alum in alumni:
        _ = alum.profile.email if hasattr(alum, 'profile') else None
        _ = alum.academic_info.program if hasattr(alum, 'academic_info') else None
    new_queries = len(connection.queries)
    new_time = time.time() - start
    print(f"  Queries: {new_queries}")
    print(f"  Time: {new_time:.4f}s")
    
    # Results
    print(f"\nIMPROVEMENT:")
    print(f"  Queries reduced: {old_queries} -> {new_queries} ({old_queries - new_queries} fewer)")
    if old_time > 0:
        print(f"  Speed improvement: {old_time/new_time:.2f}x faster")
    
    settings.DEBUG = False
    return new_queries < old_queries

def test_orm_vs_raw_sql():
    """Test 3: Verify ORM is used instead of raw SQL"""
    print_header("TEST 3: ORM vs Raw SQL in Job Alignment")
    
    # Check if the models.py uses ORM queries
    import os
    filepath = os.path.join(os.path.dirname(__file__), 'apps', 'shared', 'models.py')
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    if 'cursor.execute' in content:
        # Check if it's in the job alignment function
        if 'shared_simplecomptechjob' in content.lower():
            print("[FAIL] Still using raw SQL in job alignment!")
            return False
    
    if 'SimpleCompTechJob.objects.filter' in content:
        print("[PASS] Using Django ORM for job alignment")
        return True
    else:
        print("[WARN] Could not verify ORM usage")
        return None

def test_statistics_aggregation():
    """Test 4: Verify statistics use database aggregation"""
    print_header("TEST 4: Statistics Aggregation")
    
    from apps.shared.models import TrackerData
    from django.db.models import Q, Count
    
    # Test aggregation query
    settings.DEBUG = True
    reset_queries()
    
    start = time.time()
    alumni_qs = User.objects.filter(account_type__user=True)[:100]
    
    # New aggregation method
    stats = TrackerData.objects.filter(user__in=alumni_qs).aggregate(
        employed=Count('id', filter=Q(q_employment_status__iexact='yes')),
        unemployed=Count('id', filter=Q(q_employment_status__iexact='no'))
    )
    
    query_count = len(connection.queries)
    elapsed = time.time() - start
    
    print(f"Aggregation query executed in {elapsed:.4f}s")
    print(f"Total queries: {query_count}")
    print(f"Results: {stats}")
    
    settings.DEBUG = False
    
    if query_count <= 3:  # Should be just a few queries
        print("[PASS] Efficient aggregation")
        return True
    else:
        print("[WARN] More queries than expected")
        return False

def test_no_duplicate_functions():
    """Test 5: Verify no duplicate helper functions"""
    print_header("TEST 5: No Duplicate Helper Functions")
    
    import os
    filepath = os.path.join(os.path.dirname(__file__), 'apps', 'alumni_stats', 'views.py')
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if helper functions are defined locally
    if 'def safe_mode(' in content or 'def safe_mean(' in content:
        print("[FAIL] Duplicate helper functions still exist in views.py!")
        return False
    
    # Check if they're imported
    if 'from apps.shared.utils.stats import' in content:
        print("[PASS] Helper functions imported from utils")
        return True
    else:
        print("[FAIL] Helper functions not imported!")
        return False

def run_all_tests():
    """Run all Phase 1 tests"""
    print("\n" + "=" * 70)
    print("  PHASE 1 OPTIMIZATION - VERIFICATION TESTS")
    print("=" * 70)
    
    results = {
        'Job Tables': test_job_tables(),
        'Query Optimization': test_query_optimization(),
        'ORM Usage': test_orm_vs_raw_sql(),
        'Aggregation': test_statistics_aggregation(),
        'No Duplicates': test_no_duplicate_functions(),
    }
    
    # Summary
    print_header("TEST SUMMARY")
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    
    for test_name, result in results.items():
        status = "[PASS]" if result is True else "[FAIL]" if result is False else "[WARN]"
        print(f"{status} {test_name}")
    
    print(f"\nTotal: {passed} passed, {failed} failed")
    print("=" * 70)
    
    return failed == 0

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)

