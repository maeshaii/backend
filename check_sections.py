#!/usr/bin/env python
import os
import sys
import django

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User

# Check users for 2025
users = User.objects.filter(academic_info__year_graduated=2025)
print(f'Total users for 2025: {users.count()}')
print('\nUser details:')
for user in users:
    section = getattr(user.academic_info, 'section', 'None') if user.academic_info else 'None'
    print(f'{user.acc_username}: {user.f_name} {user.l_name} - Section: {section}')

# Check specifically for section 4-T
users_4t = User.objects.filter(
    academic_info__year_graduated=2025,
    academic_info__section__iexact='4-T'
)
print(f'\nUsers in section 4-T: {users_4t.count()}')
for user in users_4t:
    print(f'{user.acc_username}: {user.f_name} {user.l_name}')
