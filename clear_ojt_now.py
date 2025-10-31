import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.db import transaction
from apps.shared.models import (
    User, OJTImport, OJTInfo, AcademicInfo, OJTCompanyProfile,
    UserProfile, EmploymentHistory, UserInitialPassword, SendDate
)

print("\n🗑️  Clearing all OJT data...")

ojt_users = User.objects.filter(account_type__ojt=True)
user_count = ojt_users.count()

if user_count == 0:
    print("✅ No OJT data found. Database is already clean.")
else:
    print(f"📊 Found {user_count} OJT users to delete")
    
    with transaction.atomic():
        ojt_info_count = OJTInfo.objects.filter(user__in=ojt_users).delete()[0]
        ojt_company_count = OJTCompanyProfile.objects.filter(user__in=ojt_users).delete()[0]
        academic_count = AcademicInfo.objects.filter(user__in=ojt_users).delete()[0]
        profile_count = UserProfile.objects.filter(user__in=ojt_users).delete()[0]
        employment_count = EmploymentHistory.objects.filter(user__in=ojt_users).delete()[0]
        password_count = UserInitialPassword.objects.filter(user__in=ojt_users).delete()[0]
        ojt_users.delete()
        import_count = OJTImport.objects.all().delete()[0]
        send_date_count = SendDate.objects.all().delete()[0]
        
        print(f"\n✅ Successfully deleted:")
        print(f"   - {user_count} OJT users")
        print(f"   - {ojt_info_count} OJT info records")
        print(f"   - {ojt_company_count} company profiles")
        print(f"   - {academic_count} academic records")
        print(f"   - {profile_count} user profiles")
        print(f"   - {employment_count} employment records")
        print(f"   - {password_count} passwords")
        print(f"   - {import_count} import records")
        print(f"   - {send_date_count} send date schedules")
        print(f"\n✅ All OJT data cleared successfully!\n")

