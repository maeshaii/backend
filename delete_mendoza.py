#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, AcademicInfo, OJTInfo, EmploymentHistory, UserProfile, OJTImport
from django.db import transaction

# Delete Carlo Mendoza (CTU ID 1334335)
qs = User.objects.filter(acc_username='1334335') | User.objects.filter(f_name__iexact='Carlo', l_name__iexact='Mendoza')
deleted = 0

with transaction.atomic():
    for u in qs:
        print(f"Deleting user: {u.f_name} {u.l_name} (CTU ID: {u.acc_username})")
        EmploymentHistory.objects.filter(user=u).delete()
        OJTInfo.objects.filter(user=u).delete()
        AcademicInfo.objects.filter(user=u).delete()
        UserProfile.objects.filter(user=u).delete()
        u.delete()
        deleted += 1

print(f'Users deleted: {deleted}')

# Update import record count to 4
imports_updated = OJTImport.objects.filter(batch_year=2023).update(records_imported=4)
print(f'Import records updated: {imports_updated}')

print("Done! Refresh your dashboard to see the changes.")
