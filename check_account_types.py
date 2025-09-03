import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import AccountType, User

def check_account_types():
    print("=== Account Types in Database ===")
    
    account_types = AccountType.objects.all()
    for at in account_types:
        print(f"ID: {at.account_type_id}")
        print(f"  Admin: {at.admin}")
        print(f"  User (Alumni): {at.user}")
        print(f"  PESO: {at.peso}")
        print(f"  Coordinator: {at.coordinator}")
        print()
    
    print("=== Users by Account Type ===")
    for at in account_types:
        users = User.objects.filter(account_type=at)
        print(f"Account Type ID {at.account_type_id}: {users.count()} users")
        for user in users:
            print(f"  - {user.acc_username} ({user.f_name} {user.l_name})")

if __name__ == "__main__":
    check_account_types() 