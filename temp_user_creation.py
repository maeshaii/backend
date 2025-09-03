import os
import django
from datetime import datetime

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from apps.shared.models import User, AccountType

def create_user():
    """
    Creates a new user with the specified details.
    """
    # User details from your request
    username = '1330189'
    password_str = '2003-04-02'  # Corresponds to "april 2, 2003"
    first_name = 'angel'
    last_name = 'aboloc'
    gender = 'female'
    user_status = 'active' # Defaulting to 'active'

    # 1. Get or create the 'user' AccountType
    account_type, created = AccountType.objects.get_or_create(
        user=True,
        admin=False,
        peso=False,
        coordinator=False
    )

    if created:
        print("Created a new 'user' account type.")
    else:
        print("Found the existing 'user' account type.")

    # 2. Check if the user already exists to prevent duplicates
    if User.objects.filter(acc_username=username).exists():
        print(f"User with username '{username}' already exists. Aborting.")
        return

    # 3. Create the new user
    try:
        password_date = datetime.strptime(password_str, '%Y-%m-%d').date()

        User.objects.create(
            acc_username=username,
            acc_password=password_date,
            f_name=first_name,
            l_name=last_name,
            gender=gender,
            user_status=user_status,
            account_type=account_type
        )
        print(f"Successfully created user '{username}'.")
        print("IMPORTANT: The password was stored as a date and is NOT secure.")

    except Exception as e:
        print(f"An error occurred while creating the user: {e}")

if __name__ == "__main__":
    create_user() 