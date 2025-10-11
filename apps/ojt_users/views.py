"""
OJT users API endpoints.
This module uses centralized models from apps.shared (User, UserProfile, AcademicInfo, OJTInfo)
for consistency. Functions were updated to avoid legacy field access on User and instead
use related models via select_related for performance.
"""

import logging
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from apps.shared.models import User, UserProfile, AcademicInfo, OJTInfo, AccountType
import json
from django.db import models

logger = logging.getLogger(__name__)

# List all OJT users with filtering options
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_ojt_users(request):
    """
    List OJT users with optional filtering by year, course, status, and search.
    Uses related models (`academic_info`, `profile`, `ojt_info`) from shared app.
    """
    try:
        year = request.GET.get('year')
        course = request.GET.get('course')
        status = request.GET.get('status')
        search = request.GET.get('search')
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))

        ojt_users = (
            User.objects
            .filter(account_type__ojt=True)
            .select_related('academic_info', 'profile', 'ojt_info')
        )

        if year and year != 'ALL':
            ojt_users = ojt_users.filter(academic_info__year_graduated=year)
        if course and course != 'ALL':
            ojt_users = ojt_users.filter(academic_info__course=course)
        if status and status != 'ALL':
            ojt_users = ojt_users.filter(ojt_info__ojtstatus=status)
        if search:
            ojt_users = ojt_users.filter(
                Q(f_name__icontains=search) |
                Q(l_name__icontains=search) |
                Q(acc_username__icontains=search) |
                Q(profile__email__icontains=search)
            )

        total_count = ojt_users.count()
        start = (page - 1) * per_page
        end = start + per_page
        ojt_users = ojt_users[start:end]

        users_data = []
        for user in ojt_users:
            profile = getattr(user, 'profile', None)
            academic = getattr(user, 'academic_info', None)
            ojtinfo = getattr(user, 'ojt_info', None)
            users_data.append({
                'user_id': user.user_id,
                'username': user.acc_username,
                'first_name': user.f_name,
                'middle_name': user.m_name,
                'last_name': user.l_name,
                'email': getattr(profile, 'email', None) if profile else None,
                'course': getattr(academic, 'course', None) if academic else None,
                'section': getattr(academic, 'section', None) if academic else None,
                'year_graduated': getattr(academic, 'year_graduated', None) if academic else None,
                'ojt_status': getattr(ojtinfo, 'ojtstatus', None) if ojtinfo else None,
                'ojt_start_date': getattr(ojtinfo, 'ojt_start_date', None) if ojtinfo else None,
                'ojt_end_date': getattr(ojtinfo, 'ojt_end_date', None) if ojtinfo else None,
                'phone_number': getattr(profile, 'phone_num', None) if profile else None,
                'address': getattr(profile, 'address', None) if profile else None,
                'gender': user.gender,
                'civil_status': getattr(profile, 'civil_status', None) if profile else None,
                'birthdate': getattr(profile, 'birthdate', None) if profile else None,
                'age': getattr(profile, 'age', None) if profile else None,
            })

        return JsonResponse({
            'success': True,
            'users': users_data,
            'total_count': total_count,
            'page': page,
            'per_page': per_page,
            'total_pages': (total_count + per_page - 1) // per_page,
            'filters': {
                'year': year,
                'course': course,
                'status': status,
                'search': search
            }
        })
    except Exception as e:
        logger.error(f"Error in list_ojt_users: {e}")
        return JsonResponse({'success': False, 'error': 'Failed to list OJT users'}, status=500)

