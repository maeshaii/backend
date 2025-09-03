import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User

user = User.objects.filter(acc_username='1337512').first()
if user:
    print(f"CTU ID 1337512 exists: {user.f_name} {user.l_name}, Status: {user.user_status}, Account Type: user={user.account_type.user}")
else:
    print("CTU ID 1337512 does NOT exist in the database.") 