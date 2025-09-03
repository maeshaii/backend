import os
import django
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, AccountType

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