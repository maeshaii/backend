import os
import django
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, AccountType

def create_users():
    # --- Get or Create Account Type ---
    try:
        alumni_account_type = AccountType.objects.get(user=True, admin=False, peso=False, coordinator=False)
    except AccountType.DoesNotExist:
        print("Creating a new 'user' account type for alumni.")
        alumni_account_type = AccountType.objects.create(user=True, admin=False, peso=False, coordinator=False)

    # --- Create Test Alumni User ---
    ctu_id = "1337565"
    if not User.objects.filter(acc_username=ctu_id).exists():
        birthdate = datetime.strptime("2003-12-04", "%Y-%m-%d").date()
        user = User.objects.create(
            acc_username=ctu_id,
            acc_password=birthdate,
            user_status='active',
            f_name='Test',
            l_name='Alumni',
            gender='M',
            account_type=alumni_account_type
        )
        print(f"Successfully created alumni account: {user.acc_username}")
    else:
        print(f"User with CTU ID {ctu_id} already exists.")

    # --- Create Angel Aboloc User ---
    username_angel = '1330189'
    if not User.objects.filter(acc_username=username_angel).exists():
        password_date_angel = datetime.strptime('2003-04-02', '%Y-%m-%d').date()
        User.objects.create(
            acc_username=username_angel,
            acc_password=password_date_angel,
            f_name='angel',
            l_name='aboloc',
            gender='female',
            user_status='active',
            account_type=alumni_account_type
        )
        print(f"Successfully created user '{username_angel}'.")
    else:
        print(f"User with username '{username_angel}' already exists.")


if __name__ == "__main__":
    create_users() 