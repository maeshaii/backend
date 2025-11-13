import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User
<<<<<<< HEAD
from django.core.management import execute_from_command_line

def delete_all_alumni():
    """Delete all alumni users using Django ORM only"""
    try:
        # First, let's try to fix the migration issue by running migrations
        print("Attempting to fix migration issues...")
        execute_from_command_line(['manage.py', 'migrate', '--fake-initial'])
        execute_from_command_line(['manage.py', 'migrate'])
        print("Migration fix completed.")
        
    except Exception as e:
        print(f"Migration fix failed: {e}")
        print("Proceeding with deletion anyway...")
    
    # Now try to delete users
    alumni_users = User.objects.filter(account_type__user=True)
    count = alumni_users.count()
    print(f"Deleting {count} alumni users...")
    
    deleted_count = 0
    failed_count = 0
    
    for user in alumni_users:
        try:
            print(f"Deleting user: {user.f_name} {user.l_name}")
            user.delete()
            deleted_count += 1
        except Exception as e:
            print(f"Error deleting user {user.f_name} {user.l_name}: {e}")
            failed_count += 1
            continue
    
    print(f"Deletion completed. Successfully deleted: {deleted_count}, Failed: {failed_count}")
=======

def delete_all_alumni():
    alumni_users = User.objects.filter(account_type__user=True)
    count = alumni_users.count()
    print(f"Deleting {count} alumni users...")
    alumni_users.delete()
    print("All alumni users deleted.")
>>>>>>> 746e601016fd6b6113a8116f65f35a08788c789a

if __name__ == "__main__":
    delete_all_alumni() 