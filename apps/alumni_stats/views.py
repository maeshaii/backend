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
from apps.shared.utils.stats import safe_mode, safe_mean, safe_sample, safe_mode_related, safe_mean_related, safe_sample_related

logger = logging.getLogger(__name__)

# Helper functions for statistics aggregation

def safe_mode(qs, field):
    """Return the most common non-empty value for attribute `field` in an iterable of objects."""
    vals = [getattr(a, field) for a in qs if getattr(a, field)]
    return Counter(vals).most_common(1)[0][0] if vals else None

def safe_mean(qs, field):
    """Return the mean of numeric values for attribute `field`, coercing strings when possible."""
    vals = []
    for a in qs:
        v = getattr(a, field)
        if v and isinstance(v, (int, float)):
            vals.append(float(v))
        elif v and isinstance(v, str):
            try:
                vals.append(float(v.replace(',', '').replace(' ', '')))
            except:
                continue
    return round(mean(vals), 2) if vals else None

def safe_sample(qs, field):
    """Return the first non-empty value for attribute `field`, else None."""
    for a in qs:
        v = getattr(a, field)
        if v:
            return v
    return None

# Helper functions for related field access
def safe_mode_related(qs, field_path):
    """Return the most common non-empty value resolved via a double-underscore `field_path`."""
    vals = []
    for user in qs:
        try:
            # Navigate through the relationship path
            parts = field_path.split('__')
            obj = user
            for part in parts:
                obj = getattr(obj, part, None)
                if obj is None:
                    break
            if obj:
                vals.append(obj)
        except:
            continue
    return Counter(vals).most_common(1)[0][0] if vals else None

def safe_mean_related(qs, field_path):
    """Return the mean of values resolved via `field_path`, coercing strings when possible."""
    vals = []
    for user in qs:
        try:
            parts = field_path.split('__')
            obj = user
            for part in parts:
                obj = getattr(obj, part, None)
                if obj is None:
                    break
            if obj and isinstance(obj, (int, float)):
                vals.append(float(obj))
            elif obj and isinstance(obj, str):
                try:
                    vals.append(float(obj.replace(',', '').replace(' ', '')))
                except:
                    continue
        except:
            continue
    return round(mean(vals), 2) if vals else None

def safe_sample_related(qs, field_path):
    """Return the first non-empty value resolved via `field_path`, else None."""
    for user in qs:
        try:
            parts = field_path.split('__')
            obj = user
            for part in parts:
                obj = getattr(obj, part, None)
                if obj is None:
                    break
            if obj:
                return obj
        except:
            continue
    return None

