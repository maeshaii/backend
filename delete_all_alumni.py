import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User

def delete_all_alumni():
    alumni_users = User.objects.filter(account_type__user=True)
    count = alumni_users.count()
    print(f"Deleting {count} alumni users...")
    alumni_users.delete()
    print("All alumni users deleted.")

if __name__ == "__main__":
    delete_all_alumni() 