# Get individual OJT user details
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_ojt_user_details(request, user_id):
    """
    Get detailed information for a specific OJT user
    """
    try:
        user = get_object_or_404(
            User.objects.select_related('profile', 'academic_info', 'ojt_info'),
            user_id=user_id,
            account_type__ojt=True,
        )

        profile = getattr(user, 'profile', None)
        academic = getattr(user, 'academic_info', None)
        ojtinfo = getattr(user, 'ojt_info', None)

        user_data = {
            'CTU_ID': user.user_id,
            'First_Name': user.f_name,
            'Middle_Name': user.m_name,
            'Last_Name': user.l_name,
            'Gender': user.gender,
            'Birthdate': getattr(profile, 'birthdate', None) if profile else None,
            'Phone_Number': getattr(profile, 'phone_num', None) if profile else None,
            'Social_Media': getattr(profile, 'social_media', None) if profile else None,
            'Email': getattr(profile, 'email', None) if profile else None,
            'Address': getattr(profile, 'address', None) if profile else None,
            'Course': getattr(academic, 'course', None) if academic else None,
            'Ojt_Start_Date': getattr(ojtinfo, 'ojt_start_date', None) if ojtinfo else None,
            'Ojt_End_Date': getattr(ojtinfo, 'ojt_end_date', None) if ojtinfo else None,
            'Status': getattr(ojtinfo, 'ojtstatus', None) if ojtinfo else None,
            'Civil_Status': getattr(profile, 'civil_status', None) if profile else None,
        }
        
        return JsonResponse({
            'success': True,
            'user': user_data
        })
        
    except Exception as e:
        logger.error(f"Error in get_ojt_user_details for user_id={user_id}: {e}")
        return JsonResponse({'success': False, 'error': 'Failed to fetch OJT user details'}, status=500)

# Update OJT user status (for coordinators)
@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def update_ojt_status(request, user_id):
    """
    Update OJT status for a specific user (coordinator function)
    """
    try:
        user = get_object_or_404(User, user_id=user_id, account_type__ojt=True)
        
        # Parse request body
        data = json.loads(request.body)
        new_status = data.get('ojt_status')
        
        # Validate status
        valid_statuses = ['Ongoing', 'Completed', 'Incomplete']
        if new_status not in valid_statuses:
            return JsonResponse({
                'success': False,
                'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
            }, status=400)
        
        # Allow coordinators to set status to "Completed" before sending to admin
        if new_status == 'Completed':
            print(f"🔍 DEBUG: User {user.acc_username} setting status to Completed - allowing this change")
        
        # Update OJTInfo status
        ojtinfo, _ = OJTInfo.objects.get_or_create(user=user)
        ojtinfo.ojtstatus = new_status
        ojtinfo.save()
        
        return JsonResponse({
            'success': True,
            'message': f'OJT status updated to {new_status}',
            'user_id': user_id,
            'new_status': new_status
        })
        
    except Exception as e:
        logger.error(f"Error in update_ojt_status for user_id={user_id}: {e}")
        return JsonResponse({'success': False, 'error': 'Failed to update OJT status'}, status=500)

# Update OJT user information
@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def update_ojt_user(request, user_id):
    """
    Update OJT user information
    """
    try:
        user = get_object_or_404(User, user_id=user_id, account_type__ojt=True)
        profile, _ = UserProfile.objects.get_or_create(user=user)
        academic, _ = AcademicInfo.objects.get_or_create(user=user)
        ojtinfo, _ = OJTInfo.objects.get_or_create(user=user)

        data = json.loads(request.body)

        updated_fields = []

        # Core user fields
        for field in ['f_name', 'm_name', 'l_name', 'gender']:
            if field in data:
                setattr(user, field, data[field])
                updated_fields.append(field)

        # Profile fields
        for field in ['email', 'phone_num', 'address', 'profile_bio', 'birthdate', 'civil_status', 'social_media']:
            if field in data:
                setattr(profile, field, data[field])
                updated_fields.append(f'profile.{field}')

        # Academic fields
        for field in ['section', 'program', 'school_name', 'year_graduated']:
            if field in data:
                setattr(academic, field, data[field])
                updated_fields.append(f'academic.{field}')

        # OJT info fields
        for field in ['ojt_end_date', 'job_code', 'ojtstatus']:
            if field in data:
                setattr(ojtinfo, field, data[field])
                updated_fields.append(f'ojt_info.{field}')

        if updated_fields:
            user.save()
            profile.save()
            academic.save()
            ojtinfo.save()
            return JsonResponse({
                'success': True,
                'message': f'Updated fields: {", ".join(updated_fields)}',
                'user_id': user_id,
                'updated_fields': updated_fields
            })
        return JsonResponse({'success': False, 'error': 'No valid fields to update'}, status=400)
        
    except Exception as e:
        logger.error(f"Error in update_ojt_user for user_id={user_id}: {e}")
        return JsonResponse({'success': False, 'error': 'Failed to update OJT user'}, status=500)

