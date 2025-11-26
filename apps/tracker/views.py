"""
Tracker API endpoints for managing tracker questions, responses, and form settings.
If this module grows further, consider splitting into submodules (e.g., questions, responses, forms).
"""

import logging
from django.shortcuts import render
from django.http import JsonResponse
from django.db import models
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
import json
from apps.shared.models import QuestionCategory, TrackerResponse, Question, TrackerForm
# Security: Role-based permissions
from apps.api.permissions import IsAdmin

logger = logging.getLogger(__name__)

# Create your views here.

@api_view(["GET"]) 
@permission_classes([IsAuthenticated])
def tracker_questions_view(request):
    """Return all tracker categories with their questions."""
    try:
        categories = []
        for cat in QuestionCategory.objects.order_by('order'):
            questions_list = []
            # Get questions using values() to select only columns that exist
            # Exclude 'required' from the SELECT to avoid database errors
            questions_data = Question.objects.filter(category=cat).values('id', 'text', 'type', 'options', 'order').order_by('order')
            
            for q_data in questions_data:
                questions_list.append({
                    "id": q_data['id'],
                    "text": q_data['text'],
                    "type": q_data['type'],
                    "options": q_data['options'] or [],
                    "required": False,  # Default to False since column doesn't exist in database
                    "order": q_data['order']
                })
            
            categories.append({
                "id": cat.id,
                "title": cat.title,
                "description": getattr(cat, 'description', ''),
                "questions": questions_list
            })
        return JsonResponse({"success": True, "categories": categories})
    except Exception as e:
        logger.error(f"Error in tracker_questions_view: {e}", exc_info=True)
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
            """Safely resolve nested attribute paths, handling missing relationships."""
            try:
                current = obj
                for part in path.split('.'):
                    if current is None:
                        return None
                    try:
                        current = getattr(current, part, None)
                    except Exception:
                        # Handle RelatedObjectDoesNotExist for OneToOne relationships
                        return None
                    if current is None:
                        return None
                return current
            except Exception:
                return None

        for resp in tracker_responses:
            user = resp.user
            merged_answers = resp.answers.copy() if resp.answers else {}
            
            # 🔧 FIX: First, clean up broken file references (where answer says "file" but no TrackerFileUpload exists)
            actual_file_question_ids = set()
            for file_upload in resp.files.all():
                actual_file_question_ids.add(str(file_upload.question_id))
            
            # Remove file metadata from answers if no actual file exists
            for question_id, answer in list(merged_answers.items()):
                if isinstance(answer, dict) and answer.get('type') == 'file':
                    if question_id not in actual_file_question_ids:
                        # ⚠️ File metadata exists but no actual file uploaded (bug from before fix)
                        logger.warning(f"🧹 Cleaning broken file reference for question {question_id} in response {resp.id}")
                        merged_answers[question_id] = "No file uploaded"
            
            # Attach file uploads metadata with absolute URLs
            for file_upload in resp.files.all():
                question_id_str = str(file_upload.question_id)
                # Build absolute URL for file
                file_url = None
                if file_upload.file:
                    try:
                        # Get relative URL from FileField
                        relative_url = file_upload.file.url
                        # Ensure absolute URL
                        if relative_url.startswith('http://') or relative_url.startswith('https://'):
                            file_url = relative_url
                        else:
                            file_url = request.build_absolute_uri(relative_url)
                    except Exception as e:
                        logger.error(f"Error building file URL for file_upload {file_upload.id}: {e}")
                        file_url = None
                
                merged_answers[question_id_str] = {
                    'type': 'file',
                    'filename': file_upload.original_filename,
                    'file_url': file_url,
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
                'answers': merged_answers,
                'submitted_at': resp.submitted_at.isoformat() if resp.submitted_at else None
            })
        return JsonResponse({'success': True, 'responses': responses})
    except Exception as e:
        logger.error(f"Error in tracker_responses_view: {e}", exc_info=True)
        return JsonResponse({'success': False, 'message': f'Failed to load responses: {str(e)}'}, status=500)

