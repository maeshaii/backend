"""
Tracker API endpoints for managing tracker questions, responses, and form settings.
If this module grows further, consider splitting into submodules (e.g., questions, responses, forms).
"""

import logging
from django.shortcuts import render
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
import json
from apps.shared.models import QuestionCategory, TrackerResponse, Question, TrackerForm

logger = logging.getLogger(__name__)

# Create your views here.

@api_view(["GET"]) 
@permission_classes([IsAuthenticated])
def tracker_questions_view(request):
    """Return all tracker categories with their questions."""
    try:
        categories = []
        for cat in QuestionCategory.objects.prefetch_related('questions').all():
            categories.append({
                "id": cat.id,
                "title": cat.title,
                "description": cat.description,
                "questions": [
                    {
                        "id": q.id,
                        "text": q.text,
                        "type": q.type,
                        "options": q.options or []
                    }
                    for q in cat.questions.all()
                ]
            })
        return JsonResponse({"success": True, "categories": categories})
    except Exception as e:
        logger.error(f"Error in tracker_questions_view: {e}")
        return JsonResponse({"success": False, "message": "Failed to load questions"}, status=500)

@api_view(["GET"]) 
@permission_classes([IsAuthenticated])
def tracker_responses_view(request):
    """List tracker responses, optionally filtered by batch year, merging basic user fields."""
    from apps.shared.models import User
    try:
        responses = []
        batch_year = request.GET.get('batch_year')
        # Map export labels to dotted field paths on related models
        basic_fields = {
            'First Name': 'f_name',
            'Middle Name': 'm_name',
            'Last Name': 'l_name',
            'Gender': 'gender',
            'Birthdate': 'profile.birthdate',
            'Phone Number': 'profile.phone_num',
            'Address': 'profile.address',
            'Social Media': 'profile.social_media',
            'Civil Status': 'profile.civil_status',
            'Age': 'profile.age',
            'Email': 'profile.email',
            'Program Name': 'academic_info.program',
            'Status': 'user_status',
        }
        tracker_responses = (
            TrackerResponse.objects
            .select_related('user', 'user__profile', 'user__academic_info')
            .prefetch_related('files')
            .all()
        )
        if batch_year:
            tracker_responses = tracker_responses.filter(user__academic_info__year_graduated=batch_year)

        def resolve_attr(obj, path):
            current = obj
            for part in path.split('.'):
                current = getattr(current, part, None)
                if current is None:
                    return None
            return current

        for resp in tracker_responses:
            user = resp.user
            merged_answers = resp.answers.copy() if resp.answers else {}
            # Attach file uploads metadata
            for file_upload in resp.files.all():
                question_id_str = str(file_upload.question_id)
                merged_answers[question_id_str] = {
                    'type': 'file',
                    'filename': file_upload.original_filename,
                    'file_url': file_upload.file.url,
                    'file_size': file_upload.file_size,
                    'uploaded_at': file_upload.uploaded_at.strftime('%Y-%m-%d %H:%M:%S')
                }
            # Fill missing basic fields from related models
            for label, path in basic_fields.items():
                if label not in merged_answers or merged_answers[label] in [None, '', 'No answer']:
                    value = resolve_attr(user, path)
                    if value is not None and value != '':
                        merged_answers[label] = str(value)
            responses.append({
                'user_id': user.user_id,
                'name': f'{user.f_name} {user.l_name}',
                'answers': merged_answers
            })
        return JsonResponse({'success': True, 'responses': responses})
    except Exception as e:
        logger.error(f"Error in tracker_responses_view: {e}")
        return JsonResponse({'success': False, 'message': 'Failed to load responses'}, status=500)

