"""
This app intentionally does not define its own models. All alumni-related models are located in apps.shared.models for reusability across multiple apps.
"""

import logging
from django.shortcuts import render
from django.http import JsonResponse
from django.core.files.storage import default_storage
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from apps.shared.models import User, UserProfile, AcademicInfo, EmploymentHistory, TrackerData, OJTInfo
from apps.shared.services import UserService
from apps.shared.serializers import AlumniListSerializer

logger = logging.getLogger(__name__)

# Helper functions

def _build_profile_pic_url(user):
    try:
        profile = getattr(user, 'profile', None)
        pic = getattr(profile, 'profile_pic', None) if profile else None
        if pic:
            url = pic.url
            try:
                modified = default_storage.get_modified_time(pic.name)
                if modified:
                    return f"{url}?t={int(modified.timestamp())}"
            except Exception:
                pass
            return url
    except Exception:
        pass
    return None


def build_alumni_data(a):
    profile = getattr(a, 'profile', None)
    academic = getattr(a, 'academic_info', None)
    employment = getattr(a, 'employment', None)
    tracker_data = getattr(a, 'tracker_data', None)
    
    # Determine employment status
    employment_status = 'Not disclosed'
    if tracker_data and tracker_data.q_employment_status:
        if tracker_data.q_employment_status.lower() == 'yes':
            employment_status = 'Employed'
        elif tracker_data.q_employment_status.lower() == 'no':
            employment_status = 'Unemployed'
        elif tracker_data.q_employment_status.lower() == 'pending':
            employment_status = 'Pending'
        else:
            employment_status = tracker_data.q_employment_status.title()
    elif employment and employment.company_name_current:
        employment_status = 'Employed'
    
    return {
        'id': a.user_id,
        'ctu_id': a.acc_username,
        'name': f"{a.f_name} {a.m_name or ''} {a.l_name}",
        'program': getattr(academic, 'program', None) if academic else None,
        'batch': getattr(academic, 'year_graduated', None) if academic else None,
        'status': a.user_status,  # Keep user_status for account status
        'employment_status': employment_status,  # Add employment status
        'gender': a.gender,
        'birthdate': str(getattr(profile, 'birthdate', None)) if profile and getattr(profile, 'birthdate', None) else None,
        'phone': getattr(profile, 'phone_num', None) if profile else None,
        'address': getattr(profile, 'address', None) if profile else None,
        'email': getattr(profile, 'email', None) if profile else None,
        'program': getattr(academic, 'program', None) if academic else None,
        'civil_status': getattr(profile, 'civil_status', None) if profile else None,
        'age': getattr(profile, 'age', None) if profile else None,
        'social_media': getattr(profile, 'social_media', None) if profile else None,
        'school_name': getattr(academic, 'school_name', None) if academic else None,
        'profile_pic': _build_profile_pic_url(a),
        # Add employment data - Prefer TrackerData (Part III) over EmploymentHistory for current data
        'employment_type': getattr(tracker_data, 'q_employment_type', None) if tracker_data else None,
        'position_current': getattr(tracker_data, 'q_current_position', None) if tracker_data else (getattr(employment, 'position_current', None) if employment else None),
        'company_name_current': getattr(tracker_data, 'q_company_name', None) if tracker_data else (getattr(employment, 'company_name_current', None) if employment else None),
        'sector_current': getattr(tracker_data, 'q_sector_current', None) if tracker_data else (getattr(employment, 'sector_current', None) if employment else None),
        'scope_current': getattr(tracker_data, 'q_scope_current', None) if tracker_data else (getattr(employment, 'scope_current', None) if employment else None),
        'salary_current': getattr(tracker_data, 'q_salary_range', None) if tracker_data else (getattr(employment, 'salary_current', None) if employment else None),
        'employment_duration': getattr(tracker_data, 'q_employment_duration', None) if tracker_data else None,
        'employment_permanent': getattr(tracker_data, 'q_employment_permanent', None) if tracker_data else None,
    }

