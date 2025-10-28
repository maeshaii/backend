"""
Django management command to adjust user engagement points.

Usage:
    # Deduct 10 points from user with ID 123
    python manage.py adjust_user_points --user-id 123 --deduct 10
    
    # Add 5 points to user with ID 123
    python manage.py adjust_user_points --user-id 123 --add 5
    
    # Set user points to exactly 20
    python manage.py adjust_user_points --user-id 123 --set 20
    
    # Use username instead of user ID
    python manage.py adjust_user_points --username "ella.delrosario" --deduct 10
"""

from django.core.management.base import BaseCommand, CommandError
from apps.shared.models import User, UserPoints


class Command(BaseCommand):
    help = 'Adjust user engagement points (add, deduct, or set specific value)'

    def add_arguments(self, parser):
        # User identification
        parser.add_argument(
            '--user-id',
            type=int,
            help='User ID to adjust points for'
        )
        parser.add_argument(
            '--username',
            type=str,
            help='Username (acc_username) to adjust points for'
        )
        
        # Point adjustment actions (mutually exclusive)
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            '--add',
            type=int,
            help='Number of points to add'
        )
        group.add_argument(
            '--deduct',
            type=int,
            help='Number of points to deduct'
        )
        group.add_argument(
            '--set',
            type=int,
            help='Set points to this exact value'
        )
        
        parser.add_argument(
            '--reason',
            type=str,
            default='Manual adjustment by admin',
            help='Reason for adjustment (for logging)'
        )

    def handle(self, *args, **options):
        # Get user
        user = None
        if options['user_id']:
            try:
                user = User.objects.get(user_id=options['user_id'])
            except User.DoesNotExist:
                raise CommandError(f"User with ID {options['user_id']} does not exist")
        elif options['username']:
            try:
                user = User.objects.get(acc_username=options['username'])
            except User.DoesNotExist:
                raise CommandError(f"User with username '{options['username']}' does not exist")
        else:
            raise CommandError("Either --user-id or --username must be provided")
        
        # Get or create user points
        user_points, created = UserPoints.objects.get_or_create(user=user)
        
        old_points = user_points.total_points
        reason = options['reason']
        
        # Perform the adjustment
        if options['add'] is not None:
            points_to_add = options['add']
            user_points.total_points += points_to_add
            user_points.save()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Added {points_to_add} points to {user.full_name}\n"
                    f"  Old points: {old_points}\n"
                    f"  New points: {user_points.total_points}\n"
                    f"  Reason: {reason}"
                )
            )
            
        elif options['deduct'] is not None:
            points_to_deduct = options['deduct']
            user_points.total_points -= points_to_deduct
            # Don't allow negative points
            if user_points.total_points < 0:
                user_points.total_points = 0
            user_points.save()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Deducted {points_to_deduct} points from {user.full_name}\n"
                    f"  Old points: {old_points}\n"
                    f"  New points: {user_points.total_points}\n"
                    f"  Reason: {reason}"
                )
            )
            
        elif options['set'] is not None:
            new_points = options['set']
            if new_points < 0:
                raise CommandError("Points cannot be negative")
            
            user_points.total_points = new_points
            user_points.save()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Set points for {user.full_name} to {new_points}\n"
                    f"  Old points: {old_points}\n"
                    f"  New points: {user_points.total_points}\n"
                    f"  Reason: {reason}"
                )
            )
        
        # Log the adjustment
        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            f"Points adjustment: User={user.full_name} (ID={user.user_id}), "
            f"Old={old_points}, New={user_points.total_points}, Reason={reason}"
        )

