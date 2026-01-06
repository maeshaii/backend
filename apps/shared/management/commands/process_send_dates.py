from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date
from apps.shared.models import SendDate, User, OJTInfo, OJTImport, AccountType, TrackerData, Notification
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
        parser.add_argument(
            '--force-reprocess',
            action='store_true',
            help='Reprocess already-processed send dates (useful for fixing NOT STARTED students)',
        )

    def handle(self, *args, **options):
        # Ensure fresh database connections (important for background threads)
        from django.db import close_old_connections
        close_old_connections()
        
        dry_run = options['dry_run']
        force_reprocess = options.get('force_reprocess', False)
        today = date.today()
        
        self.stdout.write(f"Processing send dates for {today}")
        if force_reprocess:
            self.stdout.write(self.style.WARNING("⚠️  FORCE REPROCESS mode: Will process already-processed send dates"))
        
        # Find send dates for today or earlier
        if force_reprocess:
            # Include already-processed send dates
            send_dates = SendDate.objects.filter(
                send_date__lte=today
            ).order_by('send_date', 'coordinator', 'batch_year')
        else:
            # Only unprocessed send dates
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
                    not_started_msg = ""
                    if result.get('not_started_count', 0) > 0:
                        not_started_msg = f", {result['not_started_count']} NOT STARTED marked incomplete"
                    
                    alumni_msg = ""
                    if result.get('alumni_converted_count', 0) > 0:
                        alumni_msg = f", {result['alumni_converted_count']} automatically converted to alumni"
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  ✅ Processed batch {send_date_record.batch_year}: "
                            f"{result['completed_count']} completed{alumni_msg}, {result['ongoing_count']} ongoing marked incomplete{not_started_msg}"
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
                from django.db.models import Q
                
                # IMPORTANT: Only process students imported by this coordinator
                # Get year+section combinations imported by this coordinator
                coordinator_imports = OJTImport.objects.filter(coordinator=send_date_record.coordinator)
                coordinator_year_sections = set()
                
                for imp in coordinator_imports:
                    y = getattr(imp, 'batch_year', None)
                    s = getattr(imp, 'section', None) or ''
                    if y == send_date_record.batch_year:  # Only for this batch year
                        coordinator_year_sections.add((y, s))
                
                # Build filter for coordinator's year+section combinations
                year_section_filters = Q()
                has_filters = False
                
                for (y, s) in coordinator_year_sections:
                    if y == send_date_record.batch_year:
                        has_filters = True
                        if s:
                            year_section_filters |= Q(academic_info__year_graduated=y, academic_info__section=s)
                        else:
                            year_section_filters |= Q(academic_info__year_graduated=y)
                
                # Get OJT users - only from this coordinator's imports
                if has_filters and year_section_filters:
                    ojt_users = User.objects.filter(
                        year_section_filters,
                        account_type__ojt=True
                    ).select_related('ojt_info', 'academic_info')
                else:
                    # Fallback: if no imports found, use basic filter (shouldn't happen normally)
                    logger.warning(f"No imports found for coordinator {send_date_record.coordinator} batch {send_date_record.batch_year}")
                    ojt_users = User.objects.filter(
                        account_type__ojt=True,
                        academic_info__year_graduated=send_date_record.batch_year
                    ).select_related('ojt_info', 'academic_info')
                
                # Filter by section if specified in send_date_record
                if send_date_record.section:
                    ojt_users = ojt_users.filter(academic_info__section=send_date_record.section)
                
                logger.info(f"Found {ojt_users.count()} students for coordinator {send_date_record.coordinator}, batch {send_date_record.batch_year}")
                
                completed_users = []
                ongoing_users = []
                not_started_users = []
                
                for user in ojt_users:
                    # Check if user has ojt_info
                    has_ojt_info = hasattr(user, 'ojt_info') and user.ojt_info is not None
                    
                    if has_ojt_info:
                        # PRIORITY: Check if student has NOT STARTED status (no start date = NOT STARTED)
                        # Frontend determines NOT STARTED by checking: !ojt.ojt_start_date
                        # This check must come FIRST, even if status says "Completed" or "Ongoing"
                        is_not_started = not user.ojt_info.ojt_start_date
                        status = (user.ojt_info.ojtstatus or '').strip()
                        
                        if is_not_started:
                            # Include students without start date FIRST, regardless of their current status field
                            # This fixes cases where status is "Completed" but start_date is None
                            not_started_users.append(user)
                            logger.info(f"  Found NOT STARTED student {user.full_name or user.acc_username} (user_id: {user.user_id}) - status was '{status}' but no start_date")
                        elif status == 'Completed':
                            completed_users.append(user)
                        elif status == 'Ongoing':
                            ongoing_users.append(user)
                        # Note: Students with start date but no status will be handled by default logic
                    else:
                        # User has no ojt_info record = NOT STARTED
                        not_started_users.append(user)
                        logger.info(f"  Found user {user.user_id} ({user.full_name or user.acc_username}) without ojt_info - treating as NOT STARTED")
                
                # Automatically convert completed users to alumni when send date passes
                completed_count = 0
                alumni_converted_count = 0
                if completed_users:
                    # Get alumni account type
                    try:
                        alumni_type = AccountType.objects.filter(user=True).first()
                        if not alumni_type:
                            alumni_type = AccountType.objects.create(
                                user=True, admin=False, peso=False, coordinator=False, ojt=False
                            )
                    except Exception:
                        alumni_type = AccountType.objects.filter(user=True).first() or AccountType.objects.create(
                            user=True, admin=False, peso=False, coordinator=False, ojt=False
                        )
                    
                    # Convert each completed user to alumni automatically
                    for user in completed_users:
                        try:
                            # Skip if already alumni
                            if user.account_type and user.account_type.user:
                                logger.info(f"  User {user.full_name or user.acc_username} (user_id: {user.user_id}) is already alumni, skipping")
                                completed_count += 1
                                continue
                            
                            # Convert to alumni
                            user.account_type = alumni_type
                            user.user_status = 'active'
                            user.save()
                            
                            # Clear sent to admin flag since user is now approved
                            if hasattr(user, 'ojt_info') and user.ojt_info:
                                user.ojt_info.is_sent_to_admin = False
                                user.ojt_info.save()
                            
                            # Ensure academic info year_graduated is set
                            if hasattr(user, 'academic_info') and user.academic_info:
                                if not getattr(user.academic_info, 'year_graduated', None):
                                    user.academic_info.year_graduated = send_date_record.batch_year
                                user.academic_info.save()
                            
                            # Create TrackerData record for newly approved alumni
                            TrackerData.objects.get_or_create(
                                user=user,
                                defaults={
                                    'q_employment_status': None,  # Will be 'pending' until they fill tracker
                                    'tracker_submitted_at': None
                                }
                            )
                            
                            completed_count += 1
                            alumni_converted_count += 1
                            logger.info(f"  ✓ Automatically converted {user.full_name or user.acc_username} (user_id: {user.user_id}) to alumni")
                            
                        except Exception as conv_e:
                            logger.error(f"  ❌ Error converting user {user.user_id} to alumni: {str(conv_e)}")
                            # Still count as completed even if conversion failed
                            completed_count += 1
                    
                    # Create OJTImport record to mark this batch as automatically approved
                    ojt_import, created = OJTImport.objects.get_or_create(
                        coordinator=send_date_record.coordinator,
                        batch_year=send_date_record.batch_year,
                        course='',  # Will be filled from user data
                        section=send_date_record.section or '',
                        defaults={
                            'file_name': f'Auto-scheduled batch {send_date_record.batch_year}',
                            'records_imported': completed_count,
                            'status': 'Approved'  # Changed from 'Requested' to 'Approved' since automatically approved
                        }
                    )
                    
                    if not created:
                        ojt_import.status = 'Approved'  # Changed from 'Requested' to 'Approved'
                        ojt_import.records_imported = completed_count
                        ojt_import.save()
                    
                    # Notify all admin users about new alumni
                    if alumni_converted_count > 0:
                        try:
                            from apps.messaging.notification_broadcaster import broadcast_notification
                            admin_users = User.objects.filter(account_type__admin=True)
                            
                            for admin_user in admin_users:
                                try:
                                    notification = Notification.objects.create(
                                        user=admin_user,
                                        notif_type='OJT_APPROVAL',
                                        subject=f'New Alumni Automatically Approved - Batch {send_date_record.batch_year}',
                                        notifi_content=f'{alumni_converted_count} OJT student(s) from batch {send_date_record.batch_year} have been automatically converted to alumni after the send date passed.',
                                        notif_date=timezone.now()
                                    )
                                    # Broadcast notification in real-time
                                    try:
                                        broadcast_notification(notification)
                                    except Exception as broadcast_e:
                                        logger.error(f"Error broadcasting notification: {broadcast_e}")
                                except Exception as notif_e:
                                    logger.error(f"Error creating notification for admin {admin_user.user_id}: {str(notif_e)}")
                            
                            logger.info(f"  ✓ Notified {admin_users.count()} admin user(s) about {alumni_converted_count} new alumni")
                        except Exception as notify_e:
                            logger.error(f"Error notifying admins: {str(notify_e)}")
                
                # Mark ongoing users as incomplete
                ongoing_count = 0
                for user in ongoing_users:
                    if hasattr(user, 'ojt_info'):
                        user.ojt_info.ojtstatus = 'Incomplete'
                        # Ensure they are not flagged as sent to admin
                        user.ojt_info.is_sent_to_admin = False
                        user.ojt_info.sent_to_admin_date = None
                        user.ojt_info.save()
                        ongoing_count += 1
                
                # Mark NOT STARTED users as incomplete when send date passes
                not_started_count = 0
                for user in not_started_users:
                    # Get or create ojt_info if it doesn't exist
                    try:
                        ojt_info = user.ojt_info
                    except OJTInfo.DoesNotExist:
                        # Create ojt_info if it doesn't exist
                        ojt_info = OJTInfo.objects.create(user=user)
                        logger.info(f"  Created ojt_info for user {user.user_id} ({user.full_name or user.acc_username})")
                    
                    # Mark as Incomplete
                    ojt_info.ojtstatus = 'Incomplete'
                    # Ensure they are not flagged as sent to admin
                    ojt_info.is_sent_to_admin = False
                    ojt_info.sent_to_admin_date = None
                    ojt_info.save()
                    not_started_count += 1
                    logger.info(f"  ✓ Marked NOT STARTED student {user.full_name or user.acc_username} (user_id: {user.user_id}) as Incomplete")
                
                return {
                    'success': True,
                    'completed_count': completed_count,
                    'alumni_converted_count': alumni_converted_count,
                    'ongoing_count': ongoing_count,
                    'not_started_count': not_started_count,
                    'total_processed': completed_count + ongoing_count + not_started_count
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