# Create your views here.

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def alumni_statistics_view(request):
    """Simple overview of alumni employment status counts and available years."""
    try:
        year = request.GET.get('year')
        course = request.GET.get('course')
        alumni_qs = User.objects.filter(account_type__user=True)
        if year and year != 'ALL':
            alumni_qs = alumni_qs.filter(academic_info__year_graduated=year)
        if course and course != 'ALL':
            alumni_qs = alumni_qs.filter(academic_info__course=course)

        total_alumni = alumni_qs.count()

        # Use tracker answers for employment buckets
        from apps.shared.models import TrackerData, EmploymentHistory
        tracker_qs = TrackerData.objects.filter(user__in=alumni_qs)
        employed = 0
        unemployed = 0
        for t in tracker_qs:
            status = (t.q_employment_status or '').strip().lower()
            if status == 'yes':
                employed += 1
            elif status == 'no':
                unemployed += 1

        absorbed = EmploymentHistory.objects.filter(user__in=alumni_qs, absorbed=True).count()
        pending = max(total_alumni - employed - unemployed - absorbed, 0)

        status_counts = {
            'Employed': employed,
            'Unemployed': unemployed,
            'Absorb': absorbed,
            'Pending': pending,
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

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def generate_statistics_view(request):
    try:
        year = request.GET.get('year', 'ALL')
        course = request.GET.get('course', 'ALL')
        stats_type = request.GET.get('type', 'ALL')
        
        alumni_qs = User.objects.filter(account_type__user=True)
        
        if year and year != 'ALL':
            alumni_qs = alumni_qs.filter(academic_info__year_graduated=year)
        if course and course != 'ALL':
            alumni_qs = alumni_qs.filter(academic_info__course=course)
        
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
            # QPRO: Employment statistics based on tracker data
            # Get employment status from tracker data instead of user_status
            from apps.shared.models import TrackerData
            tracker_data = TrackerData.objects.filter(user__in=alumni_qs)
            
            # Count employment statuses from tracker data
            employed = 0
            unemployed = 0
            for tracker in tracker_data:
                status = tracker.q_employment_status
                if status and status.lower() == 'yes':
                    employed += 1
                elif status and status.lower() == 'no':
                    unemployed += 1
            
            # Calculate untracked alumni (those who haven't answered the tracker)
            tracked_alumni = tracker_data.count()
            untracked = total_alumni - tracked_alumni
            
            employment_rate = (employed / total_alumni * 100) if total_alumni > 0 else 0
            
            return JsonResponse({
                'success': True,
                'type': 'QPRO',
                'total_alumni': total_alumni,
                'employment_rate': round(employment_rate, 2),
                'employed_count': employed,
                'unemployed_count': unemployed,
                'untracked_count': untracked,
                'tracker_employed_count': employed,
                'tracker_unemployed_count': unemployed,
                # Real data fields using related models
                'most_common_company': safe_mode_related(alumni_qs, 'employment__company_name_current'),
                'most_common_position': safe_mode_related(alumni_qs, 'employment__position_current'),
                'most_common_sector': safe_mode_related(alumni_qs, 'employment__sector_current'),
                'average_salary': safe_mean_related(alumni_qs, 'employment__salary_current'),
                'most_common_awards': safe_mode_related(alumni_qs, 'employment__awards_recognition_current'),
                'most_common_unemployment_reason': safe_mode_related(alumni_qs, 'employment__unemployment_reason'),
                'most_common_civil_status': safe_mode_related(alumni_qs, 'profile__civil_status'),
                'average_age': safe_mean_related(alumni_qs, 'profile__age'),
                'sample_email': safe_sample_related(alumni_qs, 'profile__email'),
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
            
            # Aggregate job_alignment_count from Ched model
            from apps.shared.models import Standard, Ched
            ched_count = 0
            ched_records = Ched.objects.all()
            for ched in ched_records:
                ched_count += getattr(ched, 'job_alignment_count', 0)
            
            return JsonResponse({
                'success': True,
                'type': 'CHED',
                'total_alumni': total_alumni,
                'pursuing_further_study': pursuing_study,
                'tracker_pursuing_study': tracker_pursuing_study,
                'further_study_rate': round((pursuing_study / total_alumni * 100), 2) if total_alumni > 0 else 0,
                'job_alignment_count': ched_count,
                'job_aligned_count': job_aligned,
                'self_employed_count': self_employed,
                'not_aligned_count': not_aligned,
                'job_alignment_rate': round((job_aligned / total_alumni * 100), 2) if total_alumni > 0 else 0,
                'most_common_school': safe_mode_related(alumni_qs, 'academic_info__school_name'),
                'most_common_program': safe_mode_related(alumni_qs, 'academic_info__program'),
                'most_common_awards': safe_mode_related(alumni_qs, 'employment__awards_recognition_current'),
                'most_common_civil_status': safe_mode_related(alumni_qs, 'profile__civil_status'),
                'average_age': safe_mean_related(alumni_qs, 'profile__age'),
                'sample_email': safe_sample_related(alumni_qs, 'profile__email'),
                'year': year,
                'course': course
            })
        
        elif stats_type == 'SUC':
            # SUC: High position and salary statistics
            high_position = alumni_qs.filter(employment__high_position=True).count()
            job_aligned = alumni_qs.filter(employment__job_alignment_status='aligned').count()
            
            # Get sector and scope counts from tracker data
            from apps.shared.models import TrackerData
            tracker_data = TrackerData.objects.filter(user__in=alumni_qs)
            
            public_count = 0
            private_count = 0
            local_count = 0
            international_count = 0
            
            for tracker in tracker_data:
                # Check sector (Public/Private) - this would be question 27
                sector = tracker.q_sector_current
                if sector and sector.lower() == 'public':
                    public_count += 1
                elif sector and sector.lower() == 'private':
                    private_count += 1
                
                # Check scope (Local/International) - this would be question 28
                scope = tracker.q_scope_current
                if scope and scope.lower() == 'local':
                    local_count += 1
                elif scope and scope.lower() == 'international':
                    international_count += 1
            
            high_position_rate = (high_position / total_alumni * 100) if total_alumni > 0 else 0
            job_alignment_rate = (job_aligned / total_alumni * 100) if total_alumni > 0 else 0
            
            return JsonResponse({
                'success': True,
                'type': 'SUC',
                'total_alumni': total_alumni,
                'high_position_count': high_position,
                'high_position_rate': round(high_position_rate, 2),
                'job_aligned_count': job_aligned,
                'job_alignment_rate': round(job_alignment_rate, 2),
                'public_count': public_count,
                'private_count': private_count,
                'local_count': local_count,
                'international_count': international_count,
                'most_common_company': safe_mode_related(alumni_qs, 'employment__company_name_current'),
                'most_common_position': safe_mode_related(alumni_qs, 'employment__position_current'),
                'most_common_sector': safe_mode_related(alumni_qs, 'employment__sector_current'),
                'most_common_awards': safe_mode_related(alumni_qs, 'employment__awards_recognition_current'),
                'most_common_civil_status': safe_mode_related(alumni_qs, 'profile__civil_status'),
                'average_age': safe_mean_related(alumni_qs, 'profile__age'),
                'sample_email': safe_sample_related(alumni_qs, 'profile__email'),
                'year': year,
                'course': course
            })
        
        elif stats_type == 'AACUP':
            # AACUP: Absorbed, employed, high position statistics
            # Get employment status from tracker data instead of user_status
            from apps.shared.models import TrackerData
            tracker_data = TrackerData.objects.filter(user__in=alumni_qs)
            
            # Count employment statuses from tracker data
            employed = 0
            for tracker in tracker_data:
                status = tracker.q_employment_status
                if status and status.lower() == 'yes':
                    employed += 1
            
            absorbed = alumni_qs.filter(employment__absorbed=True).count()
            high_position = alumni_qs.filter(employment__high_position=True).count()
            self_employed = alumni_qs.filter(employment__self_employed=True).count()
            
            employment_rate = (employed / total_alumni * 100) if total_alumni > 0 else 0
            absorption_rate = (absorbed / total_alumni * 100) if total_alumni > 0 else 0
            high_position_rate = (high_position / total_alumni * 100) if total_alumni > 0 else 0
            
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
                'most_common_company': safe_mode_related(alumni_qs, 'employment__company_name_current'),
                'most_common_position': safe_mode_related(alumni_qs, 'employment__position_current'),
                'most_common_sector': safe_mode_related(alumni_qs, 'employment__sector_current'),
                'average_salary': safe_mean_related(alumni_qs, 'employment__salary_current'),
                'most_common_awards': safe_mode_related(alumni_qs, 'employment__awards_recognition_current'),
                'most_common_school': safe_mode_related(alumni_qs, 'academic_info__school_name'),
                'most_common_civil_status': safe_mode_related(alumni_qs, 'profile__civil_status'),
                'average_age': safe_mean_related(alumni_qs, 'profile__age'),
                'sample_email': safe_sample_related(alumni_qs, 'profile__email'),
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
                'most_common_course': safe_mode_related(high_position_alumni, 'academic_info__course'),
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
        course = request.GET.get('course', 'ALL')
        
        alumni_qs = User.objects.filter(account_type__user=True)
        
        if year and year != 'ALL':
            alumni_qs = alumni_qs.filter(academic_info__year_graduated=year)
        if course and course != 'ALL':
            alumni_qs = alumni_qs.filter(academic_info__course=course)
        
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
            'CTU_ID', 'First_Name', 'Middle_Name', 'Last_Name', 'Gender', 'Birthdate', 'Year_Graduated', 'Course', 'Section',
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
                    'Course': getattr(academic_info, 'course', None) if academic_info else None,
                    'Section': getattr(academic_info, 'section', None) if academic_info else '',
                    'Program': getattr(academic_info, 'program', None) if academic_info else '',
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
