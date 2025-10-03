#!/usr/bin/env python
"""
Check Data Script
This script checks what data exists in both OJTImport and User models.
"""
import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import OJTImport
from apps.users.models import User

def check_data():
    """Check what data exists in both models"""
    print("🔍 Checking data in both models...")
    
    # Check OJTImport records
    print("\n📊 OJTImport records:")
    ojt_imports = OJTImport.objects.all()
    print(f"Total count: {ojt_imports.count()}")
    for record in ojt_imports:
        print(f"  - Year: {record.batch_year}, Course: {record.course}, Status: {record.status}")
    
    # Check User records by graduation year
    print("\n👥 User records by graduation year:")
    for year in [2023, 2024]:
        users = User.objects.filter(academic_info__year_graduated=year)
        print(f"  Year {year}: {users.count()} users")
        for user in users[:3]:  # Show first 3 users
            print(f"    - {user.f_name} {user.l_name} (ID: {user.id})")
        if users.count() > 3:
            print(f"    ... and {users.count() - 3} more")

if __name__ == "__main__":
    check_data()



