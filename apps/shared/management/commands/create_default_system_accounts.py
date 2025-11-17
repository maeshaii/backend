from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
from apps.shared.models import User, AccountType


class Command(BaseCommand):
    help = "Create default system accounts: admin and coordinator with specified credentials"

    def add_arguments(self, parser):
        parser.add_argument('--admin-username', type=str, default='admin')
        parser.add_argument('--admin-password', type=str, default='wherenayou2025')
        parser.add_argument('--coord-username', type=str, default=settings.DEFAULT_COORDINATOR_USERNAME)
        parser.add_argument('--coord-password', type=str, default=settings.DEFAULT_COORDINATOR_PASSWORD)

    @transaction.atomic
    def handle(self, *args, **options):
        admin_username = options['admin_username']
        admin_password = options['admin_password']
        coord_username = options['coord_username']
        coord_password = options['coord_password']

        # Admin type and user
        admin_type, _ = AccountType.objects.get_or_create(
            admin=True, defaults={'peso': False, 'user': False, 'coordinator': False, 'ojt': False}
        )
        admin_user, created = User.objects.get_or_create(
            acc_username=admin_username,
            defaults={
                'f_name': 'System',
                'l_name': 'Administrator',
                'gender': 'Other',
                'user_status': 'active',
                'account_type': admin_type,
            }
        )
        # Ensure active and proper role on updates too
        admin_user.account_type = admin_type
        admin_user.user_status = 'active'
        admin_user.set_password(admin_password)
        admin_user.save()
        self.stdout.write(self.style.SUCCESS(
            f"Admin user {'created' if created else 'updated'}: {admin_username}"
        ))

        # Coordinator type and user
        coord_type, _ = AccountType.objects.get_or_create(
            coordinator=True, defaults={'admin': False, 'peso': False, 'user': False, 'ojt': False}
        )
        coord_user, created = User.objects.get_or_create(
            acc_username=coord_username,
            defaults={
                'f_name': 'BSIT',
                'l_name': 'Coordinator',
                'gender': 'Other',
                'user_status': 'active',
                'account_type': coord_type,
            }
        )
        # Ensure active and proper role on updates too
        coord_user.account_type = coord_type
        coord_user.user_status = 'active'
        coord_user.set_password(coord_password)
        coord_user.save()
        self.stdout.write(self.style.SUCCESS(
            f"Coordinator user {'created' if created else 'updated'}: {coord_username}"
        ))


