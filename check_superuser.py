import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

try:
    from django.contrib.auth import get_user_model
    User = get_user_model()
    superusers = User.objects.filter(is_superuser=True)
    if superusers.exists():
        print(f"Superuser(s) found:")
        for su in superusers:
            print(f"  Username: {su.username if hasattr(su, 'username') else su.acc_username}, Email: {su.email if hasattr(su, 'email') else ''}")
    else:
        print("No superuser exists in the database.")
except Exception as e:
    print(f"Error checking superuser: {e}") 