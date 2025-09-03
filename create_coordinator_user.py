import os
import sys
import django
from datetime import date

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, AccountType

def create_coordinator_user():
    try:
        # Get or create coordinator account type
        coordinator_account_type, created = AccountType.objects.get_or_create(
            coordinator=True,
            admin=False,
            peso=False,
            user=False
        )
        
        if created:
            print(f"Created coordinator account type with ID: {coordinator_account_type.account_type_id}")
        else:
            print(f"Using existing coordinator account type with ID: {coordinator_account_type.account_type_id}")
        
        # Check if coordinator user already exists
        existing_coordinator = User.objects.filter(acc_username='coordinator').first()
        if existing_coordinator:
            print("Coordinator user already exists!")
            return existing_coordinator
        
        # Parse the password date (01/01/1000)
        password_date = date(2002, 11, 3)  # november 3, 2002
        
        # Create coordinator user
        coordinator_user = User.objects.create(
            account_type=coordinator_account_type,
            acc_username='coordinator',
            acc_password=password_date,  # november 3, 2002
            user_status='active',
            f_name='Coordinator',
            l_name='User',
            gender='N/A',
            civil_status='N/A'
        )
        
        print(f"Successfully created coordinator user with ID: {coordinator_user.user_id}")
        print(f"Username: {coordinator_user.acc_username}")
        print(f"Password: {coordinator_user.acc_password}")
        return coordinator_user
        
    except Exception as e:
        print(f"Error creating coordinator user: {e}")
        return None

if __name__ == '__main__':
    create_coordinator_user() 