@api_view(["GET"]) 
@permission_classes([IsAuthenticated])
def tracker_responses_by_user_view(request, user_id):
    """
    Get tracker responses for a specific user
    
    🔒 SECURITY: IDOR Protection - Users can only view their own responses (admins can view any)
    """
    try:
        # Ensure user_id is an integer
        user_id = int(user_id)
        
        # 🔒 SECURITY: IDOR Protection - Verify user can access these responses
        requesting_user_id = request.user.user_id
        is_admin = getattr(request.user.account_type, 'admin', False)
        
        if str(requesting_user_id) != str(user_id) and not is_admin:
            logger.warning(
                f"IDOR ATTACK PREVENTED: User {requesting_user_id} ({request.user.acc_username}) "
                f"attempted to access tracker responses for user {user_id}"
            )
            return JsonResponse({
                'success': False,
                'message': 'Permission denied. You can only access your own tracker responses.'
            }, status=403)
        
        from apps.shared.models import User
        user = User.objects.get(user_id=user_id)
        responses = []
        for resp in TrackerResponse.objects.select_related('user').defer('is_draft', 'last_saved_at').filter(user__user_id=user_id):
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

@api_view(["GET"]) 
@permission_classes([IsAuthenticated])
def employment_history_respondents_view(request):
    """List users who have filled out their employment history."""
    from apps.shared.models import User, EmploymentHistory, TrackerResponse, TrackerData
    try:
        responses = []
        processed_user_ids = set()
        
        tracker_submissions = (
            TrackerResponse.objects
            .filter(is_draft=False, user__account_type__user=True)
            .select_related('user', 'user__academic_info', 'user__employment')
        )
        
        for submission in tracker_submissions:
            user = submission.user
            if user.user_id in processed_user_ids:
                continue

            employment = getattr(user, 'employment', None)
            has_employment_data = False
            if employment:
                has_employment_data = any([
                    employment.company_name_current,
                    employment.position_current,
                    employment.sector_current,
                    employment.date_started
                ])

            submitted_at = submission.submitted_at.isoformat() if submission.submitted_at else None
            if not submitted_at:
                tracker_data = TrackerData.objects.filter(user=user).first()
                if tracker_data and tracker_data.tracker_submitted_at:
                    submitted_at = tracker_data.tracker_submitted_at.isoformat()

            responses.append({
                'user_id': user.user_id,
                'name': f'{user.f_name} {user.l_name}'.strip() or user.acc_username,
                'program': user.academic_info.program if hasattr(user, 'academic_info') and user.academic_info else None,
                'year_graduated': str(user.academic_info.year_graduated) if hasattr(user, 'academic_info') and user.academic_info and user.academic_info.year_graduated else None,
                'submitted_at': submitted_at,
                'has_employment_data': has_employment_data
            })
            processed_user_ids.add(user.user_id)
        
        return JsonResponse({'success': True, 'responses': responses})
    except Exception as e:
        logger.error(f"Error in employment_history_respondents_view: {e}", exc_info=True)
        return JsonResponse({'success': False, 'message': f'Failed to load employment history respondents: {str(e)}'}, status=500)

@api_view(["POST"]) 
@permission_classes([IsAdmin])  # 🔒 SECURITY FIX: Changed from IsAuthenticated - Admin only
def add_category_view(request):
    """
    Add new tracker category - Admin only
    
    ⚠️ SECURITY: Restricted to Admin - Modifies tracker form structure
    """
    data = json.loads(request.body)
    title = data.get('title')
    description = data.get('description', '')
    if not title:
        return JsonResponse({'success': False, 'message': 'Title is required'}, status=400)
    cat = QuestionCategory.objects.create(title=title, description=description)
    logger.info(f"Admin {request.user.acc_username} created tracker category: {title}")
    return JsonResponse({'success': True, 'category': {'id': cat.id, 'title': cat.title, 'description': cat.description, 'questions': []}})

@api_view(["DELETE"]) 
@permission_classes([IsAdmin])  # 🔒 SECURITY FIX: Changed from IsAuthenticated - Admin only
def delete_category_view(request, category_id):
    """
    Delete tracker category - Admin only
    
    ⚠️ SECURITY: Restricted to Admin - Deletes tracker form categories
    """
    try:
        cat = QuestionCategory.objects.get(id=category_id)
        category_title = cat.title
        cat.delete()
        logger.info(f"Admin {request.user.acc_username} deleted tracker category: {category_title}")
        return JsonResponse({'success': True})
    except QuestionCategory.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Category not found'}, status=404)

@api_view(["DELETE"]) 
@permission_classes([IsAdmin])  # 🔒 SECURITY FIX: Changed from IsAuthenticated - Admin only
def delete_question_view(request, question_id):
    """
    Delete tracker question - Admin only
    
    ⚠️ SECURITY: Restricted to Admin - Deletes tracker questions
    """
    try:
        q = Question.objects.get(id=question_id)
        question_text = q.text
        q.delete()
        logger.info(f"Admin {request.user.acc_username} deleted tracker question: {question_text}")
        return JsonResponse({'success': True})
    except Question.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Question not found'}, status=404)

