#!/usr/bin/env python
import os
import sys
import django

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, OJTInfo, AcademicInfo

def check_ojt_data():
    print('=== OJT Data Analysis ===')
    
    # Check total users
    total_users = User.objects.count()
    print(f'Total users in database: {total_users}')
    
    # Check OJT users
    ojt_users = User.objects.filter(account_type__ojt=True)
    print(f'OJT users: {ojt_users.count()}')
    
    # Check users with academic info
    users_with_academic = User.objects.filter(academic_info__isnull=False)
    print(f'Users with academic info: {users_with_academic.count()}')
    
    # Check users with OJT info
    users_with_ojt_info = User.objects.filter(ojt_info__isnull=False)
    print(f'Users with OJT info: {users_with_ojt_info.count()}')
    
    # Check Class of 2024 specifically
    class_2024 = User.objects.filter(academic_info__year_graduated=2024)
    print(f'Class of 2024 users: {class_2024.count()}')
    
    # Check OJT users in Class of 2024
    ojt_2024 = User.objects.filter(account_type__ojt=True, academic_info__year_graduated=2024)
    print(f'OJT users in Class of 2024: {ojt_2024.count()}')
    
    # Show some sample data
    if ojt_2024.exists():
        print('\nSample OJT 2024 users:')
        for user in ojt_2024[:3]:
            academic = getattr(user, 'academic_info', None)
            ojt_info = getattr(user, 'ojt_info', None)
            print(f'  User: {user.f_name} {user.l_name}')
            print(f'    Year: {getattr(academic, "year_graduated", "None")}')
            print(f'    Section: {getattr(academic, "section", "None")}')
            print(f'    OJT Status: {getattr(ojt_info, "ojtstatus", "None")}')
    
    # Check all years with OJT users
    print('\nOJT users by year:')
    ojt_users_with_year = User.objects.filter(account_type__ojt=True, academic_info__isnull=False)
    years = {}
    for user in ojt_users_with_year:
        year = getattr(user.academic_info, 'year_graduated', None)
        if year:
            years[year] = years.get(year, 0) + 1
    
    for year, count in sorted(years.items()):
        print(f'  {year}: {count} OJT users')

if __name__ == '__main__':
    check_ojt_data()



