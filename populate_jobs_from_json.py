#!/usr/bin/env python
"""
Populate Simple*Job tables from frontend/all_jobs.json
This script intelligently categorizes jobs into BSIT, BSIS, and BIT-CT programs
"""
import os
import sys
import django
import json

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import SimpleCompTechJob, SimpleInfoTechJob, SimpleInfoSystemJob

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
    print("POPULATING JOB ALIGNMENT TABLES FROM all_jobs.json")
    print("=" * 70)
    
    # Load JSON file
    json_path = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'src', 'all_jobs.json')
    
    if not os.path.exists(json_path):
        print(f"[ERROR] {json_path} not found!")
        return False
    
    with open(json_path, 'r', encoding='utf-8') as f:
        jobs = json.load(f)
    
    print(f"[OK] Loaded {len(jobs)} jobs from all_jobs.json\n")
    
    # Clear existing data
    print("Clearing existing job tables...")
    SimpleCompTechJob.objects.all().delete()
    SimpleInfoTechJob.objects.all().delete()
    SimpleInfoSystemJob.objects.all().delete()
    print("[OK] Tables cleared\n")
    
    # Counters
    stats = {
        'total': 0,
        'BSIT': 0,
        'BSIS': 0,
        'BIT-CT': 0,
        'multi_program': 0
    }
    
    # Process each job
    print("Processing jobs...")
    for job in jobs:
        job_title = job.get('Job Title', '').strip()
        if not job_title:
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
        
        # Print progress every 50 jobs
        if stats['total'] % 50 == 0:
            print(f"  Processed {stats['total']} jobs...")
    
    print("\n" + "=" * 70)
    print("[SUCCESS] POPULATION COMPLETE!")
    print("=" * 70)
    print(f"Total jobs processed:     {stats['total']}")
    print(f"  BSIT jobs:              {stats['BSIT']}")
    print(f"  BSIS jobs:              {stats['BSIS']}")
    print(f"  BIT-CT jobs:            {stats['BIT-CT']}")
    print(f"\nJobs in multiple programs: {stats['multi_program']}")
    print("\n" + "=" * 70)
    
    # Verify counts
    print("\nVERIFICATION:")
    print(f"SimpleInfoTechJob count:   {SimpleInfoTechJob.objects.count()}")
    print(f"SimpleInfoSystemJob count: {SimpleInfoSystemJob.objects.count()}")
    print(f"SimpleCompTechJob count:   {SimpleCompTechJob.objects.count()}")
    print("=" * 70)
    
    return True

if __name__ == '__main__':
    success = populate_job_tables()
    sys.exit(0 if success else 1)

