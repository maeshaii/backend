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

def create_admin_user():
    try:
        # Get or create admin account type
        admin_account_type, created = AccountType.objects.get_or_create(
            admin=True,
            peso=False,
            user=False,
            coordinator=False
        )
        
        if created:
            print(f"Created admin account type with ID: {admin_account_type.account_type_id}")
        else:
            print(f"Using existing admin account type with ID: {admin_account_type.account_type_id}")
        
        # Check if admin user already exists
        existing_admin = User.objects.filter(acc_username='admin').first()
        if existing_admin:
            print("Admin user already exists!")
            return existing_admin
        
        # Create admin user
        admin_user = User.objects.create(
            account_type=admin_account_type,
            acc_username='admin',
            acc_password=date(2004, 4, 2),  # april 2, 2004
            user_status='active',
            f_name='Admin',
            l_name='User',
            gender='N/A',
            civil_status='N/A'
        )
        
        print(f"Successfully created admin user with ID: {admin_user.user_id}")
        print(f"Username: {admin_user.acc_username}")
        print(f"Password: {admin_user.acc_password}")
        return admin_user
        
    except Exception as e:
        print(f"Error creating admin user: {e}")
        return None

if __name__ == '__main__':
    create_admin_user() 