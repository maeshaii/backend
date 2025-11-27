"""
Django management command to delete all coordinator accounts.

Usage:
    python manage.py delete_all_coordinators                    # Preview what will be deleted
    python manage.py delete_all_coordinators --confirm          # Actually delete
    python manage.py delete_all_coordinators --deactivate       # Deactivate instead of delete
    python manage.py delete_all_coordinators --program BSIT     # Delete only BSIT coordinators
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.shared.models import User


class Command(BaseCommand):
    help = 'Delete or deactivate all coordinator accounts (for testing duplicate prevention)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Actually perform the deletion (required for deletion)',
        )
        parser.add_argument(
            '--deactivate',
            action='store_true',
            help='Deactivate coordinators instead of deleting them',
        )
        parser.add_argument(
            '--program',
            type=str,
            help='Only delete/deactivate coordinators for a specific program (e.g., BSIT, BSIS)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually doing it (default behavior)',
        )

    def handle(self, **options):
        confirm = options['confirm']
        deactivate = options['deactivate']
        program_filter = options.get('program', '').strip().upper() if options.get('program') else None
        dry_run = options.get('dry_run', not confirm)  # Default to dry-run unless --confirm is used

        # Get all coordinators
        coordinators = User.objects.filter(
            account_type__coordinator=True
        ).select_related('account_type', 'academic_info').order_by('acc_username')

        if program_filter:
            # Filter by program (check both f_name and AcademicInfo.program)
            filtered_coordinators = []
            for coord in coordinators:
                # Check User.f_name
                user_program = (coord.f_name or '').strip().upper().replace(' N/A', '').replace(' COORDINATOR', '')
                # Check AcademicInfo.program
                academic_program = ''
                if hasattr(coord, 'academic_info') and coord.academic_info and coord.academic_info.program:
                    academic_program = coord.academic_info.program.strip().upper().replace(' N/A', '').replace(' COORDINATOR', '')
                
                if user_program == program_filter or academic_program == program_filter:
                    filtered_coordinators.append(coord)
            coordinators = filtered_coordinators

        if not coordinators.exists():
            self.stdout.write(self.style.SUCCESS('No coordinators found to delete.'))
            return

        # Display what will be affected
        self.stdout.write(self.style.WARNING('=' * 70))
        self.stdout.write(self.style.WARNING(f'Found {coordinators.count()} coordinator(s) to process:'))
        self.stdout.write(self.style.WARNING('=' * 70))
        
        for coord in coordinators:
            program_display = coord.f_name or 'Unknown'
            if hasattr(coord, 'academic_info') and coord.academic_info and coord.academic_info.program:
                program_display = coord.academic_info.program
            
            self.stdout.write(f'  - User ID: {coord.user_id}')
            self.stdout.write(f'    Username: {coord.acc_username}')
            self.stdout.write(f'    Name: {coord.f_name} {coord.l_name}')
            self.stdout.write(f'    Program: {program_display}')
            self.stdout.write(f'    Status: {coord.user_status}')
            self.stdout.write('')

        if dry_run:
            self.stdout.write(self.style.WARNING('=' * 70))
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
            self.stdout.write(self.style.WARNING('=' * 70))
            self.stdout.write('')
            self.stdout.write('To actually delete/deactivate, run with --confirm flag:')
            if deactivate:
                self.stdout.write('  python manage.py delete_all_coordinators --deactivate --confirm')
            else:
                self.stdout.write('  python manage.py delete_all_coordinators --confirm')
            if program_filter:
                self.stdout.write(f'  (Currently filtering for program: {program_filter})')
            return

        # Confirm action
        if not confirm:
            self.stdout.write(self.style.ERROR('ERROR: --confirm flag is required to perform deletion/deactivation'))
            self.stdout.write('Run with --dry-run first to preview what will be affected.')
            return

        # Perform deletion or deactivation
        try:
            with transaction.atomic():
                deleted_count = 0
                deactivated_count = 0
                
                for coord in coordinators:
                    program_display = coord.f_name or 'Unknown'
                    if hasattr(coord, 'academic_info') and coord.academic_info and coord.academic_info.program:
                        program_display = coord.academic_info.program
                    
                    if deactivate:
                        # Deactivate instead of delete
                        coord.user_status = 'inactive'
                        coord.save()
                        deactivated_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(f'✓ Deactivated: {coord.acc_username} ({program_display})')
                        )
                    else:
                        # Delete the coordinator
                        # Related AcademicInfo will be deleted via CASCADE
                        username = coord.acc_username
                        coord.delete()
                        deleted_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(f'✓ Deleted: {username} ({program_display})')
                        )

                self.stdout.write('')
                self.stdout.write(self.style.SUCCESS('=' * 70))
                if deactivate:
                    self.stdout.write(self.style.SUCCESS(f'Successfully deactivated {deactivated_count} coordinator(s)'))
                else:
                    self.stdout.write(self.style.SUCCESS(f'Successfully deleted {deleted_count} coordinator(s)'))
                self.stdout.write(self.style.SUCCESS('=' * 70))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'ERROR: Failed to delete/deactivate coordinators: {str(e)}'))
            raise CommandError(f'Deletion failed: {str(e)}') from e

