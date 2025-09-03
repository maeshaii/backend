from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from apps.shared.models import User, TrackerResponse, Question
from collections import Counter
from django.db import models
from statistics import mean

# Helper functions for statistics aggregation

def safe_mode(qs, field):
    vals = [getattr(a, field) for a in qs if getattr(a, field)]
    return Counter(vals).most_common(1)[0][0] if vals else None

def safe_mean(qs, field):
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
    for a in qs:
        v = getattr(a, field)
        if v:
            return v
    return None

# Create your views here.

@csrf_exempt
@require_http_methods(["GET"])
def alumni_statistics_view(request):
    year = request.GET.get('year')
    course = request.GET.get('course')
    alumni_qs = User.objects.filter(account_type__user=True)
    if year and year != 'ALL':
        alumni_qs = alumni_qs.filter(year_graduated=year)
    if course and course != 'ALL':
        alumni_qs = alumni_qs.filter(course=course)
    # Count by employment status
    status_counts = Counter(alumni_qs.values_list('user_status', flat=True))
    # Count by year for year options
    year_counts = Counter(User.objects.filter(account_type__user=True).values_list('year_graduated', flat=True))
    filtered_year_counts = {y: c for y, c in year_counts.items() if y is not None}
    return JsonResponse({
        'success': True,
        'status_counts': dict(status_counts),
        'years': [
            {'year': year, 'count': count}
            for year, count in sorted(filtered_year_counts.items(), reverse=True)
        ]
    })

@csrf_exempt
@require_http_methods(["GET"])
def generate_statistics_view(request):
    year = request.GET.get('year', 'ALL')
    course = request.GET.get('course', 'ALL')
    stats_type = request.GET.get('type', 'ALL')
    
    alumni_qs = User.objects.filter(account_type__user=True)
    
    if year and year != 'ALL':
        alumni_qs = alumni_qs.filter(year_graduated=year)
    if course and course != 'ALL':
        alumni_qs = alumni_qs.filter(course=course)
    
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
            'most_common_company': safe_mode(alumni_qs, 'company_name_current'),
            'most_common_position': safe_mode(alumni_qs, 'position_current'),
            'most_common_sector': safe_mode(alumni_qs, 'sector_current'),
            'average_salary': safe_mean(alumni_qs, 'salary_current'),
            'most_common_awards': safe_mode(alumni_qs, 'awards_recognition_current'),
            'most_common_school': safe_mode(alumni_qs, 'school_name'),
            'most_common_unemployment_reason': safe_mode(alumni_qs, 'unemployment_reason'),
            'most_common_civil_status': safe_mode(alumni_qs, 'civil_status'),
            'average_age': safe_mean(alumni_qs, 'age'),
            'sample_email': safe_sample(alumni_qs, 'email'),
            'year': year,
            'course': course
        })
    
    elif stats_type == 'QPRO':
        # QPRO: Employment statistics based on real data fields
        employed = alumni_qs.filter(user_status__iexact='employed').count()  # user_status == 'employed'
        unemployed = alumni_qs.filter(user_status__iexact='unemployed').count()  # user_status == 'unemployed'
        employment_rate = (employed / total_alumni * 100) if total_alumni > 0 else 0
        return JsonResponse({
            'success': True,
            'type': 'QPRO',
            'total_alumni': total_alumni,
            'employment_rate': round(employment_rate, 2),
            'employed_count': employed,
            'unemployed_count': unemployed,
            # Real data fields
            'most_common_company': safe_mode(alumni_qs, 'company_name_current'),
            'most_common_position': safe_mode(alumni_qs, 'position_current'),
            'most_common_sector': safe_mode(alumni_qs, 'sector_current'),
            'average_salary': safe_mean(alumni_qs, 'salary_current'),
            'most_common_awards': safe_mode(alumni_qs, 'awards_recognition_current'),
            'most_common_unemployment_reason': safe_mode(alumni_qs, 'unemployment_reason'),
            'most_common_civil_status': safe_mode(alumni_qs, 'civil_status'),
            'average_age': safe_mean(alumni_qs, 'age'),
            'sample_email': safe_sample(alumni_qs, 'email'),
            'year': year,
            'course': course
        })
    
    elif stats_type == 'CHED':
        # CHED: Further study statistics based on real data fields
        pursuing_study = alumni_qs.filter(pursue_further_study__iexact='yes').count()  # pursue_further_study == 'yes'
        return JsonResponse({
            'success': True,
            'type': 'CHED',
            'total_alumni': total_alumni,
            'pursuing_further_study': pursuing_study,
            'post_graduate_degree': alumni_qs.filter(program__icontains='graduate').count(),  # program contains 'graduate'
            'further_study_rate': round((pursuing_study / total_alumni * 100), 2) if total_alumni > 0 else 0,
            'most_common_school': safe_mode(alumni_qs, 'school_name'),
            'most_common_program': safe_mode(alumni_qs, 'program'),
            'most_common_awards': safe_mode(alumni_qs, 'awards_recognition_current'),
            'most_common_civil_status': safe_mode(alumni_qs, 'civil_status'),
            'average_age': safe_mean(alumni_qs, 'age'),
            'sample_email': safe_sample(alumni_qs, 'email'),
            'year': year,
            'course': course
        })
    
    elif stats_type == 'SUC':
        # SUC: High position and salary statistics based on real data fields
        high_position = alumni_qs.filter(user_status__iexact='high position').count()  # user_status == 'high position'
        return JsonResponse({
            'success': True,
            'type': 'SUC',
            'total_alumni': total_alumni,
            'high_position_count': high_position,
            'high_position_rate': round((high_position / total_alumni * 100), 2) if total_alumni > 0 else 0,
            'average_salary': safe_mean(alumni_qs, 'salary_current'),
            'most_common_company': safe_mode(alumni_qs, 'company_name_current'),
            'most_common_position': safe_mode(alumni_qs, 'position_current'),
            'most_common_sector': safe_mode(alumni_qs, 'sector_current'),
            'most_common_awards': safe_mode(alumni_qs, 'awards_recognition_current'),
            'most_common_civil_status': safe_mode(alumni_qs, 'civil_status'),
            'average_age': safe_mean(alumni_qs, 'age'),
            'sample_email': safe_sample(alumni_qs, 'email'),
            'year': year,
            'course': course
        })
    
    elif stats_type == 'AACUP':
        # AACUP: Absorbed, employed, high position statistics based on real data fields
        employed = alumni_qs.filter(user_status__iexact='employed').count()  # user_status == 'employed'
        absorbed = alumni_qs.filter(user_status__iexact='absorb').count()  # user_status == 'absorb'
        high_position = alumni_qs.filter(user_status__iexact='high position').count()  # user_status == 'high position'
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
            'most_common_company': safe_mode(alumni_qs, 'company_name_current'),
            'most_common_position': safe_mode(alumni_qs, 'position_current'),
            'most_common_sector': safe_mode(alumni_qs, 'sector_current'),
            'average_salary': safe_mean(alumni_qs, 'salary_current'),
            'most_common_awards': safe_mode(alumni_qs, 'awards_recognition_current'),
            'most_common_school': safe_mode(alumni_qs, 'school_name'),
            'most_common_civil_status': safe_mode(alumni_qs, 'civil_status'),
            'average_age': safe_mean(alumni_qs, 'age'),
            'sample_email': safe_sample(alumni_qs, 'email'),
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

