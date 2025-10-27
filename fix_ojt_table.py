import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.core.management import execute_from_command_line

def fix_ojt_table():
    """Fix the missing OJTCompanyProfile table issue"""
    try:
        print("Creating migration for OJTCompanyProfile table...")
        # Create a new migration
        execute_from_command_line(['manage.py', 'makemigrations', 'shared'])
        
        print("Applying the migration...")
        # Apply the migration
        execute_from_command_line(['manage.py', 'migrate', 'shared'])
        
        print("Migration completed successfully!")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        print("Trying to create the table directly...")
        
        # If migration fails, try to create the table using Django's schema editor
        try:
            from django.db import connection
            from apps.shared.models import OJTCompanyProfile
            
            with connection.schema_editor() as schema_editor:
                schema_editor.create_model(OJTCompanyProfile)
            print("Table created successfully using schema editor!")
            
        except Exception as e2:
            print(f"Schema editor approach also failed: {e2}")

if __name__ == "__main__":
    fix_ojt_table()

