@api_view(["POST"]) 
@permission_classes([IsAdmin])  # 🔒 SECURITY FIX: Changed from IsAuthenticated - Admin only
def add_question_view(request):
    """
    Add new tracker question - Admin only
    
    ⚠️ SECURITY: Restricted to Admin - Adds questions to tracker form
    """
    data = json.loads(request.body)
    category_id = data.get('category_id')
    text = data.get('text')
    qtype = data.get('type')
    options = data.get('options', [])
    required = data.get('required', False)
    order = data.get('order', 0)
    if not (category_id and text and qtype):
        return JsonResponse({'success': False, 'message': 'Missing required fields'}, status=400)
    try:
        category = QuestionCategory.objects.get(id=category_id)
    except QuestionCategory.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Category not found'}, status=404)
    q = Question.objects.create(category=category, text=text, type=qtype, options=options, required=required, order=order)
    return JsonResponse({'success': True, 'question': {
        'id': q.id, 'text': q.text, 'type': q.type, 'options': q.options or [], 'required': q.required, 'order': q.order
    }})

@api_view(["PUT"]) 
@permission_classes([IsAdmin])  # 🔒 SECURITY FIX: Changed from IsAuthenticated - Admin only
def update_category_view(request, category_id):
    """
    Update tracker category - Admin only
    
    ⚠️ SECURITY: Restricted to Admin - Modifies tracker form categories
    """
    data = json.loads(request.body)
    title = data.get('title')
    description = data.get('description', '')
    try:
        cat = QuestionCategory.objects.get(id=category_id)
        if title:
            cat.title = title
        cat.description = description
        cat.save()
        logger.info(f"Admin {request.user.acc_username} updated tracker category: {cat.title}")
        return JsonResponse({'success': True, 'category': {'id': cat.id, 'title': cat.title, 'description': cat.description}})
    except QuestionCategory.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Category not found'}, status=404)

