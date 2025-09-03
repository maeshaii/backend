import os
import django
from datetime import datetime

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from apps.shared.models import User, AccountType

def create_user():
    username = '1330189'
    password_str = '2003-04-02'
    first_name = 'angel'
    last_name = 'aboloc'
    gender = 'female'

    account_type, _ = AccountType.objects.get_or_create(
        user=True,
        admin=False,
        peso=False,
        coordinator=False
    )

    if User.objects.filter(acc_username=username).exists():
        print(f"User '{username}' already exists.")
        return

    password_date = datetime.strptime(password_str, '%Y-%m-%d').date()
    User.objects.create(
        acc_username=username,
        acc_password=password_date,
        f_name=first_name,
        l_name=last_name,
        gender=gender,
        user_status='active',
        account_type=account_type
    )
    print(f"Successfully created user '{username}'.")

if __name__ == "__main__":
    create_user() 