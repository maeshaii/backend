import os
import django
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, AccountType

USERNAME = 'admin'
PASSWORD = 'wherenayou2025'
FIRST_NAME = 'Admin'
LAST_NAME = 'User'
GENDER = 'Other'
USER_STATUS = 'active'

def main():
    # Ensure AccountType with admin=True exists
    admin_type, created = AccountType.objects.get_or_create(
        admin=True,
        defaults={
            'peso': False,
            'user': False,
            'coordinator': False,
        }
    )

    user, created = User.objects.get_or_create(
        acc_username=USERNAME,
        defaults={
            'account_type': admin_type,
            'user_status': USER_STATUS,
            'f_name': FIRST_NAME,
            'l_name': LAST_NAME,
            'gender': GENDER,
        }
    )
    user.account_type = admin_type
    user.set_password(PASSWORD)
    user.save()
    print(f"Admin user '{USERNAME}' {'created' if created else 'updated'} with a secure password.")

if __name__ == "__main__":
    main() 