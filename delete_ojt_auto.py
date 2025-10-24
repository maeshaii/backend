import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User

def delete_all_ojt_users():
    """Delete all OJT users automatically without confirmation"""
    try:
        # Delete OJT users
        ojt_users = User.objects.filter(account_type__ojt=True)
        count = ojt_users.count()
        print(f"Found {count} OJT users to delete...")

        if count == 0:
            print("No OJT users found to delete.")
        else:
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
            else:
                print("No OJTImport records found.")
        except Exception as e:
            print(f"Error deleting OJTImport records: {e}")

        print("\n✅ All OJT data has been deleted successfully!")
        print("You can now re-import OJT data to test the statistics feature.")

    except Exception as e:
        print(f"Error during deletion: {e}")

if __name__ == "__main__":
    delete_all_ojt_users()

