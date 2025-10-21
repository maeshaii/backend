import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User
from django.core.management import execute_from_command_line

def delete_all_ojt_users():
    """Delete all OJT users using Django ORM only"""
    try:
        # First, let's try to fix the migration issues by running migrations
        print("Attempting to fix migration issues...")
        execute_from_command_line(['manage.py', 'migrate', '--fake-initial'])
        execute_from_command_line(['manage.py', 'migrate'])
        print("Migration fix completed.")

    except Exception as e:
        print(f"Migration fix failed: {e}")
        print("Proceeding with deletion anyway...")

    # Now try to delete OJT users
    ojt_users = User.objects.filter(account_type__ojt=True)
    count = ojt_users.count()
    print(f"Found {count} OJT users to delete...")

    if count == 0:
        print("No OJT users found to delete.")
        return

    # Ask for confirmation
    confirm = input(f"Are you sure you want to delete {count} OJT users? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Deletion cancelled.")
        return

    deleted_count = 0
    failed_count = 0

    for user in ojt_users:
        try:
            print(f"Deleting OJT user: {user.f_name} {user.l_name} (ID: {user.user_id}, Username: {user.acc_username})")
            user.delete()
            deleted_count += 1
        except Exception as e:
            print(f"Error deleting OJT user {user.f_name} {user.l_name}: {e}")
            failed_count += 1
            continue

    print(f"OJT deletion completed. Successfully deleted: {deleted_count}, Failed: {failed_count}")

    # Also delete any OJTImport records
    try:
        from apps.shared.models import OJTImport
        import_count = OJTImport.objects.count()
        if import_count > 0:
            print(f"Found {import_count} OJTImport records to delete...")
            OJTImport.objects.all().delete()
            print(f"Deleted {import_count} OJTImport records.")
    except Exception as e:
        print(f"Error deleting OJTImport records: {e}")

if __name__ == "__main__":
    delete_all_ojt_users()