@api_view(["PUT"]) 
@permission_classes([IsAdmin])  # 🔒 SECURITY FIX: Changed from IsAuthenticated - Admin only
def update_question_view(request, question_id):
    """
    Update tracker question - Admin only
    
    ⚠️ SECURITY: Restricted to Admin - Modifies tracker questions
    """
    data = json.loads(request.body)
    text = data.get('text')
    qtype = data.get('type')
    # Only update fields that are explicitly provided to avoid unintended resets
    options_provided = 'options' in data
    required_provided = 'required' in data
    order_provided = 'order' in data
    options = data.get('options')
    required = data.get('required')
    order = data.get('order')
    try:
        q = Question.objects.get(id=question_id)
        if text:
            q.text = text
        if qtype:
            q.type = qtype
        if options_provided:
            q.options = options or []
        if required_provided:
            q.required = bool(required)
        if order_provided:
            q.order = order
        q.save()
        return JsonResponse({'success': True, 'question': {'id': q.id, 'text': q.text, 'type': q.type, 'options': q.options or [], 'required': q.required, 'order': q.order}})
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
    import logging
    
    logger = logging.getLogger(__name__)
    
    user_id = request.GET.get('user_id')
    if not user_id:
        logger.warning(f'check_user_tracker_status: Missing user_id parameter')
        return JsonResponse({'success': False, 'message': 'user_id is required'}, status=400)
    
    try:
        user = User.objects.get(user_id=user_id)
        # Only check for FINAL submissions, not drafts
        existing_response = TrackerResponse.objects.filter(user=user, is_draft=False).first()
        
        has_submitted = existing_response is not None
        submitted_at = existing_response.submitted_at.strftime('%Y-%m-%d %H:%M:%S') if existing_response else None
        
        logger.info(f'check_user_tracker_status: User {user_id} - has_submitted={has_submitted}, submitted_at={submitted_at}')
        
        # CRITICAL: Always return has_submitted as boolean to ensure consistent response structure
        return JsonResponse({
            'success': True, 
            'has_submitted': bool(has_submitted),  # Explicitly cast to boolean
            'submitted_at': submitted_at
        })
    except User.DoesNotExist:
        logger.error(f'check_user_tracker_status: User {user_id} not found')
        return JsonResponse({'success': False, 'message': 'User not found'}, status=404)
    except Exception as e:
        logger.error(f'check_user_tracker_status: Error for user {user_id}: {str(e)}', exc_info=True)
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def save_tracker_draft_view(request):
    """
    Auto-save tracker responses as draft (doesn't trigger notifications or data processing)
    
    🔒 SECURITY: IDOR Protection - Users can only save their own drafts
    """
    import json
    from django.utils import timezone
    from apps.shared.models import TrackerResponse, User
    
    try:
        user_id = request.data.get('user_id')
        answers_json = request.data.get('answers')
        
        if not user_id:
            return JsonResponse({'success': False, 'message': 'Missing user_id'}, status=400)
        
        # 🔒 SECURITY: IDOR Protection - Verify user can save this draft
        requesting_user_id = request.user.user_id
        is_admin = getattr(request.user.account_type, 'admin', False)
        
        if str(requesting_user_id) != str(user_id) and not is_admin:
            logger.warning(
                f"IDOR ATTACK PREVENTED: User {requesting_user_id} ({request.user.acc_username}) "
                f"attempted to save tracker draft for user {user_id}"
            )
            return JsonResponse({
                'success': False,
                'message': 'Permission denied. You can only save your own drafts.'
            }, status=403)
        
        # Empty answers are okay for drafts
        if answers_json is None:
            answers = {}
        elif isinstance(answers_json, str):
            answers = json.loads(answers_json)
        else:
            answers = answers_json
        
        # SANITIZE: Remove empty objects, null, undefined, and other invalid values
        # that React can't render as text in input fields
        # IMPORTANT: Preserve file upload markers ({ type: 'file', uploaded: true, ... })
        sanitized_answers = {}
        for key, value in answers.items():
            # Skip empty objects, empty dicts, null, None
            if value is None:
                continue
            # PRESERVE file markers (indicate files were uploaded but lost after refresh)
            if isinstance(value, dict):
                # Check if it's a file marker (has 'type' and 'uploaded' keys)
                if 'type' in value and 'uploaded' in value and value.get('type') == 'file' and value.get('uploaded') is True:
                    # This is a file marker - PRESERVE IT
                    sanitized_answers[key] = value
                    continue
                # Skip empty dicts (but file markers are not empty)
                if len(value) == 0:
                    continue
            # Skip empty strings only if explicitly empty (keep spaces, keep "0")
            if isinstance(value, str) and value.strip() == '':
                continue
            # Keep valid values (strings, numbers, booleans, non-empty dicts/lists)
            sanitized_answers[key] = value
        
        user = User.objects.get(user_id=user_id)
        
        # Check if user already has a final submission
        final_submission = TrackerResponse.objects.filter(user=user, is_draft=False).exists()
        if final_submission:
            return JsonResponse({
                'success': False, 
                'message': 'Cannot save draft - form already submitted'
            }, status=400)
        
        # Create or update draft
        tr, created = TrackerResponse.objects.update_or_create(
            user=user,
            defaults={
                'answers': sanitized_answers,
                'is_draft': True
            }
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Draft saved',
            'last_saved_at': tr.last_saved_at.isoformat(),
            'is_new': created
        })
        
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'User not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON in answers'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def load_tracker_draft_view(request):
    """
    Load saved draft for a user
    
    🔒 SECURITY: IDOR Protection - Users can only load their own drafts
    """
    from apps.shared.models import TrackerResponse, User
    
    try:
        user_id = request.GET.get('user_id')
        if not user_id:
            return JsonResponse({'success': False, 'message': 'Missing user_id'}, status=400)
        
        # 🔒 SECURITY: IDOR Protection - Verify user can load this draft
        requesting_user_id = request.user.user_id
        is_admin = getattr(request.user.account_type, 'admin', False)
        
        if str(requesting_user_id) != str(user_id) and not is_admin:
            logger.warning(
                f"IDOR ATTACK PREVENTED: User {requesting_user_id} ({request.user.acc_username}) "
                f"attempted to load tracker draft for user {user_id}"
            )
            return JsonResponse({
                'success': False,
                'message': 'Permission denied. You can only load your own drafts.'
            }, status=403)
        
        user = User.objects.get(user_id=user_id)
        
        # Try to find a draft
        draft = TrackerResponse.objects.filter(user=user, is_draft=True).first()
        
        if draft:
            # SANITIZE: Remove empty objects and invalid values from loaded data
            # This protects against corrupted data that's already in the database
            # IMPORTANT: Preserve file upload markers ({ type: 'file', uploaded: true, ... })
            sanitized_answers = {}
            for key, value in draft.answers.items():
                # Skip empty objects, empty dicts, null, None
                if value is None:
                    continue
                # PRESERVE file markers (indicate files were uploaded but lost after refresh)
                if isinstance(value, dict):
                    # Check if it's a file marker (has 'type' and 'uploaded' keys)
                    if 'type' in value and 'uploaded' in value and value.get('type') == 'file' and value.get('uploaded') is True:
                        # This is a file marker - PRESERVE IT
                        sanitized_answers[key] = value
                        continue
                    # Skip empty dicts (but file markers are not empty)
                    if len(value) == 0:
                        continue
                # Skip empty strings
                if isinstance(value, str) and value.strip() == '':
                    continue
                # Keep valid values
                sanitized_answers[key] = value
            
            return JsonResponse({
                'success': True,
                'has_draft': True,
                'answers': sanitized_answers,
                'last_saved_at': draft.last_saved_at.isoformat()
            })
        else:
            return JsonResponse({
                'success': True,
                'has_draft': False,
                'answers': {}
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
        
        # Check if user has already submitted a FINAL response (not draft)
        existing_response = TrackerResponse.objects.filter(user=user, is_draft=False).first()
        if existing_response:
            return JsonResponse({'success': False, 'message': 'You have already submitted the tracker form'}, status=400)
        
        # Create or update the tracker response (convert draft to final submission)
        tr, created = TrackerResponse.objects.get_or_create(user=user, defaults={
            'answers': answers,
            'submitted_at': timezone.now(),
            'is_draft': False
        })
        
        if not created:
            # Update existing draft to final submission
            tr.answers = answers
            tr.is_draft = False
            tr.submitted_at = timezone.now()
            tr.save()  # This will trigger update_user_fields() because is_draft=False
        else:
            tr.save()  # Triggers update_user_fields() for new submission
        
        # Refresh user object from database after save (update_user_fields modifies it)
        user.refresh_from_db()
        
        # Handle file uploads
        uploaded_files = []
        for question_id, answer in answers.items():
            if isinstance(answer, dict) and answer.get('type') == 'file':
                # Check if this is a multiple file upload (e.g., award supporting documents)
                is_multiple = answer.get('multiple', False)
                
                if is_multiple:
                    # Handle multiple files: file_{question_id}_0, file_{question_id}_1, etc.
                    file_count = answer.get('count', 0)
                    logger.info(f"Processing multiple files for question {question_id}, expected count: {file_count}")
                    
                    for i in range(file_count):
                        file_key = f'file_{question_id}_{i}'
                        if file_key in request.FILES:
                            uploaded_file = request.FILES[file_key]
                            logger.info(f"Found file: {file_key} - {uploaded_file.name}")
                            
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
                            logger.info(f"Saved award document {i + 1} for question {question_id}: {uploaded_file.name}")
                        else:
                            logger.warning(f"Missing file: {file_key}")
                else:
                    # Handle single file upload: file_{question_id}
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

        # Award engagement points for completing tracker form (configurable points for Alumni only)
        if user.account_type and user.account_type.user:  # Check if Alumni
            try:
                from apps.shared.models import UserPoints, EngagementPointsSettings
                from apps.api.views import award_engagement_points
                
                # Use the award_engagement_points function which handles settings
                award_engagement_points(user, 'tracker_form')
            except Exception as e:
                logger.error(f"Error awarding tracker points: {e}")
        
        # Create a thank you notification
        try:
            user_name = f"{user.f_name or ''} {user.l_name or ''}".strip() or "User"
            thank_you_notification = Notification.objects.create(
                user=user,
                notif_type='CCICT',
                subject='Thank You for Completing the Tracker Form',
                notifi_content=f'Thank you {user_name} for completing the alumni tracker form. Your response has been recorded successfully.',
                notif_date=timezone.now()
            )

            # Broadcast thank you notification in real-time
            try:
                from apps.messaging.notification_broadcaster import broadcast_notification
                broadcast_notification(thank_you_notification)
            except Exception as e:
                logger.error(f"Error broadcasting thank you notification: {e}")
        except Exception as e:
            logger.error(f"Error creating thank you notification: {e}")
            # Don't fail the whole submission if notification fails

        # Notify all admin users that a tracker response was submitted
        admin_notifications = []
        try:
            from apps.shared.models import User as SharedUser, AccountType as SharedAccountType
            from apps.messaging.notification_broadcaster import broadcast_notification
            admin_accounts = SharedUser.objects.filter(account_type__admin=True)
            user_name = f"{user.f_name or ''} {user.l_name or ''}".strip() or "A user"
            
            for admin_user in admin_accounts:
                try:
                    admin_notification = Notification.objects.create(
                        user=admin_user,
                        notif_type='tracker_submission',
                        subject='New Tracker Response Submitted',
                        notifi_content=f'{user_name} has submitted a tracker response.',
                        notif_date=timezone.now()
                    )
                    admin_notifications.append(admin_notification)
                    # Broadcast admin notification in real-time
                    try:
                        broadcast_notification(admin_notification)
                    except Exception as e:
                        logger.error(f"Error broadcasting admin notification: {e}")
                except Exception as e:
                    logger.error(f"Error creating admin notification for user {admin_user.user_id}: {e}")
        except Exception as e:
            logger.error(f"Error creating admin notifications: {e}")
        
        return JsonResponse({
            'success': True, 
            'message': 'Response recorded', 
            'user_id': user.user_id,
            'files_uploaded': len(uploaded_files)
        })
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in tracker submission: {e}")
        return JsonResponse({'success': False, 'message': 'Invalid JSON in answers'}, status=400)
    except User.DoesNotExist:
        logger.error(f"User not found in tracker submission: {user_id}")
        return JsonResponse({'success': False, 'message': 'User not found'}, status=404)
    except Exception as e:
        import traceback
        logger.error(f"Unexpected error in tracker submission for user {user_id if 'user_id' in locals() else 'unknown'}: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return JsonResponse({'success': False, 'message': f'Server error: {str(e)}'}, status=500)

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
    # Check if TrackerForm with id=1 exists (required by constraint)
    try:
        form = TrackerForm.objects.get(pk=1)
        return JsonResponse({'tracker_form_id': form.pk})
    except TrackerForm.DoesNotExist:
        # If no TrackerForm exists, create one with id=1 (required by constraint)
        try:
            default_form = TrackerForm.objects.create(
                id=1,  # Explicitly set id=1 to satisfy the CheckConstraint
                title="CTU MAIN ALUMNI TRACKER",
                description="Default tracker form for CTU alumni",
                accepting_responses=True
            )
            return JsonResponse({'tracker_form_id': default_form.pk})
        except Exception as e:
            import traceback
            error_msg = str(e)
            traceback.print_exc()
            return JsonResponse({'tracker_form_id': None, 'error': error_msg}, status=500)

@api_view(["GET"]) 
@permission_classes([IsAuthenticated])
def file_upload_stats_view(request):
    """Get statistics about file uploads grouped by question type - shows ALL file questions"""
    try:
        from apps.shared.models import TrackerFileUpload, Question
        
        # 🔧 FIX: Get ALL file upload questions (not just those with uploads)
        file_questions = Question.objects.filter(type='file').all()
        
        # Initialize stats for ALL file questions
        stats = {}
        for question in file_questions:
            stats[question.text] = {
                'question_id': question.id,
                'question_text': question.text,
                'total_files': 0,
                'total_size_mb': 0,
                'users': set(),
                'files': []
            }
        
        # Get all file uploads
        file_uploads = TrackerFileUpload.objects.select_related('response__user').all()
        
        # Add file upload data to stats with absolute URLs
        for upload in file_uploads:
            question = Question.objects.filter(id=upload.question_id).first()
            if question and question.text in stats:
                question_text = question.text
                stats[question_text]['total_files'] += 1
                stats[question_text]['total_size_mb'] += upload.file_size / 1024 / 1024
                stats[question_text]['users'].add(upload.response.user.user_id)
                
                # Build absolute URL for file
                file_url = None
                if upload.file:
                    try:
                        # Get relative URL from FileField
                        relative_url = upload.file.url
                        # Ensure absolute URL
                        if relative_url.startswith('http://') or relative_url.startswith('https://'):
                            file_url = relative_url
                        else:
                            file_url = request.build_absolute_uri(relative_url)
                    except Exception as e:
                        logger.error(f"Error building file URL for upload {upload.id}: {e}")
                        file_url = None
                
                stats[question_text]['files'].append({
                    'filename': upload.original_filename,
                    'user': f"{upload.response.user.f_name} {upload.response.user.l_name}",
                    'file_size_mb': round(upload.file_size / 1024 / 1024, 2),
                    'uploaded_at': upload.uploaded_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'file_url': file_url
                })
        
        # Convert sets to counts and format the response (sorted by question_id)
        formatted_stats = []
        for question_text, data in sorted(stats.items(), key=lambda x: x[1]['question_id']):
            formatted_stats.append({
                'question_text': data['question_text'],
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
