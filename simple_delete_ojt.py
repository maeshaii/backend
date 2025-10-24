import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, OJTInfo, OJTCompanyProfile, OJTImport, AcademicInfo, UserProfile, AccountType

def simple_delete_all_ojt():
    """Simple approach - delete using Django ORM with manual cascade"""
    try:
        print("=" * 60)
        print("DELETING ALL OJT DATA (Simple Method)")
        print("=" * 60)
        
        # Get all OJT users
        ojt_users = User.objects.filter(account_type__ojt=True)
        user_count = ojt_users.count()
        print(f"\nFound {user_count} OJT users to delete")
        
        if user_count > 0:
            for user in ojt_users:
                print(f"Deleting user: {user.f_name} {user.l_name} (ID: {user.user_id})")
                
                # Delete related records manually
                try:
                    OJTCompanyProfile.objects.filter(user=user).delete()
                    OJTInfo.objects.filter(user=user).delete()
                    AcademicInfo.objects.filter(user=user).delete()
                    UserProfile.objects.filter(user=user).delete()
                    AccountType.objects.filter(user=user).delete()
                    
                    # Finally delete the user
                    User.objects.filter(user_id=user.user_id).delete()
                    print(f"   ✅ Deleted successfully")
                except Exception as e:
                    print(f"   ⚠️  Error: {e}")
        
        # Delete import records
        print("\nDeleting OJT Import Records...")
        import_count = OJTImport.objects.count()
        OJTImport.objects.all().delete()
        print(f"✅ Deleted {import_count} import records")
        
        # Verify
        print("\n" + "=" * 60)
        print("VERIFICATION")
        print("=" * 60)
        print(f"OJT Users: {User.objects.filter(account_type__ojt=True).count()}")
        print(f"Company Profiles: {OJTCompanyProfile.objects.count()}")
        print(f"Import Records: {OJTImport.objects.count()}")
        print("=" * 60)
        print("\n✅ CLEANUP COMPLETE!")
        print("Refresh your Statistics page - it should now show 0!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    simple_delete_all_ojt()

