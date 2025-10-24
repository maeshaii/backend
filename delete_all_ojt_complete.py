import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, OJTImport, OJTCompanyProfile

def delete_all_ojt_data():
    """Completely delete all OJT-related data"""
    try:
        print("=" * 60)
        print("DELETING ALL OJT DATA")
        print("=" * 60)
        
        # 1. Delete OJT Company Profiles
        print("\n1. Deleting OJT Company Profiles...")
        company_count = OJTCompanyProfile.objects.count()
        if company_count > 0:
            OJTCompanyProfile.objects.all().delete()
            print(f"   ✅ Deleted {company_count} company profiles")
        else:
            print("   ℹ️  No company profiles found")
        
        # 2. Delete OJT Users
        print("\n2. Deleting OJT Users...")
        ojt_users = User.objects.filter(account_type__ojt=True)
        user_count = ojt_users.count()
        
        if user_count > 0:
            for user in ojt_users:
                try:
                    print(f"   Deleting: {user.f_name} {user.l_name} (ID: {user.user_id})")
                    # Delete related data first
                    if hasattr(user, 'ojt_info'):
                        user.ojt_info.delete()
                    if hasattr(user, 'academic_info'):
                        user.academic_info.delete()
                    if hasattr(user, 'profile'):
                        user.profile.delete()
                    # Delete user
                    user.delete()
                except Exception as e:
                    print(f"   ⚠️  Error deleting user {user.user_id}: {e}")
            print(f"   ✅ Deleted {user_count} OJT users")
        else:
            print("   ℹ️  No OJT users found")
        
        # 3. Delete OJT Import Records
        print("\n3. Deleting OJT Import Records...")
        import_count = OJTImport.objects.count()
        if import_count > 0:
            OJTImport.objects.all().delete()
            print(f"   ✅ Deleted {import_count} import records")
        else:
            print("   ℹ️  No import records found")
        
        # 4. Verify deletion
        print("\n" + "=" * 60)
        print("VERIFICATION")
        print("=" * 60)
        print(f"Remaining OJT Users: {User.objects.filter(account_type__ojt=True).count()}")
        print(f"Remaining Company Profiles: {OJTCompanyProfile.objects.count()}")
        print(f"Remaining Import Records: {OJTImport.objects.count()}")
        print("=" * 60)
        print("\n✅ ALL OJT DATA HAS BEEN COMPLETELY DELETED!")
        print("You can now refresh the Statistics page - it should show 0.")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    delete_all_ojt_data()

