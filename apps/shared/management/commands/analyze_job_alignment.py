"""
Management command to analyze job alignment status and identify issues.
Provides insights for improving job title database and data quality.

Usage: python manage.py analyze_job_alignment [--verbose]
"""
from django.core.management.base import BaseCommand
from apps.shared.models import User, EmploymentHistory, SimpleCompTechJob, SimpleInfoTechJob, SimpleInfoSystemJob
from collections import Counter


class Command(BaseCommand):
    help = 'Analyze job alignment status and identify unmatched positions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed list of unmatched positions',
        )
        parser.add_argument(
            '--program',
            type=str,
            help='Filter by program (BSIT, BSIS, BIT-CT)',
        )

    def handle(self, *args, **options):
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("JOB ALIGNMENT ANALYSIS REPORT"))
        self.stdout.write("=" * 70)
        
        verbose = options.get('verbose', False)
        program_filter = options.get('program')
        
        # Get all alumni
        alumni_qs = User.objects.filter(account_type__user=True).select_related(
            'academic_info', 'employment'
        )
        
        if program_filter:
            alumni_qs = alumni_qs.filter(academic_info__program__icontains=program_filter)
        
        total_alumni = alumni_qs.count()
        
        # Statistics
        aligned = 0
        not_aligned = 0
        no_position = 0
        nan_positions = 0
        
        unmatched_positions = []
        position_counts = Counter()
        program_breakdown = Counter()
        
        self.stdout.write(f"\nAnalyzing {total_alumni} alumni users...")
        
        for user in alumni_qs:
            employment = getattr(user, 'employment', None)
            academic = getattr(user, 'academic_info', None)
            program = academic.program if academic else 'Unknown'
            
            if not employment:
                no_position += 1
                continue
            
            position = employment.position_current
            
            if not position or not str(position).strip():
                no_position += 1
                continue
            
            position_str = str(position).strip()
            
            # Check for nan values
            if position_str.lower() in ['nan', 'none', 'null', 'n/a']:
                nan_positions += 1
                continue
            
            # Count alignment status
            if employment.job_alignment_status == 'aligned':
                aligned += 1
            else:
                not_aligned += 1
                unmatched_positions.append({
                    'position': position_str,
                    'program': program,
                    'user_id': user.user_id,
                    'name': user.full_name
                })
                position_counts[position_str] += 1
            
            program_breakdown[program] += 1
        
        # Display results
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("ALIGNMENT STATISTICS")
        self.stdout.write("=" * 70)
        
        self.stdout.write(f"\nTotal Alumni:           {total_alumni}")
        self.stdout.write(f"  Aligned:              {aligned} ({aligned/total_alumni*100:.1f}%)" if total_alumni > 0 else "  Aligned:              0")
        self.stdout.write(f"  Not Aligned:          {not_aligned} ({not_aligned/total_alumni*100:.1f}%)" if total_alumni > 0 else "  Not Aligned:          0")
        self.stdout.write(f"  No Position Data:     {no_position} ({no_position/total_alumni*100:.1f}%)" if total_alumni > 0 else "  No Position Data:     0")
        self.stdout.write(f"  'nan' Values:         {nan_positions} ({nan_positions/total_alumni*100:.1f}%)" if total_alumni > 0 else "  'nan' Values:         0")
        
        # Program breakdown
        self.stdout.write("\n" + "-" * 70)
        self.stdout.write("PROGRAM BREAKDOWN")
        self.stdout.write("-" * 70)
        for program, count in program_breakdown.most_common():
            self.stdout.write(f"  {program}: {count}")
        
        # Top unmatched positions
        if position_counts:
            self.stdout.write("\n" + "-" * 70)
            self.stdout.write("TOP UNMATCHED POSITIONS (add these to job tables)")
            self.stdout.write("-" * 70)
            for position, count in position_counts.most_common(20):
                self.stdout.write(f"  {position} ({count}x)")
        
        # Detailed list if verbose
        if verbose and unmatched_positions:
            self.stdout.write("\n" + "-" * 70)
            self.stdout.write("DETAILED UNMATCHED POSITIONS")
            self.stdout.write("-" * 70)
            for item in unmatched_positions[:50]:  # Limit to 50
                self.stdout.write(f"  {item['name']} ({item['program']})")
                self.stdout.write(f"    Position: {item['position']}")
        
        # Recommendations
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("RECOMMENDATIONS")
        self.stdout.write("=" * 70)
        
        if nan_positions > 0:
            self.stdout.write(self.style.WARNING(f"\n! DATA QUALITY ISSUE: {nan_positions} positions stored as 'nan'"))
            self.stdout.write("  Action: Run data cleaning script to fix nan values")
        
        if not_aligned > aligned and not_aligned > 5:
            self.stdout.write(self.style.WARNING(f"\n! LOW ALIGNMENT RATE: {not_aligned} unmatched positions"))
            self.stdout.write("  Action: Add top unmatched positions to job tables")
            self.stdout.write(f"  Suggested additions: {min(20, len(position_counts))} job titles")
        
        if position_counts:
            self.stdout.write(f"\n! MISSING JOB TITLES: {len(position_counts)} unique unmatched positions")
            self.stdout.write("  Use top unmatched list above to expand job tables")
        
        self.stdout.write("\n" + "=" * 70)
        
        # Job table coverage
        job_count = (SimpleCompTechJob.objects.count() + 
                     SimpleInfoTechJob.objects.count() + 
                     SimpleInfoSystemJob.objects.count())
        self.stdout.write(f"\nCurrent job table size: {job_count} titles")
        self.stdout.write(f"Alignment coverage: {aligned}/{total_alumni} alumni ({aligned/total_alumni*100:.1f}%)" if total_alumni > 0 else "Alignment coverage: 0%")
        self.stdout.write("=" * 70)



