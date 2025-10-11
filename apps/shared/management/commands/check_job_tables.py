"""
Management command to check the status of Simple*Job tables.
Useful for verifying job alignment setup and monitoring.

Usage: python manage.py check_job_tables
"""
from django.core.management.base import BaseCommand
from apps.shared.models import SimpleCompTechJob, SimpleInfoTechJob, SimpleInfoSystemJob


class Command(BaseCommand):
    help = 'Check Simple*Job table counts and report status'

    def handle(self, *args, **options):
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("JOB ALIGNMENT TABLES STATUS"))
        self.stdout.write("=" * 70)
        
        # Get counts
        ct_count = SimpleCompTechJob.objects.count()
        it_count = SimpleInfoTechJob.objects.count()
        is_count = SimpleInfoSystemJob.objects.count()
        
        total = ct_count + it_count + is_count
        
        # Display results
        self.stdout.write(f"\nSimpleCompTechJob (BIT-CT):      {ct_count:4d} jobs")
        self.stdout.write(f"SimpleInfoTechJob (BSIT):        {it_count:4d} jobs")
        self.stdout.write(f"SimpleInfoSystemJob (BSIS):      {is_count:4d} jobs")
        self.stdout.write(f"{'-' * 40}")
        self.stdout.write(f"Total job titles:                 {total:4d}")
        
        # Status check
        self.stdout.write("\n" + "=" * 70)
        if total == 0:
            self.stdout.write(self.style.ERROR("[CRITICAL] ALL TABLES ARE EMPTY!"))
            self.stdout.write(self.style.ERROR("Job alignment will NOT work."))
            self.stdout.write("\nAction required:")
            self.stdout.write("  Run: python populate_jobs_from_json.py")
        elif total < 50:
            self.stdout.write(self.style.WARNING(f"[WARNING] Only {total} jobs found."))
            self.stdout.write("Consider adding more job titles for better coverage.")
        else:
            self.stdout.write(self.style.SUCCESS(f"[OK] {total} job titles loaded. System operational."))
        
        self.stdout.write("=" * 70)
        
        # Show sample jobs
        if ct_count > 0:
            self.stdout.write(f"\nSample BIT-CT jobs (showing first 5):")
            for job in SimpleCompTechJob.objects.all()[:5]:
                self.stdout.write(f"  - {job.job_title}")
        
        if it_count > 0:
            self.stdout.write(f"\nSample BSIT jobs (showing first 5):")
            for job in SimpleInfoTechJob.objects.all()[:5]:
                self.stdout.write(f"  - {job.job_title}")
        
        if is_count > 0:
            self.stdout.write(f"\nSample BSIS jobs (showing first 5):")
            for job in SimpleInfoSystemJob.objects.all()[:5]:
                self.stdout.write(f"  - {job.job_title}")
        
        self.stdout.write("\n" + "=" * 70)



