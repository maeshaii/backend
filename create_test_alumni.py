import os
import django
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, AccountType

<<<<<<< HEAD
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
=======
def create_test_alumni():
    # Get alumni account type (user=True)
    try:
        alumni_account_type = AccountType.objects.get(user=True)
    except AccountType.DoesNotExist:
        print("Error: Alumni account type not found")
        return
    
    # Check if user already exists
    ctu_id = "1337565"
    if User.objects.filter(acc_username=ctu_id).exists():
        print(f"Error: CTU ID {ctu_id} already exists")
        return
    
    # Parse birthdate (December 4, 2003)
    birthdate = datetime.strptime("2003-12-04", "%Y-%m-%d").date()
    
    # Create the alumni user
    user = User.objects.create(
        acc_username=ctu_id,
        acc_password=birthdate,
        user_status='active',
        f_name='Test',
        m_name='',
        l_name='Alumni',
        gender='M',
        phone_num=None,
        address=None,
        year_graduated=2023,
        course='BSIT',
        account_type=alumni_account_type
    )
    
    print(f"Successfully created alumni account:")
    print(f"CTU ID: {user.acc_username}")
    print(f"Name: {user.f_name} {user.m_name or ''} {user.l_name}")
    print(f"Birthdate: {user.acc_password}")
    print(f"Course: {user.course}")
    print(f"Year Graduated: {user.year_graduated}")
    print(f"Status: {user.user_status}")

if __name__ == "__main__":
    create_test_alumni() 
>>>>>>> 746e601016fd6b6113a8116f65f35a08788c789a
