from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date
from apps.shared.models import SendDate, User, OJTInfo, OJTImport
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Process scheduled send dates and automatically send OJT batches to admin'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be processed without actually doing it',
        )

    def handle(self, *args, **options):
        # Ensure fresh database connections (important for background threads)
        from django.db import close_old_connections
        close_old_connections()
        
        dry_run = options['dry_run']
        today = date.today()
        
        self.stdout.write(f"Processing send dates for {today}")
        
        # Find all unprocessed send dates for today or earlier
        send_dates = SendDate.objects.filter(
            send_date__lte=today,
            is_processed=False
        ).order_by('send_date', 'coordinator', 'batch_year')
        
        if not send_dates.exists():
            self.stdout.write(self.style.SUCCESS("No send dates to process"))
            return
        
        processed_count = 0
        
        for send_date_record in send_dates:
            try:
                self.stdout.write(f"\nProcessing: {send_date_record}")
                
                if dry_run:
                    self.stdout.write(f"  [DRY RUN] Would process batch {send_date_record.batch_year} for coordinator {send_date_record.coordinator}")
                    continue
                
                # Process the batch
                result = self.process_batch(send_date_record)
                
                if result['success']:
                    # Mark as processed
                    send_date_record.is_processed = True
                    send_date_record.processed_at = timezone.now()
                    send_date_record.save()
                    
                    processed_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  ✅ Processed batch {send_date_record.batch_year}: "
                            f"{result['completed_count']} completed, {result['ongoing_count']} marked incomplete"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f"  ❌ Failed to process batch: {result['error']}")
                    )
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  ❌ Error processing {send_date_record}: {str(e)}")
                )
                logger.error(f"Error processing send date {send_date_record.id}: {str(e)}")
        
        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"\n🎉 Successfully processed {processed_count} send dates")
            )
        else:
            self.stdout.write(f"\n[DRY RUN] Would process {send_dates.count()} send dates")
        
        # Close connections after command completes
        close_old_connections()

    def process_batch(self, send_date_record):
        """Process a single batch - send completed OJT students to admin and mark ongoing as incomplete"""
        try:
            with transaction.atomic():
                # Get all OJT users for this coordinator and batch year
                ojt_users = User.objects.filter(
                    account_type__ojt=True,
                    academic_info__year_graduated=send_date_record.batch_year
                ).select_related('ojt_info', 'academic_info')
                
                # Filter by section if specified
                if send_date_record.section:
                    ojt_users = ojt_users.filter(academic_info__section=send_date_record.section)
                
                completed_users = []
                ongoing_users = []
                
                for user in ojt_users:
                    if hasattr(user, 'ojt_info') and user.ojt_info:
                        if user.ojt_info.ojtstatus == 'Completed':
                            completed_users.append(user)
                        elif user.ojt_info.ojtstatus == 'Ongoing':
                            ongoing_users.append(user)
                
                # Send completed users to admin
                completed_count = 0
                if completed_users:
                    # Mark each completed user as sent to admin
                    for user in completed_users:
                        if hasattr(user, 'ojt_info') and user.ojt_info:
                            user.ojt_info.is_sent_to_admin = True
                            user.ojt_info.sent_to_admin_date = timezone.now()
                            user.ojt_info.save()
                            completed_count += 1
                    
                    # Create OJTImport record to mark this batch as requested
                    ojt_import, created = OJTImport.objects.get_or_create(
                        coordinator=send_date_record.coordinator,
                        batch_year=send_date_record.batch_year,
                        course='',  # Will be filled from user data
                        section=send_date_record.section or '',
                        defaults={
                            'file_name': f'Auto-scheduled batch {send_date_record.batch_year}',
                            'records_imported': completed_count,
                            'status': 'Requested'
                        }
                    )
                    
                    if not created:
                        ojt_import.status = 'Requested'
                        ojt_import.records_imported = completed_count
                        ojt_import.save()
                
                # Mark ongoing users as incomplete
                ongoing_count = 0
                for user in ongoing_users:
                    if hasattr(user, 'ojt_info'):
                        user.ojt_info.ojtstatus = 'Incomplete'
                        user.ojt_info.save()
                        ongoing_count += 1
                
                return {
                    'success': True,
                    'completed_count': completed_count,
                    'ongoing_count': ongoing_count,
                    'total_processed': completed_count + ongoing_count
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

