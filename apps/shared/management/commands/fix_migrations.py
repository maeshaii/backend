from django.core.management.base import BaseCommand
from django.db.migrations.recorder import MigrationRecorder
from django.utils import timezone
from datetime import datetime


class Command(BaseCommand):
    help = 'Fix migration dependency issues by manually updating migration history'

    def handle(self, *args, **options):
        recorder = MigrationRecorder(connection=None)
        
        # Check current migration state using ORM
        current_migrations = recorder.migration_qs.filter(app='shared').order_by('id').values_list('app', 'name')
        
        self.stdout.write("Current migrations in database:")
        for app, name in current_migrations:
            self.stdout.write(f"  {app}: {name}")
        
        # Check if the problematic migration exists
        exists = recorder.migration_qs.filter(
            app='shared', 
            name='0031_merge_20250809_1357'
        ).exists()
        
        if not exists:
            # Insert the missing migration using ORM
            self.stdout.write("Inserting missing migration 0031_merge_20250809_1357...")
            recorder.record_applied('shared', '0031_merge_20250809_1357')
            self.stdout.write(self.style.SUCCESS("Successfully inserted migration 0031_merge_20250809_1357"))
        else:
            self.stdout.write("Migration 0031_merge_20250809_1357 already exists")
        
        # Check for other missing migrations
        missing_migrations = [
            '0033_merge_20250810_1232',
            '0029_user_ojt_end_date_alter_post_post_image_and_more',
            '0035_ensure_ojt_end_date_column'
        ]
        
        for migration_name in missing_migrations:
            exists = recorder.migration_qs.filter(app='shared', name=migration_name).exists()
            
            if not exists:
                self.stdout.write(f"Inserting missing migration {migration_name}...")
                recorder.record_applied('shared', migration_name)
                self.stdout.write(self.style.SUCCESS(f"Successfully inserted migration {migration_name}"))
            else:
                self.stdout.write(f"Migration {migration_name} already exists")
        
        # Fix the specific dependency issue - add the missing 0034 migration
        exists = recorder.migration_qs.filter(
            app='shared',
            name='0034_merge_0003_add_ojt_end_date_0033_merge_20250810_1232'
        ).exists()
        
        if not exists:
            self.stdout.write("Inserting missing migration 0034_merge_0003_add_ojt_end_date_0033_merge_20250810_1232...")
            recorder.record_applied('shared', '0034_merge_0003_add_ojt_end_date_0033_merge_20250810_1232')
            self.stdout.write(self.style.SUCCESS("Successfully inserted migration 0034_merge_0003_add_ojt_end_date_0033_merge_20250810_1232"))
        else:
            self.stdout.write("Migration 0034_merge_0003_add_ojt_end_date_0033_merge_20250810_1232 already exists")
        
        self.stdout.write(self.style.SUCCESS("Migration history has been fixed!"))
