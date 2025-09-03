from django.core.management.base import BaseCommand
from django.db import transaction
from apps.shared.models import User, AccountType


class Command(BaseCommand):
    help = "Create or update an admin AccountType and admin user with a specific password"

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, default='admin', help='Admin username (CTU ID)')
        parser.add_argument('--password', type=str, default='wherenayou2025', help='Admin password')
        parser.add_argument('--first-name', type=str, default='Admin')
        parser.add_argument('--last-name', type=str, default='User')

    @transaction.atomic
    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        first_name = options['first_name']
        last_name = options['last_name']

        # Ensure admin AccountType exists and is exclusive
        admin_type, _ = AccountType.objects.get_or_create(
            admin=True, defaults={'peso': False, 'user': False, 'coordinator': False, 'ojt': False}
        )

        # Create or update the user
        user, created = User.objects.get_or_create(
            acc_username=username,
            defaults={
                'f_name': first_name,
                'l_name': last_name,
                'gender': 'N/A',
                'user_status': 'active',
                'account_type': admin_type,
            }
        )
        # Set or reset password
        user.account_type = admin_type
        user.set_password(password)
        user.save()

        self.stdout.write(self.style.SUCCESS(
            f"Admin user {'created' if created else 'updated'}: {username}"
        ))
