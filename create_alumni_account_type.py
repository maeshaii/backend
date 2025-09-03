import os
import sys
import django

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import AccountType

def create_alumni_account_type():
    try:
        alumni_account_type, created = AccountType.objects.get_or_create(
            user=True,
            admin=False,
            peso=False,
            coordinator=False
        )
        if created:
            print(f"Successfully created alumni account type with ID: {alumni_account_type.account_type_id}")
        else:
            print(f"Alumni account type already exists with ID: {alumni_account_type.account_type_id}")
        return alumni_account_type
    except Exception as e:
        print(f"Error creating alumni account type: {e}")
        return None

if __name__ == '__main__':
    create_alumni_account_type() 