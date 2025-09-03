import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.db import connection

def manual_job_add():
    print("=== MANUALLY ADDING JOB TITLES ===")
    
    # The job titles that users actually have
    user_job_titles = [
        'Budget Analysts',
        'Business Operations Specialists, All Other',
        'Automotive Body and Related Repairers',
        'Compliance Managers'
    ]
    
    try:
        # Clear existing data
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM shared_infosystemjob")
            cursor.execute("DELETE FROM shared_infotechjob")
            cursor.execute("DELETE FROM shared_comptechjob")
        print("Cleared existing job mapping data")
        
        # Add job titles to all three tables (since users are BSIS)
        for job_title in user_job_titles:
            with connection.cursor() as cursor:
                # Add to InfoSystemJob (BSIS)
                cursor.execute(
                    "INSERT INTO shared_infosystemjob (job_title) VALUES (%s)",
                    [job_title]
                )
                # Add to InfoTechJob (BSIT)
                cursor.execute(
                    "INSERT INTO shared_infotechjob (job_title) VALUES (%s)",
                    [job_title]
                )
                # Add to CompTechJob (BIT-CT)
                cursor.execute(
                    "INSERT INTO shared_comptechjob (job_title) VALUES (%s)",
                    [job_title]
                )
                print(f"Added: {job_title}")
        
        # Print summary
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM shared_infosystemjob")
            bsis_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM shared_infotechjob")
            bsit_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM shared_comptechjob")
            bit_ct_count = cursor.fetchone()[0]
        
        print(f"\n=== SUMMARY ===")
        print(f"InfoSystemJob (BSIS): {bsis_count} jobs")
        print(f"InfoTechJob (BSIT): {bsit_count} jobs")
        print(f"CompTechJob (BIT-CT): {bit_ct_count} jobs")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    manual_job_add() 