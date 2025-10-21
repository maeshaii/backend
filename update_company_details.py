#!/usr/bin/env python
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import EmploymentHistory, User

# Update the company details for user 1005 (Christine Lopez)
try:
    user = User.objects.get(acc_username='1005')
    employment, created = EmploymentHistory.objects.get_or_create(user=user)
    
    # Update with sample company details
    employment.company_address = "Banilad, Cebu City"
    employment.company_email = "admin@brightminds.com"
    employment.company_contact = "(032) 678-1234"
    employment.contact_person = "Joan Uy"
    employment.position = "Intern"
    employment.save()
    
    print(f"✅ Updated company details for {user.f_name} {user.l_name}:")
    print(f"   Company Address: {employment.company_address}")
    print(f"   Company Email: {employment.company_email}")
    print(f"   Company Contact: {employment.company_contact}")
    print(f"   Contact Person: {employment.contact_person}")
    print(f"   Position: {employment.position}")
    
except Exception as e:
    print(f"❌ Error: {e}")














