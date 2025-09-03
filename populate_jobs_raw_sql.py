import os
import django
import pandas as pd
from django.db import connection
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

def populate_jobs_raw_sql():
    print("=== POPULATING JOB DATABASES USING RAW SQL ===")
    
    try:
        # Read the Excel file
        df = pd.read_excel('job_alignment_mapping.xlsx')
        print(f"Loaded Excel file with {len(df)} rows")
        print(f"Columns: {list(df.columns)}")
        
        # Clear existing data using raw SQL
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM shared_simpleinfosystemjob")
            cursor.execute("DELETE FROM shared_simpleinfotechjob")
            cursor.execute("DELETE FROM shared_simplecomptechjob")
        print("Cleared existing job mapping data")
        
        # Process each row
        for index, row in df.iterrows():
            try:
                # Get job title and course
                job_title = str(row.get('Job Title', '')).strip()
                course = str(row.get('Course', '')).strip().upper()
                
                if not job_title or job_title == 'nan':
                    continue
                
                # Create job mapping based on course using raw SQL
                with connection.cursor() as cursor:
                    if 'BSIS' in course or 'INFORMATION SYSTEMS' in course:
                        cursor.execute(
                            "INSERT INTO shared_simpleinfosystemjob (job_title) VALUES (%s)",
                            [job_title]
                        )
                        print(f"Added BSIS: {job_title}")
                    elif 'BSIT' in course or 'INFORMATION TECHNOLOGY' in course:
                        cursor.execute(
                            "INSERT INTO shared_simpleinfotechjob (job_title) VALUES (%s)",
                            [job_title]
                        )
                        print(f"Added BSIT: {job_title}")
                    elif 'BIT-CT' in course or 'COMPUTER TECHNOLOGY' in course:
                        cursor.execute(
                            "INSERT INTO shared_simplecomptechjob (job_title) VALUES (%s)",
                            [job_title]
                        )
                        print(f"Added BIT-CT: {job_title}")
                    else:
                        # If no specific course, add to all three
                        cursor.execute(
                            "INSERT INTO shared_simpleinfosystemjob (job_title) VALUES (%s)",
                            [job_title]
                        )
                        cursor.execute(
                            "INSERT INTO shared_simpleinfotechjob (job_title) VALUES (%s)",
                            [job_title]
                        )
                        cursor.execute(
                            "INSERT INTO shared_simplecomptechjob (job_title) VALUES (%s)",
                            [job_title]
                        )
                        print(f"Added to all courses: {job_title}")
                        
            except Exception as e:
                print(f"Error processing row {index}: {e}")
                continue
        
        # Print summary
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM shared_simpleinfosystemjob")
            bsis_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM shared_simpleinfotechjob")
            bsit_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM shared_simplecomptechjob")
            bit_ct_count = cursor.fetchone()[0]
        
        print(f"\n=== SUMMARY ===")
        print(f"SimpleInfoSystemJob (BSIS): {bsis_count} jobs")
        print(f"SimpleInfoTechJob (BSIT): {bsit_count} jobs")
        print(f"SimpleCompTechJob (BIT-CT): {bit_ct_count} jobs")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    populate_jobs_raw_sql() 