#!/usr/bin/env python
"""
Setup script for Job Autocomplete feature in Question 26.

This script populates the job tables needed for the JobTitleAutocomplete component
to work in the tracker form (Question 26: Current Position).

Run this script once to set up job autocomplete for your local database.

Usage:
    cd backend
    python setup_job_autocomplete.py
"""

import os
import sys
import django
import json

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import SimpleCompTechJob, SimpleInfoTechJob, SimpleInfoSystemJob


def check_job_tables():
    """Check if job tables are populated"""
    bsit_count = SimpleInfoTechJob.objects.count()
    bsis_count = SimpleInfoSystemJob.objects.count()
    bitct_count = SimpleCompTechJob.objects.count()
    
    return {
        'BSIT': bsit_count,
        'BSIS': bsis_count,
        'BIT-CT': bitct_count,
        'total': bsit_count + bsis_count + bitct_count
    }


def categorize_job(job_title):
    """
    Categorize a job title into one or more programs based on keywords.
    Returns list of program codes: ['BSIT', 'BSIS', 'BIT-CT']
    """
    title_lower = job_title.lower()
    programs = []
    
    # BSIT - Information Technology (software, networks, databases, programming)
    bsit_keywords = [
        'software', 'developer', 'programmer', 'engineer', 'network', 'database',
        'web', 'mobile', 'app', 'system administrator', 'devops', 'cloud',
        'security', 'analyst', 'architect', 'full stack', 'backend', 'frontend',
        'qa', 'quality assurance', 'automation', 'integration', 'api',
        'machine learning', 'ai', 'data engineer', 'infrastructure'
    ]
    
    # BSIS - Information Systems (business, analysis, management, consulting)
    bsis_keywords = [
        'business', 'analyst', 'consultant', 'manager', 'project',
        'data analyst', 'business intelligence', 'bi', 'erp', 'crm',
        'systems analyst', 'process', 'strategy', 'operations',
        'product manager', 'scrum', 'agile', 'coordinator'
    ]
    
    # BIT-CT - Computer Technology (hardware, technical support, maintenance)
    bitct_keywords = [
        'technician', 'technical support', 'hardware', 'repair', 'maintenance',
        'installer', 'desktop support', 'helpdesk', 'it support',
        'field', 'service', 'specialist', 'computer support',
        'equipment', 'telecommunications', 'electronics'
    ]
    
    # Check each category
    if any(kw in title_lower for kw in bsit_keywords):
        programs.append('BSIT')
    
    if any(kw in title_lower for kw in bsis_keywords):
        programs.append('BSIS')
    
    if any(kw in title_lower for kw in bitct_keywords):
        programs.append('BIT-CT')
    
    # If no match, try to make intelligent guess based on common patterns
    if not programs:
        if 'manager' in title_lower or 'director' in title_lower:
            programs.append('BSIS')  # Management roles → BSIS
        elif 'tech' in title_lower:
            programs.append('BIT-CT')  # Generic tech → BIT-CT
        else:
            # Default: add to BSIT as it's the most general IT program
            programs.append('BSIT')
    
    return programs


