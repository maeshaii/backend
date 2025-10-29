#!/usr/bin/env python
"""
Complete Local Development Setup Script

This script sets up everything needed for local development:
1. Tracker questions (from seed file)
2. Job autocomplete tables (from all_jobs.json)

Run this after pulling the latest code to ensure you have:
- ✅ All tracker questions synced
- ✅ Job autocomplete working (Question 26)

Usage:
    cd backend
    python setup_complete_local_dev.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import QuestionCategory, Question, SimpleCompTechJob, SimpleInfoTechJob, SimpleInfoSystemJob


def check_tracker_questions():
    """Check tracker questions status"""
    categories = QuestionCategory.objects.count()
    questions = Question.objects.count()
    return categories > 0 and questions > 0


def check_job_tables():
    """Check job tables status"""
    bsit_count = SimpleInfoTechJob.objects.count()
    bsis_count = SimpleInfoSystemJob.objects.count()
    bitct_count = SimpleCompTechJob.objects.count()
    return (bsit_count + bsis_count + bitct_count) > 0


def setup_tracker_questions():
    """Sync tracker questions from seed file"""
    print("📋 Step 1: Setting up Tracker Questions...")
    print("-" * 70)
    
    try:
        # Import the sync function
        from sync_tracker_questions import sync_tracker_questions
        return sync_tracker_questions()
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print("   Try running: python sync_tracker_questions.py")
        return False


def setup_job_autocomplete():
    """Populate job autocomplete tables"""
    print()
    print("💼 Step 2: Setting up Job Autocomplete...")
    print("-" * 70)
    
    try:
        # Import from setup script
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        setup_job_path = os.path.join(backend_dir, 'setup_job_autocomplete.py')
        
        if not os.path.exists(setup_job_path):
            print(f"❌ setup_job_autocomplete.py not found!")
            print("   Make sure all files are pulled from git.")
            return False
        
        # Import and run the populate function
        import importlib.util
        spec = importlib.util.spec_from_file_location("setup_job_autocomplete", setup_job_path)
        setup_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(setup_module)
        
        if hasattr(setup_module, 'populate_job_tables'):
            return setup_module.populate_job_tables()
        else:
            print("❌ populate_job_tables function not found in setup_job_autocomplete.py")
            return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        print()
        print("💡 Try running: python setup_job_autocomplete.py")
        return False


def main():
    print("=" * 70)
    print("🚀 COMPLETE LOCAL DEVELOPMENT SETUP")
    print("=" * 70)
    print()
    print("This will set up:")
    print("  1. Tracker questions (for tracker form)")
    print("  2. Job autocomplete tables (for Question 26)")
    print()
    
    # Check current status
    print("📊 Checking current status...")
    has_questions = check_tracker_questions()
    has_jobs = check_job_tables()
    
    print(f"   Tracker Questions: {'✅ Already set up' if has_questions else '❌ Needs setup'}")
    print(f"   Job Autocomplete:  {'✅ Already set up' if has_jobs else '❌ Needs setup'}")
    print()
    
    if has_questions and has_jobs:
        print("✅ Everything is already set up!")
        print()
        response = input("   Do you want to re-setup anyway? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print()
            print("✅ Setup skipped. Everything is ready!")
            return True
        print()
    
    # Setup tracker questions
    if not has_questions:
        tracker_ok = setup_tracker_questions()
        if not tracker_ok:
            print()
            print("❌ Tracker questions setup failed!")
            return False
    else:
        print("⏭️  Skipping tracker questions (already set up)")
    
    # Setup job autocomplete
    if not has_jobs:
        jobs_ok = setup_job_autocomplete()
        if not jobs_ok:
            print()
            print("❌ Job autocomplete setup failed!")
            return False
    else:
        print("⏭️  Skipping job autocomplete (already set up)")
    
    # Final verification
    print()
    print("=" * 70)
    print("✅ SETUP COMPLETE!")
    print("=" * 70)
    print()
    
    final_questions = check_tracker_questions()
    final_jobs = check_job_tables()
    
    print("📋 Final Status:")
    print(f"   Tracker Questions: {'✅ Ready' if final_questions else '❌ Not ready'}")
    print(f"   Job Autocomplete:  {'✅ Ready' if final_jobs else '❌ Not ready'}")
    print()
    
    if final_questions and final_jobs:
        print("🎉 Everything is ready for local development!")
        print()
        print("📝 Next Steps:")
        print("   1. Restart your Django server (if running)")
        print("   2. Open the tracker form")
        print("   3. Go to Question 26 (Current Position)")
        print("   4. Start typing - autocomplete should work!")
        return True
    else:
        print("⚠️  Some setup may have failed. Check the errors above.")
        return False


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

