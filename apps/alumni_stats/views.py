"""Alumni statistics API endpoints providing overview, typed statistics, and export."""
import logging
from django.shortcuts import render
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from apps.shared.models import User, TrackerResponse, Question
from collections import Counter
from django.db import models
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

@cache_statistics(timeout=30)  # Cache for 30 seconds
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def alumni_statistics_view(request):
    """Simple overview of alumni employment status counts and available years."""
    try:
        year = request.GET.get('year')
        course = request.GET.get('program')
        
        # OPTIMIZED: Add select_related() for performance
        alumni_qs = User.objects.filter(account_type__user=True).select_related(
            'academic_info', 'employment', 'tracker_data'
        )
        
        if year and year != 'ALL':
            alumni_qs = alumni_qs.filter(academic_info__year_graduated=year)
        if course and course != 'ALL':
            alumni_qs = alumni_qs.filter(academic_info__program=course)

        total_alumni = alumni_qs.count()

        # OPTIMIZED: Use database aggregation instead of Python loops
        from apps.shared.models import TrackerData, EmploymentHistory
        from django.db.models import Q, Count, Case, When, IntegerField
        
        # Count employment status using database aggregation
        employment_stats = TrackerData.objects.filter(user__in=alumni_qs).aggregate(
            employed=Count('id', filter=Q(q_employment_status__iexact='yes')),
            unemployed=Count('id', filter=Q(q_employment_status__iexact='no')),
            pending_tracker=Count('id', filter=Q(q_employment_status__isnull=True) | Q(q_employment_status=''))
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
        
        if year and year != 'ALL':
            alumni_qs = alumni_qs.filter(academic_info__year_graduated=year)
        if course and course != 'ALL':
            alumni_qs = alumni_qs.filter(academic_info__program=course)
        
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
                # Use exact same logic as alumni_statistics_view
                untracked = max(total_alumni_count - employed - unemployed - absorbed, 0)
            except Exception as e:
                logger.error(f"Error in QPRO stats calculation: {e}")
                # Fallback to simple calculation
                employed = 0
                unemployed = 0
                absorbed = 0
                untracked = total_alumni
            employment_rate = (employed / total_alumni_count * 100) if total_alumni_count > 0 else 0

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
                'year': year,
                'course': course
            })
        
        elif stats_type == 'CHED':
            # CHED: Further study and job alignment statistics
            pursuing_study = alumni_qs.filter(academic_info__pursue_further_study__iexact='yes').count()
            tracker_pursuing_study = alumni_qs.filter(academic_info__q_pursue_study__iexact='yes').count()
            
            # Job alignment statistics using new fields
            job_aligned = alumni_qs.filter(employment__job_alignment_status='aligned').count()
            self_employed = alumni_qs.filter(employment__self_employed=True).count()
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
                # Real data fields using related models with null safety
                'most_common_company': most_common_company,
                'most_common_position': most_common_position,
                'most_common_sector': most_common_sector,
                'most_common_awards': most_common_awards,
                'most_common_civil_status': most_common_civil_status,
                'average_age': average_age,
                'sample_email': sample_email,
                'year': year,
                'course': course
            })
        
        elif stats_type == 'AACUP':
            # AACUP: Absorbed, employed, high position statistics - OPTIMIZED
            from apps.shared.models import TrackerData
            from django.db.models import Q, Count
            
            # OPTIMIZED: Use database aggregation
            employment_stats = TrackerData.objects.filter(user__in=alumni_qs).aggregate(
                employed=Count('id', filter=Q(q_employment_status__iexact='yes'))
            )
            employed = employment_stats['employed']
            
            absorbed = alumni_qs.filter(employment__absorbed=True).count()
            high_position = alumni_qs.filter(employment__high_position=True).count()
            self_employed = alumni_qs.filter(employment__self_employed=True).count()
            
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
                    'course': academic.course if academic else None,
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
@permission_classes([IsAuthenticated])
def export_detailed_alumni_data(request):
    """Export detailed alumni data for the current filter, including tracker answers."""
    try:
        year = request.GET.get('year', 'ALL')
        course = request.GET.get('program', 'ALL')
        
        # OPTIMIZED: Add select_related() to prevent N+1 queries during export
        alumni_qs = User.objects.filter(account_type__user=True).select_related(
            'profile', 'academic_info', 'employment', 'tracker_data', 'ojt_info'
        ).prefetch_related('trackerresponse_set')
        
        if year and year != 'ALL':
            alumni_qs = alumni_qs.filter(academic_info__year_graduated=year)
        if course and course != 'ALL':
            alumni_qs = alumni_qs.filter(academic_info__program=course)
        
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
            'Company_Name_Current', 'Position_Current', 'Sector_Current', 'Employment_Duration_Current', 'Salary_Current',
            'Supporting_Document_Current', 'Awards_Recognition_Current', 'Supporting_Document_Awards_Recognition',
            'Unemployment_Reason', 'Pursue_Further_Study', 'Date_Started', 'School_Name', 'Profile_Pic', 'Profile_Bio',
            'Profile_Resume'
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
                    'Program': getattr(academic_info, 'course', None) if academic_info else None,
                    'Section': getattr(academic_info, 'section', None) if academic_info else '',
                    'Status': alumni.user_status,
                    'Phone_Number': getattr(profile, 'phone_num', None) if profile else None,
                    'Email': getattr(profile, 'email', None) if profile else None,
                    'Address': getattr(profile, 'address', None) if profile else None,
                    'Civil_Status': getattr(profile, 'civil_status', None) if profile else None,
                    'Social_Media': getattr(profile, 'social_media', None) if profile else None,
                    'Age': getattr(profile, 'age', None) if profile else None,
                    'Company_Name_Current': getattr(employment, 'company_name_current', None) if employment else None,
                    'Position_Current': getattr(employment, 'position_current', None) if employment else None,
                    'Sector_Current': getattr(employment, 'sector_current', None) if employment else None,
                    'Employment_Duration_Current': getattr(employment, 'employment_duration_current', None) if employment else None,
                    'Salary_Current': getattr(employment, 'salary_current', None) if employment else None,
                    'Supporting_Document_Current': safe_file_field(getattr(employment, 'supporting_document_current', None)) if employment else '',
                    'Awards_Recognition_Current': getattr(employment, 'awards_recognition_current', None) if employment else None,
                    'Supporting_Document_Awards_Recognition': safe_file_field(getattr(employment, 'supporting_document_awards_recognition', None)) if employment else '',
                    'Unemployment_Reason': getattr(employment, 'unemployment_reason', None) if employment else None,
                    'Pursue_Further_Study': getattr(academic_info, 'pursue_further_study', None) if academic_info else None,
                    'Date_Started': getattr(academic_info, 'q_study_start_date', None) if academic_info else None,
                    'School_Name': getattr(academic_info, 'school_name', None) if academic_info else None,
                    'Profile_Pic': safe_file_field(getattr(profile, 'profile_pic', None)) if profile else '',
                    'Profile_Bio': getattr(profile, 'profile_bio', None) if profile else None,
                    'Profile_Resume': safe_file_field(getattr(profile, 'profile_resume', None)) if profile else '',
                }
                # Add tracker answers
                tracker_responses = TrackerResponse.objects.filter(user=alumni).order_by('-submitted_at')
                latest_tracker = tracker_responses.first() if tracker_responses.exists() else None
                tracker_answers = latest_tracker.answers if latest_tracker and latest_tracker.answers else {}
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
