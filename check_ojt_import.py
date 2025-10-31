import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, OJTInfo, OJTImport, AcademicInfo

print("\n" + "="*70)
print("📊 OJT DATA CHECK")
print("="*70)

# Check OJT users
ojt_users = User.objects.filter(account_type__ojt=True)
print(f"\n✅ Total OJT users: {ojt_users.count()}")

# Check OJT info
ojt_info_count = OJTInfo.objects.all().count()
print(f"✅ Total OJT info records: {ojt_info_count}")

# Check import records
import_records = OJTImport.objects.all()
print(f"✅ Total import records: {import_records.count()}")

if import_records.exists():
    print("\n📋 Import History:")
    for record in import_records:
        print(f"   - Batch {record.batch_year}, Course: {record.course}, Section: {record.section}")
        print(f"     Records: {record.records_imported}, Status: {record.status}")

# Check academic info
if ojt_users.exists():
    print("\n👥 Sample OJT Users:")
    for user in ojt_users[:5]:
        academic = AcademicInfo.objects.filter(user=user).first()
        ojt = OJTInfo.objects.filter(user=user).first()
        print(f"   - {user.acc_username}: {user.full_name}")
        if academic:
            print(f"     Year: {academic.year_graduated}, Course: {academic.course}")
        if ojt:
            print(f"     Status: {ojt.ojtstatus}, Company: {ojt.company_name}")
else:
    print("\n❌ No OJT users found!")
    print("\nPossible reasons:")
    print("   1. Import failed silently")
    print("   2. Wrong account type assigned")
    print("   3. Data was cleared after import")

print("\n" + "="*70 + "\n")

