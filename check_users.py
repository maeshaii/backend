import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User

def main():
    print("=== LISTING ALL ALUMNI USERS ===")
    users = User.objects.filter(account_type__user=True)
    print(f"Found {users.count()} alumni users:")
    print("-" * 50)
    for user in users:
        print(f"User ID: {user.user_id}")
        print(f"Name: {user.f_name} {user.l_name}")
        print(f"Course: {user.course}")
        print(f"Email: {user.email}")
        print("-" * 50)

if __name__ == '__main__':
    main() 