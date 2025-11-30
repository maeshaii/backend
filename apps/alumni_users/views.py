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
        'q_institution_name': getattr(academic, 'q_institution_name', None) if academic else None,
        'q_study_start_date': str(getattr(academic, 'q_study_start_date', None)) if academic and getattr(academic, 'q_study_start_date', None) else None,
        'pursue_further_study': getattr(academic, 'pursue_further_study', None) if academic else None,
        'profile_pic': _build_profile_pic_url(a),
        # Add employment data - Prefer TrackerData (Part III) over EmploymentHistory for current data
        'employment_type': getattr(tracker_data, 'q_employment_type', None) if tracker_data else None,
        'q_awards_received': getattr(tracker_data, 'q_awards_received', None) if tracker_data else None,
        'q_unemployment_reason': getattr(tracker_data, 'q_unemployment_reason', None) if tracker_data else None,
        'position_current': getattr(tracker_data, 'q_current_position', None) if tracker_data else (getattr(employment, 'position_current', None) if employment else None),
        'company_name_current': getattr(tracker_data, 'q_company_name', None) if tracker_data else (getattr(employment, 'company_name_current', None) if employment else None),
        'sector_current': getattr(tracker_data, 'q_sector_current', None) if tracker_data else (getattr(employment, 'sector_current', None) if employment else None),
        'scope_current': getattr(tracker_data, 'q_scope_current', None) if tracker_data else (getattr(employment, 'scope_current', None) if employment else None),
        'salary_current': getattr(tracker_data, 'q_salary_range', None) if tracker_data else (getattr(employment, 'salary_current', None) if employment else None),
        'employment_duration': getattr(tracker_data, 'q_employment_duration', None) if tracker_data else None,
        'employment_permanent': getattr(tracker_data, 'q_employment_permanent', None) if tracker_data else None,
    }

