import os
import django
import pandas as pd
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import SimpleInfoSystemJob, SimpleInfoTechJob, SimpleCompTechJob

def populate_simple_job_mapping():
    print("=== POPULATING SIMPLE JOB MAPPING TABLES ===")
    
    try:
        # Read the Excel file
        df = pd.read_excel('job_alignment_mapping.xlsx')
        print(f"Loaded Excel file with {len(df)} rows")
        print(f"Columns: {list(df.columns)}")
        
        # Clear existing data
        SimpleInfoSystemJob.objects.all().delete()
        SimpleInfoTechJob.objects.all().delete()
        SimpleCompTechJob.objects.all().delete()
        print("Cleared existing simple job mapping data")
        
        # Process each row
        for index, row in df.iterrows():
            try:
                # Get job title and course
                job_title = str(row.get('Job Title', '')).strip()
                course = str(row.get('Course', '')).strip().upper()
                
                if not job_title or job_title == 'nan':
                    continue
                
                # Create job mapping based on course
                if 'BSIS' in course or 'INFORMATION SYSTEMS' in course:
                    SimpleInfoSystemJob.objects.create(job_title=job_title)
                    print(f"Added BSIS: {job_title}")
                elif 'BSIT' in course or 'INFORMATION TECHNOLOGY' in course:
                    SimpleInfoTechJob.objects.create(job_title=job_title)
                    print(f"Added BSIT: {job_title}")
                elif 'BIT-CT' in course or 'COMPUTER TECHNOLOGY' in course:
                    SimpleCompTechJob.objects.create(job_title=job_title)
                    print(f"Added BIT-CT: {job_title}")
                else:
                    # If no specific course, add to all three
                    SimpleInfoSystemJob.objects.create(job_title=job_title)
                    SimpleInfoTechJob.objects.create(job_title=job_title)
                    SimpleCompTechJob.objects.create(job_title=job_title)
                    print(f"Added to all courses: {job_title}")
                    
            except Exception as e:
                print(f"Error processing row {index}: {e}")
                continue
        
        # Print summary
        print(f"\n=== SUMMARY ===")
        print(f"SimpleInfoSystemJob (BSIS): {SimpleInfoSystemJob.objects.count()} jobs")
        print(f"SimpleInfoTechJob (BSIT): {SimpleInfoTechJob.objects.count()} jobs")
        print(f"SimpleCompTechJob (BIT-CT): {SimpleCompTechJob.objects.count()} jobs")
        
    except Exception as e:
        print(f"Error reading Excel file: {e}")

if __name__ == '__main__':
    populate_simple_job_mapping() 