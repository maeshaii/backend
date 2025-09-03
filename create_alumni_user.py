import os
import django
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, AccountType

USERNAME = '1337565'
PASSWORD = '2003-12-04'  # Must be in YYYY-MM-DD format for DateField
FIRST_NAME = 'Alumni'
LAST_NAME = 'User'
GENDER = 'Other'
USER_STATUS = 'active'

def main():
    # Ensure AccountType with user=True exists
    alumni_type, created = AccountType.objects.get_or_create(
        user=True,
        defaults={
            'admin': False,
            'peso': False,
            'coordinator': False,
        }
    )

    # Check if user already exists
    if User.objects.filter(acc_username=USERNAME).exists():
        print(f"User '{USERNAME}' already exists.")
    else:
        user = User.objects.create(
            acc_username=USERNAME,
            acc_password=datetime.strptime(PASSWORD, '%Y-%m-%d'),
            account_type=alumni_type,
            user_status=USER_STATUS,
            f_name=FIRST_NAME,
            l_name=LAST_NAME,
            gender=GENDER,
        )
        print(f"Alumni user '{USERNAME}' created successfully.")

if __name__ == "__main__":
    main() 