# Create new OJT user
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_ojt_user(request):
    """
    Create a new OJT user
    """
    try:
        data = json.loads(request.body)

        required_fields = ['acc_username', 'f_name', 'l_name', 'course']
        for field in required_fields:
            if not data.get(field):
                return JsonResponse({'success': False, 'error': f'Missing required field: {field}'}, status=400)

        if User.objects.filter(acc_username=data['acc_username']).exists():
            return JsonResponse({'success': False, 'error': 'Username already exists'}, status=400)

        try:
            account_type = AccountType.objects.get(ojt=True, admin=False, peso=False, user=False, coordinator=False)
        except AccountType.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'OJT account type not configured'}, status=500)

        user = User.objects.create(
            acc_username=data['acc_username'],
            f_name=data['f_name'],
            m_name=data.get('m_name', ''),
            l_name=data['l_name'],
            gender=data.get('gender', ''),
            user_status='active',
            account_type=account_type,
        )

        # Create related models
        profile = UserProfile.objects.create(
            user=user,
            email=data.get('email'),
            phone_num=data.get('phone_num'),
            address=data.get('address'),
            civil_status=data.get('civil_status'),
            birthdate=data.get('birthdate'),
            social_media=data.get('social_media'),
        )

        academic = AcademicInfo.objects.create(
            user=user,
            course=data.get('course'),
            section=data.get('section'),
            program=data.get('program'),
            school_name=data.get('school_name'),
            year_graduated=data.get('year_graduated'),
        )

        ojtinfo = OJTInfo.objects.create(
            user=user,
            ojt_end_date=data.get('ojt_end_date'),
            job_code=data.get('job_code'),
            ojtstatus='Ongoing',
        )

        return JsonResponse({'success': True, 'message': 'OJT user created successfully', 'user_id': user.user_id, 'username': user.acc_username}, status=201)
    except Exception as e:
        logger.error(f"Error in create_ojt_user: {e}")
        return JsonResponse({'success': False, 'error': 'Failed to create OJT user'}, status=500)

# Delete OJT user
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_ojt_user(request, user_id):
    """
    Delete an OJT user
    """
    try:
        user = get_object_or_404(User, user_id=user_id, account_type__ojt=True)
        
        # Soft delete by setting user_status to inactive
        user.user_status = 'Inactive'
        user.save()
        
        return JsonResponse({
            'success': True,
            'message': 'OJT user deactivated successfully',
            'user_id': user_id
        })
        
    except Exception as e:
        logger.error(f"Error in delete_ojt_user for user_id={user_id}: {e}")
        return JsonResponse({'success': False, 'error': 'Failed to delete OJT user'}, status=500)

# Get OJT statistics summary
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ojt_users_summary(request):
    """
    Get summary statistics for OJT users
    """
    try:
        # Get filter parameters
        year = request.GET.get('year')
        course = request.GET.get('course')
        
        # Start with all OJT users and join related models
        ojt_users = User.objects.filter(account_type__ojt=True).select_related('ojt_info', 'academic_info')
        
        # Apply filters via related models
        if year and year != 'ALL':
            ojt_users = ojt_users.filter(academic_info__year_graduated=year)
        if course and course != 'ALL':
            ojt_users = ojt_users.filter(academic_info__course=course)
        
        # Calculate statistics
        total_users = ojt_users.count()
        status_counts = ojt_users.values('ojt_info__ojtstatus').annotate(count=models.Count('ojt_info__ojtstatus'))
        course_counts = ojt_users.values('academic_info__course').annotate(count=models.Count('academic_info__course'))
        year_counts = ojt_users.values('academic_info__year_graduated').annotate(count=models.Count('academic_info__year_graduated'))
        
        return JsonResponse({
            'success': True,
            'summary': {
                'total_users': total_users,
                'status_breakdown': list(status_counts),
                'course_breakdown': list(course_counts),
                'year_breakdown': list(year_counts),
                'filters': {
                    'year': year,
                    'course': course
                }
            }
        })
        
    except Exception as e:
        logger.error(f"Error in ojt_users_summary: {e}")
        return JsonResponse({'success': False, 'error': 'Failed to summarize OJT users'}, status=500)
