"""Alumni statistics API endpoints providing overview, typed statistics, and export."""
import logging
from django.shortcuts import render
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
# Security: Role-based permissions
from apps.api.permissions import IsAdminOrPeso, IsAdminOrCoordinator
from apps.shared.models import User, TrackerResponse, Question
from collections import Counter
from django.db import models
from django.db.models import Q, Count
from statistics import mean
# OPTIMIZED: Import all helper functions from shared utils (no duplication)
from apps.shared.utils.stats import (
    safe_mode, safe_mean, safe_sample,
    safe_mode_related, safe_mean_related, safe_sample_related,
    convert_salary_range_to_number
)
from .decorators import cache_statistics

logger = logging.getLogger(__name__)

# Create your views here.


def count_self_employed_users(qs):
    """Return number of alumni marked self-employed via employment record or tracker answer."""
    # Debug logging to help diagnose self-employed detection
    self_employed_users = qs.filter(
        Q(employment__self_employed=True) |
        Q(tracker_data__q_employment_type__iregex=r'self[\s\-]*employ')
    ).distinct()
    
    count = self_employed_users.count()
    
    # Log for debugging
    if count > 0:
        for user in self_employed_users[:5]:  # Log first 5
            emp_type = user.tracker_data.q_employment_type if hasattr(user, 'tracker_data') and user.tracker_data else 'N/A'
            emp_bool = user.employment.self_employed if hasattr(user, 'employment') and user.employment else False
            logger.info(f"Self-employed user found: {user.user_id} - Type: {emp_type}, Boolean: {emp_bool}")
    else:
        # Log why no one matched
        logger.info(f"No self-employed users found. Checking all employment types:")
        for user in qs[:5]:  # Check first 5 users
            emp_type = user.tracker_data.q_employment_type if hasattr(user, 'tracker_data') and user.tracker_data else 'N/A'
            emp_bool = user.employment.self_employed if hasattr(user, 'employment') and user.employment else False
            logger.info(f"User {user.user_id}: Type='{emp_type}', Boolean={emp_bool}")
    
    return count


def count_award_recipients(qs):
    """Return number of alumni who indicated receiving awards (tracker or employment details)."""
    award_tracker_filter = Q(tracker_data__q_awards_received__icontains='yes')
    award_employment_filter = (
        Q(employment__awards_recognition_current__isnull=False)
        & ~Q(employment__awards_recognition_current__exact='')
    )
    return (
        qs.filter(award_tracker_filter | award_employment_filter)
        .distinct()
        .count()
    )

@cache_statistics(timeout=30)  # Cache for 30 seconds
@api_view(["GET"])
@permission_classes([IsAdminOrPeso])  # 🔒 SECURITY FIX: Changed from IsAuthenticated - Statistics for admins/PESO only
def alumni_statistics_view(request):
    """
    Simple overview of alumni employment status counts and available years - Admin/PESO only
    
    ⚠️ SECURITY: Restricted to Admin/PESO to protect aggregate alumni data
    Supports multi-select: year and program can be comma-separated values
    """
    try:
        year = request.GET.get('year')
        course = request.GET.get('program')
        
        # OPTIMIZED: Add select_related() for performance
        alumni_qs = User.objects.filter(account_type__user=True).select_related(
            'academic_info', 'employment', 'tracker_data'
        )
        
        # Support multi-select: year can be comma-separated (e.g., "2020,2021,2022")
        if year and year != 'ALL':
            years_list = [y.strip() for y in year.split(',') if y.strip()]
            if years_list:
                alumni_qs = alumni_qs.filter(academic_info__year_graduated__in=years_list)
        
        # Support multi-select: program can be comma-separated (e.g., "BSIT,BSIS")
        if course and course != 'ALL':
            programs_list = [p.strip() for p in course.split(',') if p.strip()]
            if programs_list:
                alumni_qs = alumni_qs.filter(academic_info__program__in=programs_list)

        total_alumni = alumni_qs.count()

        # OPTIMIZED: Use database aggregation instead of Python loops
        from apps.shared.models import TrackerData, EmploymentHistory
        from django.db.models import Q, Count, Case, When, IntegerField
        
        # Count employment status using database aggregation
        employment_stats = TrackerData.objects.filter(user__in=alumni_qs).aggregate(
            employed=Count('id', filter=Q(q_employment_status__iexact='yes')),
            unemployed=Count('id', filter=Q(q_employment_status__iexact='no')),
            pending_tracker=Count(
                'id',
                filter=(
                    Q(q_employment_status__isnull=True)
                    | Q(q_employment_status='')
                    | Q(q_employment_status__iexact='pending')
                    | Q(q_employment_status__iexact='untracked')
                    | Q(q_employment_status__iexact='n/a')
                    | Q(q_employment_status__iexact='na')
                ),
            ),
        )
        employed = employment_stats['employed']
        unemployed = employment_stats['unemployed']
        pending_tracker = employment_stats['pending_tracker']

        # Count absorbed users (who are also employed)
        absorbed = EmploymentHistory.objects.filter(user__in=alumni_qs, absorbed=True).count()
        
        # Alumni without TrackerData are also considered pending
        alumni_without_tracker = alumni_qs.filter(tracker_data__isnull=True).count()
        
        # Total pending = alumni without tracker + alumni with tracker but no employment status
        pending = pending_tracker + alumni_without_tracker

        # NEW LOGIC: Combine employed and absorbed, but keep track of absorbed count for indicator
        status_counts = {
            'Employed': employed,  # This includes both employed and absorbed
            'Unemployed': unemployed,
            'Pending': pending,
            'Absorbed_Count': absorbed,  # Keep track of absorbed count for frontend indicator
        }

        year_counts = Counter(
            User.objects.filter(account_type__user=True)
            .select_related('academic_info')
            .values_list('academic_info__year_graduated', flat=True)
        )
        filtered_year_counts = {y: c for y, c in year_counts.items() if y is not None}
        return JsonResponse({
            'success': True,
            'status_counts': status_counts,
            'years': [
                {'year': year, 'count': count}
                for year, count in sorted(filtered_year_counts.items(), reverse=True)
            ]
        })
    except Exception as e:
        logger.error(f"Error in alumni_statistics_view: {e}")
        return JsonResponse({'success': False, 'message': 'Failed to load alumni statistics'}, status=500)

