"""
Django management command to view user engagement points.

Usage:
    # View specific user by ID
    python manage.py view_user_points --user-id 123
    
    # View specific user by username
    python manage.py view_user_points --username "ella.delrosario"
    
    # View top 10 users
    python manage.py view_user_points --top 10
    
    # Search by name
    python manage.py view_user_points --search "Ella Grace"
"""

from django.core.management.base import BaseCommand, CommandError
from apps.shared.models import User, UserPoints


class Command(BaseCommand):
    help = 'View user engagement points'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            help='View points for specific user ID'
        )
        parser.add_argument(
            '--username',
            type=str,
            help='View points for specific username'
        )
        parser.add_argument(
            '--search',
            type=str,
            help='Search users by name'
        )
        parser.add_argument(
            '--top',
            type=int,
            help='Show top N users by points'
        )

    def handle(self, *args, **options):
        if options['user_id']:
            self.show_user_by_id(options['user_id'])
        elif options['username']:
            self.show_user_by_username(options['username'])
        elif options['search']:
            self.search_users(options['search'])
        elif options['top']:
            self.show_top_users(options['top'])
        else:
            raise CommandError("Please provide --user-id, --username, --search, or --top")

    def show_user_by_id(self, user_id):
        try:
            user = User.objects.get(user_id=user_id)
            self.display_user_points(user)
        except User.DoesNotExist:
            raise CommandError(f"User with ID {user_id} does not exist")

    def show_user_by_username(self, username):
        try:
            user = User.objects.get(acc_username=username)
            self.display_user_points(user)
        except User.DoesNotExist:
            raise CommandError(f"User with username '{username}' does not exist")

    def search_users(self, search_term):
        users = User.objects.filter(
            f_name__icontains=search_term
        ) | User.objects.filter(
            l_name__icontains=search_term
        )
        
        if not users.exists():
            self.stdout.write(self.style.WARNING(f"No users found matching '{search_term}'"))
            return
        
        self.stdout.write(self.style.SUCCESS(f"\nFound {users.count()} user(s) matching '{search_term}':\n"))
        for user in users:
            user_points = UserPoints.objects.filter(user=user).first()
            points = user_points.total_points if user_points else 0
            self.stdout.write(
                f"  • {user.full_name} (ID: {user.user_id}, Username: {user.acc_username or 'N/A'}) - {points} points"
            )

    def show_top_users(self, limit):
        top_users = UserPoints.objects.select_related('user').order_by('-total_points')[:limit]
        
        if not top_users.exists():
            self.stdout.write(self.style.WARNING("No users with points found"))
            return
        
        self.stdout.write(self.style.SUCCESS(f"\nTop {limit} Users by Points:\n"))
        for rank, user_points in enumerate(top_users, start=1):
            user = user_points.user
            self.stdout.write(
                f"  {rank}. {user.full_name} (ID: {user.user_id}) - {user_points.total_points} points"
            )

    def display_user_points(self, user):
        try:
            user_points = UserPoints.objects.get(user=user)
        except UserPoints.DoesNotExist:
            self.stdout.write(
                self.style.WARNING(
                    f"\nUser: {user.full_name} (ID: {user.user_id})\n"
                    f"Username: {user.acc_username or 'N/A'}\n"
                    f"Points: 0 (No points record found)"
                )
            )
            return
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'='*60}\n"
                f"User: {user.full_name}\n"
                f"User ID: {user.user_id}\n"
                f"Username: {user.acc_username or 'N/A'}\n"
                f"{'='*60}\n"
                f"Total Points: {user_points.total_points}\n"
                f"\nPoints Breakdown:\n"
                f"  👍 Likes:           {user_points.points_from_likes:>3} pts ({user_points.like_count} count)\n"
                f"  💬 Comments:        {user_points.points_from_comments:>3} pts ({user_points.comment_count} count)\n"
                f"  🔄 Shares:          {user_points.points_from_shares:>3} pts ({user_points.share_count} count)\n"
                f"  ↩️  Replies:         {user_points.points_from_replies:>3} pts ({user_points.reply_count} count)\n"
                f"  📸 Posts w/ Photos: {user_points.points_from_posts_with_photos:>3} pts ({user_points.post_with_photo_count} count)\n"
                f"  📋 Tracker Forms:   {user_points.points_from_tracker_form:>3} pts ({user_points.tracker_form_count} count)\n"
                f"\nLast Updated: {user_points.updated_at}\n"
                f"{'='*60}\n"
            )
        )

