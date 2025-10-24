import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, OJTInfo, OJTCompanyProfile, OJTImport
from django.db import connection

def force_delete_all_ojt():
    """Force delete all OJT data using direct SQL where needed"""
    try:
        print("=" * 60)
        print("FORCE DELETING ALL OJT DATA")
        print("=" * 60)
        
        # Get all OJT user IDs
        ojt_user_ids = list(User.objects.filter(account_type__ojt=True).values_list('user_id', flat=True))
        print(f"\nFound {len(ojt_user_ids)} OJT users to delete: {ojt_user_ids}")
        
        if ojt_user_ids:
            with connection.cursor() as cursor:
                # Delete related data first
                print("\n1. Deleting OJT Company Profiles...")
                cursor.execute("DELETE FROM shared_ojtcompanyprofile WHERE user_id IN %s", [tuple(ojt_user_ids)])
                print(f"   ✅ Deleted company profiles")
                
                print("\n2. Deleting OJT Info...")
                cursor.execute("DELETE FROM shared_ojtinfo WHERE user_id IN %s", [tuple(ojt_user_ids)])
                print(f"   ✅ Deleted OJT info records")
                
                print("\n3. Deleting Academic Info...")
                cursor.execute("DELETE FROM shared_academicinfo WHERE user_id IN %s", [tuple(ojt_user_ids)])
                print(f"   ✅ Deleted academic info")
                
                print("\n4. Deleting User Profiles...")
                cursor.execute("DELETE FROM shared_userprofile WHERE user_id IN %s", [tuple(ojt_user_ids)])
                print(f"   ✅ Deleted user profiles")
                
                print("\n5. Deleting Account Types...")
                cursor.execute("DELETE FROM shared_accounttype WHERE user_id IN %s", [tuple(ojt_user_ids)])
                print(f"   ✅ Deleted account types")
                
                print("\n6. Deleting Users...")
                cursor.execute("DELETE FROM shared_user WHERE user_id IN %s", [tuple(ojt_user_ids)])
                print(f"   ✅ Deleted {len(ojt_user_ids)} users")
        
        # Delete OJT Import records
        print("\n7. Deleting OJT Import Records...")
        OJTImport.objects.all().delete()
        print(f"   ✅ Deleted all import records")
        
        # Verify
        print("\n" + "=" * 60)
        print("VERIFICATION")
        print("=" * 60)
        print(f"Remaining OJT Users: {User.objects.filter(account_type__ojt=True).count()}")
        print(f"Remaining Company Profiles: {OJTCompanyProfile.objects.count()}")
        print(f"Remaining OJT Info: {OJTInfo.objects.count()}")
        print(f"Remaining Import Records: {OJTImport.objects.count()}")
        print("=" * 60)
        print("\n✅ ALL OJT DATA COMPLETELY DELETED!")
        print("Refresh your Statistics page now - it should show 0!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    force_delete_all_ojt()