def get_field_from_question_map(user, question_text_map, field, *question_labels):
    for label in question_labels:
        for qtext, answer in question_text_map.items():
            if label in qtext:
                return answer
    
    # Handle fields that are in the User model
    user_fields = ['f_name', 'm_name', 'l_name', 'gender', 'user_status', 'acc_username']
    if field in user_fields:
        return getattr(user, field, '')
    
    # Handle fields that are in the UserProfile model
    profile_fields = ['birthdate', 'phone_num', 'address', 'email', 'civil_status', 'age', 'social_media']
    if field in profile_fields:
        if hasattr(user, 'profile') and user.profile:
            val = getattr(user.profile, field, None)
            # Special handling for birthdate to avoid 'None' string
            if field == 'birthdate':
                return str(val) if val else ''
            return val if val is not None else ''
        return ''
    
    # Handle fields that are in the AcademicInfo model
    academic_fields = ['year_graduated', 'program']
    if field in academic_fields:
        if hasattr(user, 'academic_info') and user.academic_info:
            val = getattr(user.academic_info, field, None)
            return val if val is not None else ''
        return ''
    
    # Fallback to direct user attribute access
    return getattr(user, field, '')

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def alumni_list_view(request):
    """
    Returns a list of alumni with selected fields. Uses models from apps.shared.models.
    """
    year = request.GET.get('year')
    alumni_qs = User.objects.select_related('profile', 'academic_info', 'employment', 'tracker_data').filter(account_type__user=True)
    if year:
        alumni_qs = alumni_qs.filter(academic_info__year_graduated=year)
    alumni_data = [build_alumni_data(a) for a in alumni_qs]
    return JsonResponse({'success': True, 'alumni': alumni_data})

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def alumni_detail_view(request, user_id):
    """
    Returns detailed information for a single alumni, including tracker answers if available.
    Uses models from apps.shared.models.
    """
    from apps.shared.models import TrackerResponse, Question
    try:
        # Always pull related data to avoid extra queries and ensure academic_info is available
        user = User.objects.select_related('profile', 'academic_info', 'employment', 'tracker_data').get(user_id=user_id)
        tracker_responses = TrackerResponse.objects.filter(user=user).order_by('-submitted_at')
        latest_tracker = tracker_responses.first() if tracker_responses.exists() else None
        tracker_answers = latest_tracker.answers if latest_tracker and latest_tracker.answers else {}
        question_text_map = {}
        if tracker_answers:
            qids = [int(qid) for qid in tracker_answers.keys() if str(qid).isdigit()]
            for q in Question.objects.filter(id__in=qids):
                question_text_map[q.text.lower()] = tracker_answers.get(str(q.id)) or tracker_answers.get(q.id)

        def get_field(field, *question_labels):
            return get_field_from_question_map(user, question_text_map, field, *question_labels)

        academic_info = getattr(user, 'academic_info', None)
        employment_info = getattr(user, 'employment', None)
        tracker_data = getattr(user, 'tracker_data', None)
        batch_year = getattr(academic_info, 'year_graduated', None)

        # Determine employment status
        employment_status = 'Not disclosed'
        if tracker_data and tracker_data.q_employment_status:
            if tracker_data.q_employment_status.lower() == 'yes':
                employment_status = 'Employed'
            elif tracker_data.q_employment_status.lower() == 'no':
                employment_status = 'Unemployed'
            elif tracker_data.q_employment_status.lower() == 'pending':
                employment_status = 'Pending'
            else:
                employment_status = tracker_data.q_employment_status.title()
        elif employment_info and employment_info.company_name_current:
            employment_status = 'Employed'
        
        # Get follower and following counts
        from apps.shared.models import Follow
        followers_count = Follow.objects.filter(following=user).count()
        following_count = Follow.objects.filter(follower=user).count()

        data = {
            'id': user.user_id,
            'ctu_id': user.acc_username,
            'name': f"{get_field('f_name', 'first name')} {get_field('m_name', 'middle name') or ''} {get_field('l_name', 'last name')}".strip(),
            'first_name': get_field('f_name', 'first name'),
            'profile_bio': user.profile.profile_bio if hasattr(user, 'profile') and user.profile else None,
            'middle_name': get_field('m_name', 'middle name'),
            'last_name': get_field('l_name', 'last name'),
            'course': getattr(academic_info, 'program', None) if academic_info else get_field('program', 'course', 'program'),
            # Always prefer academic_info.year_graduated for batch
            'batch': batch_year if batch_year is not None else get_field('year_graduated', 'batch', 'year graduated'),
            'status': get_field('user_status', 'status'),
            'gender': get_field('gender', 'gender'),
            'birthdate': get_field('birthdate', 'birthdate', 'birth date', 'birthday', 'date of birth', 'dob', 'bday'),
            'phone': get_field('phone_num', 'phone', 'contact', 'mobile'),
            'address': get_field('address', 'address'),
            'email': get_field('email', 'email'),
            'program': getattr(academic_info, 'program', None) if academic_info else get_field('program', 'program'),
            'civil_status': get_field('civil_status', 'civil status'),
            'age': get_field('age', 'age'),
            'social_media': get_field('social_media', 'social media'),
            'school_name': getattr(academic_info, 'school_name', None) if academic_info else get_field('school_name', 'school name'),
            'profile_pic': _build_profile_pic_url(user),
            # Employment data - Prefer TrackerData (Part III) over EmploymentHistory for accurate current data
            'employment_type': getattr(tracker_data, 'q_employment_type', None) if tracker_data else None,
            'position_current': getattr(tracker_data, 'q_current_position', None) if tracker_data else (getattr(employment_info, 'position_current', None) if employment_info else get_field('position_current', 'current position')),
            'company_name_current': getattr(tracker_data, 'q_company_name', None) if tracker_data else (getattr(employment_info, 'company_name_current', None) if employment_info else get_field('company_name_current', 'current company')),
            'sector_current': getattr(tracker_data, 'q_sector_current', None) if tracker_data else (getattr(employment_info, 'sector_current', None) if employment_info else get_field('sector_current', 'employment sector')),
            'scope_current': getattr(tracker_data, 'q_scope_current', None) if tracker_data else (getattr(employment_info, 'scope_current', None) if employment_info else get_field('scope_current', 'current scope')),
            'salary_current': getattr(tracker_data, 'q_salary_range', None) if tracker_data else (getattr(employment_info, 'salary_current', None) if employment_info else get_field('salary_current', 'salary')),
            'employment_duration': getattr(tracker_data, 'q_employment_duration', None) if tracker_data else None,
            'employment_permanent': getattr(tracker_data, 'q_employment_permanent', None) if tracker_data else None,
            'self_employed': getattr(employment_info, 'self_employed', False) if employment_info else False,
            'employment_status': employment_status,
            'followers_count': followers_count,
            'following_count': following_count,
            'account_type': {
                'user': getattr(user.account_type, 'user', False),
                'admin': getattr(user.account_type, 'admin', False),
                'peso': getattr(user.account_type, 'peso', False),
                'coordinator': getattr(user.account_type, 'coordinator', False),
                'ojt': getattr(user.account_type, 'ojt', False),
            },
        }
        return JsonResponse({'success': True, 'alumni': data})
    except User.DoesNotExist as e:
        logger.error(f"User with id {user_id} not found: {e}")
        return JsonResponse({'success': False, 'message': 'User not found'}, status=404)