@api_view(["GET"]) 
@permission_classes([IsAuthenticated])
def tracker_responses_by_user_view(request, user_id):
    try:
        # Ensure user_id is an integer
        user_id = int(user_id)
        from apps.shared.models import User
        user = User.objects.get(user_id=user_id)
        responses = []
        for resp in TrackerResponse.objects.select_related('user').filter(user__user_id=user_id):
            responses.append({
                'name': f'{resp.user.f_name} {resp.user.l_name}',
                'answers': resp.answers,
                'submitted_at': resp.submitted_at
            })
        return JsonResponse({'success': True, 'responses': responses})
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@api_view(["POST"]) 
@permission_classes([IsAuthenticated])
def add_category_view(request):
    data = json.loads(request.body)
    title = data.get('title')
    description = data.get('description', '')
    if not title:
        return JsonResponse({'success': False, 'message': 'Title is required'}, status=400)
    cat = QuestionCategory.objects.create(title=title, description=description)
    return JsonResponse({'success': True, 'category': {'id': cat.id, 'title': cat.title, 'description': cat.description, 'questions': []}})

@api_view(["DELETE"]) 
@permission_classes([IsAuthenticated])
def delete_category_view(request, category_id):
    try:
        cat = QuestionCategory.objects.get(id=category_id)
        cat.delete()
        return JsonResponse({'success': True})
    except QuestionCategory.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Category not found'}, status=404)

@api_view(["DELETE"]) 
@permission_classes([IsAuthenticated])
def delete_question_view(request, question_id):
    try:
        q = Question.objects.get(id=question_id)
        q.delete()
        return JsonResponse({'success': True})
    except Question.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Question not found'}, status=404)

@api_view(["POST"]) 
@permission_classes([IsAuthenticated])
def add_question_view(request):
    data = json.loads(request.body)
    category_id = data.get('category_id')
    text = data.get('text')
    qtype = data.get('type')
    options = data.get('options', [])
    if not (category_id and text and qtype):
        return JsonResponse({'success': False, 'message': 'Missing required fields'}, status=400)
    try:
        category = QuestionCategory.objects.get(id=category_id)
    except QuestionCategory.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Category not found'}, status=404)
    q = Question.objects.create(category=category, text=text, type=qtype, options=options)
    return JsonResponse({'success': True, 'question': {
        'id': q.id, 'text': q.text, 'type': q.type, 'options': q.options or []
    }})

@api_view(["PUT"]) 
@permission_classes([IsAuthenticated])
def update_category_view(request, category_id):
    data = json.loads(request.body)
    title = data.get('title')
    description = data.get('description', '')
    try:
        cat = QuestionCategory.objects.get(id=category_id)
        if title:
            cat.title = title
        cat.description = description
        cat.save()
        return JsonResponse({'success': True, 'category': {'id': cat.id, 'title': cat.title, 'description': cat.description}})
    except QuestionCategory.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Category not found'}, status=404)

@api_view(["PUT"]) 
@permission_classes([IsAuthenticated])
def update_question_view(request, question_id):
    data = json.loads(request.body)
    text = data.get('text')
    qtype = data.get('type')
    options = data.get('options', [])
    try:
        q = Question.objects.get(id=question_id)
        if text:
            q.text = text
        if qtype:
            q.type = qtype
        q.options = options
        q.save()
        return JsonResponse({'success': True, 'question': {'id': q.id, 'text': q.text, 'type': q.type, 'options': q.options or []}})
    except Question.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Question not found'}, status=404)

@api_view(["PUT"]) 
@permission_classes([IsAuthenticated])
def update_tracker_form_title_view(request, tracker_form_id):
    import json
    try:
        data = json.loads(request.body)
        title = data.get('title')
        if title is None:
            return JsonResponse({'success': False, 'message': 'Title is required'}, status=400)
        form = TrackerForm.objects.get(pk=tracker_form_id)
        form.title = title
        form.save()
        return JsonResponse({'success': True, 'title': form.title})
    except TrackerForm.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'TrackerForm not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@api_view(["GET"]) 
