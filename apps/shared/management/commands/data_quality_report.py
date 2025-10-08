"""
Management command to generate data quality report.
Identifies and reports on 'nan' values and other data quality issues.
"""
from django.core.management.base import BaseCommand
from apps.shared.models import User, EmploymentHistory, TrackerData
from collections import Counter


class Command(BaseCommand):
    help = 'Generate comprehensive data quality report'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix-nan',
            action='store_true',
            help='Automatically fix nan values by setting them to empty strings',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed breakdown of issues',
        )

    def handle(self, *args, **options):
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("DATA QUALITY REPORT"))
        self.stdout.write("=" * 70)
        
        fix_nan = options.get('fix_nan', False)
        verbose = options.get('verbose', False)
        
        # Check for nan values in key fields
        self.check_nan_values(fix_nan, verbose)
        
        # Check for empty/null values
        self.check_empty_values(verbose)
        
        # Check for data consistency issues
        self.check_consistency_issues(verbose)
        
        self.stdout.write("\n" + "=" * 70)

    def check_nan_values(self, fix_nan, verbose):
        """Check for 'nan' string values in database"""
        self.stdout.write("\nNAN VALUES CHECK")
        self.stdout.write("-" * 40)
        
        # Check EmploymentHistory
        nan_employment = EmploymentHistory.objects.filter(
            position_current__iexact='nan'
        ).count()
        
        nan_company = EmploymentHistory.objects.filter(
            company_name_current__iexact='nan'
        ).count()
        
        # Check TrackerData for nan values
        nan_tracker_fields = {}
        tracker_fields = [
            'q_employment_status', 'q_sector_current', 'q_scope_current',
            'q_salary_range', 'q_job_satisfaction', 'q_skills_utilization'
        ]
        
        for field in tracker_fields:
            count = TrackerData.objects.filter(**{f"{field}__iexact": 'nan'}).count()
            if count > 0:
                nan_tracker_fields[field] = count
        
        # Report results
        total_nan = nan_employment + nan_company + sum(nan_tracker_fields.values())
        
        if total_nan > 0:
            self.stdout.write(self.style.WARNING(f"Found {total_nan} 'nan' values:"))
            self.stdout.write(f"  Employment positions: {nan_employment}")
            self.stdout.write(f"  Company names: {nan_company}")
            
            for field, count in nan_tracker_fields.items():
                self.stdout.write(f"  Tracker {field}: {count}")
            
            if fix_nan:
                self.stdout.write("\nFixing nan values...")
                fixed_count = 0
                
                # Fix employment nan values
                if nan_employment > 0:
                    updated = EmploymentHistory.objects.filter(
                        position_current__iexact='nan'
                    ).update(position_current='')
                    fixed_count += updated
                    self.stdout.write(f"  Fixed {updated} employment positions")
                
                if nan_company > 0:
                    updated = EmploymentHistory.objects.filter(
                        company_name_current__iexact='nan'
                    ).update(company_name_current='')
                    fixed_count += updated
                    self.stdout.write(f"  Fixed {updated} company names")
                
                # Fix tracker nan values
                for field in nan_tracker_fields:
                    updated = TrackerData.objects.filter(
                        **{f"{field}__iexact": 'nan'}
                    ).update(**{field: ''})
                    fixed_count += updated
                    self.stdout.write(f"  Fixed {updated} {field} values")
                
                self.stdout.write(self.style.SUCCESS(f"Total fixed: {fixed_count}"))
            else:
                self.stdout.write(self.style.WARNING("Use --fix-nan to automatically fix these values"))
        else:
            self.stdout.write(self.style.SUCCESS("No 'nan' values found!"))

    def check_empty_values(self, verbose):
        """Check for empty/null values in critical fields"""
        self.stdout.write("\nEMPTY VALUES CHECK")
        self.stdout.write("-" * 40)
        
        # Check critical empty fields
        empty_position = EmploymentHistory.objects.filter(
            position_current__in=['', None]
        ).count()
        
        empty_company = EmploymentHistory.objects.filter(
            company_name_current__in=['', None]
        ).count()
        
        # Check users without employment data
        users_without_employment = User.objects.filter(
            account_type__user=True,
            employment__isnull=True
        ).count()
        
        # Check users without tracker data
        users_without_tracker = User.objects.filter(
            account_type__user=True,
            tracker_data__isnull=True
        ).count()
        
        total_issues = empty_position + empty_company + users_without_employment + users_without_tracker
        
        if total_issues > 0:
            self.stdout.write(self.style.WARNING(f"Found {total_issues} empty value issues:"))
            self.stdout.write(f"  Empty positions: {empty_position}")
            self.stdout.write(f"  Empty company names: {empty_company}")
            self.stdout.write(f"  Users without employment: {users_without_employment}")
            self.stdout.write(f"  Users without tracker data: {users_without_tracker}")
        else:
            self.stdout.write(self.style.SUCCESS("No critical empty values found!"))

    def check_consistency_issues(self, verbose):
        """Check for data consistency issues"""
        self.stdout.write("\nCONSISTENCY CHECK")
        self.stdout.write("-" * 40)
        
        # Check for inconsistent employment status
        employed_but_no_position = TrackerData.objects.filter(
            q_employment_status__iexact='yes'
        ).exclude(
            user__employment__position_current__isnull=False
        ).exclude(
            user__employment__position_current=''
        ).count()
        
        unemployed_but_has_position = TrackerData.objects.filter(
            q_employment_status__iexact='no'
        ).filter(
            user__employment__position_current__isnull=False
        ).exclude(
            user__employment__position_current=''
        ).count()
        
        # Check for future start dates
        from django.utils import timezone
        future_dates = EmploymentHistory.objects.filter(
            date_started__gt=timezone.now().date()
        ).count()
        
        total_issues = employed_but_no_position + unemployed_but_has_position + future_dates
        
        if total_issues > 0:
            self.stdout.write(self.style.WARNING(f"Found {total_issues} consistency issues:"))
            self.stdout.write(f"  Employed but no position: {employed_but_no_position}")
            self.stdout.write(f"  Unemployed but has position: {unemployed_but_has_position}")
            self.stdout.write(f"  Future start dates: {future_dates}")
        else:
            self.stdout.write(self.style.SUCCESS("No consistency issues found!"))
        
        if verbose:
            self.stdout.write("\nDETAILED BREAKDOWN:")
            self.stdout.write("-" * 20)
            
            # Show sample inconsistent records
            if employed_but_no_position > 0:
                self.stdout.write("\nSample 'Employed but no position' records:")
                samples = TrackerData.objects.filter(
                    q_employment_status__iexact='yes'
                ).exclude(
                    user__employment__position_current__isnull=False
                ).exclude(
                    user__employment__position_current=''
                )[:5]
                
                for sample in samples:
                    self.stdout.write(f"  User: {sample.user.full_name} (ID: {sample.user.user_id})")
            
            if unemployed_but_has_position > 0:
                self.stdout.write("\nSample 'Unemployed but has position' records:")
                samples = TrackerData.objects.filter(
                    q_employment_status__iexact='no'
                ).filter(
                    user__employment__position_current__isnull=False
                ).exclude(
                    user__employment__position_current=''
                )[:5]
                
                for sample in samples:
                    self.stdout.write(f"  User: {sample.user.full_name} - Position: {sample.user.employment.position_current}")
