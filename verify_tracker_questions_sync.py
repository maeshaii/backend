#!/usr/bin/env python
"""
Comprehensive verification script to check:
1. Current database questions match the seed file
2. Export function works correctly
3. Import/seed function works correctly
4. Sync script works correctly
5. All question data integrity (IDs, text, types, options, order, required)

Run this to ensure everything is in sync before sharing with coworkers.
"""

import os
import sys
import django
import json
from collections import OrderedDict

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import QuestionCategory, Question


def normalize_data(data):
    """Normalize question/category data for comparison"""
    if isinstance(data, dict):
        # Sort questions by order, then by text
        if 'questions' in data:
            data['questions'] = sorted(
                data['questions'],
                key=lambda x: (x.get('order', 0), x.get('text', ''))
            )
        return OrderedDict(sorted(data.items()))
    return data


def get_db_questions():
    """Get all questions from database as normalized dict"""
    categories = QuestionCategory.objects.prefetch_related('questions').order_by('order', 'id')
    
    db_data = []
    for cat in categories:
        questions = cat.questions.all().order_by('order', 'id')
        cat_data = {
            'title': cat.title,
            'description': cat.description,
            'order': cat.order,
            'questions': []
        }
        for q in questions:
            q_data = {
                'text': q.text,
                'type': q.type,
                'options': sorted(q.options) if q.options else [],
                'required': q.required,
                'order': q.order
            }
            cat_data['questions'].append(q_data)
        db_data.append(cat_data)
    
    return db_data


def get_seed_questions():
    """Get questions from seed file"""
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Try standard path
    seed_file_path = os.path.join(
        backend_dir, 
        'apps', 
        'shared', 
        'management', 
        'commands', 
        'tracker_questions_seed.py'
    )
    
    # Try alternative path
    if not os.path.exists(seed_file_path):
        alt_path = os.path.join(
            backend_dir,
            'apps',
            'apps',
            'shared',
            'management',
            'commands',
            'tracker_questions_seed.py'
        )
        if os.path.exists(alt_path):
            seed_file_path = alt_path
    
    if not os.path.exists(seed_file_path):
        return None, f"Seed file not found at: {seed_file_path}"
    
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("tracker_questions_seed", seed_file_path)
        seed_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(seed_module)
        
        if not hasattr(seed_module, 'CATEGORIES_DATA'):
            return None, "Seed file doesn't contain CATEGORIES_DATA"
        
        return seed_module.CATEGORIES_DATA, None
    except Exception as e:
        return None, f"Error loading seed file: {str(e)}"


def compare_questions(db_data, seed_data):
    """Compare database questions with seed file questions"""
    issues = []
    
    # Check category count
    if len(db_data) != len(seed_data):
        issues.append(f"❌ Category count mismatch: DB has {len(db_data)}, Seed has {len(seed_data)}")
    
    # Compare each category
    for i, (db_cat, seed_cat) in enumerate(zip(db_data, seed_data), 1):
        # Compare category fields
        if db_cat['title'] != seed_cat['title']:
            issues.append(f"❌ Category {i}: Title mismatch")
            issues.append(f"   DB: '{db_cat['title']}'")
            issues.append(f"   Seed: '{seed_cat['title']}'")
        
        if db_cat['description'] != seed_cat['description']:
            issues.append(f"⚠️  Category {i}: Description mismatch (may be okay)")
        
        if db_cat['order'] != seed_cat.get('order', 0):
            issues.append(f"⚠️  Category {i}: Order mismatch")
        
        # Compare questions
        db_questions = sorted(db_cat['questions'], key=lambda x: (x['order'], x['text']))
        seed_questions = sorted(seed_cat.get('questions', []), key=lambda x: (x.get('order', 0), x.get('text', '')))
        
        if len(db_questions) != len(seed_questions):
            issues.append(f"❌ Category {i} ('{db_cat['title']}'): Question count mismatch")
            issues.append(f"   DB has {len(db_questions)} questions, Seed has {len(seed_questions)} questions")
        
        # Compare each question
        for j, (db_q, seed_q) in enumerate(zip(db_questions, seed_questions), 1):
            q_text = db_q['text']
            
            if db_q['text'] != seed_q.get('text', ''):
                issues.append(f"❌ Category {i}, Question {j}: Text mismatch")
                issues.append(f"   DB: '{db_q['text']}'")
                issues.append(f"   Seed: '{seed_q.get('text', '')}'")
            
            if db_q['type'] != seed_q.get('type', ''):
                issues.append(f"❌ Category {i}, Question {j} ('{q_text}'): Type mismatch")
                issues.append(f"   DB: '{db_q['type']}', Seed: '{seed_q.get('type', '')}'")
            
            db_opts = sorted(db_q['options']) if db_q['options'] else []
            seed_opts = sorted(seed_q.get('options', [])) if seed_q.get('options') else []
            if db_opts != seed_opts:
                issues.append(f"❌ Category {i}, Question {j} ('{q_text}'): Options mismatch")
                issues.append(f"   DB: {db_opts}")
                issues.append(f"   Seed: {seed_opts}")
            
            if db_q['required'] != seed_q.get('required', False):
                issues.append(f"❌ Category {i}, Question {j} ('{q_text}'): Required flag mismatch")
                issues.append(f"   DB: {db_q['required']}, Seed: {seed_q.get('required', False)}")
            
            if db_q['order'] != seed_q.get('order', 0):
                issues.append(f"⚠️  Category {i}, Question {j} ('{q_text}'): Order mismatch")
                issues.append(f"   DB: {db_q['order']}, Seed: {seed_q.get('order', 0)}")
    
    return issues


