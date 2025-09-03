from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Fix migration dependency issues by manually updating migration history'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            # Check current migration state
            cursor.execute("SELECT app, name FROM django_migrations WHERE app = 'shared' ORDER BY id")
            current_migrations = cursor.fetchall()
            
            self.stdout.write("Current migrations in database:")
            for app, name in current_migrations:
                self.stdout.write(f"  {app}: {name}")
            
            # Check if the problematic migration exists
            cursor.execute("SELECT COUNT(*) FROM django_migrations WHERE app = 'shared' AND name = '0031_merge_20250809_1357'")
            exists = cursor.fetchone()[0]
            
            if exists == 0:
                # Insert the missing migration
                self.stdout.write("Inserting missing migration 0031_merge_20250809_1357...")
                cursor.execute(
                    "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, %s)",
                    ['shared', '0031_merge_20250809_1357', '2025-08-09 13:57:00']
                )
                self.stdout.write(self.style.SUCCESS("Successfully inserted migration 0031_merge_20250809_1357"))
            else:
                self.stdout.write("Migration 0031_merge_20250809_1357 already exists")
            
            # Check for other missing migrations
            missing_migrations = [
                ('0033_merge_20250810_1232', '2025-08-10 12:32:00'),
                ('0029_user_ojt_end_date_alter_post_post_image_and_more', '2025-08-10 12:32:00'),
                ('0035_ensure_ojt_end_date_column', '2025-08-10 12:35:00')
            ]
            
            for migration_name, applied_date in missing_migrations:
                cursor.execute("SELECT COUNT(*) FROM django_migrations WHERE app = 'shared' AND name = %s", [migration_name])
                exists = cursor.fetchone()[0]
                
                if exists == 0:
                    self.stdout.write(f"Inserting missing migration {migration_name}...")
                    cursor.execute(
                        "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, %s)",
                        ['shared', migration_name, applied_date]
                    )
                    self.stdout.write(self.style.SUCCESS(f"Successfully inserted migration {migration_name}"))
                else:
                    self.stdout.write(f"Migration {migration_name} already exists")
            
            # Fix the specific dependency issue - add the missing 0034 migration
            cursor.execute("SELECT COUNT(*) FROM django_migrations WHERE app = 'shared' AND name = '0034_merge_0003_add_ojt_end_date_0033_merge_20250810_1232'")
            exists = cursor.fetchone()[0]
            
            if exists == 0:
                self.stdout.write("Inserting missing migration 0034_merge_0003_add_ojt_end_date_0033_merge_20250810_1232...")
                cursor.execute(
                    "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, %s)",
                    ['shared', '0034_merge_0003_add_ojt_end_date_0033_merge_20250810_1232', '2025-08-10 12:34:00']
                )
                self.stdout.write(self.style.SUCCESS("Successfully inserted migration 0034_merge_0003_add_ojt_end_date_0033_merge_20250810_1232"))
            else:
                self.stdout.write("Migration 0034_merge_0003_add_ojt_end_date_0033_merge_20250810_1232 already exists")
            
            connection.commit()
            self.stdout.write(self.style.SUCCESS("Migration history has been fixed!"))
