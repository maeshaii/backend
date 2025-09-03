import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, AccountType

def update_alumni_account_type():
    # Get the dedicated alumni account type
    try:
        alumni_account_type = AccountType.objects.get(user=True, admin=False, peso=False, coordinator=False)
    except AccountType.DoesNotExist:
        print("Error: Alumni account type not found")
        return
    
    # Update the existing alumni account
    try:
        user = User.objects.get(acc_username="1337565")
        user.account_type = alumni_account_type
        user.save()
        print(f"Successfully updated account {user.acc_username} to use alumni account type")
    except User.DoesNotExist:
        print("Error: User with CTU ID 1337565 not found")

if __name__ == "__main__":
    update_alumni_account_type() 