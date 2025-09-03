import os
import django
from datetime import datetime, date
import random

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, AccountType

# Get or create alumni account type
alumni_type, _ = AccountType.objects.get_or_create(user=True, defaults={
    'admin': False, 'peso': False, 'coordinator': False
})

# Remove any existing 2025 alumni for a clean test
to_delete = User.objects.filter(year_graduated=2025)
to_delete.delete()

# Add 5 alumni for batch 2025 with all fields filled
alumni_data = [
    {
        'acc_username': '2025A001', 'acc_password': date(2025, 1, 1), 'user_status': 'employed',
        'f_name': 'Alice', 'm_name': 'B.', 'l_name': 'Cruz', 'gender': 'F', 'phone_num': '09171234567',
        'address': 'Cebu City', 'profile_pic': '', 'profile_bio': 'Bio 1', 'profile_resume': '',
        'year_graduated': 2025, 'course': 'BSIT', 'section': 'A', 'civil_status': 'Single',
        'social_media': 'alice_fb', 'birthdate': date(2003, 5, 10), 'age': 22, 'email': 'alice@alumni.com',
        'program': 'BSIT', 'status': 'Active', 'company_name_current': 'TechCorp', 'position_current': 'Developer',
        'sector_current': 'Private', 'employment_duration_current': '2 years', 'salary_current': '35000',
        'supporting_document_current': '', 'awards_recognition_current': 'Best Intern',
        'supporting_document_awards_recognition': '', 'unemployment_reason': '', 'pursue_further_study': 'no',
        'date_started': date(2025, 6, 1), 'school_name': '', 'account_type': alumni_type
    },
    {
        'acc_username': '2025A002', 'acc_password': date(2025, 1, 1), 'user_status': 'unemployed',
        'f_name': 'Bob', 'm_name': 'D.', 'l_name': 'Reyes', 'gender': 'M', 'phone_num': '09181234567',
        'address': 'Mandaue City', 'profile_pic': '', 'profile_bio': 'Bio 2', 'profile_resume': '',
        'year_graduated': 2025, 'course': 'BSIT', 'section': 'B', 'civil_status': 'Married',
        'social_media': 'bob_fb', 'birthdate': date(2002, 8, 15), 'age': 23, 'email': 'bob@alumni.com',
        'program': 'BSIT', 'status': 'Inactive', 'company_name_current': '', 'position_current': '',
        'sector_current': '', 'employment_duration_current': '', 'salary_current': '',
        'supporting_document_current': '', 'awards_recognition_current': '',
        'supporting_document_awards_recognition': '', 'unemployment_reason': 'Further Study', 'pursue_further_study': 'yes',
        'date_started': None, 'school_name': 'UP Cebu', 'account_type': alumni_type
    },
    {
        'acc_username': '2025A003', 'acc_password': date(2025, 1, 1), 'user_status': 'high position',
        'f_name': 'Carla', 'm_name': 'E.', 'l_name': 'Santos', 'gender': 'F', 'phone_num': '09191234567',
        'address': 'Lapu-Lapu City', 'profile_pic': '', 'profile_bio': 'Bio 3', 'profile_resume': '',
        'year_graduated': 2025, 'course': 'BSIT', 'section': 'C', 'civil_status': 'Single',
        'social_media': 'carla_fb', 'birthdate': date(2001, 12, 20), 'age': 24, 'email': 'carla@alumni.com',
        'program': 'BSIT Graduate', 'status': 'Active', 'company_name_current': 'BizInc', 'position_current': 'Manager',
        'sector_current': 'Government', 'employment_duration_current': '3 years', 'salary_current': '50000',
        'supporting_document_current': '', 'awards_recognition_current': 'Leadership Award',
        'supporting_document_awards_recognition': '', 'unemployment_reason': '', 'pursue_further_study': 'no',
        'date_started': date(2025, 7, 1), 'school_name': '', 'account_type': alumni_type
    },
    {
        'acc_username': '2025A004', 'acc_password': date(2025, 1, 1), 'user_status': 'absorb',
        'f_name': 'Dan', 'm_name': 'F.', 'l_name': 'Lim', 'gender': 'M', 'phone_num': '09201234567',
        'address': 'Talisay City', 'profile_pic': '', 'profile_bio': 'Bio 4', 'profile_resume': '',
        'year_graduated': 2025, 'course': 'BSIT', 'section': 'D', 'civil_status': 'Single',
        'social_media': 'dan_fb', 'birthdate': date(2003, 2, 28), 'age': 22, 'email': 'dan@alumni.com',
        'program': 'BSIT', 'status': 'Active', 'company_name_current': 'MegaSoft', 'position_current': 'Analyst',
        'sector_current': 'Private', 'employment_duration_current': '1 year', 'salary_current': '28000',
        'supporting_document_current': '', 'awards_recognition_current': 'Top Performer',
        'supporting_document_awards_recognition': '', 'unemployment_reason': '', 'pursue_further_study': 'no',
        'date_started': date(2025, 8, 1), 'school_name': '', 'account_type': alumni_type
    },
    {
        'acc_username': '2025A005', 'acc_password': date(2025, 1, 1), 'user_status': 'employed',
        'f_name': 'Ella', 'm_name': 'G.', 'l_name': 'Torres', 'gender': 'F', 'phone_num': '09211234567',
        'address': 'Consolacion', 'profile_pic': '', 'profile_bio': 'Bio 5', 'profile_resume': '',
        'year_graduated': 2025, 'course': 'BSIT', 'section': 'E', 'civil_status': 'Married',
        'social_media': 'ella_fb', 'birthdate': date(2002, 11, 5), 'age': 23, 'email': 'ella@alumni.com',
        'program': 'BSIT', 'status': 'Active', 'company_name_current': 'TechCorp', 'position_current': 'QA Engineer',
        'sector_current': 'Private', 'employment_duration_current': '2 years', 'salary_current': '32000',
        'supporting_document_current': '', 'awards_recognition_current': 'Best QA',
        'supporting_document_awards_recognition': '', 'unemployment_reason': '', 'pursue_further_study': 'yes',
        'date_started': date(2025, 9, 1), 'school_name': 'USC', 'account_type': alumni_type
    },
]

for alum in alumni_data:
    User.objects.create(**alum)

print('Sample alumni for batch 2025 created successfully.') 