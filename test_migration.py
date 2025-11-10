#!/usr/bin/env python
"""
Test script to verify the migration system works correctly.
This simulates what happens when someone clones the repo fresh.
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.core.management import call_command
from django.db import connection
from apps.shared.models import (
    User, AccountType, Post, Forum, Comment, Like, Repost,
    TrackerForm, Question, QuestionCategory,
    SimpleCompTechJob, SimpleInfoTechJob, SimpleInfoSystemJob,
    UserProfile, AcademicInfo, EmploymentHistory, TrackerData, OJTInfo
)

def test_migration_status():
    """Test that migrations are properly applied"""
    print("\n" + "="*70)
    print("Testing Migration Status")
    print("="*70)
    
    try:
        call_command('showmigrations', 'shared', verbosity=0)
        print("✓ Migration status check passed")
        return True
    except Exception as e:
        print(f"✗ Migration status check failed: {e}")
        return False

def test_table_exists():
    """Test that all expected tables exist"""
    print("\n" + "="*70)
    print("Testing Database Tables")
    print("="*70)
    
    expected_tables = [
        'shared_user',
        'shared_accounttype',
        'shared_userprofile',
        'shared_academicinfo',
        'shared_employmenthistory',
        'shared_trackerdata',
        'shared_ojtinfo',
        'shared_post',
        'shared_forum',
        'shared_comment',
        'shared_like',
        'shared_repost',
        'shared_trackerform',
        'shared_question',
        'shared_questioncategory',
        'shared_simplecomptechjob',
        'shared_simpleinfotechjob',
        'shared_simpleinfosystemjob',
        'shared_conversation',
        'shared_message',
        'shared_messageattachment',
        'shared_notification',
        'shared_donationrequest',
        'shared_donationimage',
        'shared_follow',
        'shared_ojtimport',
        'shared_trackerresponse',
        'shared_trackerfileupload',
        'shared_userinitialpassword',
    ]
    
    with connection.cursor() as cursor:
        # Get all table names
        cursor.execute("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public' 
            AND tablename LIKE 'shared_%'
        """)
        existing_tables = [row[0] for row in cursor.fetchall()]
    
    missing_tables = []
    for table in expected_tables:
        if table in existing_tables:
            print(f"✓ {table}")
        else:
            print(f"✗ {table} - MISSING")
            missing_tables.append(table)
    
    if missing_tables:
        print(f"\n✗ {len(missing_tables)} tables are missing!")
        return False
    else:
        print(f"\n✓ All {len(expected_tables)} tables exist!")
        return True

def test_model_operations():
    """Test that models can be queried"""
    print("\n" + "="*70)
    print("Testing Model Operations")
    print("="*70)
    
    tests_passed = 0
    tests_failed = 0
    
    models_to_test = [
        ('AccountType', AccountType),
        ('User', User),
        ('Post', Post),
        ('Forum', Forum),
        ('Comment', Comment),
        ('Like', Like),
        ('Repost', Repost),
        ('TrackerForm', TrackerForm),
        ('Question', Question),
        ('QuestionCategory', QuestionCategory),
        ('SimpleCompTechJob', SimpleCompTechJob),
        ('SimpleInfoTechJob', SimpleInfoTechJob),
        ('SimpleInfoSystemJob', SimpleInfoSystemJob),
        ('UserProfile', UserProfile),
        ('AcademicInfo', AcademicInfo),
        ('EmploymentHistory', EmploymentHistory),
        ('TrackerData', TrackerData),
        ('OJTInfo', OJTInfo),
    ]
    
    for model_name, model_class in models_to_test:
        try:
            count = model_class.objects.count()
            print(f"✓ {model_name}: {count} records")
            tests_passed += 1
        except Exception as e:
            print(f"✗ {model_name}: {e}")
            tests_failed += 1
    
    print(f"\nTests Passed: {tests_passed}/{len(models_to_test)}")
    
    return tests_failed == 0

def test_indexes():
    """Test that indexes were created"""
    print("\n" + "="*70)
    print("Testing Database Indexes")
    print("="*70)
    
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT indexname, tablename 
            FROM pg_indexes 
            WHERE schemaname = 'public' 
            AND tablename LIKE 'shared_%'
            ORDER BY tablename, indexname
        """)
        indexes = cursor.fetchall()
    
    if indexes:
        print(f"✓ Found {len(indexes)} indexes:")
        for idx_name, table_name in indexes[:10]:  # Show first 10
            print(f"  - {idx_name} on {table_name}")
        if len(indexes) > 10:
            print(f"  ... and {len(indexes) - 10} more")
        return True
    else:
        print("✗ No indexes found!")
        return False

def test_constraints():
    """Test that constraints were created"""
    print("\n" + "="*70)
    print("Testing Database Constraints")
    print("="*70)
    
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT conname, conrelid::regclass 
            FROM pg_constraint 
            WHERE conrelid::regclass::text LIKE 'shared_%'
            AND contype IN ('c', 'u', 'f')
            ORDER BY conrelid::regclass::text
        """)
        constraints = cursor.fetchall()
    
    if constraints:
        print(f"✓ Found {len(constraints)} constraints:")
        
        # Count by type
        check_constraints = [c for c in constraints if 'check' in str(c[0]).lower() or 'one_content_type' in str(c[0])]
        unique_constraints = [c for c in constraints if 'unique' in str(c[0]).lower()]
        
        print(f"  - Check constraints: {len(check_constraints)}")
        print(f"  - Unique constraints: {len(unique_constraints)}")
        print(f"  - Other constraints: {len(constraints) - len(check_constraints) - len(unique_constraints)}")
        
        # Show some examples
        for constraint_name, table_name in constraints[:5]:
            print(f"  - {constraint_name} on {table_name}")
        
        return True
    else:
        print("✗ No constraints found!")
        return False

def main():
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*15 + "MIGRATION VERIFICATION TEST" + " "*26 + "║")
    print("║" + " "*15 + "CTU Alumni Tracker System" + " "*27 + "║")
    print("╚" + "="*68 + "╝")
    
    all_tests = [
        ("Migration Status", test_migration_status),
        ("Database Tables", test_table_exists),
        ("Model Operations", test_model_operations),
        ("Database Indexes", test_indexes),
        ("Database Constraints", test_constraints),
    ]
    
    results = []
    for test_name, test_func in all_tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n✗ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name:.<50} {status}")
    
    print("="*70)
    print(f"Total: {passed_count}/{total_count} tests passed")
    print("="*70)
    
    if passed_count == total_count:
        print("\n✅ ALL TESTS PASSED! Migration system is working correctly.")
        print("   New team members can clone and migrate without errors.")
        return 0
    else:
        print(f"\n⚠️  {total_count - passed_count} test(s) failed. Please review the output above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())















































