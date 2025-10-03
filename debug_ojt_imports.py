#!/usr/bin/env python
import os
import sys
import django

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import OJTImport
from apps.shared.models import User

print("=== OJTImport Records ===")
imports = OJTImport.objects.all()
print(f"Total OJTImport records: {imports.count()}")
for imp in imports:
    print(f"Year: {imp.batch_year}, Status: {imp.status}, Course: {imp.course}, Records: {imp.records_imported}")

print("\n=== OJT Users by Year ===")
users_qs = User.objects.filter(account_type__ojt=True).select_related('academic_info')
years_to_counts = {}
for u in users_qs:
    try:
        year = getattr(u.academic_info, 'year_graduated', None)
        if year is None:
            continue
        years_to_counts[year] = years_to_counts.get(year, 0) + 1
    except Exception:
        continue

print(f"OJT Users by year: {years_to_counts}")

print("\n=== Testing OJT Statistics Logic ===")
# Simulate the ojt_statistics_view logic
years_to_counts = {}
for u in users_qs:
    try:
        year = getattr(u.academic_info, 'year_graduated', None)
        if year is None:
            continue
        years_to_counts[year] = years_to_counts.get(year, 0) + 1
    except Exception:
        continue

# Add OJTImport data
for imp in OJTImport.objects.all():
    y = getattr(imp, 'batch_year', None)
    if y is None:
        continue
    import_count = max(int(getattr(imp, 'records_imported', 0) or 1), 1)
    if y in years_to_counts:
        years_to_counts[y] = max(years_to_counts[y], import_count)
    else:
        years_to_counts[y] = import_count

print(f"Final years_to_counts: {years_to_counts}")