@cache_statistics(timeout=30)  # Cache for 30 seconds
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def generate_statistics_view(request):
    try:
        year = request.GET.get('year', 'ALL')
        course = request.GET.get('program', 'ALL')
        stats_type = request.GET.get('type', 'ALL')
        
        # OPTIMIZED: Add select_related() to prevent N+1 queries
        alumni_qs = User.objects.filter(account_type__user=True).select_related(
            'profile', 'academic_info', 'employment', 'tracker_data', 'ojt_info'
        )
        
        # Support multi-select: year can be comma-separated (e.g., "2020,2021,2022")
        if year and year != 'ALL':
            years_list = [y.strip() for y in year.split(',') if y.strip()]
            if years_list:
                alumni_qs = alumni_qs.filter(academic_info__year_graduated__in=years_list)
        
        # Support multi-select: program can be comma-separated (e.g., "BSIT,BSIS")
        if course and course != 'ALL':
            programs_list = [p.strip() for p in course.split(',') if p.strip()]
            if programs_list:
                alumni_qs = alumni_qs.filter(academic_info__program__in=programs_list)
        
        total_alumni = alumni_qs.count()
        
        if stats_type == 'ALL':
            # Return all employment status counts and professional aggregates
            status_counts = Counter(alumni_qs.values_list('user_status', flat=True))
            # Professional aggregates
            return JsonResponse({
                'success': True,
                'type': 'ALL',
                'total_alumni': total_alumni,
                'status_counts': dict(status_counts),
                'most_common_company': safe_mode_related(alumni_qs, 'employment__company_name_current'),
                'most_common_position': safe_mode_related(alumni_qs, 'employment__position_current'),
                'most_common_sector': safe_mode_related(alumni_qs, 'employment__sector_current'),
                'average_salary': safe_mean_related(alumni_qs, 'employment__salary_current'),
                'most_common_awards': safe_mode_related(alumni_qs, 'employment__awards_recognition_current'),
                'most_common_school': safe_mode_related(alumni_qs, 'academic_info__school_name'),
                'most_common_unemployment_reason': safe_mode_related(alumni_qs, 'employment__unemployment_reason'),
                'most_common_civil_status': safe_mode_related(alumni_qs, 'profile__civil_status'),
                'average_age': safe_mean_related(alumni_qs, 'profile__age'),
                'sample_email': safe_sample_related(alumni_qs, 'profile__email'),
                'year': year,
                'course': course
            })
        
        elif stats_type == 'QPRO':
            # QPRO: Employment statistics - Use same logic as alumni_statistics_view
            try:
                from apps.shared.models import TrackerData, EmploymentHistory
                from django.db.models import Q, Count
                
                # Use same logic as alumni_statistics_view for consistency
                employment_stats = TrackerData.objects.filter(user__in=alumni_qs).aggregate(
                    employed=Count('id', filter=Q(q_employment_status__iexact='yes')),
                    unemployed=Count('id', filter=Q(q_employment_status__iexact='no'))
                )
                
                employed = employment_stats['employed']
                unemployed = employment_stats['unemployed']
                absorbed = EmploymentHistory.objects.filter(user__in=alumni_qs, absorbed=True).count()
                
                total_alumni_count = total_alumni  # preserve original count explicitly
                # Calculate untracked: alumni who haven't answered tracker at all
                # Check if they've ACTUALLY submitted by looking for non-null employment status or submitted timestamp
                alumni_with_tracker = TrackerData.objects.filter(
                    user__in=alumni_qs
                ).filter(
                    Q(q_employment_status__isnull=False) & ~Q(q_employment_status='') |
                    Q(tracker_submitted_at__isnull=False)
                ).values_list('user_id', flat=True).distinct().count()
                untracked = max(total_alumni_count - alumni_with_tracker, 0)
            except Exception as e:
                logger.error(f"Error in QPRO stats calculation: {e}")
                # Fallback to simple calculation
                employed = 0
                unemployed = 0
                absorbed = 0
                untracked = total_alumni
            employment_rate = (employed / total_alumni_count * 100) if total_alumni_count > 0 else 0
            awards_count = count_award_recipients(alumni_qs)
            self_employed_count = count_self_employed_users(alumni_qs)

            # Calculate statistics with proper null handling
            most_common_company = safe_mode_related(alumni_qs, 'employment__company_name_current')
            most_common_position = safe_mode_related(alumni_qs, 'employment__position_current')
            most_common_sector = safe_mode_related(alumni_qs, 'employment__sector_current')
            average_salary = safe_mean_related(alumni_qs, 'employment__salary_current')
            most_common_awards = safe_mode_related(alumni_qs, 'employment__awards_recognition_current')
            most_common_unemployment_reason = safe_mode_related(alumni_qs, 'employment__unemployment_reason')
            most_common_civil_status = safe_mode_related(alumni_qs, 'profile__civil_status')
            average_age = safe_mean_related(alumni_qs, 'profile__age')
            sample_email = safe_sample_related(alumni_qs, 'profile__email')
            
            return JsonResponse({
                'success': True,
                'type': 'QPRO',
                'total_alumni': total_alumni_count,
                'employment_rate': round(employment_rate, 2),
                'employed_count': employed,
                'unemployed_count': unemployed,
                'untracked_count': untracked,
                'tracker_employed_count': employed,
                'tracker_unemployed_count': unemployed,
                # Real data fields using related models with null safety
                'most_common_company': most_common_company,
                'most_common_position': most_common_position,
                'most_common_sector': most_common_sector,
                'average_salary': average_salary,
                'most_common_awards': most_common_awards,
                'most_common_unemployment_reason': most_common_unemployment_reason,
                'most_common_civil_status': most_common_civil_status,
                'average_age': average_age,
                'sample_email': sample_email,
                'awards_count': awards_count,
                'self_employed_count': self_employed_count,
                'year': year,
                'course': course
            })
        
        elif stats_type == 'CHED':
            # CHED: Further study and job alignment statistics
            pursuing_study = alumni_qs.filter(academic_info__pursue_further_study__iexact='yes').count()
            tracker_pursuing_study = alumni_qs.filter(academic_info__q_pursue_study__iexact='yes').count()
            
            # Job alignment statistics using new fields
            job_aligned = alumni_qs.filter(employment__job_alignment_status='aligned').count()
            self_employed = count_self_employed_users(alumni_qs)
            not_aligned = alumni_qs.filter(employment__job_alignment_status='not_aligned').count()
            
            # REMOVED: Dead code querying empty Ched model (always returned 0)
            # job_aligned already contains the correct count from EmploymentHistory
            
            # Calculate statistics with proper null handling
            most_common_school = safe_mode_related(alumni_qs, 'academic_info__school_name')
            most_common_program = safe_mode_related(alumni_qs, 'academic_info__program')
            most_common_awards = safe_mode_related(alumni_qs, 'employment__awards_recognition_current')
            most_common_civil_status = safe_mode_related(alumni_qs, 'profile__civil_status')
            average_age = safe_mean_related(alumni_qs, 'profile__age')
            sample_email = safe_sample_related(alumni_qs, 'profile__email')
            awards_count = count_award_recipients(alumni_qs)
            
            return JsonResponse({
                'success': True,
                'type': 'CHED',
                'total_alumni': total_alumni,
                'pursuing_further_study': pursuing_study,
                'tracker_pursuing_study': tracker_pursuing_study,
                'further_study_rate': round((pursuing_study / total_alumni * 100), 2) if total_alumni > 0 else 0,
                'job_alignment_count': job_aligned,  # FIXED: Use actual aligned count, not legacy Ched model
                'job_aligned_count': job_aligned,
                'self_employed_count': self_employed,
                'not_aligned_count': not_aligned,
                'job_alignment_rate': round((job_aligned / total_alumni * 100), 2) if total_alumni > 0 else 0,
                # Real data fields using related models with null safety
                'most_common_school': most_common_school,
                'most_common_program': most_common_program,
                'most_common_awards': most_common_awards,
                'most_common_civil_status': most_common_civil_status,
                'average_age': average_age,
                'sample_email': sample_email,
                'awards_count': awards_count,
                'year': year,
                'course': course
            })
        
        elif stats_type == 'SUC':
            # SUC: High position and salary statistics - OPTIMIZED
            high_position = alumni_qs.filter(employment__high_position=True).count()
            job_aligned = alumni_qs.filter(employment__job_alignment_status='aligned').count()
            
            # OPTIMIZED: Use database aggregation for sector and scope counts
            from apps.shared.models import TrackerData
            from django.db.models import Q, Count
            
            sector_scope_stats = TrackerData.objects.filter(user__in=alumni_qs).aggregate(
                government=Count('id', filter=Q(q_sector_current__iexact='public') | Q(q_sector_current__iexact='government')),
                private=Count('id', filter=Q(q_sector_current__iexact='private')),
                local=Count('id', filter=Q(q_scope_current__iexact='local')),
                international=Count('id', filter=Q(q_scope_current__iexact='international'))
            )
            
            government_count = sector_scope_stats['government']
            private_count = sector_scope_stats['private']
            local_count = sector_scope_stats['local']
            international_count = sector_scope_stats['international']
            
            high_position_rate = (high_position / total_alumni * 100) if total_alumni > 0 else 0
            job_alignment_rate = (job_aligned / total_alumni * 100) if total_alumni > 0 else 0
            
            # Calculate statistics with proper null handling
            most_common_company = safe_mode_related(alumni_qs, 'employment__company_name_current')
            most_common_position = safe_mode_related(alumni_qs, 'employment__position_current')
            most_common_sector = safe_mode_related(alumni_qs, 'employment__sector_current')
            most_common_awards = safe_mode_related(alumni_qs, 'employment__awards_recognition_current')
            most_common_civil_status = safe_mode_related(alumni_qs, 'profile__civil_status')
            average_age = safe_mean_related(alumni_qs, 'profile__age')
            sample_email = safe_sample_related(alumni_qs, 'profile__email')
            awards_count = count_award_recipients(alumni_qs)
            self_employed = count_self_employed_users(alumni_qs)
            
            return JsonResponse({
                'success': True,
                'type': 'SUC',
                'total_alumni': total_alumni,
                'high_position_count': high_position,
                'high_position_rate': round(high_position_rate, 2),
                'job_aligned_count': job_aligned,
                'job_alignment_rate': round(job_alignment_rate, 2),
                'public_count': government_count,
                'private_count': private_count,
                'local_count': local_count,
                'international_count': international_count,
                'average_salary': safe_mean_related(alumni_qs, 'employment__salary_current'),
                # Real data fields using related models with null safety
                'most_common_company': most_common_company,
                'most_common_position': most_common_position,
                'most_common_sector': most_common_sector,
                'most_common_awards': most_common_awards,
                'most_common_civil_status': most_common_civil_status,
                'average_age': average_age,
                'sample_email': sample_email,
                'self_employed_count': self_employed,
                'awards_count': awards_count,
                'year': year,
                'course': course
            })
        
        elif stats_type == 'AACUP':
            # AACUP: Absorbed, employed, high position statistics - OPTIMIZED
            from apps.shared.models import TrackerData, EmploymentHistory
            from django.db.models import Q, Count
            
            # Count employed from BOTH TrackerData and EmploymentHistory to avoid missing users
            # Use EmploymentHistory as primary source since it's more complete
            try:
                # Try to get employment status from tracker first
                employment_stats = TrackerData.objects.filter(user__in=alumni_qs).aggregate(
                    employed=Count('id', filter=Q(q_employment_status__iexact='yes'))
                )
                employed_from_tracker = employment_stats['employed']
                
                # Also count from employment history for users who might not have tracker yet
                employed_from_history = alumni_qs.filter(
                    Q(employment__isnull=False) &
                    ~Q(employment__position_current__isnull=True) &
                    ~Q(employment__position_current='')
                ).count()
                
                # Use the higher count (more conservative estimate)
                employed = max(employed_from_tracker, employed_from_history)
            except Exception as e:
                logger.error(f"Error counting employed in AACUP: {e}")
                # Fallback: count any alumni with employment data
                employed = alumni_qs.filter(employment__isnull=False).count()
            
            absorbed = alumni_qs.filter(employment__absorbed=True).count()
            high_position = alumni_qs.filter(employment__high_position=True).count()
            self_employed = count_self_employed_users(alumni_qs)
            awards_received = count_award_recipients(alumni_qs)
            
            employment_rate = (employed / total_alumni * 100) if total_alumni > 0 else 0
            absorption_rate = (absorbed / total_alumni * 100) if total_alumni > 0 else 0
            high_position_rate = (high_position / total_alumni * 100) if total_alumni > 0 else 0
            
            # Calculate statistics with proper null handling
            most_common_company = safe_mode_related(alumni_qs, 'employment__company_name_current')
            most_common_position = safe_mode_related(alumni_qs, 'employment__position_current')
            most_common_sector = safe_mode_related(alumni_qs, 'employment__sector_current')
            average_salary = safe_mean_related(alumni_qs, 'employment__salary_current')
            most_common_awards = safe_mode_related(alumni_qs, 'employment__awards_recognition_current')
            most_common_school = safe_mode_related(alumni_qs, 'academic_info__school_name')
            most_common_civil_status = safe_mode_related(alumni_qs, 'profile__civil_status')
            average_age = safe_mean_related(alumni_qs, 'profile__age')
            sample_email = safe_sample_related(alumni_qs, 'profile__email')
            
            return JsonResponse({
                'success': True,
                'type': 'AACUP',
                'total_alumni': total_alumni,
                'employment_rate': round(employment_rate, 2),
                'absorption_rate': round(absorption_rate, 2),
                'high_position_rate': round(high_position_rate, 2),
                'employed_count': employed,
                'absorbed_count': absorbed,
                'high_position_count': high_position,
                'self_employed_count': self_employed,
                'awards_count': awards_received,
                # Real data fields using related models with null safety
                'most_common_company': most_common_company,
                'most_common_position': most_common_position,
                'most_common_sector': most_common_sector,
                'average_salary': average_salary,
                'most_common_awards': most_common_awards,
                'most_common_school': most_common_school,
                'most_common_civil_status': most_common_civil_status,
                'average_age': average_age,
                'sample_email': sample_email,
                'year': year,
                'course': course
            })
        
        elif stats_type == 'HIGH_POSITION':
            # HIGH_POSITION: Detailed statistics for alumni with high positions
            high_position_alumni = alumni_qs.filter(employment__high_position=True)
            high_position_count = high_position_alumni.count()
            
            # Get detailed information about high position alumni
            high_position_data = []
            for alum in high_position_alumni:
                profile = getattr(alum, 'profile', None)
                academic = getattr(alum, 'academic_info', None)
                employment = getattr(alum, 'employment', None)
                
                high_position_data.append({
                    'ctu_id': alum.acc_username,
                    'name': f"{alum.f_name} {alum.m_name or ''} {alum.l_name}".strip(),
                    'position': employment.position_current if employment else None,
                    'company': employment.company_name_current if employment else None,
                    'sector': employment.sector_current if employment else None,
                    'course': academic.program if academic else None,
                    'year_graduated': academic.year_graduated if academic else None,
                    'email': profile.email if profile else None,
                    'phone': profile.phone_num if profile else None,
                    'address': profile.address if profile else None,
                })
            
            # Calculate statistics
            high_position_rate = (high_position_count / total_alumni * 100) if total_alumni > 0 else 0
            
            return JsonResponse({
                'success': True,
                'type': 'HIGH_POSITION',
                'total_alumni': total_alumni,
                'high_position_count': high_position_count,
                'high_position_rate': round(high_position_rate, 2),
                'high_position_data': high_position_data,
                'most_common_position': safe_mode_related(high_position_alumni, 'employment__position_current'),
                'most_common_company': safe_mode_related(high_position_alumni, 'employment__company_name_current'),
                'most_common_sector': safe_mode_related(high_position_alumni, 'employment__sector_current'),
                'most_common_course': safe_mode_related(high_position_alumni, 'academic_info__program'),
                'average_salary': safe_mean_related(high_position_alumni, 'employment__salary_current'),
                'year': year,
                'course': course
            })
        
        else:
            # Default fallback
            status_counts = Counter(alumni_qs.values_list('user_status', flat=True))
            return JsonResponse({
                'success': True,
                'type': 'DEFAULT',
                'total_alumni': total_alumni,
                'status_counts': dict(status_counts),
                'year': year,
                'course': course
            })
    except Exception as e:
        logger.error(f"Error in generate_statistics_view: {e}")
        return JsonResponse({'success': False, 'message': 'Failed to generate statistics'}, status=500)

