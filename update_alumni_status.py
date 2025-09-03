import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, AccountType

# Get the alumni account type(s)
alumni_account_types = AccountType.objects.filter(user=True)

# Update alumni with user_status 'active' or 'Absorb' to 'Unemployed'
updated = User.objects.filter(account_type__in=alumni_account_types, user_status__in=['active', 'Absorb']).update(user_status='Unemployed')
print(f"Updated {updated} alumni records from 'active' or 'Absorb' to 'Unemployed'.") 