@csrf_exempt
@require_http_methods(["GET"])
def export_detailed_alumni_data(request):
    """Export detailed alumni data for specific statistics types"""
    year = request.GET.get('year', 'ALL')
    course = request.GET.get('course', 'ALL')
    # stats_type = request.GET.get('type', 'ALL')  # No longer used for filtering
    
    alumni_qs = User.objects.filter(account_type__user=True)
    
    if year and year != 'ALL':
        alumni_qs = alumni_qs.filter(year_graduated=year)
    if course and course != 'ALL':
        alumni_qs = alumni_qs.filter(course=course)
    
    # Do NOT filter by stats_type. Always return all alumni for the filter.
    # Collect all tracker question texts that have been answered by any alumni in the queryset
    all_tracker_qids = set()
    for alum in alumni_qs:
        tracker_responses = TrackerResponse.objects.filter(user=alum).order_by('-submitted_at')
        latest_tracker = tracker_responses.first() if tracker_responses.exists() else None
        tracker_answers = latest_tracker.answers if latest_tracker and latest_tracker.answers else {}
        all_tracker_qids.update([int(qid) for qid in tracker_answers.keys() if str(qid).isdigit()])
    
    # Get question text for all qids
    tracker_questions = {q.id: q.text for q in Question.objects.filter(id__in=all_tracker_qids)}
    tracker_columns = [tracker_questions[qid] for qid in sorted(tracker_questions.keys())]
    
    # Canonical list of all User fields for export
    export_fields = [
        'CTU_ID', 'First_Name', 'Middle_Name', 'Last_Name', 'Gender', 'Birthdate', 'Year_Graduated', 'Course', 'Section',
        'Program', 'Status', 'Phone_Number', 'Email', 'Address', 'Civil_Status', 'Social_Media', 'Age',
        'Company_Name_Current', 'Position_Current', 'Sector_Current', 'Employment_Duration_Current', 'Salary_Current',
        'Supporting_Document_Current', 'Awards_Recognition_Current', 'Supporting_Document_Awards_Recognition',
        'Unemployment_Reason', 'Pursue_Further_Study', 'Date_Started', 'School_Name', 'Profile_Pic', 'Profile_Bio',
        'Profile_Resume'
    ]
    
    # Build a unique set of export columns: basic fields + tracker question texts (no duplicates)
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
        data = {
            'CTU_ID': alumni.acc_username,
            'First_Name': alumni.f_name,
            'Middle_Name': alumni.m_name or '',
            'Last_Name': alumni.l_name,
            'Gender': alumni.gender,
            'Birthdate': str(alumni.birthdate) if alumni.birthdate else '',
            'Year_Graduated': alumni.year_graduated,
            'Course': alumni.course,
            'Section': alumni.section or '',
            'Program': alumni.program or '',
            # ... (add all other fields as needed) ...
        }
        # Add tracker answers
        tracker_responses = TrackerResponse.objects.filter(user=alumni).order_by('-submitted_at')
        latest_tracker = tracker_responses.first() if tracker_responses.exists() else None
        tracker_answers = latest_tracker.answers if latest_tracker and latest_tracker.answers else {}
        for qid, qtext in tracker_questions.items():
            answer = tracker_answers.get(str(qid)) or tracker_answers.get(qid)
            if isinstance(answer, list):
                answer = ', '.join(str(a) for a in answer)
            data[qtext] = answer if answer is not None else ''
        detailed_data.append(data)
    return JsonResponse({'detailed_data': detailed_data})