def get_field_from_question_map(user, question_text_map, field, *question_labels):
    # DEBUG: Log function call
    logger.debug(f"get_field_from_question_map called: field='{field}', labels={question_labels}")
    
    # CRITICAL FIX: For basic profile fields, prioritize database fields over tracker answers
    # This prevents empty tracker answers from overriding valid profile data
    
    # Handle fields that are in the UserProfile model - CHECK PROFILE FIRST
    profile_fields = ['birthdate', 'phone_num', 'address', 'email', 'civil_status', 'age', 'social_media']
    if field in profile_fields:
        if hasattr(user, 'profile') and user.profile:
            val = getattr(user.profile, field, None)
            logger.debug(f"  Profile field '{field}' = '{val}' (type: {type(val)})")
            # If profile has a value, use it (don't check tracker answers)
            if val is not None and val != '':
                # Special handling for birthdate to avoid 'None' string
                if field == 'birthdate':
                    result = str(val) if val else ''
                    logger.debug(f"  Returning profile birthdate: '{result}'")
                    return result
                logger.debug(f"  Returning profile value: '{val}'")
                return val
            else:
                logger.debug(f"  Profile field '{field}' is empty/None, checking tracker answers...")
        else:
            logger.debug(f"  No profile exists, checking tracker answers...")
        
        # Only check tracker answers if profile doesn't have the value
        for label in question_labels:
            for qtext, answer in question_text_map.items():
                if label in qtext:
                    logger.debug(f"  Found tracker match: label='{label}' in qtext='{qtext}', answer='{answer}'")
                    if answer and str(answer).strip():
                        logger.debug(f"  Returning tracker answer: '{answer}'")
                        return answer
                    else:
                        logger.debug(f"  Tracker answer is empty, continuing search...")
        logger.debug(f"  No valid tracker answer found, returning empty string")
        return ''
    
    # Handle fields that are in the User model - CHECK USER FIRST
    user_fields = ['f_name', 'm_name', 'l_name', 'gender', 'user_status', 'acc_username']
    if field in user_fields:
        val = getattr(user, field, '')
        if val:
            return val
        # Only check tracker answers if user field is empty
        for label in question_labels:
            for qtext, answer in question_text_map.items():
                if label in qtext and answer and str(answer).strip():
                    return answer
        return ''
    
    # Handle fields that are in the AcademicInfo model - CHECK ACADEMIC INFO FIRST
    academic_fields = ['year_graduated', 'program', 'school_name']
    if field in academic_fields:
        if hasattr(user, 'academic_info') and user.academic_info:
            val = getattr(user.academic_info, field, None)
            if val is not None and val != '':
                return val
        # Only check tracker answers if academic_info doesn't have the value
        for label in question_labels:
            for qtext, answer in question_text_map.items():
                if label in qtext and answer and str(answer).strip():
                    return answer
        return ''
    
    # For other fields, check tracker answers first, then fallback
    for label in question_labels:
        for qtext, answer in question_text_map.items():
            if label in qtext and answer and str(answer).strip():
                return answer
    
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

        # DEBUG: Log all profile data to trace root cause
        logger.debug(f"=== DEBUG alumni_detail_view for user_id={user_id} ===")
        logger.debug(f"User: {user.acc_username} ({user.f_name} {user.l_name})")
        
        # DEBUG: Check UserProfile directly
        if hasattr(user, 'profile') and user.profile:
            profile = user.profile
            logger.debug(f"UserProfile exists:")
            logger.debug(f"  - phone_num: '{getattr(profile, 'phone_num', None)}' (type: {type(getattr(profile, 'phone_num', None))})")
            logger.debug(f"  - email: '{getattr(profile, 'email', None)}' (type: {type(getattr(profile, 'email', None))})")
            logger.debug(f"  - social_media: '{getattr(profile, 'social_media', None)}' (type: {type(getattr(profile, 'social_media', None))})")
            logger.debug(f"  - address: '{getattr(profile, 'address', None)}'")
            logger.debug(f"  - birthdate: '{getattr(profile, 'birthdate', None)}'")
        else:
            logger.debug(f"UserProfile does NOT exist!")
        
        # DEBUG: Check AcademicInfo
        if academic_info:
            logger.debug(f"AcademicInfo exists:")
            logger.debug(f"  - q_study_start_date: '{getattr(academic_info, 'q_study_start_date', None)}'")
            logger.debug(f"  - q_institution_name: '{getattr(academic_info, 'q_institution_name', None)}'")
            logger.debug(f"  - school_name: '{getattr(academic_info, 'school_name', None)}'")
        else:
            logger.debug(f"AcademicInfo does NOT exist!")
        
        # DEBUG: Check TrackerData
        if tracker_data:
            logger.debug(f"TrackerData exists:")
            logger.debug(f"  - q_company_name: '{getattr(tracker_data, 'q_company_name', None)}'")
        else:
            logger.debug(f"TrackerData does NOT exist!")
        
        # DEBUG: Check tracker answers (question_text_map)
        logger.debug(f"Tracker answers (question_text_map) has {len(question_text_map)} entries:")
        for qtext, answer in list(question_text_map.items())[:10]:  # Show first 10
            logger.debug(f"  - '{qtext}': '{answer}'")
        
        # DEBUG: Test get_field function
        phone_from_get_field = get_field('phone_num', 'phone', 'contact', 'mobile')
        email_from_get_field = get_field('email', 'email')
        social_from_get_field = get_field('social_media', 'social media')
        logger.debug(f"get_field results:")
        logger.debug(f"  - phone_num: '{phone_from_get_field}'")
        logger.debug(f"  - email: '{email_from_get_field}'")
        logger.debug(f"  - social_media: '{social_from_get_field}'")
        
        # DEBUG: Test direct profile access
        phone_direct = getattr(user.profile, 'phone_num', None) if hasattr(user, 'profile') and user.profile else None
        email_direct = getattr(user.profile, 'email', None) if hasattr(user, 'profile') and user.profile else None
        social_direct = getattr(user.profile, 'social_media', None) if hasattr(user, 'profile') and user.profile else None
        logger.debug(f"Direct profile access:")
        logger.debug(f"  - phone_num: '{phone_direct}'")
        logger.debug(f"  - email: '{email_direct}'")
        logger.debug(f"  - social_media: '{social_direct}'")
        
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
            # CRITICAL FIX: Prioritize profile fields directly - don't use get_field for basic profile data
            # This ensures imported data from UserProfile is shown, not empty tracker answers
            'phone': getattr(user.profile, 'phone_num', None) if hasattr(user, 'profile') and user.profile else get_field('phone_num', 'phone', 'contact', 'mobile'),
            'address': getattr(user.profile, 'address', None) if hasattr(user, 'profile') and user.profile else get_field('address', 'address'),
            'email': getattr(user.profile, 'email', None) if hasattr(user, 'profile') and user.profile else get_field('email', 'email'),
            'program': getattr(academic_info, 'program', None) if academic_info else get_field('program', 'program'),
            'civil_status': getattr(user.profile, 'civil_status', None) if hasattr(user, 'profile') and user.profile else get_field('civil_status', 'civil status'),
            'age': getattr(user.profile, 'age', None) if hasattr(user, 'profile') and user.profile else get_field('age', 'age'),
            'social_media': getattr(user.profile, 'social_media', None) if hasattr(user, 'profile') and user.profile else get_field('social_media', 'social media'),
            # CRITICAL FIX: For school_name, prioritize AcademicInfo, avoid tracker answers that might match wrong fields
            'school_name': getattr(academic_info, 'school_name', None) if academic_info else None,
            'q_post_graduate_degree': getattr(academic_info, 'q_post_graduate_degree', None) if academic_info else None,
            'q_units_obtained': getattr(academic_info, 'q_units_obtained', None) if academic_info else None,
            'q_institution_name': getattr(academic_info, 'q_institution_name', None) if academic_info else None,
            'q_study_start_date': str(getattr(academic_info, 'q_study_start_date', None)) if academic_info and getattr(academic_info, 'q_study_start_date', None) else None,
            'pursue_further_study': getattr(academic_info, 'pursue_further_study', None) if academic_info else None,
            'profile_pic': _build_profile_pic_url(user),
            # Employment data - Prefer TrackerData (Part III) over EmploymentHistory for accurate current data
            'employment_type': getattr(tracker_data, 'q_employment_type', None) if tracker_data else None,
            'q_awards_received': getattr(tracker_data, 'q_awards_received', None) if tracker_data else None,
            'q_unemployment_reason': getattr(tracker_data, 'q_unemployment_reason', None) if tracker_data else None,
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
        
        # DEBUG: Log final data being returned
        logger.debug(f"Final data being returned:")
        logger.debug(f"  - phone: '{data.get('phone')}'")
        logger.debug(f"  - email: '{data.get('email')}'")
        logger.debug(f"  - social_media: '{data.get('social_media')}'")
        logger.debug(f"  - q_study_start_date: '{data.get('q_study_start_date')}'")
        logger.debug(f"  - q_institution_name: '{data.get('q_institution_name')}'")
        logger.debug(f"  - school_name: '{data.get('school_name')}'")
        logger.debug(f"  - company_name_current: '{data.get('company_name_current')}'")
        logger.debug(f"=== END DEBUG ===")
        
        return JsonResponse({'success': True, 'alumni': data})
    except User.DoesNotExist as e:
        logger.error(f"User with id {user_id} not found: {e}")
        return JsonResponse({'success': False, 'message': 'User not found'}, status=404)
