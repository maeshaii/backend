import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.db import connection
from apps.shared.models import OJTCompanyProfile

def create_missing_table():
    """Create the missing OJTCompanyProfile table using Django ORM"""
    try:
        # Try to access the model to trigger table creation
        print("Creating OJTCompanyProfile table...")
        
        # This will create the table if it doesn't exist
        with connection.cursor() as cursor:
            # Check if table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'shared_ojtcompanyprofile'
                );
            """)
            table_exists = cursor.fetchone()[0]
            
            if not table_exists:
                print("Table does not exist, creating it...")
                # Create the table using Django's schema editor
                from django.db import connection
                with connection.schema_editor() as schema_editor:
                    schema_editor.create_model(OJTCompanyProfile)
                print("OJTCompanyProfile table created successfully!")
            else:
                print("OJTCompanyProfile table already exists!")
                
    except Exception as e:
        print(f"Error creating table: {e}")
        print("Trying alternative approach...")
        
        # Alternative: Use makemigrations and migrate
        try:
            from django.core.management import execute_from_command_line
            print("Running makemigrations...")
            execute_from_command_line(['manage.py', 'makemigrations', 'shared', '--empty'])
            print("Running migrate...")
            execute_from_command_line(['manage.py', 'migrate'])
        except Exception as e2:
            print(f"Alternative approach failed: {e2}")

if __name__ == "__main__":
    create_missing_table()