def populate_job_tables():
    """Main population function"""
    print("=" * 70)
    print("🔧 SETTING UP JOB AUTOCOMPLETE FOR QUESTION 26")
    print("=" * 70)
    print()
    print("This will populate job tables needed for autocomplete in tracker form.")
    print()
    
    # Check current state
    current = check_job_tables()
    print(f"📊 Current Job Table Status:")
    print(f"   BSIT jobs:    {current['BSIT']:,}")
    print(f"   BSIS jobs:    {current['BSIS']:,}")
    print(f"   BIT-CT jobs:  {current['BIT-CT']:,}")
    print(f"   Total:        {current['total']:,}")
    print()
    
    if current['total'] > 0:
        print("⚠️  WARNING: You already have jobs in the database!")
        response = input("   Do you want to REPLACE them with jobs from all_jobs.json? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print()
            print("❌ Aborted. Existing jobs remain unchanged.")
            print()
            print("💡 If autocomplete isn't working, you may need to populate the tables.")
            print("   Run this script again and type 'yes' to replace.")
            return False
        print()
    
    # Load JSON file
    json_path = os.path.join(
        os.path.dirname(__file__),
        '..',
        'frontend',
        'src',
        'all_jobs.json'
    )
    
    # Normalize path
    json_path = os.path.normpath(json_path)
    
    if not os.path.exists(json_path):
        print(f"❌ ERROR: all_jobs.json not found!")
        print(f"   Expected location: {json_path}")
        print()
        print("📝 SOLUTION:")
        print("   1. Make sure you've pulled the latest code from git")
        print("   2. Verify all_jobs.json exists in frontend/src/")
        print("   3. If missing, ask a teammate to commit it to git")
        return False
    
    print(f"✅ Found all_jobs.json: {os.path.relpath(json_path)}")
    print()
    
    # Load JSON
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            jobs = json.load(f)
        print(f"✅ Loaded {len(jobs)} jobs from all_jobs.json")
        print()
    except Exception as e:
        print(f"❌ ERROR loading JSON file: {str(e)}")
        return False
    
    # Clear existing data
    print("🗑️  Clearing existing job tables...")
    SimpleCompTechJob.objects.all().delete()
    SimpleInfoTechJob.objects.all().delete()
    SimpleInfoSystemJob.objects.all().delete()
    print("   ✅ Tables cleared")
    print()
    
    # Counters
    stats = {
        'total': 0,
        'BSIT': 0,
        'BSIS': 0,
        'BIT-CT': 0,
        'multi_program': 0,
        'skipped': 0
    }
    
    # Process each job
    print("⚙️  Processing jobs...")
    for job in jobs:
        job_title = job.get('Job Title', '').strip()
        if not job_title:
            stats['skipped'] += 1
            continue
        
        programs = categorize_job(job_title)
        
        # Add to appropriate tables
        if 'BSIT' in programs:
            SimpleInfoTechJob.objects.get_or_create(job_title=job_title)
            stats['BSIT'] += 1
        
        if 'BSIS' in programs:
            SimpleInfoSystemJob.objects.get_or_create(job_title=job_title)
            stats['BSIS'] += 1
        
        if 'BIT-CT' in programs:
            SimpleCompTechJob.objects.get_or_create(job_title=job_title)
            stats['BIT-CT'] += 1
        
        if len(programs) > 1:
            stats['multi_program'] += 1
        
        stats['total'] += 1
        
        # Print progress every 100 jobs
        if stats['total'] % 100 == 0:
            print(f"   Processed {stats['total']} jobs...")
    
    print()
    print("=" * 70)
    print("✅ SUCCESS! Job Autocomplete Setup Complete")
    print("=" * 70)
    print()
    print("📊 Population Summary:")
    print(f"   Total jobs processed:     {stats['total']:,}")
    print(f"   BSIT jobs added:          {stats['BSIT']:,}")
    print(f"   BSIS jobs added:          {stats['BSIS']:,}")
    print(f"   BIT-CT jobs added:        {stats['BIT-CT']:,}")
    print(f"   Jobs in multiple programs: {stats['multi_program']:,}")
    if stats['skipped'] > 0:
        print(f"   Skipped (empty titles):   {stats['skipped']:,}")
    print()
    
    # Verify counts
    print("📋 Verification:")
    final = check_job_tables()
    print(f"   SimpleInfoTechJob:    {final['BSIT']:,} jobs")
    print(f"   SimpleInfoSystemJob:  {final['BSIS']:,} jobs")
    print(f"   SimpleCompTechJob:    {final['BIT-CT']:,} jobs")
    print(f"   Total in database:    {final['total']:,} jobs")
    print()
    
    if final['total'] == 0:
        print("⚠️  WARNING: No jobs were added to the database!")
        print("   Check the all_jobs.json file format.")
        return False
    
    print("=" * 70)
    print()
    print("🎉 Job autocomplete is now ready!")
    print()
    print("📝 Next Steps:")
    print("   1. Restart your Django server (if running)")
    print("   2. Open the tracker form (Question 26: Current Position)")
    print("   3. Start typing a job title - autocomplete should appear!")
    print()
    print("💡 Troubleshooting:")
    print("   - If autocomplete still doesn't work, check browser console for errors")
    print("   - Make sure backend server is running")
    print("   - Verify API endpoint: GET /api/shared/job-autocomplete/")
    print()
    
    return True


if __name__ == '__main__':
    try:
        success = populate_job_tables()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n❌ Aborted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

