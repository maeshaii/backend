import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import CompTechJob, InfoTechJob, InfoSystemJob, Suc, Standard

def add_sample_jobs():
    print("=== Adding Sample Job Titles ===")
    
    # Check if we have any existing jobs
    print(f"Current job counts:")
    print(f"  CompTechJob: {CompTechJob.objects.count()}")
    print(f"  InfoTechJob: {InfoTechJob.objects.count()}")
    print(f"  InfoSystemJob: {InfoSystemJob.objects.count()}")
    
    # Get or create a Standard
    standard, created = Standard.objects.get_or_create(
        standard_id=1,
        defaults={'name': 'CTU Standard', 'description': 'Default standard'}
    )
    print(f"Using Standard: {standard.name}")
    
    # Get or create a Suc
    suc, created = Suc.objects.get_or_create(
        standard=standard,
        defaults={}
    )
    print(f"Using Suc: {suc.suc_id}")
    
    # Sample job titles for each category
    comptech_jobs = [
        'Software Developer',
        'Web Developer', 
        'Mobile App Developer',
        'System Administrator',
        'Network Administrator',
        'IT Support Specialist',
        'Computer Technician',
        'Hardware Engineer',
        'Software Engineer',
        'DevOps Engineer'
    ]
    
    infotech_jobs = [
        'IT Support Specialist',
        'Help Desk Technician',
        'Network Administrator',
        'System Administrator',
        'IT Consultant',
        'Technical Support',
        'IT Project Manager',
        'Business Analyst',
        'Data Analyst',
        'IT Manager'
    ]
    
    infosystem_jobs = [
        'Database Administrator',
        'Systems Analyst',
        'Business Analyst',
        'IT Project Manager',
        'Information Systems Manager',
        'Data Analyst',
        'Database Developer',
        'Systems Administrator',
        'IT Consultant',
        'Information Security Analyst'
    ]
    
    # Add CompTechJob titles
    print("\nAdding CompTechJob titles...")
    for job_title in comptech_jobs:
        job, created = CompTechJob.objects.get_or_create(
            job_title=job_title,
            defaults={
                'suc': suc,
                'info_system_jobs_id': 1,
                'info_tech_jobs_id': 1
            }
        )
        if created:
            print(f"  ✓ Created: {job_title}")
        else:
            print(f"  - Exists: {job_title}")
    
    # Add InfoTechJob titles
    print("\nAdding InfoTechJob titles...")
    for job_title in infotech_jobs:
        job, created = InfoTechJob.objects.get_or_create(
            job_title=job_title,
            defaults={
                'suc': suc,
                'info_systems_jobs_id': 1,
                'comp_tech_jobs_id': 1
            }
        )
        if created:
            print(f"  ✓ Created: {job_title}")
        else:
            print(f"  - Exists: {job_title}")
    
    # Add InfoSystemJob titles
    print("\nAdding InfoSystemJob titles...")
    for job_title in infosystem_jobs:
        job, created = InfoSystemJob.objects.get_or_create(
            job_title=job_title,
            defaults={
                'suc': suc,
                'info_tech_jobs_id': 1,
                'comp_tech_jobs_id': 1
            }
        )
        if created:
            print(f"  ✓ Created: {job_title}")
        else:
            print(f"  - Exists: {job_title}")
    
    print(f"\nFinal job counts:")
    print(f"  CompTechJob: {CompTechJob.objects.count()}")
    print(f"  InfoTechJob: {InfoTechJob.objects.count()}")
    print(f"  InfoSystemJob: {InfoSystemJob.objects.count()}")

if __name__ == "__main__":
    add_sample_jobs() 