@permission_classes([IsAuthenticated])
def tracker_form_view(request, tracker_form_id):
    try:
        form = TrackerForm.objects.get(pk=tracker_form_id)
        return JsonResponse({'success': True, 'title': form.title or 'Alumni Tracker Form'})
    except TrackerForm.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'TrackerForm not found'}, status=404)

@api_view(["GET"]) 
@permission_classes([IsAuthenticated])
def check_user_tracker_status_view(request):
    from apps.shared.models import User, TrackerResponse
    
    user_id = request.GET.get('user_id')
    if not user_id:
        return JsonResponse({'success': False, 'message': 'user_id is required'}, status=400)
    
    try:
        user = User.objects.get(user_id=user_id)
        existing_response = TrackerResponse.objects.filter(user=user).first()
        
        return JsonResponse({
            'success': True, 
            'has_submitted': existing_response is not None,
            'submitted_at': existing_response.submitted_at.strftime('%Y-%m-%d %H:%M:%S') if existing_response else None
        })
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@api_view(["POST"]) 
@permission_classes([IsAuthenticated])
def submit_tracker_response_view(request):
    import json
    from django.utils import timezone
    from apps.shared.models import TrackerResponse, User, Notification, TrackerFileUpload
    import os

    try:
        user_id = request.POST.get('user_id')
        answers_json = request.POST.get('answers')
        
        if not user_id or not answers_json:
            return JsonResponse({'success': False, 'message': 'Missing user_id or answers'}, status=400)
        
        # Parse answers JSON
        answers = json.loads(answers_json)
        user = User.objects.get(pk=user_id)
        
        # Check if user has already submitted a response
        existing_response = TrackerResponse.objects.filter(user=user).first()
        if existing_response:
            return JsonResponse({'success': False, 'message': 'You have already submitted the tracker form'}, status=400)
        
        # Create the tracker response
        tr = TrackerResponse.objects.create(user=user, answers=answers, submitted_at=timezone.now())
        
        # Handle file uploads
        uploaded_files = []
        for question_id, answer in answers.items():
            if isinstance(answer, dict) and answer.get('type') == 'file':
                # This is a file upload answer
                file_key = f'file_{question_id}'
                if file_key in request.FILES:
                    uploaded_file = request.FILES[file_key]
                    
                    # Validate file size (10MB limit)
                    if uploaded_file.size > 10 * 1024 * 1024:  # 10MB
                        return JsonResponse({'success': False, 'message': f'File {uploaded_file.name} is too large. Maximum size is 10MB.'}, status=400)
                    
                    # Validate file type
                    allowed_extensions = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png', '.gif']
                    file_extension = os.path.splitext(uploaded_file.name)[1].lower()
                    if file_extension not in allowed_extensions:
                        return JsonResponse({'success': False, 'message': f'File type {file_extension} is not allowed. Allowed types: {", ".join(allowed_extensions)}'}, status=400)
                    
                    # Save the file
                    file_upload = TrackerFileUpload.objects.create(
                        response=tr,
                        question_id=int(question_id),
                        file=uploaded_file,
                        original_filename=uploaded_file.name,
                        file_size=uploaded_file.size
                    )
                    uploaded_files.append(file_upload)
        
        # Legacy direct writes to `User` have been removed.
        # Domain updates are handled in TrackerResponse.save() via update_user_fields().

        # Create a thank you notification
        Notification.objects.create(
            user=user,
            notif_type='CCICT',
            subject='Thank You for Completing the Tracker Form',
            notifi_content=f'Thank you {user.f_name} {user.l_name} for completing the alumni tracker form. Your response has been recorded successfully.',
            notif_date=timezone.now()
        )

        # Notify all admin users that a tracker response was submitted
        try:
            from apps.shared.models import User as SharedUser, AccountType as SharedAccountType
            admin_accounts = SharedUser.objects.filter(account_type__admin=True)
            for admin_user in admin_accounts:
                Notification.objects.create(
                    user=admin_user,
                    notif_type='tracker_submission',
                    subject='New Tracker Response Submitted',
                    notifi_content=f'{user.f_name} {user.l_name} has submitted a tracker response.',
                    notif_date=timezone.now()
                )
        except Exception:
            pass
        
        return JsonResponse({
            'success': True, 
            'message': 'Response recorded', 
            'user_id': user.user_id,
            'files_uploaded': len(uploaded_files)
        })
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON in answers'}, status=400)
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@api_view(["GET"]) 
@permission_classes([IsAuthenticated])
def tracker_accepting_responses_view(request, tracker_form_id):
    try:
        form = TrackerForm.objects.get(pk=tracker_form_id)
        return JsonResponse({'success': True, 'accepting_responses': form.accepting_responses})
    except TrackerForm.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'TrackerForm not found'}, status=404)

