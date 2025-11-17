from django.core.management.base import BaseCommand
from apps.shared.points_milestones import reset_daily_task_progress
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Reset daily engagement task progress for all users (resets counts and milestone completions, keeps points)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be reset without actually doing it',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made"))
            # In dry run, we could show stats, but for simplicity, just show message
            self.stdout.write("Would reset:")
            self.stdout.write("  - like_count, comment_count, share_count, reply_count, post_count, post_with_photo_count")
            self.stdout.write("  - Delete milestone task completions")
            self.stdout.write("  - Keep all points intact")
            return
        
        try:
            self.stdout.write("🔄 Resetting daily task progress...")
            result = reset_daily_task_progress()
            
            self.stdout.write(self.style.SUCCESS(
                f"✅ Successfully reset daily task progress!"
            ))
            self.stdout.write(f"   Users reset: {result.get('users_reset', 0)}")
            self.stdout.write(f"   Completions deleted: {result.get('completions_deleted', 0)}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error resetting daily task progress: {e}"))
            logger.error(f"Error in reset_daily_task_progress command: {e}", exc_info=True)
            raise