@api_view(["GET"])
@permission_classes([IsAdminOrPeso])  # 🔒 SECURITY FIX: Changed from IsAuthenticated - Export for admins/PESO only
def export_detailed_alumni_data(request):
    """
    Export detailed alumni data - Admin/PESO only
    
    ⚠️ SECURITY: Restricted to Admin/PESO - Exports sensitive alumni data
    Supports multi-select: year and program can be comma-separated values
    """
    try:
        year = request.GET.get('year', 'ALL')
        course = request.GET.get('program', 'ALL')
        
        # OPTIMIZED: Add select_related() to prevent N+1 queries during export
        alumni_qs = User.objects.filter(account_type__user=True).select_related(
            'profile', 'academic_info', 'employment', 'tracker_data', 'ojt_info'
        ).prefetch_related('trackerresponse_set')
        
        # Support multi-select: year can be comma-separated (e.g., "2020,2021,2022")
        if year and year != 'ALL':
            years_list = [y.strip() for y in year.split(',') if y.strip()]
            if years_list:
                alumni_qs = alumni_qs.filter(academic_info__year_graduated__in=years_list)
        
        # Support multi-select: program can be comma-separated (e.g., "BSIT,BSIS")
        if course and course != 'ALL':
            programs_list = [p.strip() for p in course.split(',') if p.strip()]
            if programs_list:
                alumni_qs = alumni_qs.filter(academic_info__program__in=programs_list)
        
        # Collect all tracker question texts that have been answered by any alumni in the queryset
        all_tracker_qids = set()
        for alum in alumni_qs:
            tracker_responses = TrackerResponse.objects.filter(user=alum).order_by('-submitted_at')
            latest_tracker = tracker_responses.first() if tracker_responses.exists() else None
            tracker_answers = latest_tracker.answers if latest_tracker and latest_tracker.answers else {}
            all_tracker_qids.update([int(qid) for qid in tracker_answers.keys() if str(qid).isdigit()])
        
        tracker_questions = {q.id: q.text for q in Question.objects.filter(id__in=all_tracker_qids)}
        tracker_columns = [tracker_questions[qid] for qid in sorted(tracker_questions.keys())]
        
        export_fields = [
            'CTU_ID', 'First_Name', 'Middle_Name', 'Last_Name', 'Gender', 'Birthdate', 'Year_Graduated', 'Program', 'Section',
            'Program', 'Status', 'Phone_Number', 'Email', 'Address', 'Civil_Status', 'Social_Media', 'Age',
            'Employment_Type', 'Company_Name_Current', 'Position_Current', 'Sector_Current', 'Scope_Current', 'Employment_Permanent',
            'Employment_Duration_Current', 'Salary_Current', 'Supporting_Document_Current', 'Awards_Recognition_Current', 
            'Supporting_Document_Awards_Recognition', 'Unemployment_Reason', 'Pursue_Further_Study', 'Date_Started', 
            'School_Name', 'Profile_Pic', 'Profile_Bio', 'Profile_Resume'
        ]
        
        export_columns = []
        seen = set()
        for field in export_fields:
            if field not in seen:
                export_columns.append(field)
                seen.add(field)
        for qtext in tracker_columns:
            if qtext not in seen:
                export_columns.append(qtext)
                seen.add(qtext)
        
        detailed_data = []
        for alumni in alumni_qs:
            try:
                # Get related data safely
                profile = getattr(alumni, 'profile', None)
                academic_info = getattr(alumni, 'academic_info', None)
                employment = getattr(alumni, 'employment', None)
                tracker_data = getattr(alumni, 'tracker_data', None)
                
                # Helper function to safely convert file fields to strings
                def safe_file_field(field_value):
                    if field_value and hasattr(field_value, 'url'):
                        return field_value.url
                    elif field_value and hasattr(field_value, 'name'):
                        return field_value.name
                    elif field_value:
                        return str(field_value)
                    return ''
                
                data = {
                    'CTU_ID': alumni.acc_username,
                    'First_Name': alumni.f_name,
                    'Middle_Name': alumni.m_name or '',
                    'Last_Name': alumni.l_name,
                    'Gender': alumni.gender,
                    'Birthdate': str(profile.birthdate) if profile and profile.birthdate else '',
                    'Year_Graduated': getattr(academic_info, 'year_graduated', None) if academic_info else None,
                    'Program': getattr(academic_info, 'program', None) if academic_info else None,
                    'Section': getattr(academic_info, 'section', None) if academic_info else '',
                    'Status': alumni.user_status,
                    'Phone_Number': getattr(profile, 'phone_num', None) if profile else None,
                    'Email': getattr(profile, 'email', None) if profile else None,
                    'Address': getattr(profile, 'address', None) if profile else None,
                    'Civil_Status': getattr(profile, 'civil_status', None) if profile else None,
                    'Social_Media': getattr(profile, 'social_media', None) if profile else None,
                    'Age': getattr(profile, 'age', None) if profile else None,
                    # Employment data - Prefer TrackerData (Part III) for current accurate data
                    'Employment_Type': getattr(tracker_data, 'q_employment_type', None) if tracker_data else None,
                    'Company_Name_Current': getattr(tracker_data, 'q_company_name', None) if tracker_data else (getattr(employment, 'company_name_current', None) if employment else None),
                    'Position_Current': getattr(tracker_data, 'q_current_position', None) if tracker_data else (getattr(employment, 'position_current', None) if employment else None),
                    'Sector_Current': getattr(tracker_data, 'q_sector_current', None) if tracker_data else (getattr(employment, 'sector_current', None) if employment else None),
                    'Scope_Current': getattr(tracker_data, 'q_scope_current', None) if tracker_data else (getattr(employment, 'scope_current', None) if employment else None),
                    'Employment_Permanent': getattr(tracker_data, 'q_employment_permanent', None) if tracker_data else None,
                    'Employment_Duration_Current': getattr(tracker_data, 'q_employment_duration', None) if tracker_data else (getattr(employment, 'employment_duration_current', None) if employment else None),
                    'Salary_Current': getattr(tracker_data, 'q_salary_range', None) if tracker_data else (getattr(employment, 'salary_current', None) if employment else None),
                    'Supporting_Document_Current': safe_file_field(getattr(tracker_data, 'q_employment_document', None)) if tracker_data else (safe_file_field(getattr(employment, 'supporting_document_current', None)) if employment else ''),
                    'Awards_Recognition_Current': getattr(tracker_data, 'q_awards_received', None) if tracker_data else (getattr(employment, 'awards_recognition_current', None) if employment else None),
                    'Supporting_Document_Awards_Recognition': safe_file_field(getattr(tracker_data, 'q_awards_document', None)) if tracker_data else (safe_file_field(getattr(employment, 'supporting_document_awards_recognition', None)) if employment else ''),
                    'Unemployment_Reason': getattr(tracker_data, 'q_unemployment_reason', None) if tracker_data else (getattr(employment, 'unemployment_reason', None) if employment else None),
                    'Pursue_Further_Study': getattr(academic_info, 'pursue_further_study', None) if academic_info else None,
                    'Date_Started': getattr(academic_info, 'q_study_start_date', None) if academic_info else None,
                    'School_Name': getattr(academic_info, 'school_name', None) if academic_info else None,
                    'Profile_Pic': safe_file_field(getattr(profile, 'profile_pic', None)) if profile else '',
                    'Profile_Bio': getattr(profile, 'profile_bio', None) if profile else None,
                    'Profile_Resume': safe_file_field(getattr(profile, 'profile_resume', None)) if profile else '',
                }
                # Add tracker answers and submission date
                tracker_responses = TrackerResponse.objects.filter(user=alumni).order_by('-submitted_at')
                latest_tracker = tracker_responses.first() if tracker_responses.exists() else None
                tracker_answers = latest_tracker.answers if latest_tracker and latest_tracker.answers else {}
                
                # Add tracker submission date for quarterly calculations
                data['Tracker_Submission_Date'] = latest_tracker.submitted_at.strftime('%Y-%m-%d') if latest_tracker and latest_tracker.submitted_at else ''
                
                for qid, qtext in tracker_questions.items():
                    answer = tracker_answers.get(str(qid)) or tracker_answers.get(qid)
                    if isinstance(answer, list):
                        answer = ', '.join(str(a) for a in answer)
                    # Handle file uploads in tracker answers
                    elif isinstance(answer, dict) and answer.get('type') == 'file':
                        answer = answer.get('filename', 'File uploaded')
                    data[qtext] = answer if answer is not None else ''
                
                # Add tracker data file fields
                tracker_data = getattr(alumni, 'tracker_data', None)
                if tracker_data:
                    data['Awards_Document'] = safe_file_field(tracker_data.q_awards_document)
                    data['Employment_Document'] = safe_file_field(tracker_data.q_employment_document)
                
                detailed_data.append(data)
            except Exception as e:
                logger.error(f"Error processing alumni {alumni.user_id} for export: {e}")
                # Add a minimal record with error info
                detailed_data.append({
                    'CTU_ID': alumni.acc_username,
                    'First_Name': alumni.f_name,
                    'Last_Name': alumni.l_name,
                    'Error': f'Failed to process: {str(e)}'
                })
        
        return JsonResponse({'detailed_data': detailed_data})
    except Exception as e:
        logger.error(f"Error in export_detailed_alumni_data: {e}")
        return JsonResponse({'success': False, 'message': 'Failed to export detailed data'}, status=500)


