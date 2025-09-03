import os
import django
from django.db import connection
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

def create_simple_job_tables():
    print("=== CREATING SIMPLE JOB TABLES ===")
    
    try:
        with connection.cursor() as cursor:
            # Create SimpleInfoSystemJob table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS shared_simpleinfosystemjob (
                    id SERIAL PRIMARY KEY,
                    job_title VARCHAR(255) UNIQUE NOT NULL
                )
            """)
            print("Created shared_simpleinfosystemjob table")
            
            # Create SimpleInfoTechJob table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS shared_simpleinfotechjob (
                    id SERIAL PRIMARY KEY,
                    job_title VARCHAR(255) UNIQUE NOT NULL
                )
            """)
            print("Created shared_simpleinfotechjob table")
            
            # Create SimpleCompTechJob table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS shared_simplecomptechjob (
                    id SERIAL PRIMARY KEY,
                    job_title VARCHAR(255) UNIQUE NOT NULL
                )
            """)
            print("Created shared_simplecomptechjob table")
            
        print("All simple job tables created successfully!")
        
    except Exception as e:
        print(f"Error creating tables: {e}")

if __name__ == '__main__':
    create_simple_job_tables() 