@api_view(["PUT"]) 
@permission_classes([IsAuthenticated])
def update_tracker_accepting_responses_view(request, tracker_form_id):
    try:
        form = TrackerForm.objects.get(pk=tracker_form_id)
        data = json.loads(request.body)
        accepting = data.get('accepting_responses')
        if accepting is None:
            return JsonResponse({'success': False, 'message': 'accepting_responses is required'}, status=400)
        form.accepting_responses = bool(accepting)
        form.save()
        return JsonResponse({'success': True, 'accepting_responses': form.accepting_responses})
    except TrackerForm.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'TrackerForm not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@api_view(["GET"]) 
@permission_classes([IsAuthenticated])
def get_active_tracker_form(request):
    form = TrackerForm.objects.order_by('-id').first()  # Fixed: use 'id' instead of 'tracker_form_id'
    if form:
        return JsonResponse({'tracker_form_id': form.pk})
    
    # If no TrackerForm exists, create one automatically
    try:
        default_form = TrackerForm.objects.create(
            title="CTU MAIN ALUMNI TRACKER",
            description="Default tracker form for CTU alumni",
            accepting_responses=True
        )
        return JsonResponse({'tracker_form_id': default_form.pk})
    except Exception as e:
        return JsonResponse({'tracker_form_id': None, 'error': str(e)}, status=500)

@api_view(["GET"]) 
@permission_classes([IsAuthenticated])
def file_upload_stats_view(request):
    """Get statistics about file uploads grouped by question type"""
    try:
        from apps.shared.models import TrackerFileUpload, Question
        
        # Get all file uploads with question information
        file_uploads = TrackerFileUpload.objects.select_related('response__user').all()
        
        # Group by question
        stats = {}
        for upload in file_uploads:
            question = Question.objects.filter(id=upload.question_id).first()
            question_text = question.text if question else f"Question ID: {upload.question_id}"
            
            if question_text not in stats:
                stats[question_text] = {
                    'question_id': upload.question_id,
                    'total_files': 0,
                    'total_size_mb': 0,
                    'users': set(),
                    'files': []
                }
            
            stats[question_text]['total_files'] += 1
            stats[question_text]['total_size_mb'] += upload.file_size / 1024 / 1024
            stats[question_text]['users'].add(upload.response.user.user_id)
            stats[question_text]['files'].append({
                'filename': upload.original_filename,
                'user': f"{upload.response.user.f_name} {upload.response.user.l_name}",
                'file_size_mb': round(upload.file_size / 1024 / 1024, 2),
                'uploaded_at': upload.uploaded_at.strftime('%Y-%m-%d %H:%M:%S'),
                'file_url': upload.file.url
            })
        
        # Convert sets to counts and format the response
        formatted_stats = []
        for question_text, data in stats.items():
            formatted_stats.append({
                'question_text': question_text,
                'question_id': data['question_id'],
                'total_files': data['total_files'],
                'total_size_mb': round(data['total_size_mb'], 2),
                'unique_users': len(data['users']),
                'files': data['files']
            })
        
        return JsonResponse({
            'success': True,
            'stats': formatted_stats
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)
