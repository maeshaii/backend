#!/usr/bin/env python
"""
Simple script to sync tracker questions from seed file.
Run this to ensure your local database has the same questions as everyone else.

Usage:
    python sync_tracker_questions.py

Or from the backend directory:
    cd backend
    python sync_tracker_questions.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import QuestionCategory, Question


def sync_tracker_questions():
    """Sync tracker questions from seed file to database"""
    
    print("=" * 70)
    print("📋 TRACKER QUESTIONS SYNC")
    print("=" * 70)
    print()
    
    # Find the seed file (try both possible paths)
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Try standard path first
    seed_file_path = os.path.join(
        backend_dir, 
        'apps', 
        'shared', 
        'management', 
        'commands', 
        'tracker_questions_seed.py'
    )
    
    # If not found, try alternative path (handles export path bug)
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
    
    # Check if seed file exists
    if not os.path.exists(seed_file_path):
        print("❌ ERROR: Seed file not found!")
        print(f"   Expected location: {seed_file_path}")
        print()
        print("📝 SOLUTION:")
        print("   1. Make sure you've pulled the latest code from git")
        print("   2. Ask a teammate to export questions:")
        print("      python manage.py export_tracker_questions")
        print("   3. Commit and push the generated seed file")
        print()
        return False
    
    print(f"✅ Found seed file: {os.path.relpath(seed_file_path)}")
    print()
    
    # Check current state
    existing_categories = QuestionCategory.objects.count()
    existing_questions = Question.objects.count()
    
    print(f"📊 Current Database State:")
    print(f"   Categories: {existing_categories}")
    print(f"   Questions: {existing_questions}")
    print()
    
    # Import the seed module
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("tracker_questions_seed", seed_file_path)
        seed_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(seed_module)
        
        # Get the seed function
        if not hasattr(seed_module, 'seed_tracker_questions'):
            print("❌ ERROR: Seed file doesn't contain 'seed_tracker_questions' function")
            return False
        
        # Ask for confirmation if questions exist
        if existing_questions > 0 or existing_categories > 0:
            print("⚠️  WARNING: You already have questions in your database!")
            print("   This will DELETE all existing questions and replace them.")
            print()
            response = input("   Continue? (yes/no): ").strip().lower()
            
            if response not in ['yes', 'y']:
                print()
                print("❌ Aborted. Your questions remain unchanged.")
                return False
            
            print()
            print("🗑️  Deleting existing questions...")
            Question.objects.all().delete()
            QuestionCategory.objects.all().delete()
            print("   ✅ Deleted")
            print()
        
        # Run the seed function
        print("🌱 Seeding tracker questions...")
        print()
        
        categories, questions = seed_module.seed_tracker_questions(apps=None, schema_editor=None)
        
        print()
        print("=" * 70)
        print("✅ SUCCESS! Questions synced successfully")
        print("=" * 70)
        print()
        print(f"📦 Created:")
        print(f"   • {len(categories)} categories")
        print(f"   • {len(questions)} questions")
        print()
        print("📋 Categories:")
        for cat in categories:
            q_count = cat.questions.count()
            print(f"   • {cat.title} ({q_count} questions)")
        print()
        print("🎉 Your database is now in sync with the team!")
        print()
        
        return True
        
    except ImportError as e:
        print(f"❌ ERROR: Failed to import seed file")
        print(f"   {str(e)}")
        print()
        print("💡 Make sure the seed file is valid Python.")
        return False
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        print()
        print("📋 Full error details:")
        traceback.print_exc()
        return False


if __name__ == '__main__':
    try:
        success = sync_tracker_questions()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print()
        print()
        print("❌ Aborted by user.")
        sys.exit(1)

