<<<<<<< HEAD
"""
API views for job alignment confirmation system.
Handles cross-program job alignment with user confirmation.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from apps.shared.models import EmploymentHistory, User, ReportSettings
import logging
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import transaction

logger = logging.getLogger('apps.shared.views')


def parse_boolean(value):
    """Convert string boolean from FormData to actual boolean"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes')
    return False


@api_view(['POST'])
@permission_classes([])  # No authentication required for job alignment confirmation
def confirm_job_alignment(request):
    """
    Confirm or reject cross-program job alignment suggestion.
    
    Expected payload:
    {
        "employment_id": 123,
        "confirmed": true/false  // true = Yes, false = No
    }
    """
    try:
        employment_id = request.data.get('employment_id')
        confirmed = request.data.get('confirmed', False)
        user_id = request.data.get('user_id')
        
        if employment_id is None:
            return Response({
                'error': 'employment_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if user_id is None:
            return Response({
                'error': 'user_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get employment record
        employment = get_object_or_404(EmploymentHistory, id=employment_id)
        
        # Verify user owns this employment record
        if employment.user.user_id != user_id:
            return Response({
                'error': 'Permission denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Confirm the alignment
        employment.confirm_job_alignment(confirmed=confirmed)
        
        # Return updated status
        return Response({
            'success': True,
            'message': 'Job alignment confirmed' if confirmed else 'Job alignment rejected',
            'job_alignment_status': employment.job_alignment_status,
            'job_alignment_title': employment.job_alignment_title,
            'job_alignment_category': employment.job_alignment_category
        })
        
    except Exception as e:
        logger.error(f"Error confirming job alignment: {str(e)}")
        return Response({
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_job_alignment_suggestions(request):
    """
    Get pending job alignment suggestions for the current user.
    Returns employment records that need user confirmation.
    """
    try:
        # Get user's employment records with pending confirmations
        pending_alignments = EmploymentHistory.objects.filter(
            user=request.user,
            job_alignment_status='pending_user_confirmation'
        ).select_related('user')
        
        suggestions = []
        for employment in pending_alignments:
            suggestions.append({
                'employment_id': employment.id,
                'position_current': employment.position_current,
                'company_name_current': employment.company_name_current,
                'suggested_job_title': employment.job_alignment_title,
                'suggested_program': employment.job_alignment_suggested_program,
                'original_program': employment.job_alignment_original_program,
                'match_method': getattr(employment, 'match_method', 'unknown')
            })
        
        return Response({
            'success': True,
            'suggestions': suggestions,
            'count': len(suggestions)
        })
        
    except Exception as e:
        logger.error(f"Error getting job alignment suggestions: {str(e)}")
        return Response({
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([])  # No authentication required for job alignment check
def check_job_alignment(request):
    """
    AUTOCOMPLETE-FIRST SYSTEM: Check job alignment after user input.
    Handles both autocomplete selection and manual typing.
    
    Expected payload:
    {
        "position": "Software Developer",
        "user_id": 123,
        "from_autocomplete": true/false  // Whether user selected from autocomplete
    }
    """
    try:
        position = request.data.get('position', '').strip()
        user_id = request.data.get('user_id')
        from_autocomplete = request.data.get('from_autocomplete', False)
        
        if not position:
            return Response({
                'error': 'Position is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get user
        user = get_object_or_404(User, user_id=user_id)
        
        # Get or create user's employment record for job alignment checking
        employment, created = EmploymentHistory.objects.get_or_create(user=user)
        if created:
            logger.info(f"Created temporary employment record for job alignment check (user {user_id})")
        
        # Temporarily update position for alignment checking (don't save yet)
        employment.position_current = position
        
        # Get user's program for alignment checking
        program = None
        if hasattr(user, 'academic_info') and user.academic_info:
            program = user.academic_info.program
        
        # Perform job alignment check without saving
        employment._check_job_alignment_for_position(position, program)
        
        # Keep user's original input for UI display, don't force uppercase
        # Normalization to uppercase will happen only when saving to database
        display_position = ' '.join(position.strip().split())  # Just normalize whitespace

        # Check if alignment needs confirmation
        needs_confirmation = employment.job_alignment_status == 'pending_user_confirmation'
        
        response_data = {
            'success': True,
            'needs_confirmation': needs_confirmation,
            'job_alignment_status': employment.job_alignment_status,
            'from_autocomplete': from_autocomplete,
            'normalized_position': display_position,  # Send user's input back, not uppercase
            'normalized_company_name': employment.company_name_current,
        }
        
        # DEBUG: Log the response for investigation
        logger.info(f"🔍 check_job_alignment: user={user_id}, pos='{position[:30]}', program={program}, status={employment.job_alignment_status}, needs_confirm={needs_confirmation}")
        
        if needs_confirmation:
            response_data.update({
                'suggestion': {
                    'employment_id': employment.id,
                    'position': display_position,
                    'user_program': user.academic_info.program if hasattr(user, 'academic_info') else 'Unknown',
                    'question': f"Is '{display_position}' aligned to your {user.academic_info.program if hasattr(user, 'academic_info') else 'program'} program?"
                }
            })
        
        return Response(response_data)
        
    except Exception as e:
        logger.error(f"Error checking job alignment: {str(e)}")
        return Response({
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Placeholder functions for API compatibility
def export_alumni_excel(request):
    """Placeholder for alumni export functionality"""
    from django.http import HttpResponse
    return HttpResponse("Export functionality not implemented", status=501)

def import_alumni_excel(request):
    """Placeholder for alumni import functionality"""
    from django.http import HttpResponse
    return HttpResponse("Import functionality not implemented", status=501)

def import_exported_alumni_excel(request):
    """Placeholder for exported alumni import functionality"""
    from django.http import HttpResponse
    return HttpResponse("Import exported functionality not implemented", status=501)

def export_initial_passwords(request):
    """Placeholder for initial passwords export functionality"""
    from django.http import HttpResponse
    return HttpResponse("Export passwords functionality not implemented", status=501)


@api_view(['GET'])
@permission_classes([])  # No authentication required for job suggestions
def get_job_autocomplete_suggestions(request):
    """
    Get job title suggestions for autocomplete dropdown.
    Shows jobs from ALL programs (BSIT + BSIS + BIT-CT) for comprehensive coverage.
    
    Query params:
    - q: search query (optional)
    - limit: max results (default 20)
    """
    try:
        from apps.shared.models import SimpleCompTechJob, SimpleInfoTechJob, SimpleInfoSystemJob
        
        query = request.GET.get('q', '').strip()
        limit = int(request.GET.get('limit', 20))
        
        suggestions = []
        
        # Get suggestions from all 3 job tables
        job_tables = [
            ('BIT-CT', SimpleCompTechJob),
            ('BSIT', SimpleInfoTechJob),
            ('BSIS', SimpleInfoSystemJob)
        ]
        
        for program_name, job_model in job_tables:
            if query:
                # Search with query
                jobs = job_model.objects.filter(
                    job_title__icontains=query
                ).values_list('job_title', flat=True)[:limit//3]
            else:
                # Get popular jobs (first N)
                jobs = job_model.objects.values_list('job_title', flat=True)[:limit//3]
            
            for job_title in jobs:
                suggestions.append({
                    'title': job_title,
                    'program': program_name,
                    'code': f"{program_name}-{hash(job_title) % 10000:04d}"  # Generate code
                })
        
        # Remove duplicates and sort
        seen_titles = set()
        unique_suggestions = []
        for suggestion in suggestions:
            if suggestion['title'] not in seen_titles:
                seen_titles.add(suggestion['title'])
                unique_suggestions.append(suggestion)
        
        # Sort by title
        unique_suggestions.sort(key=lambda x: x['title'])
        
        # Limit results
        unique_suggestions = unique_suggestions[:limit]
        
        return Response({
            'success': True,
            'suggestions': unique_suggestions,
            'count': len(unique_suggestions),
            'query': query
        })
        
    except Exception as e:
        logger.error(f"Error getting job autocomplete suggestions: {str(e)}")
        return Response({
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_report_settings_view(request):
    """
    Get current report header/footer settings for export generation.
    Returns the most recently updated header/footer settings.
    """
    try:
        settings_obj = ReportSettings.get_active_settings()
        
        if not settings_obj:
            # Return default settings structure
            return Response({
                'success': True,
                'settings': None,
                'message': 'No custom settings found. Using defaults.'
            })
        
        # Build response with file URLs
        from django.conf import settings
        from django.core.files.storage import default_storage
        
        response_data = {
            'success': True,
            'settings': {
                'header_enabled': settings_obj.header_enabled,
                'header_layout_type': settings_obj.header_layout_type,
                'left_logo_enabled': settings_obj.left_logo_enabled,
                'left_logo_url': settings_obj.left_logo.url if settings_obj.left_logo else None,
                'right_logo_enabled': settings_obj.right_logo_enabled,
                'right_logo_url': settings_obj.right_logo.url if settings_obj.right_logo else None,
                'header_line1': settings_obj.header_line1,
                'header_line2': settings_obj.header_line2,
                'header_line2_color': settings_obj.header_line2_color,
                'header_line2_bold': settings_obj.header_line2_bold,
                'header_line3': settings_obj.header_line3,
                'header_line4': settings_obj.header_line4,
                'header_line5': settings_obj.header_line5,
                'header_line6': settings_obj.header_line6,
                'header_line6_color': settings_obj.header_line6_color,
                'header_line6_bold': settings_obj.header_line6_bold,
                'footer_enabled': settings_obj.footer_enabled,
                'footer_image_enabled': settings_obj.footer_image_enabled,
                'footer_image_url': settings_obj.footer_image.url if settings_obj.footer_image else None,
                'footer_text1': settings_obj.footer_text1,
                'footer_text2': settings_obj.footer_text2,
                'signature_enabled': settings_obj.signature_enabled,
                'prepared_by_name': settings_obj.prepared_by_name,
                'prepared_by_title': settings_obj.prepared_by_title,
                'approved_by_name': settings_obj.approved_by_name,
                'approved_by_title': settings_obj.approved_by_title,
                'custom_settings': settings_obj.custom_settings,
                'updated_at': settings_obj.updated_at.isoformat()
            }
        }
        
        return Response(response_data)
        
    except Exception as e:
        logger.error(f"Error getting header/footer settings: {str(e)}")
        return Response({
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_report_settings_view(request):
    """
    Update report header/footer settings.
    Supports file uploads for logos.
    
    Expected payload:
    - All header/footer settings fields
    - File uploads: left_logo, right_logo, footer_image
    """
    try:
        # Check if user is admin
        user = request.user
        if not (hasattr(user, 'account_type') and 
                (user.account_type.admin if hasattr(user.account_type, 'admin') else False)):
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get or create settings object
        settings_obj = ReportSettings.get_active_settings()
        if not settings_obj:
            settings_obj = ReportSettings(created_by=user, updated_by=user)
        
        # Update basic fields
        settings_obj.header_enabled = parse_boolean(request.data.get('header_enabled', True))
        settings_obj.header_layout_type = request.data.get('header_layout_type', 'three_column')
        settings_obj.left_logo_enabled = parse_boolean(request.data.get('left_logo_enabled', True))
        settings_obj.right_logo_enabled = parse_boolean(request.data.get('right_logo_enabled', True))
        
        settings_obj.header_line1 = request.data.get('header_line1', '')
        settings_obj.header_line2 = request.data.get('header_line2', '')
        settings_obj.header_line2_color = request.data.get('header_line2_color', '#DC143C')
        settings_obj.header_line2_bold = parse_boolean(request.data.get('header_line2_bold', True))
        settings_obj.header_line3 = request.data.get('header_line3', '')
        settings_obj.header_line4 = request.data.get('header_line4', '')
        settings_obj.header_line5 = request.data.get('header_line5', '')
        settings_obj.header_line6 = request.data.get('header_line6', '')
        settings_obj.header_line6_color = request.data.get('header_line6_color', '#DC143C')
        settings_obj.header_line6_bold = parse_boolean(request.data.get('header_line6_bold', True))
        
        settings_obj.footer_enabled = parse_boolean(request.data.get('footer_enabled', True))
        settings_obj.footer_image_enabled = parse_boolean(request.data.get('footer_image_enabled', True))
        settings_obj.footer_text1 = request.data.get('footer_text1', '')
        settings_obj.footer_text2 = request.data.get('footer_text2', '')
        
        settings_obj.signature_enabled = parse_boolean(request.data.get('signature_enabled', True))
        settings_obj.prepared_by_name = request.data.get('prepared_by_name', '')
        settings_obj.prepared_by_title = request.data.get('prepared_by_title', '')
        settings_obj.approved_by_name = request.data.get('approved_by_name', '')
        settings_obj.approved_by_title = request.data.get('approved_by_title', '')
        
        # Handle file uploads
        if 'left_logo' in request.FILES:
            if settings_obj.left_logo:
                settings_obj.left_logo.delete()
            settings_obj.left_logo = request.FILES['left_logo']
        
        if 'right_logo' in request.FILES:
            if settings_obj.right_logo:
                settings_obj.right_logo.delete()
            settings_obj.right_logo = request.FILES['right_logo']
        
        if 'footer_image' in request.FILES:
            if settings_obj.footer_image:
                settings_obj.footer_image.delete()
            settings_obj.footer_image = request.FILES['footer_image']
        
        # Update metadata
        settings_obj.updated_by = user
        
        settings_obj.save()
        
        return Response({
            'success': True,
            'message': 'Header/Footer Settings updated successfully',
            'settings_id': settings_obj.settings_id
        })
        
    except Exception as e:
        logger.error(f"Error updating header/footer settings: {str(e)}")
        return Response({
            'error': 'Internal server error',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
=======
from django.shortcuts import render
import pandas as pd
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.http import JsonResponse
import os
from .models import User, TrackerResponse, Question
from io import BytesIO
import logging

# Create your views here.

# Export alumni data to Excel

def export_alumni_excel(request):
    batch_year = request.GET.get('batch_year')
    alumni = User.objects.filter(account_type__user=True)
    if batch_year:
        alumni = alumni.filter(year_graduated=batch_year)

    # Basic User model fields to always include
    basic_fields = [
        ("CTU_ID", "acc_username"),
        ("First Name", "f_name"),
        ("Middle Name", "m_name"),
        ("Last Name", "l_name"),
        ("Gender", "gender"),
        ("Birthdate", "birthdate"),
        ("Phone Number", "phone_num"),
        ("Address", "address"),
        ("Social Media", "social_media"),
        ("Civil Status", "civil_status"),
        ("Age", "age"),
        ("Email", "email"),
        ("Program Name", "program"),
        
    ]

    # Collect all tracker question texts that have been answered by any alumni
    all_tracker_qids = set()
    for alum in alumni:
        tracker_responses = TrackerResponse.objects.filter(user=alum).order_by('-submitted_at')
        latest_tracker = tracker_responses.first() if tracker_responses.exists() else None
        tracker_answers = latest_tracker.answers if latest_tracker and latest_tracker.answers else {}
        all_tracker_qids.update([int(qid) for qid in tracker_answers.keys() if str(qid).isdigit()])
    # Get question text for all qids
    tracker_questions = {q.id: q.text for q in Question.objects.filter(id__in=all_tracker_qids)}
    tracker_columns = [tracker_questions[qid] for qid in sorted(tracker_questions.keys())]

    # Build a unique set of export columns: basic fields + tracker question texts (no duplicates)
    export_columns = []
    seen = set()
    for col, _ in basic_fields:
        if col not in seen:
            export_columns.append(col)
            seen.add(col)
    for qtext in tracker_columns:
        if qtext not in seen:
            export_columns.append(qtext)
            seen.add(qtext)

    data = []
    for alum in alumni:
        row = {}
        # Fill basic fields
        for col, field in basic_fields:
            value = getattr(alum, field, "")
            row[col] = value if value is not None else ""
        # Fill tracker answers, but only if not already filled by user model
        tracker_responses = TrackerResponse.objects.filter(user=alum).order_by('-submitted_at')
        latest_tracker = tracker_responses.first() if tracker_responses.exists() else None
        tracker_answers = latest_tracker.answers if latest_tracker and latest_tracker.answers else {}
        for qid, qtext in tracker_questions.items():
            if qtext in row and row[qtext]:
                continue  # Already filled by user model
            answer = tracker_answers.get(str(qid)) or tracker_answers.get(qid)
            if isinstance(answer, list):
                answer = ', '.join(str(a) for a in answer)
            row[qtext] = answer if answer is not None else ""
        data.append(row)
    df = pd.DataFrame(data, columns=export_columns)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=alumni_export.xlsx'
    return response

# Import alumni data from Excel, updating only missing fields
@csrf_exempt
def import_alumni_excel(request):
    if request.method == 'POST' and request.FILES.get('file'):
        batch_year = request.POST.get('batch_year')
        if not batch_year:
            return JsonResponse({'success': False, 'message': 'Batch year is required'}, status=400)
        df = pd.read_excel(request.FILES['file'])
        for _, row in df.iterrows():
            ctu_id = row.get('CTU_ID')
            if not ctu_id:
                continue
            # Try to find user by CTU ID and batch year
            user = User.objects.filter(acc_username=ctu_id, year_graduated=batch_year).first()
            field_map = {
                'First_Name': 'f_name',
                'Middle_Name': 'm_name',
                'Last_Name': 'l_name',
                'Gender': 'gender',
                'Phone_Number': 'phone_num',
                'Address': 'address',
                'Social Media Acc Link': 'social_media',
                'Civil Status': 'civil_status',
                'Company name current': 'company_name_current',
                'salary current': 'salary_current',
                'Post Graduate Degree': 'post_graduate_degree',
                # Add more mappings as needed
            }
            if user:
                # Only update fields that are empty in DB and present in Excel
                for excel_col, model_field in field_map.items():
                    excel_value = row.get(excel_col)
                    if excel_value and (not hasattr(user, model_field) or not getattr(user, model_field) or getattr(user, model_field) == ''):
                        setattr(user, model_field, excel_value)
                user.save()
            else:
                # Create new user for this batch
                user_data = {
                    'acc_username': ctu_id,
                    'year_graduated': batch_year,
                    # Set all fields from Excel if present
                }
                for excel_col, model_field in field_map.items():
                    excel_value = row.get(excel_col)
                    if excel_value:
                        user_data[model_field] = excel_value
                user_data['account_type_id'] = 1  # Default to alumni account type
                User.objects.create(**user_data)
        return JsonResponse({'success': True, 'message': 'Import complete'})
    return JsonResponse({'success': False, 'message': 'No file uploaded'}, status=400)

@csrf_exempt
def import_exported_alumni_excel(request):
    logger = logging.getLogger(__name__)
    debug_info = []
    if request.method == 'POST' and request.FILES.get('file'):
        batch_year = request.POST.get('batch_year')
        if not batch_year:
            return JsonResponse({'success': False, 'message': 'Batch year is required'}, status=400)
        df = pd.read_excel(request.FILES['file'])
        for idx, row in df.iterrows():
            ctu_id = row.get('CTU_ID')
            if not ctu_id:
                debug_info.append(f'Row {idx+2}: Missing CTU_ID, skipped.')
                continue
            user = User.objects.filter(acc_username=ctu_id, year_graduated=batch_year).first()
            field_map = {
                'First_Name': 'f_name',
                'Middle_Name': 'm_name',
                'Last_Name': 'l_name',
                'Gender': 'gender',
                'Phone_Number': 'phone_num',
                'Address': 'address',
                'Social_Media': 'social_media',
                'Civil_Status': 'civil_status',
                'Age': 'age',
                'Email': 'email',
                'Program_Name': 'program',
                'Status': 'status',
                'Company name current': 'company_name_current',
                'Position current': 'position_current',
                'Sector current': 'sector_current',
                'Employment duration current': 'employment_duration_current',
                'Salary current': 'salary_current',
                'Supporting document current': 'supporting_document_current',
                'Awards recognition current': 'awards_recognition_current',
                'Supporting document awards recognition': 'supporting_document_awards_recognition',
                'Unemployment reason': 'unemployment_reason',
                'Pursue further study': 'pursue_further_study',
                'Date started': 'date_started',
                'School name': 'school_name',
                'Birthdate': 'birthdate',
            }
            updated_fields = []
            try:
                if user:
                    for excel_col, model_field in field_map.items():
                        excel_value = row.get(excel_col)
                        if excel_value and (not hasattr(user, model_field) or not getattr(user, model_field) or getattr(user, model_field) == ''):
                            setattr(user, model_field, excel_value)
                            updated_fields.append(model_field)
                    user.save()
                    debug_info.append(f'Row {idx+2}: Updated user {ctu_id} (fields: {", ".join(updated_fields) if updated_fields else "none"})')
                else:
                    user_data = {'acc_username': ctu_id, 'year_graduated': batch_year}
                    for excel_col, model_field in field_map.items():
                        excel_value = row.get(excel_col)
                        if excel_value:
                            user_data[model_field] = excel_value
                    user_data['account_type_id'] = 1
                    User.objects.create(**user_data)
                    debug_info.append(f'Row {idx+2}: Created new user {ctu_id}')
            except Exception as e:
                debug_info.append(f'Row {idx+2}: Error for CTU_ID {ctu_id}: {str(e)}')
        return JsonResponse({'success': True, 'message': 'Import complete', 'debug': debug_info})
    return JsonResponse({'success': False, 'message': 'No file uploaded'}, status=400)
>>>>>>> 746e601016fd6b6113a8116f65f35a08788c789a
