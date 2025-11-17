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
        for cat in QuestionCategory.objects.prefetch_related('questions').order_by('order'):
            categories.append({
                "id": cat.id,
                "title": cat.title,
                "description": cat.description,
                "questions": [
                    {
                        "id": q.id,
                        "text": q.text,
                        "type": q.type,
                        "options": q.options or [],
                        "required": q.required,
                        "order": q.order
                    }
                    for q in cat.questions.all().order_by('order')
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
            try:
                user = resp.user
                if not user:
                    continue
                
                # Safely get answers, defaulting to empty dict
                merged_answers = {}
                if resp.answers:
                    try:
                        merged_answers = resp.answers.copy() if isinstance(resp.answers, dict) else {}
                    except (AttributeError, TypeError):
                        merged_answers = {}
                
                # Attach file uploads metadata
                try:
                    for file_upload in resp.files.all():
                        try:
                            question_id_str = str(file_upload.question_id)
                            file_url = ''
                            if file_upload.file:
                                try:
                                    file_url = file_upload.file.url
                                except (ValueError, AttributeError):
                                    file_url = ''
                            
                            merged_answers[question_id_str] = {
                                'type': 'file',
                                'filename': file_upload.original_filename or '',
                                'file_url': file_url,
                                'file_size': file_upload.file_size or 0,
                                'uploaded_at': file_upload.uploaded_at.strftime('%Y-%m-%d %H:%M:%S') if file_upload.uploaded_at else ''
                            }
                        except Exception as e:
                            logger.warning(f"Error processing file upload for response {resp.id}: {e}")
                            continue
                except Exception as e:
                    logger.warning(f"Error accessing files for response {resp.id}: {e}")
                
                # Fill missing basic fields from related models
                for label, path in basic_fields.items():
                    try:
                        if label not in merged_answers or merged_answers[label] in [None, '', 'No answer']:
                            value = resolve_attr(user, path)
                            if value is not None and value != '':
                                # Handle date/datetime objects
                                if hasattr(value, 'isoformat'):
                                    merged_answers[label] = value.isoformat()
                                elif hasattr(value, 'strftime'):
                                    merged_answers[label] = value.strftime('%Y-%m-%d')
                                else:
                                    merged_answers[label] = str(value)
                    except Exception as e:
                        logger.warning(f"Error resolving field {label} for user {user.user_id}: {e}")
                        continue
                
                responses.append({
                    'user_id': user.user_id,
                    'name': f'{user.f_name or ""} {user.l_name or ""}'.strip(),
                    'answers': merged_answers,
                    'submitted_at': resp.submitted_at.isoformat() if resp.submitted_at else None
                })
            except Exception as e:
                logger.warning(f"Error processing tracker response {resp.id}: {e}")
                continue
        
        return JsonResponse({'success': True, 'responses': responses})
    except Exception as e:
        logger.error(f"Error in tracker_responses_view: {e}", exc_info=True)
        return JsonResponse({'success': False, 'message': f'Failed to load responses: {str(e)}'}, status=500)

@api_view(["GET"]) 
@permission_classes([IsAuthenticated])
def tracker_responses_by_user_view(request, user_id):
    try:
        # Ensure user_id is an integer
        user_id = int(user_id)
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
    
    user_id = request.GET.get('user_id')
    if not user_id:
        return JsonResponse({'success': False, 'message': 'user_id is required'}, status=400)
    
    try:
        user = User.objects.get(user_id=user_id)
        # Only check for FINAL submissions, not drafts
        existing_response = TrackerResponse.objects.filter(user=user, is_draft=False).first()
        
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
def save_tracker_draft_view(request):
    """Auto-save tracker responses as draft (doesn't trigger notifications or data processing)"""
    import json
    from django.utils import timezone
    from apps.shared.models import TrackerResponse, User
    
    try:
        user_id = request.data.get('user_id')
        answers_json = request.data.get('answers')
        
        if not user_id:
            return JsonResponse({'success': False, 'message': 'Missing user_id'}, status=400)
        
        # Empty answers are okay for drafts
        if answers_json is None:
            answers = {}
        elif isinstance(answers_json, str):
            answers = json.loads(answers_json)
        else:
            answers = answers_json
        
        # SANITIZE: Remove empty objects, null, undefined, and other invalid values
        # that React can't render as text in input fields
        sanitized_answers = {}
        for key, value in answers.items():
            # Skip empty objects, empty dicts, null, None
            if value is None:
                continue
            if isinstance(value, dict) and len(value) == 0:
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
    """Load saved draft for a user"""
    from apps.shared.models import TrackerResponse, User
    
    try:
        user_id = request.GET.get('user_id')
        if not user_id:
            return JsonResponse({'success': False, 'message': 'Missing user_id'}, status=400)
        
        user = User.objects.get(user_id=user_id)
        
        # Try to find a draft
        draft = TrackerResponse.objects.filter(user=user, is_draft=True).first()
        
        if draft:
            # SANITIZE: Remove empty objects and invalid values from loaded data
            # This protects against corrupted data that's already in the database
            sanitized_answers = {}
            for key, value in draft.answers.items():
                # Skip empty objects, empty dicts, null, None
                if value is None:
                    continue
                if isinstance(value, dict) and len(value) == 0:
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

        # Award engagement points for completing tracker form (configurable points for Alumni only)
        if user.account_type and user.account_type.user:  # Check if Alumni
            try:
                from apps.shared.models import UserPoints, EngagementPointsSettings
                from apps.api.views import award_engagement_points
                
                # Use the award_engagement_points function which handles settings
                award_engagement_points(user, 'tracker_form')
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error awarding tracker points: {e}")
        
        # Create a thank you notification
        thank_you_notification = Notification.objects.create(
            user=user,
            notif_type='CCICT',
            subject='Thank You for Completing the Tracker Form',
            notifi_content=f'Thank you {user.f_name} {user.l_name} for completing the alumni tracker form. Your response has been recorded successfully.',
            notif_date=timezone.now()
        )

        # Broadcast thank you notification in real-time
        try:
            from apps.messaging.notification_broadcaster import broadcast_notification
            broadcast_notification(thank_you_notification)
        except Exception as e:
            logger.error(f"Error broadcasting thank you notification: {e}")

        # Notify all admin users that a tracker response was submitted
        admin_notifications = []
        try:
            from apps.shared.models import User as SharedUser, AccountType as SharedAccountType
            from apps.messaging.notification_broadcaster import broadcast_notification
            admin_accounts = SharedUser.objects.filter(account_type__admin=True)
            for admin_user in admin_accounts:
                admin_notification = Notification.objects.create(
                    user=admin_user,
                    notif_type='tracker_submission',
                    subject='New Tracker Response Submitted',
                    notifi_content=f'{user.f_name} {user.l_name} has submitted a tracker response.',
                    notif_date=timezone.now()
                )
                admin_notifications.append(admin_notification)
                # Broadcast admin notification in real-time
                try:
                    broadcast_notification(admin_notification)
                except Exception as e:
                    logger.error(f"Error broadcasting admin notification: {e}")
        except Exception as e:
            logger.error(f"Error creating admin notifications: {e}")
        
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