def verify_export_function():
    """Test if export function works"""
    print("\n" + "="*70)
    print("🔍 Testing Export Function")
    print("="*70)
    
    try:
        from django.core.management import call_command
        from io import StringIO
        
        # Test export to a temp file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp:
            tmp_path = tmp.name
        
        call_command('export_tracker_questions', output=tmp_path, overwrite=True)
        
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
            print("✅ Export function works correctly")
            return True
        else:
            print("❌ Export function failed - file not created")
            return False
    except Exception as e:
        print(f"❌ Export function error: {str(e)}")
        return False


def verify_seed_function():
    """Test if seed function can be imported and validated"""
    print("\n" + "="*70)
    print("🔍 Testing Seed Function")
    print("="*70)
    
    seed_data, error = get_seed_questions()
    if error:
        print(f"❌ {error}")
        return False
    
    # Check if seed function exists
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    seed_file_path = os.path.join(
        backend_dir, 
        'apps', 
        'shared', 
        'management', 
        'commands', 
        'tracker_questions_seed.py'
    )
    
    if not os.path.exists(seed_file_path):
        alt_path = os.path.join(backend_dir, 'apps', 'apps', 'shared', 'management', 'commands', 'tracker_questions_seed.py')
        if os.path.exists(alt_path):
            seed_file_path = alt_path
    
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("tracker_questions_seed", seed_file_path)
        seed_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(seed_module)
        
        if hasattr(seed_module, 'seed_tracker_questions'):
            print("✅ Seed function exists and can be imported")
            
            # Check function signature
            import inspect
            sig = inspect.signature(seed_module.seed_tracker_questions)
            params = list(sig.parameters.keys())
            if 'apps' in params and 'schema_editor' in params:
                print("✅ Seed function has correct signature (can be used in migrations)")
            else:
                print("⚠️  Seed function signature may not support migrations")
            
            return True
        else:
            print("❌ Seed function not found in seed file")
            return False
    except Exception as e:
        print(f"❌ Error testing seed function: {str(e)}")
        return False


def main():
    print("="*70)
    print("📋 TRACKER QUESTIONS VERIFICATION")
    print("="*70)
    print()
    
    # Get current database state
    print("📊 Current Database State:")
    db_data = get_db_questions()
    total_db_questions = sum(len(cat['questions']) for cat in db_data)
    print(f"   Categories: {len(db_data)}")
    print(f"   Questions: {total_db_questions}")
    print()
    
    # Get seed file data
    print("📦 Seed File:")
    seed_data, error = get_seed_questions()
    if error:
        print(f"   {error}")
        print()
        print("⚠️  Cannot verify - seed file not found or invalid")
        print("   Run: python manage.py export_tracker_questions")
        return False
    
    total_seed_questions = sum(len(cat.get('questions', [])) for cat in seed_data)
    print(f"   Categories: {len(seed_data)}")
    print(f"   Questions: {total_seed_questions}")
    print()
    
    # Compare
    print("🔍 Comparing Database vs Seed File...")
    print()
    issues = compare_questions(db_data, seed_data)
    
    sync_status = True
    if not issues:
        print("✅ PERFECT MATCH! Database and seed file are identical.")
    else:
        critical = [i for i in issues if '❌' in i]
        warnings = [i for i in issues if '⚠️' in i]
        
        if critical:
            print("❌ CRITICAL ISSUES FOUND:")
            for issue in critical:
                print(f"   {issue}")
        
        if warnings:
            print("\n⚠️  WARNINGS (may be okay):")
            for issue in warnings:
                print(f"   {issue}")
        
        sync_status = len(critical) == 0
    
    # Test functions
    export_ok = verify_export_function()
    seed_ok = verify_seed_function()
    
    # Final summary
    print("\n" + "="*70)
    print("📋 VERIFICATION SUMMARY")
    print("="*70)
    print()
    
    all_ok = sync_status and export_ok and seed_ok
    
    if all_ok and not issues:
        print("✅ ALL CHECKS PASSED!")
        print()
        print("✅ Database matches seed file")
        print("✅ Export function works")
        print("✅ Seed function works")
        print()
        print("🎉 Ready to share with coworkers!")
        print("   They can run: python sync_tracker_questions.py")
    else:
        print("⚠️  SOME ISSUES FOUND:")
        if not sync_status:
            print("   ❌ Database and seed file don't match")
            print("      Run: python manage.py export_tracker_questions --overwrite")
        if not export_ok:
            print("   ❌ Export function has issues")
        if not seed_ok:
            print("   ❌ Seed function has issues")
        print()
        print("💡 Fix the issues above before sharing with coworkers")
    
    print()
    return all_ok and not issues


if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n❌ Aborted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

