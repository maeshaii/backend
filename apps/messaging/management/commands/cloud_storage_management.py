"""
Django management command for cloud storage management and migration.

Usage:
    python manage.py cloud_storage_management --status
    python manage.py cloud_storage_management --migrate-local-to-s3
    python manage.py cloud_storage_management --cleanup-orphaned
    python manage.py cloud_storage_management --test-upload
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from apps.messaging.cloud_storage import cloud_storage
from apps.shared.models import MessageAttachment
import os


class Command(BaseCommand):
    help = 'Manage cloud storage for file attachments'

    def add_arguments(self, parser):
        parser.add_argument(
            '--status',
            action='store_true',
            help='Show cloud storage status and statistics',
        )
        parser.add_argument(
            '--migrate-local-to-s3',
            action='store_true',
            help='Migrate local files to S3 storage',
        )
        parser.add_argument(
            '--cleanup-orphaned',
            action='store_true',
            help='Clean up orphaned files in storage',
        )
        parser.add_argument(
            '--test-upload',
            action='store_true',
            help='Test file upload to cloud storage',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually doing it',
        )

    def handle(self, *args, **options):
        if options['status']:
            self.handle_status()
        elif options['migrate_local_to_s3']:
            self.handle_migrate_local_to_s3(options['dry_run'])
        elif options['cleanup_orphaned']:
            self.handle_cleanup_orphaned(options['dry_run'])
        elif options['test_upload']:
            self.handle_test_upload()
        else:
            self.stdout.write(
                self.style.ERROR('Please specify an action: --status, --migrate-local-to-s3, --cleanup-orphaned, or --test-upload')
            )

    def handle_status(self):
        """Show cloud storage status and statistics."""
        self.stdout.write('Cloud Storage Status:')
        self.stdout.write('=' * 50)
        
        try:
            # Get storage info
            storage_info = cloud_storage.get_storage_info()
            
            self.stdout.write(f'Storage Type: {storage_info["storage_type"]}')
            self.stdout.write(f'S3 Available: {storage_info["s3_available"]}')
            
            if storage_info['s3_stats']['available']:
                s3_stats = storage_info['s3_stats']
                self.stdout.write(f'S3 Bucket: {s3_stats.get("bucket_name", "N/A")}')
                self.stdout.write(f'S3 Region: {s3_stats.get("region", "N/A")}')
                self.stdout.write(f'CDN Enabled: {s3_stats.get("cdn_enabled", False)}')
                if s3_stats.get("cdn_domain"):
                    self.stdout.write(f'CDN Domain: {s3_stats["cdn_domain"]}')
            else:
                self.stdout.write('S3 Configuration: Not available')
                if 'error' in storage_info['s3_stats']:
                    self.stdout.write(f'S3 Error: {storage_info["s3_stats"]["error"]}')
            
            self.stdout.write('')
            
            # Get attachment statistics
            total_attachments = MessageAttachment.objects.count()
            s3_attachments = MessageAttachment.objects.filter(storage_type='s3').count()
            local_attachments = MessageAttachment.objects.filter(storage_type='local').count()
            
            self.stdout.write('Attachment Statistics:')
            self.stdout.write(f'  Total Attachments: {total_attachments}')
            self.stdout.write(f'  S3 Attachments: {s3_attachments}')
            self.stdout.write(f'  Local Attachments: {local_attachments}')
            
            if total_attachments > 0:
                s3_percentage = (s3_attachments / total_attachments) * 100
                self.stdout.write(f'  S3 Migration Progress: {s3_percentage:.1f}%')
            
        except Exception as e:
            raise CommandError(f'Failed to get status: {e}')

    def handle_migrate_local_to_s3(self, dry_run=False):
        """Migrate local files to S3 storage."""
        self.stdout.write('Migrating Local Files to S3:')
        self.stdout.write('=' * 50)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No files will be migrated'))
            self.stdout.write('')
        
        try:
            # Get local attachments that need migration
            local_attachments = MessageAttachment.objects.filter(
                storage_type='local',
                file__isnull=False
            )
            
            total_count = local_attachments.count()
            self.stdout.write(f'Found {total_count} local attachments to migrate')
            
            if total_count == 0:
                self.stdout.write(self.style.SUCCESS('No local attachments to migrate'))
                return
            
            migrated_count = 0
            failed_count = 0
            
            for attachment in local_attachments:
                try:
                    self.stdout.write(f'Processing: {attachment.file_name}')
                    
                    if not dry_run:
                        # Read file content
                        if not attachment.file:
                            self.stdout.write(self.style.WARNING(f'  Skipping: No file found for {attachment.file_name}'))
                            failed_count += 1
                            continue
                        
                        file_content = attachment.file.read()
                        
                        # Upload to S3
                        upload_result = cloud_storage.upload_file(
                            file_content=file_content,
                            file_name=attachment.file_name,
                            content_type=attachment.file_type,
                            user_id=attachment.message.sender.user_id if attachment.message else None
                        )
                        
                        if upload_result.get('success', False):
                            # Update attachment record
                            attachment.file_key = upload_result['file_key']
                            attachment.file_url = upload_result['file_url']
                            attachment.storage_type = 's3'
                            attachment.save()
                            
                            # Delete local file
                            attachment.file.delete(save=False)
                            
                            migrated_count += 1
                            self.stdout.write(self.style.SUCCESS(f'  Migrated: {attachment.file_name}'))
                        else:
                            failed_count += 1
                            self.stdout.write(self.style.ERROR(f'  Failed: {upload_result.get("error", "Unknown error")}'))
                    else:
                        self.stdout.write(f'  Would migrate: {attachment.file_name}')
                        migrated_count += 1
                        
                except Exception as e:
                    failed_count += 1
                    self.stdout.write(self.style.ERROR(f'  Error processing {attachment.file_name}: {e}'))
            
            self.stdout.write('')
            self.stdout.write('Migration Summary:')
            self.stdout.write(f'  Total Processed: {total_count}')
            self.stdout.write(f'  Successfully Migrated: {migrated_count}')
            self.stdout.write(f'  Failed: {failed_count}')
            
            if not dry_run and migrated_count > 0:
                self.stdout.write(self.style.SUCCESS('Migration completed successfully'))
            elif dry_run:
                self.stdout.write(self.style.WARNING('Dry run completed - no files were actually migrated'))
            
        except Exception as e:
            raise CommandError(f'Migration failed: {e}')

    def handle_cleanup_orphaned(self, dry_run=False):
        """Clean up orphaned files in storage."""
        self.stdout.write('Cleaning Up Orphaned Files:')
        self.stdout.write('=' * 50)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No files will be deleted'))
            self.stdout.write('')
        
        try:
            # Find attachments without messages (orphaned)
            orphaned_attachments = MessageAttachment.objects.filter(message__isnull=True)
            
            total_count = orphaned_attachments.count()
            self.stdout.write(f'Found {total_count} orphaned attachments')
            
            if total_count == 0:
                self.stdout.write(self.style.SUCCESS('No orphaned attachments found'))
                return
            
            deleted_count = 0
            failed_count = 0
            
            for attachment in orphaned_attachments:
                try:
                    self.stdout.write(f'Processing orphaned: {attachment.file_name}')
                    
                    if not dry_run:
                        # Delete from storage
                        if attachment.delete_file_from_storage():
                            # Delete database record
                            attachment.delete()
                            deleted_count += 1
                            self.stdout.write(self.style.SUCCESS(f'  Deleted: {attachment.file_name}'))
                        else:
                            failed_count += 1
                            self.stdout.write(self.style.ERROR(f'  Failed to delete: {attachment.file_name}'))
                    else:
                        self.stdout.write(f'  Would delete: {attachment.file_name}')
                        deleted_count += 1
                        
                except Exception as e:
                    failed_count += 1
                    self.stdout.write(self.style.ERROR(f'  Error processing {attachment.file_name}: {e}'))
            
            self.stdout.write('')
            self.stdout.write('Cleanup Summary:')
            self.stdout.write(f'  Total Processed: {total_count}')
            self.stdout.write(f'  Successfully Deleted: {deleted_count}')
            self.stdout.write(f'  Failed: {failed_count}')
            
            if not dry_run and deleted_count > 0:
                self.stdout.write(self.style.SUCCESS('Cleanup completed successfully'))
            elif dry_run:
                self.stdout.write(self.style.WARNING('Dry run completed - no files were actually deleted'))
            
        except Exception as e:
            raise CommandError(f'Cleanup failed: {e}')

    def handle_test_upload(self):
        """Test file upload to cloud storage."""
        self.stdout.write('Testing Cloud Storage Upload:')
        self.stdout.write('=' * 50)
        
        try:
            # Create test file content
            test_content = b'This is a test file for cloud storage upload.'
            test_filename = 'test_upload.txt'
            test_content_type = 'text/plain'
            
            self.stdout.write(f'Uploading test file: {test_filename}')
            
            # Upload test file
            upload_result = cloud_storage.upload_file(
                file_content=test_content,
                file_name=test_filename,
                content_type=test_content_type,
                user_id=1  # Test user ID
            )
            
            if upload_result.get('success', False):
                self.stdout.write(self.style.SUCCESS('Upload successful!'))
                self.stdout.write(f'  File Key: {upload_result["file_key"]}')
                self.stdout.write(f'  File URL: {upload_result["file_url"]}')
                self.stdout.write(f'  Storage Type: {upload_result["storage_type"]}')
                self.stdout.write(f'  File Size: {upload_result["size"]} bytes')
                
                # Test file deletion
                if upload_result['storage_type'] == 's3':
                    self.stdout.write('')
                    self.stdout.write('Testing file deletion...')
                    
                    if cloud_storage.delete_file(upload_result['file_key']):
                        self.stdout.write(self.style.SUCCESS('File deletion successful!'))
                    else:
                        self.stdout.write(self.style.ERROR('File deletion failed!'))
                else:
                    self.stdout.write('Skipping deletion test for local storage')
                    
            else:
                self.stdout.write(self.style.ERROR('Upload failed!'))
                self.stdout.write(f'  Error: {upload_result.get("error", "Unknown error")}')
            
        except Exception as e:
            raise CommandError(f'Test upload failed: {e}')









































