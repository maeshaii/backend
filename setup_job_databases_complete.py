import os
import django
import pandas as pd
from django.db import connection
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

def setup_job_databases():
    print("=== SETTING UP JOB DATABASES FOR COWORKER ===")
    
    try:
        # Step 1: Create simple job tables if they don't exist
        print("Step 1: Creating simple job tables...")
        with connection.cursor() as cursor:
            # Create SimpleInfoSystemJob table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS shared_simpleinfosystemjob (
                    id SERIAL PRIMARY KEY,
                    job_title VARCHAR(255) UNIQUE NOT NULL
                )
            """)
            print("✓ Created shared_simpleinfosystemjob table")
            
            # Create SimpleInfoTechJob table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS shared_simpleinfotechjob (
                    id SERIAL PRIMARY KEY,
                    job_title VARCHAR(255) UNIQUE NOT NULL
                )
            """)
            print("✓ Created shared_simpleinfotechjob table")
            
            # Create SimpleCompTechJob table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS shared_simplecomptechjob (
                    id SERIAL PRIMARY KEY,
                    job_title VARCHAR(255) UNIQUE NOT NULL
                )
            """)
            print("✓ Created shared_simplecomptechjob table")
        
        # Step 2: Read the Excel file
        print("\nStep 2: Reading job alignment mapping...")
        df = pd.read_excel('job_alignment_mapping.xlsx')
        print(f"✓ Loaded Excel file with {len(df)} rows")
        print(f"Columns: {list(df.columns)}")
        
        # Step 3: Clear existing data
        print("\nStep 3: Clearing existing data...")
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM shared_simpleinfosystemjob")
            cursor.execute("DELETE FROM shared_simpleinfotechjob")
            cursor.execute("DELETE FROM shared_simplecomptechjob")
        print("✓ Cleared existing job data")
        
        # Step 4: Populate job databases based on Course column
        print("\nStep 4: Populating job databases...")
        bsis_count = 0
        bsit_count = 0
        bit_ct_count = 0
        
        for index, row in df.iterrows():
            job_title = str(row.get('Job Title', '')).strip()
            course = str(row.get('Course', '')).strip()
            
            if not job_title or job_title == 'nan' or not course or course == 'nan':
                continue
                
            with connection.cursor() as cursor:
                # Insert based on course
                if 'BSIS' in course.upper():
                    try:
                        cursor.execute(
                            "INSERT INTO shared_simpleinfosystemjob (job_title) VALUES (%s)",
                            [job_title]
                        )
                        bsis_count += 1
                    except Exception as e:
                        if "duplicate key" not in str(e).lower():
                            print(f"Warning: Could not insert BSIS job '{job_title}': {e}")
                
                elif 'BSIT' in course.upper():
                    try:
                        cursor.execute(
                            "INSERT INTO shared_simpleinfotechjob (job_title) VALUES (%s)",
                            [job_title]
                        )
                        bsit_count += 1
                    except Exception as e:
                        if "duplicate key" not in str(e).lower():
                            print(f"Warning: Could not insert BSIT job '{job_title}': {e}")
                
                elif 'BIT-CT' in course.upper():
                    try:
                        cursor.execute(
                            "INSERT INTO shared_simplecomptechjob (job_title) VALUES (%s)",
                            [job_title]
                        )
                        bit_ct_count += 1
                    except Exception as e:
                        if "duplicate key" not in str(e).lower():
                            print(f"Warning: Could not insert BIT-CT job '{job_title}': {e}")
        
        print(f"✓ Populated job databases:")
        print(f"  - BSIS Jobs: {bsis_count}")
        print(f"  - BSIT Jobs: {bsit_count}")
        print(f"  - BIT-CT Jobs: {bit_ct_count}")
        
        # Step 5: Verify the data
        print("\nStep 5: Verifying job counts...")
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM shared_simpleinfosystemjob")
            bsis_actual = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM shared_simpleinfotechjob")
            bsit_actual = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM shared_simplecomptechjob")
            bit_ct_actual = cursor.fetchone()[0]
        
        print(f"✓ Verification complete:")
        print(f"  - BSIS Jobs in database: {bsis_actual}")
        print(f"  - BSIT Jobs in database: {bsit_actual}")
        print(f"  - BIT-CT Jobs in database: {bit_ct_actual}")
        
        # Step 6: Update all existing users' job alignment
        print("\nStep 6: Updating existing users' job alignment...")
        from apps.shared.models import User
        
        alumni_users = User.objects.filter(account_type__user=True)
        updated_count = 0
        
        for user in alumni_users:
            try:
                user.update_job_alignment()
                user.save()
                updated_count += 1
            except Exception as e:
                print(f"Warning: Could not update job alignment for {user.f_name} {user.l_name}: {e}")
        
        print(f"✓ Updated job alignment for {updated_count} users")
        
        print("\n=== SETUP COMPLETE ===")
        print("Your coworker can now use the job alignment system!")
        
    except Exception as e:
        print(f"❌ Error during setup: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    setup_job_databases() 