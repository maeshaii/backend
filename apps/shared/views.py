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
import json
import time
from datetime import datetime
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

@api_view(['GET'])
@permission_classes([IsAuthenticated])  # TODO: Change to IsAdmin when implemented - EXPORTS PASSWORDS!
def export_initial_passwords(request):
    """
    Export initial passwords - CRITICAL SECURITY ENDPOINT
    
    ⚠️ SECURITY WARNING: This endpoint will export user passwords!
    ⚠️ MUST be restricted to Admin only when implemented
    ⚠️ Currently placeholder - returns 501 Not Implemented
    
    TODO when implementing:
    1. Change @permission_classes to [IsAdmin]
    2. Add security audit logging
    3. Implement rate limiting
    4. Add confirmation step
    """
    from django.http import HttpResponse
    
    # SECURITY CHECK: Verify user is admin (extra layer of protection)
    try:
        account_type = getattr(request.user, 'account_type', None)
        is_admin = account_type and getattr(account_type, 'admin', False)
        
        if not is_admin:
            logger.warning(
                f"CRITICAL: Non-admin user {request.user.user_id} ({request.user.acc_username}) "
                f"attempted to access password export endpoint"
            )
            return HttpResponse("Forbidden - Admin access only", status=403)
    except Exception as e:
        logger.error(f"Error checking admin permission for password export: {e}")
        return HttpResponse("Forbidden", status=403)
    
    # Placeholder - when implemented, add security logging here
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
        
        # Handle header lines - new dynamic format
        header_lines_json = request.data.get('header_lines')
        if header_lines_json:
            try:
                if isinstance(header_lines_json, str):
                    header_lines = json.loads(header_lines_json)
                else:
                    header_lines = header_lines_json
                
                # Save to custom_settings
                if not settings_obj.custom_settings:
                    settings_obj.custom_settings = {}
                settings_obj.custom_settings['header_lines'] = header_lines
            except (json.JSONDecodeError, TypeError) as e:
                # If parsing fails, continue with old format
                pass
        
        # Handle title lines - new dynamic format
        title_lines_json = request.data.get('title_lines')
        if title_lines_json is not None:  # Check for None explicitly, allow empty arrays
            try:
                if isinstance(title_lines_json, str):
                    title_lines = json.loads(title_lines_json) if title_lines_json else []
                else:
                    title_lines = title_lines_json if title_lines_json else []
                
                # Save to custom_settings (always save, even if empty array)
                if not settings_obj.custom_settings:
                    settings_obj.custom_settings = {}
                settings_obj.custom_settings['title_lines'] = title_lines if isinstance(title_lines, list) else []
            except (json.JSONDecodeError, TypeError) as e:
                # If parsing fails, set to empty array
                if not settings_obj.custom_settings:
                    settings_obj.custom_settings = {}
                settings_obj.custom_settings['title_lines'] = []
        
        # Also update fixed fields for backward compatibility
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
        
        # Handle footer image - clear if disabled, update if new file uploaded
        if not settings_obj.footer_image_enabled:
            # Clear footer image if disabled
            if settings_obj.footer_image:
                settings_obj.footer_image.delete()
                settings_obj.footer_image = None
        elif 'footer_image' in request.FILES:
            # Update footer image if new file uploaded
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_report_presets_view(request):
    """Get all saved header/footer presets"""
    try:
        user = request.user
        if not (hasattr(user, 'account_type') and 
                (user.account_type.admin if hasattr(user.account_type, 'admin') else False)):
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        settings_obj = ReportSettings.get_active_settings()
        if not settings_obj or not settings_obj.custom_settings:
            return Response({
                'success': True,
                'presets': []
            })
        
        presets = settings_obj.custom_settings.get('presets', [])
        return Response({
            'success': True,
            'presets': presets
        })
        
    except Exception as e:
        logger.error(f"Error getting presets: {str(e)}")
        return Response({
            'error': 'Internal server error',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_report_preset_view(request):
    """Save current settings as a preset"""
    try:
        user = request.user
        if not (hasattr(user, 'account_type') and 
                (user.account_type.admin if hasattr(user.account_type, 'admin') else False)):
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        preset_name = request.data.get('name', '').strip()
        if not preset_name:
            return Response({
                'error': 'Preset name is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get current settings - reload from database to ensure we have latest data
        # Use a fresh query to get the most recent settings with updated custom_settings
        settings_obj = ReportSettings.objects.order_by('-updated_at').first()
        if not settings_obj:
            return Response({
                'error': 'No settings found to save as preset'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Ensure custom_settings is initialized
        if not settings_obj.custom_settings:
            settings_obj.custom_settings = {}
        
        # Ensure title_lines exists in custom_settings (defensive check)
        if 'title_lines' not in settings_obj.custom_settings:
            settings_obj.custom_settings['title_lines'] = []
        
        # Get information about which images were uploaded in current session
        # If images_uploaded is provided, only include images that were uploaded
        # If not provided (e.g., from "Save Current as Preset"), include existing images if enabled
        images_uploaded = request.data.get('images_uploaded')
        strict_mode = images_uploaded is not None  # If provided, use strict mode (only uploaded images)
        
        if strict_mode and isinstance(images_uploaded, dict):
            left_logo_uploaded = images_uploaded.get('left_logo', False)
            right_logo_uploaded = images_uploaded.get('right_logo', False)
            footer_image_uploaded = images_uploaded.get('footer_image', False)
        else:
            # If images_uploaded not provided, include existing images if enabled (for "Save Current as Preset")
            left_logo_uploaded = True  # Will be filtered by enabled check
            right_logo_uploaded = True
            footer_image_uploaded = True
        
        # Build preset data with absolute URLs for images
        def get_absolute_url(relative_url):
            """Convert relative URL to absolute URL"""
            if not relative_url:
                return None
            if relative_url.startswith('http'):
                return relative_url
            return request.build_absolute_uri(relative_url)
        
        # Include image URLs based on mode:
        # - Strict mode (from Save Settings): only if uploaded in current session
        # - Normal mode (from Save Current as Preset): if enabled and exists
        left_logo_url = None
        if settings_obj.left_logo_enabled and settings_obj.left_logo:
            if not strict_mode or left_logo_uploaded:
                left_logo_url = get_absolute_url(settings_obj.left_logo.url)
        
        right_logo_url = None
        if settings_obj.right_logo_enabled and settings_obj.right_logo:
            if not strict_mode or right_logo_uploaded:
                right_logo_url = get_absolute_url(settings_obj.right_logo.url)
        
        footer_image_url = None
        if settings_obj.footer_image_enabled and settings_obj.footer_image:
            if not strict_mode or footer_image_uploaded:
                footer_image_url = get_absolute_url(settings_obj.footer_image.url)
        
        preset_data = {
            'id': str(int(time.time() * 1000)),  # Unique ID
            'name': preset_name,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'header_enabled': settings_obj.header_enabled,
            'header_layout_type': settings_obj.header_layout_type,
            'left_logo_enabled': settings_obj.left_logo_enabled,
            'right_logo_enabled': settings_obj.right_logo_enabled,
            'left_logo_url': left_logo_url,
            'right_logo_url': right_logo_url,
            'header_lines': settings_obj.custom_settings.get('header_lines', []) if isinstance(settings_obj.custom_settings.get('header_lines'), list) else [],
            'title_lines': settings_obj.custom_settings.get('title_lines', []) if isinstance(settings_obj.custom_settings.get('title_lines'), list) else [],
            'footer_enabled': settings_obj.footer_enabled,
            'footer_image_enabled': settings_obj.footer_image_enabled,
            'footer_image_url': footer_image_url,
            'footer_text1': settings_obj.footer_text1,
            'footer_text2': settings_obj.footer_text2,
            'signature_enabled': settings_obj.signature_enabled,
            'prepared_by_name': settings_obj.prepared_by_name,
            'prepared_by_title': settings_obj.prepared_by_title,
            'approved_by_name': settings_obj.approved_by_name,
            'approved_by_title': settings_obj.approved_by_title,
        }
        
        # Add to presets
        if not settings_obj.custom_settings:
            settings_obj.custom_settings = {}
        if 'presets' not in settings_obj.custom_settings:
            settings_obj.custom_settings['presets'] = []
        
        settings_obj.custom_settings['presets'].append(preset_data)
        settings_obj.save()
        
        return Response({
            'success': True,
            'message': 'Preset saved successfully',
            'preset': preset_data
        })
        
    except Exception as e:
        logger.error(f"Error saving preset: {str(e)}")
        return Response({
            'error': 'Internal server error',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def apply_report_preset_view(request):
    """Apply a preset to current settings"""
    try:
        user = request.user
        if not (hasattr(user, 'account_type') and 
                (user.account_type.admin if hasattr(user.account_type, 'admin') else False)):
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        preset_id = request.data.get('preset_id')
        if not preset_id:
            return Response({
                'error': 'Preset ID is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        settings_obj = ReportSettings.get_active_settings()
        if not settings_obj:
            settings_obj = ReportSettings(created_by=user, updated_by=user)
        
        # Find preset
        presets = settings_obj.custom_settings.get('presets', []) if settings_obj.custom_settings else []
        preset = next((p for p in presets if p.get('id') == preset_id), None)
        
        if not preset:
            return Response({
                'error': 'Preset not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Apply preset data
        settings_obj.header_enabled = preset.get('header_enabled', True)
        settings_obj.header_layout_type = preset.get('header_layout_type', 'three_column')
        settings_obj.left_logo_enabled = preset.get('left_logo_enabled', True)
        settings_obj.right_logo_enabled = preset.get('right_logo_enabled', True)
        
        if not settings_obj.custom_settings:
            settings_obj.custom_settings = {}
        settings_obj.custom_settings['header_lines'] = preset.get('header_lines', [])
        settings_obj.custom_settings['title_lines'] = preset.get('title_lines', [])
        
        settings_obj.footer_enabled = preset.get('footer_enabled', True)
        settings_obj.footer_image_enabled = preset.get('footer_image_enabled', True)
        settings_obj.footer_text1 = preset.get('footer_text1', '')
        settings_obj.footer_text2 = preset.get('footer_text2', '')
        settings_obj.signature_enabled = preset.get('signature_enabled', True)
        settings_obj.prepared_by_name = preset.get('prepared_by_name', '')
        settings_obj.prepared_by_title = preset.get('prepared_by_title', '')
        settings_obj.approved_by_name = preset.get('approved_by_name', '')
        settings_obj.approved_by_title = preset.get('approved_by_title', '')
        
        settings_obj.updated_by = user
        settings_obj.save()
        
        return Response({
            'success': True,
            'message': 'Preset applied successfully',
            'settings': {
                'header_enabled': settings_obj.header_enabled,
                'header_layout_type': settings_obj.header_layout_type,
                'left_logo_enabled': settings_obj.left_logo_enabled,
                'right_logo_enabled': settings_obj.right_logo_enabled,
                'left_logo_url': settings_obj.left_logo.url if settings_obj.left_logo else None,
                'right_logo_url': settings_obj.right_logo.url if settings_obj.right_logo else None,
                'header_lines': settings_obj.custom_settings.get('header_lines', []),
                'title_lines': settings_obj.custom_settings.get('title_lines', []),
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
            }
        })
        
    except Exception as e:
        logger.error(f"Error applying preset: {str(e)}")
        return Response({
            'error': 'Internal server error',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_report_preset_view(request, preset_id):
    """Delete a preset"""
    try:
        user = request.user
        if not (hasattr(user, 'account_type') and 
                (user.account_type.admin if hasattr(user.account_type, 'admin') else False)):
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        settings_obj = ReportSettings.get_active_settings()
        if not settings_obj or not settings_obj.custom_settings:
            return Response({
                'error': 'No presets found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        presets = settings_obj.custom_settings.get('presets', [])
        original_count = len(presets)
        settings_obj.custom_settings['presets'] = [p for p in presets if p.get('id') != preset_id]
        
        if len(settings_obj.custom_settings['presets']) == original_count:
            return Response({
                'error': 'Preset not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        settings_obj.save()
        
        return Response({
            'success': True,
            'message': 'Preset deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error deleting preset: {str(e)}")
        return Response({
            'error': 'Internal server error',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)