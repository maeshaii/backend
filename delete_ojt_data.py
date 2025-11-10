import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.db import transaction
from django.db.models import Q
from apps.shared.models import (
    User, OJTImport, OJTInfo, AcademicInfo, OJTCompanyProfile,
    UserProfile, EmploymentHistory, UserInitialPassword, SendDate
)

print("\n🗑️  Deleting all OJT data...")

# Get all OJT users
ojt_users = User.objects.filter(account_type__ojt=True)
user_count = ojt_users.count()

if user_count == 0:
    print("✅ No OJT users found with account_type__ojt=True")
else:
    print(f"📊 Found {user_count} OJT users to delete")

# Also check for users with OJT-related data but without the flag
ojt_info_users = User.objects.filter(ojt_info__isnull=False).distinct()
orphaned_count = ojt_info_users.exclude(account_type__ojt=True).count()

if orphaned_count > 0:
    print(f"📊 Found {orphaned_count} users with OJT data but without OJT flag")

try:
    with transaction.atomic():
        # Delete all related data first
        print("\nDeleting related records...")
        
        # Get all users that have OJT data (including orphaned ones)
        all_ojt_users = User.objects.filter(
            Q(account_type__ojt=True) | 
            Q(ojt_info__isnull=False)
        ).distinct()
        
        ojt_info_count = OJTInfo.objects.filter(user__in=all_ojt_users).delete()[0]
        print(f"   ✓ Deleted {ojt_info_count} OJT info records")
        
        ojt_company_count = OJTCompanyProfile.objects.filter(user__in=all_ojt_users).delete()[0]
        print(f"   ✓ Deleted {ojt_company_count} company profiles")
        
        academic_count = AcademicInfo.objects.filter(user__in=all_ojt_users).delete()[0]
        print(f"   ✓ Deleted {academic_count} academic records")
        
        profile_count = UserProfile.objects.filter(user__in=all_ojt_users).delete()[0]
        print(f"   ✓ Deleted {profile_count} user profiles")
        
        employment_count = EmploymentHistory.objects.filter(user__in=all_ojt_users).delete()[0]
        print(f"   ✓ Deleted {employment_count} employment records")
        
        password_count = UserInitialPassword.objects.filter(user__in=all_ojt_users).delete()[0]
        print(f"   ✓ Deleted {password_count} initial passwords")
        
        # Delete OJT users using raw SQL to bypass ORM cascade issues
        from django.db import connection
        with connection.cursor() as cursor:
            user_ids = list(ojt_users.values_list('user_id', flat=True))
            if user_ids:
                placeholders = ','.join(['%s'] * len(user_ids))
                cursor.execute(f"DELETE FROM shared_user WHERE user_id IN ({placeholders})", user_ids)
                deleted_users = cursor.rowcount
                print(f"   ✓ Deleted {deleted_users} OJT users (via raw SQL)")
            else:
                deleted_users = 0
        
        # Delete orphaned users (those with OJT data but no flag)
        deleted_orphaned = 0
        if orphaned_count > 0:
            orphaned_users = ojt_info_users.exclude(account_type__ojt=True)
            orphaned_user_ids = list(orphaned_users.values_list('user_id', flat=True))
            if orphaned_user_ids:
                with connection.cursor() as cursor:
                    placeholders = ','.join(['%s'] * len(orphaned_user_ids))
                    cursor.execute(f"DELETE FROM shared_user WHERE user_id IN ({placeholders})", orphaned_user_ids)
                    deleted_orphaned = cursor.rowcount
                    print(f"   ✓ Deleted {deleted_orphaned} orphaned users (via raw SQL)")
        
        # Remove import history
        import_count = OJTImport.objects.all().delete()[0]
        print(f"   ✓ Deleted {import_count} import records")
        
        # Clear all scheduled send dates
        send_date_count = SendDate.objects.all().delete()[0]
        print(f"   ✓ Deleted {send_date_count} send date schedules")
    
    print("\n✅ Successfully deleted all OJT data!")
    print(f"   - {deleted_users} OJT users")
    if deleted_orphaned > 0:
        print(f"   - {deleted_orphaned} orphaned users")
    print(f"   - {ojt_info_count} OJT info records")
    print(f"   - {ojt_company_count} company profiles")
    print(f"   - {academic_count} academic records")
    print(f"   - {profile_count} user profiles")
    print(f"   - {employment_count} employment records")
    print(f"   - {password_count} passwords")
    print(f"   - {import_count} import records")
    print(f"   - {send_date_count} send date schedules")
    print("\n✅ Database is now clean. You can re-import OJT data.\n")
    
except Exception as e:
    print(f"\n❌ ERROR: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

