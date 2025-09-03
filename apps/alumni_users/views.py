from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from apps.shared.models import User

# Create your views here.

@csrf_exempt
@require_http_methods(["GET"])
def alumni_list_view(request):
    year = request.GET.get('year')
    alumni_qs = User.objects.filter(account_type__user=True)
    if year:
        alumni_qs = alumni_qs.filter(year_graduated=year)
    alumni_data = [
        {
            'id': a.user_id,
            'ctu_id': a.acc_username,
            'name': f"{a.f_name} {a.m_name or ''} {a.l_name}",
            'course': a.course,
            'batch': a.year_graduated,
            'status': a.user_status,
            'gender': a.gender,
            'birthdate': str(a.birthdate),
            'phone': a.phone_num,
            'address': a.address,
            'email': a.email,
            'program': a.program,
            'civil_status': a.civil_status,
            'age': a.age,
            'social_media': a.social_media,
            'school_name': a.school_name,
        }
        for a in alumni_qs
    ]
    return JsonResponse({'success': True, 'alumni': alumni_data})

@csrf_exempt
@require_http_methods(["GET"])
def alumni_detail_view(request, user_id):
    from apps.shared.models import TrackerResponse, Question
    try:
        user = User.objects.get(user_id=user_id)
        tracker_responses = TrackerResponse.objects.filter(user=user).order_by('-submitted_at')
        latest_tracker = tracker_responses.first() if tracker_responses.exists() else None
        tracker_answers = latest_tracker.answers if latest_tracker and latest_tracker.answers else {}
        question_text_map = {}
        if tracker_answers:
            qids = [int(qid) for qid in tracker_answers.keys() if str(qid).isdigit()]
            for q in Question.objects.filter(id__in=qids):
                question_text_map[q.text.lower()] = tracker_answers.get(str(q.id)) or tracker_answers.get(q.id)
        def get_field(field, *question_labels):
            for label in question_labels:
                for qtext, answer in question_text_map.items():
                    if label in qtext:
                        return answer
            # Special handling for birthdate to avoid 'None' string
            if field == 'birthdate':
                val = getattr(user, field, None)
                return str(val) if val else ''
            return getattr(user, field, '')
        data = {
            'id': user.user_id,
            'ctu_id': user.acc_username,
            'first_name': get_field('f_name', 'first name'),
            'middle_name': get_field('m_name', 'middle name'),
            'last_name': get_field('l_name', 'last name'),
            'course': get_field('course', 'course'),
            'batch': get_field('year_graduated', 'batch', 'year graduated'),
            'status': get_field('user_status', 'status'),
            'gender': get_field('gender', 'gender'),
            'birthdate': get_field('birthdate', 'birthdate', 'birth date', 'birthday', 'date of birth', 'dob', 'bday'),
            'phone': get_field('phone_num', 'phone', 'contact', 'mobile'),
            'address': get_field('address', 'address'),
            'email': get_field('email', 'email'),
            'program': get_field('program', 'program'),
            'civil_status': get_field('civil_status', 'civil status'),
            'age': get_field('age', 'age'),
            'social_media': get_field('social_media', 'social media'),
            'school_name': get_field('school_name', 'school name'),
        }
        return JsonResponse({'success': True, 'alumni': data})
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'User not found'}, status=404)