@api_view(["GET"])
@permission_classes([IsAdminOrPeso])
def chart_statistics_by_year(request):
    """
    Get employment statistics grouped by year for chart visualization.
    Returns E (Employed), UE (Unemployed), NT (Not Tracked), and GT (Graduate Tracing Rate %)
    for each year, filtered by selected programs.
    
    Supports multi-select: year and program can be comma-separated values
    """
    try:
        year = request.GET.get('year', 'ALL')
        course = request.GET.get('program', 'ALL')
        
        from apps.shared.models import TrackerData, EmploymentHistory
        from django.db.models import Q, Count
        
        # Get base alumni queryset
        alumni_qs = User.objects.filter(account_type__user=True).select_related(
            'academic_info', 'employment', 'tracker_data'
        )
        
        # Filter by program if specified
        if course and course != 'ALL':
            programs_list = [p.strip() for p in course.split(',') if p.strip()]
            if programs_list:
                alumni_qs = alumni_qs.filter(academic_info__program__in=programs_list)
        
        # Get all available years from the filtered alumni
        all_years = alumni_qs.values_list(
            'academic_info__year_graduated', flat=True
        ).distinct().order_by('academic_info__year_graduated')
        all_years = [y for y in all_years if y is not None]
        
        # If specific years are selected, filter to only those
        if year and year != 'ALL':
            years_list = [y.strip() for y in year.split(',') if y.strip()]
            if years_list:
                all_years = [y for y in all_years if str(y) in years_list]
        
        chart_data = []
        
        for yr in all_years:
            # Get alumni for this specific year
            year_alumni = alumni_qs.filter(academic_info__year_graduated=yr)
            total_for_year = year_alumni.count()
            
            if total_for_year == 0:
                continue
            
            # Count employment status using TrackerData
            employment_stats = TrackerData.objects.filter(user__in=year_alumni).aggregate(
                employed=Count('id', filter=Q(q_employment_status__iexact='yes')),
                unemployed=Count('id', filter=Q(q_employment_status__iexact='no'))
            )
            
            employed = employment_stats['employed'] or 0
            unemployed = employment_stats['unemployed'] or 0
            
            # Calculate not tracked: alumni who haven't answered tracker
            alumni_with_tracker = TrackerData.objects.filter(
                user__in=year_alumni
            ).filter(
                Q(q_employment_status__isnull=False) & ~Q(q_employment_status='') |
                Q(tracker_submitted_at__isnull=False)
            ).values_list('user_id', flat=True).distinct().count()
            
            not_tracked = max(total_for_year - alumni_with_tracker, 0)
            
            # Calculate Graduate Tracing Rate (percentage of tracked alumni)
            tracked = employed + unemployed
            tracking_rate = round((tracked / total_for_year * 100), 2) if total_for_year > 0 else 0
            
            chart_data.append({
                'year': str(yr),
                'E': employed,           # Employed
                'UE': unemployed,        # Unemployed
                'NT': not_tracked,       # Not Tracked
                'GT': tracking_rate,     # Graduate Tracing Rate %
                'total': total_for_year
            })
        
        # Sort by year
        chart_data.sort(key=lambda x: x['year'])
        
        return JsonResponse({
            'success': True,
            'chart_data': chart_data,
            'years': [d['year'] for d in chart_data],
            'programs': course
        })
        
    except Exception as e:
        logger.error(f"Error in chart_statistics_by_year: {e}")
        return JsonResponse({'success': False, 'message': 'Failed to generate chart data'}, status=500)


