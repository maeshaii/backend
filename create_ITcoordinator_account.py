#!/usr/bin/env python
import os
import sys
import django

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from django.conf import settings
from apps.shared.models import User, AccountType


def _get_setting(name: str, default: str) -> str:
    """Safely read coordinator credentials from Django settings or env vars."""
    if hasattr(settings, name):
        return getattr(settings, name)
    return os.getenv(name, default)


def create_coordinator_account():
    try:
        # Ensure a coordinator account type exists
        coordinator_account_type, created = AccountType.objects.get_or_create(
            coordinator=True,
            defaults={
                "admin": False,
                "peso": False,
                "user": False,
                "ojt": False,
            },
        )

        if created:
            print("✅ Created new coordinator account type")
        else:
            print("✅ Using existing coordinator account type")

        username = _get_setting("DEFAULT_IT_COORDINATOR_USERNAME", "ITCOORDINATOR")
        existing_user = User.objects.filter(acc_username=username).first()

        if existing_user:
            print("ℹ️ IT coordinator account already exists!")
            print(f"   Username: {username}")
            password = _get_setting("DEFAULT_IT_COORDINATOR_PASSWORD", "ITWHERENAYOU")
            print(f"   Password: {password}")
            print(f"   Status: {existing_user.user_status}")
            print("\n✅ You can login with these credentials.")
            return

        coordinator_password = _get_setting(
            "DEFAULT_IT_COORDINATOR_PASSWORD", "ITWHERENAYOU"
        )
        
        coordinator_user = User.objects.create(
            account_type=coordinator_account_type,
            acc_username=username,
            user_status="active",
            f_name="BSIT",
            l_name="Coordinator",
            gender="N/A",  # keep within max_length=10
        )
        coordinator_user.set_password(coordinator_password)
        coordinator_user.save()

        print("✅ Successfully created IT coordinator account!")
        print(f"   Username: {coordinator_user.acc_username}")
        print(f"   Password: {coordinator_password} (securely hashed)")
        print("   Account Type: Coordinator")
        print(f"   Status: {coordinator_user.user_status}")

    except Exception as e:
        print(f"❌ Error creating IT coordinator account: {e}")


if __name__ == "__main__":
    create_coordinator_account() 