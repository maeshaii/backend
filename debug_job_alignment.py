import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, TrackerResponse, InfoSystemJob, InfoTechJob, CompTechJob

def debug_job_alignment():
    print("=== DEBUGGING JOB ALIGNMENT ===")
    
    # Check what job titles users have
    print("\n1. User job titles:")
    users = User.objects.filter(account_type__user=True)
    for user in users:
        print(f"   {user.f_name} {user.l_name} ({user.course}): '{user.position_current}'")
    
    # Check what's in the job mapping tables
    print(f"\n2. InfoSystemJob titles (BSIS):")
    for job in InfoSystemJob.objects.all()[:10]:  # First 10
        print(f"   '{job.job_title}'")
    
    print(f"\n3. InfoTechJob titles (BSIT):")
    for job in InfoTechJob.objects.all()[:10]:  # First 10
        print(f"   '{job.job_title}'")
    
    print(f"\n4. CompTechJob titles (BIT-CT):")
    for job in CompTechJob.objects.all()[:10]:  # First 10
        print(f"   '{job.job_title}'")
    
    # Check specific matches
    print(f"\n5. Checking specific matches:")
    user_jobs = ['Budget Analysts', 'Business Operations Specialists, All Other', 'Automotive Body and Related Repairers', 'Compliance Managers']
    
    for job_title in user_jobs:
        print(f"\n   Looking for: '{job_title}'")
        
        # Check InfoSystemJob (BSIS)
        matches = InfoSystemJob.objects.filter(job_title__icontains=job_title)
        if matches.exists():
            print(f"     Found in InfoSystemJob: {[m.job_title for m in matches]}")
        else:
            print(f"     NOT found in InfoSystemJob")
        
        # Check InfoTechJob (BSIT)
        matches = InfoTechJob.objects.filter(job_title__icontains=job_title)
        if matches.exists():
            print(f"     Found in InfoTechJob: {[m.job_title for m in matches]}")
        else:
            print(f"     NOT found in InfoTechJob")
        
        # Check CompTechJob (BIT-CT)
        matches = CompTechJob.objects.filter(job_title__icontains=job_title)
        if matches.exists():
            print(f"     Found in CompTechJob: {[m.job_title for m in matches]}")
        else:
            print(f"     NOT found in CompTechJob")

if __name__ == '__main__':
    debug_job_alignment() 