@api_view(["GET"])
@permission_classes([IsAdminOrPeso])
def ched_chart_statistics_by_year(request):
    """
    Get CHED statistics grouped by year for chart visualization.
    Returns Pursuing Further Study, Job Alignment, Self-Employed for each year.
    """
    try:
        year = request.GET.get('year', 'ALL')
        course = request.GET.get('program', 'ALL')
        
        from apps.shared.models import TrackerData, EmploymentHistory
        from django.db.models import Q, Count
        
        # Get base alumni queryset
        alumni_qs = User.objects.filter(account_type__user=True).select_related(
            'academic_info', 'employment', 'tracker_data'
        )
        
        # Filter by program if specified
        if course and course != 'ALL':
            programs_list = [p.strip() for p in course.split(',') if p.strip()]
            if programs_list:
                alumni_qs = alumni_qs.filter(academic_info__program__in=programs_list)
        
        # Get all available years
        all_years = alumni_qs.values_list(
            'academic_info__year_graduated', flat=True
        ).distinct().order_by('academic_info__year_graduated')
        all_years = [y for y in all_years if y is not None]
        
        # If specific years are selected, filter to only those
        if year and year != 'ALL':
            years_list = [y.strip() for y in year.split(',') if y.strip()]
            if years_list:
                all_years = [y for y in all_years if str(y) in years_list]
        
        chart_data = []
        
        for yr in all_years:
            year_alumni = alumni_qs.filter(academic_info__year_graduated=yr)
            total_for_year = year_alumni.count()
            
            if total_for_year == 0:
                continue
            
            # Pursuing Further Study - using academic_info.pursue_further_study field
            pursuing_study = year_alumni.filter(
                Q(academic_info__pursue_further_study__iexact='yes')
            ).count()
            
            # Job Alignment - using employment.job_alignment_status field
            job_aligned = year_alumni.filter(
                employment__job_alignment_status='aligned'
            ).count()
            
            # Self-Employed - check employment type from TrackerData
            tracker_data = TrackerData.objects.filter(user__in=year_alumni)
            self_employed = tracker_data.filter(
                Q(q_employment_type__icontains='self') |
                Q(q_employment_type__icontains='business') |
                Q(q_employment_type__icontains='freelance')
            ).count()
            
            chart_data.append({
                'year': str(yr),
                'PFS': pursuing_study,      # Pursuing Further Study
                'JA': job_aligned,          # Job Alignment
                'SE': self_employed,        # Self-Employed
                'total': total_for_year
            })
        
        chart_data.sort(key=lambda x: x['year'])
        
        return JsonResponse({
            'success': True,
            'chart_data': chart_data,
            'years': [d['year'] for d in chart_data],
            'programs': course
        })
        
    except Exception as e:
        logger.error(f"Error in ched_chart_statistics_by_year: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return JsonResponse({'success': False, 'message': 'Failed to generate CHED chart data'}, status=500)


@api_view(["GET"])
@permission_classes([IsAdminOrPeso])
def suc_chart_statistics_by_year(request):
    """
    Get SUC statistics grouped by year for chart visualization.
    Returns High Position, Government, Private, Local, International for each year.
    """
    try:
        year = request.GET.get('year', 'ALL')
        course = request.GET.get('program', 'ALL')
        
        from apps.shared.models import TrackerData, EmploymentHistory
        from django.db.models import Q, Count
        
        # Get base alumni queryset
        alumni_qs = User.objects.filter(account_type__user=True).select_related(
            'academic_info', 'employment', 'tracker_data'
        )
        
        # Filter by program if specified
        if course and course != 'ALL':
            programs_list = [p.strip() for p in course.split(',') if p.strip()]
            if programs_list:
                alumni_qs = alumni_qs.filter(academic_info__program__in=programs_list)
        
        # Get all available years
        all_years = alumni_qs.values_list(
            'academic_info__year_graduated', flat=True
        ).distinct().order_by('academic_info__year_graduated')
        all_years = [y for y in all_years if y is not None]
        
        # If specific years are selected, filter to only those
        if year and year != 'ALL':
            years_list = [y.strip() for y in year.split(',') if y.strip()]
            if years_list:
                all_years = [y for y in all_years if str(y) in years_list]
        
        chart_data = []
        
        for yr in all_years:
            year_alumni = alumni_qs.filter(academic_info__year_graduated=yr)
            total_for_year = year_alumni.count()
            
            if total_for_year == 0:
                continue
            
            # High Position count - using employment.high_position field
            high_position = year_alumni.filter(employment__high_position=True).count()
            
            # Get TrackerData for sector and scope stats
            tracker_data = TrackerData.objects.filter(user__in=year_alumni)
            
            # Government (Public sector) - using q_sector_current field
            government = tracker_data.filter(
                Q(q_sector_current__iexact='public') | 
                Q(q_sector_current__iexact='government')
            ).count()
            
            # Private sector - using q_sector_current field
            private = tracker_data.filter(
                Q(q_sector_current__iexact='private')
            ).count()
            
            # Local employment - using q_scope_current field
            local = tracker_data.filter(
                Q(q_scope_current__iexact='local')
            ).count()
            
            # International employment - using q_scope_current field
            international = tracker_data.filter(
                Q(q_scope_current__iexact='international')
            ).count()
            
            chart_data.append({
                'year': str(yr),
                'HP': high_position,    # High Position
                'GOV': government,      # Government
                'PVT': private,         # Private
                'LOC': local,           # Local
                'INTL': international,  # International
                'total': total_for_year
            })
        
        chart_data.sort(key=lambda x: x['year'])
        
        return JsonResponse({
            'success': True,
            'chart_data': chart_data,
            'years': [d['year'] for d in chart_data],
            'programs': course
        })
        
    except Exception as e:
        logger.error(f"Error in suc_chart_statistics_by_year: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return JsonResponse({'success': False, 'message': 'Failed to generate SUC chart data'}, status=500)


@api_view(["GET"])
@permission_classes([IsAdminOrPeso])
def aacup_chart_statistics_by_year(request):
    """
    Get AACUP statistics grouped by year for chart visualization.
    Returns Employed, Absorbed, High Position, Self-Employed, Awards Received for each year.
    """
    try:
        year = request.GET.get('year', 'ALL')
        course = request.GET.get('program', 'ALL')
        
        from apps.shared.models import TrackerData, EmploymentHistory
        from django.db.models import Q, Count
        
        # Get base alumni queryset
        alumni_qs = User.objects.filter(account_type__user=True).select_related(
            'academic_info', 'employment', 'tracker_data'
        )
        
        # Filter by program if specified
        if course and course != 'ALL':
            programs_list = [p.strip() for p in course.split(',') if p.strip()]
            if programs_list:
                alumni_qs = alumni_qs.filter(academic_info__program__in=programs_list)
        
        # Get all available years
        all_years = alumni_qs.values_list(
            'academic_info__year_graduated', flat=True
        ).distinct().order_by('academic_info__year_graduated')
        all_years = [y for y in all_years if y is not None]
        
        # If specific years are selected, filter to only those
        if year and year != 'ALL':
            years_list = [y.strip() for y in year.split(',') if y.strip()]
            if years_list:
                all_years = [y for y in all_years if str(y) in years_list]
        
        chart_data = []
        
        for yr in all_years:
            year_alumni = alumni_qs.filter(academic_info__year_graduated=yr)
            total_for_year = year_alumni.count()
            
            if total_for_year == 0:
                continue
            
            # Get tracker data
            tracker_data = TrackerData.objects.filter(user__in=year_alumni)
            
            # Employed count - using q_employment_status field
            employed = tracker_data.filter(
                Q(q_employment_status__iexact='yes')
            ).count()
            
            # Absorbed - using employment.absorbed field
            absorbed = year_alumni.filter(employment__absorbed=True).count()
            
            # High Position count - using employment.high_position field
            high_position = year_alumni.filter(employment__high_position=True).count()
            
            # Self-Employed - check employment type from TrackerData
            self_employed = tracker_data.filter(
                Q(q_employment_type__icontains='self') |
                Q(q_employment_type__icontains='business') |
                Q(q_employment_type__icontains='freelance')
            ).count()
            
            # Awards Received - check tracker data for awards (yes/no field)
            awards = tracker_data.filter(
                Q(q_awards_received__iexact='yes')
            ).count()
            
            chart_data.append({
                'year': str(yr),
                'EMP': employed,        # Employed
                'ABS': absorbed,        # Absorbed
                'HP': high_position,    # High Position
                'SE': self_employed,    # Self-Employed
                'AWD': awards,          # Awards Received
                'total': total_for_year
            })
        
        chart_data.sort(key=lambda x: x['year'])
        
        return JsonResponse({
            'success': True,
            'chart_data': chart_data,
            'years': [d['year'] for d in chart_data],
            'programs': course
        })
        
    except Exception as e:
        logger.error(f"Error in aacup_chart_statistics_by_year: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return JsonResponse({'success': False, 'message': 'Failed to generate AACUP chart data'}, status=500)


@api_view(["POST"])
@permission_classes([IsAdminOrPeso])
def generate_ai_summary(request):
    """
    Generate AI-powered summary for statistics using Groq API (Llama 3.1 70B).
    Accepts statistics data and returns a professional summary paragraph.
    """
    import requests
    from django.conf import settings
    
    try:
        stats_type = request.data.get('stats_type', 'QPRO')
        stats_data = request.data.get('stats_data', {})
        chart_data = request.data.get('chart_data', [])
        year_filter = request.data.get('year_filter', 'ALL')
        program_filter = request.data.get('program_filter', 'ALL')
        
        logger.info(f"AI Summary request received for {stats_type}")
        logger.info(f"Stats data: {stats_data}")
        
        # Build the prompt based on statistics type
        prompt = build_summary_prompt(stats_type, stats_data, chart_data, year_filter, program_filter)
        
        # Call Groq API
        groq_api_key = getattr(settings, 'GROQ_API_KEY', None)
        logger.info(f"Groq API Key configured: {bool(groq_api_key)}")
        
        if not groq_api_key:
            return JsonResponse({
                'success': False, 
                'message': 'Groq API key not configured'
            }, status=500)
        
        response = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {groq_api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'llama-3.3-70b-versatile',  # Updated to latest supported model
                'messages': [
                    {
                        'role': 'system',
                        'content': 'You are a professional data analyst specializing in alumni employment statistics. Generate comprehensive, insightful summaries that highlight key findings, trends, patterns, and implications. Write 5-7 sentences that provide meaningful analysis including: overall performance assessment, notable trends across years, comparison of metrics, areas of strength, areas needing improvement, and actionable recommendations. Be professional, factual, and analytical.'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'temperature': 0.7,
                'max_tokens': 500
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            summary = result['choices'][0]['message']['content'].strip()
            return JsonResponse({
                'success': True,
                'summary': summary,
                'stats_type': stats_type
            })
        else:
            logger.error(f"Groq API error: {response.status_code} - {response.text}")
            return JsonResponse({
                'success': False,
                'message': f'AI service error: {response.status_code}'
            }, status=500)
            
    except requests.exceptions.Timeout:
        logger.error("Groq API timeout")
        return JsonResponse({
            'success': False,
            'message': 'AI service timeout. Please try again.'
        }, status=504)
    except Exception as e:
        logger.error(f"Error generating AI summary: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'message': 'Failed to generate AI summary'
        }, status=500)


def build_summary_prompt(stats_type, stats_data, chart_data, year_filter, program_filter):
    """Build a detailed prompt for the AI based on statistics type and data."""
    
    base_context = f"Year Filter: {year_filter}, Program Filter: {program_filter}"
    
    if stats_type == 'QPRO':
        total = stats_data.get('total_alumni', 0)
        employed = stats_data.get('employed_count', 0)
        unemployed = stats_data.get('unemployed_count', 0)
        untracked = stats_data.get('untracked_count', 0)
        emp_rate = stats_data.get('employment_rate', 0)
        
        # Calculate tracking rate
        tracked = employed + unemployed
        tracking_rate = round((tracked / total * 100), 2) if total > 0 else 0
        
        prompt = f"""Analyze and summarize the following QPRO (Quarterly Progress Report on Outcomes) employment statistics:

{base_context}
- Total Alumni: {total}
- Employed: {employed} ({round(employed/total*100, 1) if total > 0 else 0}%)
- Unemployed: {unemployed} ({round(unemployed/total*100, 1) if total > 0 else 0}%)
- Not Tracked: {untracked} ({round(untracked/total*100, 1) if total > 0 else 0}%)
- Employment Rate: {emp_rate}%
- Graduate Tracking Rate: {tracking_rate}%

Yearly breakdown: {chart_data if chart_data else 'N/A'}

Provide a professional summary highlighting employment performance, tracking coverage, and any notable trends."""

    elif stats_type == 'CHED':
        total = stats_data.get('total_alumni', 0)
        pursuing = stats_data.get('pursuing_further_study', 0)
        job_aligned = stats_data.get('job_aligned_count', 0)
        self_employed = stats_data.get('self_employed_count', 0)
        
        prompt = f"""Analyze and summarize the following CHED (Commission on Higher Education) statistics:

{base_context}
- Total Alumni: {total}
- Pursuing Further Study: {pursuing} ({round(pursuing/total*100, 1) if total > 0 else 0}%)
- Job Aligned with Course: {job_aligned} ({round(job_aligned/total*100, 1) if total > 0 else 0}%)
- Self-Employed: {self_employed} ({round(self_employed/total*100, 1) if total > 0 else 0}%)

Yearly breakdown: {chart_data if chart_data else 'N/A'}

Provide a professional summary highlighting further education trends, job-course alignment, and entrepreneurship among graduates."""

    elif stats_type == 'SUC':
        total = stats_data.get('total_alumni', 0)
        high_pos = stats_data.get('high_position_count', 0)
        govt = stats_data.get('public_count', 0)
        private = stats_data.get('private_count', 0)
        local = stats_data.get('local_count', 0)
        intl = stats_data.get('international_count', 0)
        avg_salary = stats_data.get('average_salary', 'N/A')
        
        prompt = f"""Analyze and summarize the following SUC (State Universities and Colleges) statistics:

{base_context}
- Total Alumni: {total}
- High Position Holders: {high_pos} ({round(high_pos/total*100, 1) if total > 0 else 0}%)
- Government Sector: {govt} ({round(govt/total*100, 1) if total > 0 else 0}%)
- Private Sector: {private} ({round(private/total*100, 1) if total > 0 else 0}%)
- Local Employment: {local} ({round(local/total*100, 1) if total > 0 else 0}%)
- International Employment: {intl} ({round(intl/total*100, 1) if total > 0 else 0}%)
- Average Salary: {avg_salary}

Yearly breakdown: {chart_data if chart_data else 'N/A'}

Provide a professional summary highlighting career advancement, sector distribution, geographic employment patterns, and salary insights."""

    elif stats_type == 'AACUP':
        total = stats_data.get('total_alumni', 0)
        employed = stats_data.get('employed_count', 0)
        absorbed = stats_data.get('absorbed_count', 0)
        high_pos = stats_data.get('high_position_count', 0)
        self_emp = stats_data.get('self_employed_count', 0)
        awards = stats_data.get('awards_count', 0)
        
        prompt = f"""Analyze and summarize the following AACUP (Accrediting Agency of Chartered Colleges and Universities in the Philippines) statistics:

{base_context}
- Total Alumni: {total}
- Employed: {employed} ({round(employed/total*100, 1) if total > 0 else 0}%)
- Absorbed (Job-Course Aligned): {absorbed} ({round(absorbed/total*100, 1) if total > 0 else 0}%)
- High Position Holders: {high_pos} ({round(high_pos/total*100, 1) if total > 0 else 0}%)
- Self-Employed: {self_emp} ({round(self_emp/total*100, 1) if total > 0 else 0}%)
- Awards Received: {awards} ({round(awards/total*100, 1) if total > 0 else 0}%)

Yearly breakdown: {chart_data if chart_data else 'N/A'}

Provide a professional summary highlighting employment outcomes, career progression, entrepreneurship, and recognition/achievements among graduates."""

    else:
        prompt = f"""Analyze and summarize the following alumni statistics:

{base_context}
Statistics Data: {stats_data}
Chart Data: {chart_data}

Provide a professional summary of the key findings."""

    return prompt
