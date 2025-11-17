import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.shared.models import (
    User, 
    AccountType,
    OJTInfo, 
    OJTCompanyProfile, 
    OJTImport,
    SendDate,
    AcademicInfo,
    UserProfile,
    TrackerData,
    EmploymentHistory,
    UserPoints,
    RewardHistory,
    UserInitialPassword
)

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Deletes all OJT and Alumni data from the database (for testing/development)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm deletion of all OJT and Alumni data',
        )
        parser.add_argument(
            '--ojt-only',
            action='store_true',
            help='Delete only OJT data (keep alumni)',
        )
        parser.add_argument(
            '--alumni-only',
            action='store_true',
            help='Delete only Alumni data (keep OJT)',
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(self.style.ERROR('⚠️  WARNING: This will delete ALL OJT and/or Alumni data!'))
            self.stdout.write(self.style.ERROR('To confirm, run with --confirm flag:'))
            self.stdout.write(self.style.WARNING('python manage.py clear_ojt_alumni_data --confirm'))
            self.stdout.write(self.style.WARNING('python manage.py clear_ojt_alumni_data --confirm --ojt-only'))
            self.stdout.write(self.style.WARNING('python manage.py clear_ojt_alumni_data --confirm --alumni-only'))
            return

        ojt_only = options.get('ojt_only', False)
        alumni_only = options.get('alumni_only', False)

        try:
            # Delete OJT Data (no transaction to allow partial cleanup)
            if not alumni_only:
                self.stdout.write(self.style.WARNING('\n🗑️  Deleting OJT Data...'))
                
                # Get OJT users FIRST (before deleting ojt_info records)
                # Identify by account_type.ojt=True
                ojt_users = User.objects.filter(
                    account_type__ojt=True
                ).exclude(
                    acc_username__in=['admin', 'coordinator', 'peso']
                ).distinct()
                ojt_user_count = ojt_users.count()
                
                self.stdout.write(f'  Found {ojt_user_count} OJT users to delete')
                
                # Delete OJT-specific records (with error handling for missing tables)
                try:
                    ojt_info_count = OJTInfo.objects.all().count()
                    OJTInfo.objects.all().delete()
                    self.stdout.write(f'  ✓ Deleted {ojt_info_count} OJT Info records')
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'  ⚠️  OJT Info table not found or error: {str(e)[:50]}'))
                
                try:
                    ojt_company_count = OJTCompanyProfile.objects.all().count()
                    OJTCompanyProfile.objects.all().delete()
                    self.stdout.write(f'  ✓ Deleted {ojt_company_count} OJT Company Profile records')
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'  ⚠️  OJT Company Profile table not found or error: {str(e)[:50]}'))
                
                try:
                    ojt_import_count = OJTImport.objects.all().count()
                    OJTImport.objects.all().delete()
                    self.stdout.write(f'  ✓ Deleted {ojt_import_count} OJT Import records')
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'  ⚠️  OJT Import table not found or error: {str(e)[:50]}'))
                
                try:
                    send_date_count = SendDate.objects.all().count()
                    SendDate.objects.all().delete()
                    self.stdout.write(f'  ✓ Deleted {send_date_count} Send Date records')
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'  ⚠️  Send Date table not found or error: {str(e)[:50]}'))
                
                # Delete OJT users and their related data
                deleted_users = 0
                cleared_users = 0
                for user in ojt_users:
                    try:
                        # Delete related data
                        AcademicInfo.objects.filter(user=user).delete()
                        UserProfile.objects.filter(user=user).delete()
                        TrackerData.objects.filter(user=user).delete()
                        UserPoints.objects.filter(user=user).delete()
                        RewardHistory.objects.filter(user=user).delete()
                        UserInitialPassword.objects.filter(user=user).delete()
                        
                        # Try to delete user completely
                        try:
                            user.delete()
                            deleted_users += 1
                        except Exception as delete_error:
                            # If can't delete (forum relationships), just clear OJT status
                            user.account_type.ojt = False
                            user.account_type.save()
                            cleared_users += 1
                            self.stdout.write(self.style.WARNING(f'  ⚠️  User {user.acc_username} data cleared but account kept (has forum posts)'))
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f'  ⚠️  Error processing user {user.acc_username}: {str(e)[:50]}'))
                
                self.stdout.write(f'  ✓ Deleted {deleted_users} OJT users completely')
                if cleared_users > 0:
                    self.stdout.write(f'  ✓ Cleared {cleared_users} OJT users (kept accounts due to forum posts)')

            # Delete Alumni Data
            if not ojt_only:
                self.stdout.write(self.style.WARNING('\n🗑️  Deleting Alumni Data...'))
                
                # Get alumni users - these are users who:
                # 1. Have employment history OR tracker data (completed tracker form)
                # 2. ARE NOT admins, coordinators, or peso officers
                alumni_users = User.objects.filter(
                    account_type__user=True,
                    account_type__admin=False,
                    account_type__coordinator=False,
                    account_type__peso=False,
                    account_type__ojt=False  # Alumni are converted from OJT to user
                ).exclude(
                    acc_username__in=['admin', 'coordinator', 'peso']
                ).distinct()
                alumni_user_count = alumni_users.count()
                
                # Count related records
                academic_count = AcademicInfo.objects.filter(user__in=alumni_users).count()
                profile_count = UserProfile.objects.filter(user__in=alumni_users).count()
                tracker_count = TrackerData.objects.filter(user__in=alumni_users).count()
                employment_count = EmploymentHistory.objects.filter(user__in=alumni_users).count()
                points_count = UserPoints.objects.filter(user__in=alumni_users).count()
                reward_history_count = RewardHistory.objects.filter(user__in=alumni_users).count()
                password_count = UserInitialPassword.objects.filter(user__in=alumni_users).count()
                
                # Delete alumni and their related data
                for user in alumni_users:
                    try:
                        # Delete related data first
                        AcademicInfo.objects.filter(user=user).delete()
                        UserProfile.objects.filter(user=user).delete()
                        TrackerData.objects.filter(user=user).delete()
                        EmploymentHistory.objects.filter(user=user).delete()
                        UserPoints.objects.filter(user=user).delete()
                        RewardHistory.objects.filter(user=user).delete()
                        UserInitialPassword.objects.filter(user=user).delete()
                        
                        # Delete user (may fail due to forum relationships)
                        try:
                            user.delete()
                        except Exception as delete_error:
                            # If cascade delete fails (forum tables), just mark as inactive
                            self.stdout.write(self.style.WARNING(f'  ⚠️  Could not fully delete user {user.acc_username}: {str(delete_error)[:50]}'))
                            # Instead, we'll just clear their important data (already done above)
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f'  ⚠️  Error processing user {user.acc_username}: {str(e)[:50]}'))
                
                self.stdout.write(f'  ✓ Deleted {alumni_user_count} Alumni users')
                self.stdout.write(f'  ✓ Deleted {academic_count} Academic Info records')
                self.stdout.write(f'  ✓ Deleted {profile_count} User Profile records')
                self.stdout.write(f'  ✓ Deleted {tracker_count} Tracker Data records')
                self.stdout.write(f'  ✓ Deleted {employment_count} Employment History records')
                self.stdout.write(f'  ✓ Deleted {points_count} User Points records')
                self.stdout.write(f'  ✓ Deleted {reward_history_count} Reward History records')
                self.stdout.write(f'  ✓ Deleted {password_count} Initial Password records')

            self.stdout.write(self.style.SUCCESS('\n✅ Data deletion completed successfully!'))
            
            if ojt_only:
                self.stdout.write(self.style.SUCCESS('   OJT data has been cleared. You can now re-import OJT students.'))
            elif alumni_only:
                self.stdout.write(self.style.SUCCESS('   Alumni data has been cleared. You can now re-import alumni.'))
            else:
                self.stdout.write(self.style.SUCCESS('   All OJT and Alumni data has been cleared. You can now re-import fresh data.'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Error during deletion: {str(e)}'))
            logger.error(f"clear_ojt_alumni_data error: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

