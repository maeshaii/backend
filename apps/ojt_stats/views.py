"""
OJT statistics API views for coordinator dashboards.
Provides overview, detailed statistics, and export endpoints. If this file grows,
consider splitting endpoints into submodules (e.g., overview_views.py, detail_views.py, export_views.py).
"""

import logging
from django.shortcuts import render
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from apps.shared.models import User, OJTImport
from collections import Counter
from django.db import models
from statistics import mean
from django.utils import timezone
from datetime import datetime, timedelta
import json
from apps.shared.utils.stats import safe_mode_related, safe_mean_related

logger = logging.getLogger(__name__)

# Helper functions for statistics aggregation

def safe_mode(qs, field):
	"""Return the most common non-empty value of attribute `field` from iterable `qs`."""
	vals = [getattr(a, field) for a in qs if getattr(a, field)]
	return Counter(vals).most_common(1)[0][0] if vals else None

def safe_mean(qs, field):
	"""Return the mean of numeric values from attribute `field` in iterable `qs`. Strings are coerced when possible."""
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
	"""Return the first non-empty value found for attribute `field` in iterable `qs`, else None."""
	for a in qs:
		v = getattr(a, field)
		if v:
			return v
	return None

# Create your views here.

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ojt_statistics_view(request):
	"""
	Overview of OJT statuses for coordinators.
	Query params:
	- year: filter by graduation year or 'ALL'
	- course: filter by course or 'ALL'
	Returns counts and rates per OJT status and available years.
	"""
	try:
		year = request.GET.get('year')
		course = request.GET.get('course')
		ojt_qs = User.objects.filter(account_type__ojt=True)
		if year and year != 'ALL':
			ojt_qs = ojt_qs.filter(academic_info__year_graduated=year)
		if course and course != 'ALL':
			ojt_qs = ojt_qs.filter(academic_info__program=course)
		status_counts = Counter(ojt_qs.values_list('ojtstatus', flat=True))
		year_counts = Counter(User.objects.filter(account_type__ojt=True).values_list('academic_info__year_graduated', flat=True))
		filtered_year_counts = {y: c for y, c in year_counts.items() if y is not None}
		total_ojt = ojt_qs.count()
		completed_count = status_counts.get('Completed', 0)
		ongoing_count = status_counts.get('Ongoing', 0)
		incomplete_count = status_counts.get('Incomplete', 0)
		completion_rate = round((completed_count / total_ojt * 100), 2) if total_ojt > 0 else 0
		ongoing_rate = round((ongoing_count / total_ojt * 100), 2) if total_ojt > 0 else 0
		incomplete_rate = round((incomplete_count / total_ojt * 100), 2) if total_ojt > 0 else 0
		return JsonResponse({
			'success': True,
			'total_ojt': total_ojt,
			'status_counts': dict(status_counts),
			'completion_rate': completion_rate,
			'ongoing_rate': ongoing_rate,
			'incomplete_rate': incomplete_rate,
			'years': [
				{'year': year, 'count': count}
				for year, count in sorted(filtered_year_counts.items(), reverse=True)
			]
		})
	except Exception as e:
		logger.error(f"Error in ojt_statistics_view: {e}")
		return JsonResponse({'success': False, 'message': 'Failed to generate OJT statistics'}, status=500)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def generate_ojt_statistics_view(request):
	"""
	Detailed OJT statistics for coordinators.
	Query params:
	- year: graduation year or 'ALL'
	- course: course code or 'ALL'
	- type: one of ['ALL','status_tracking','academic_progress','coordinator_summary']
	"""
	try:
		year = request.GET.get('year', 'ALL')
		course = request.GET.get('course', 'ALL')
		stats_type = request.GET.get('type', 'ALL')
		ojt_qs = User.objects.filter(account_type__ojt=True)
		if year and year != 'ALL':
			ojt_qs = ojt_qs.filter(academic_info__year_graduated=year)
		if course and course != 'ALL':
			ojt_qs = ojt_qs.filter(academic_info__program=course)
		total_ojt = ojt_qs.count()
		if stats_type == 'ALL':
			status_counts = Counter(ojt_qs.values_list('ojtstatus', flat=True))
			completed_rate = round((status_counts.get('Completed', 0) / total_ojt * 100), 2) if total_ojt > 0 else 0
			ongoing_rate = round((status_counts.get('Ongoing', 0) / total_ojt * 100), 2) if total_ojt > 0 else 0
			incomplete_rate = round((status_counts.get('Incomplete', 0) / total_ojt * 100), 2) if total_ojt > 0 else 0
			return JsonResponse({
				'success': True,
				'type': 'ALL',
				'total_ojt': total_ojt,
				'status_counts': dict(status_counts),
				'completion_rate': completed_rate,
				'ongoing_rate': ongoing_rate,
				'incomplete_rate': incomplete_rate,
				'most_common_course': safe_mode_related(ojt_qs, 'academic_info__program'),
				'most_common_section': safe_mode_related(ojt_qs, 'academic_info__section'),
				'most_common_gender': safe_mode(ojt_qs, 'gender'),
				'most_common_civil_status': safe_mode_related(ojt_qs, 'profile__civil_status'),
				'average_age': safe_mean_related(ojt_qs, 'profile__age'),
				'year': year,
				'course': course
			})
		elif stats_type == 'status_tracking':
			status_counts = Counter(ojt_qs.values_list('ojtstatus', flat=True))
			completed_students = ojt_qs.filter(ojtstatus='Completed')
			ongoing_students = ojt_qs.filter(ojtstatus='Ongoing')
			incomplete_students = ojt_qs.filter(ojtstatus='Incomplete')
			return JsonResponse({
				'success': True,
				'type': 'status_tracking',
				'total_ojt': total_ojt,
				'status_counts': dict(status_counts),
				'completed_students_count': completed_students.count(),
				'ongoing_students_count': ongoing_students.count(),
				'incomplete_students_count': incomplete_students.count(),
				'completion_rate': round((completed_students.count() / total_ojt * 100), 2) if total_ojt > 0 else 0,
				'ongoing_rate': round((ongoing_students.count() / total_ojt * 100), 2) if total_ojt > 0 else 0,
				'incomplete_rate': round((incomplete_students.count() / total_ojt * 100), 2) if total_ojt > 0 else 0,
				'year': year,
				'course': course
			})
		elif stats_type == 'academic_progress':
			completed_students = ojt_qs.filter(ojtstatus='Completed')
			ongoing_students = ojt_qs.filter(ojtstatus='Ongoing')
			incomplete_students = ojt_qs.filter(ojtstatus='Incomplete')
			return JsonResponse({
				'success': True,
				'type': 'academic_progress',
				'total_ojt': total_ojt,
				'completed': {
					'count': completed_students.count(),
					'most_common_course': safe_mode_related(completed_students, 'academic_info__program'),
					'most_common_section': safe_mode_related(completed_students, 'academic_info__section'),
					'most_common_school': safe_mode_related(completed_students, 'academic_info__school_name'),
				},
				'ongoing': {
					'count': ongoing_students.count(),
					'most_common_course': safe_mode_related(ongoing_students, 'academic_info__program'),
					'most_common_section': safe_mode_related(ongoing_students, 'academic_info__section'),
					'most_common_school': safe_mode_related(ongoing_students, 'academic_info__school_name'),
				},
				'incomplete': {
					'count': incomplete_students.count(),
					'most_common_course': safe_mode_related(incomplete_students, 'academic_info__program'),
					'most_common_section': safe_mode_related(incomplete_students, 'academic_info__section'),
					'most_common_school': safe_mode_related(incomplete_students, 'academic_info__school_name'),
				},
				'year': year,
				'course': course
			})
		elif stats_type == 'coordinator_summary':
			status_counts = Counter(ojt_qs.values_list('ojtstatus', flat=True))
			total_completed = status_counts.get('Completed', 0)
			total_ongoing = status_counts.get('Ongoing', 0)
			total_incomplete = status_counts.get('Incomplete', 0)
			return JsonResponse({
				'success': True,
				'type': 'coordinator_summary',
				'total_ojt': total_ojt,
				'status_summary': {
					'completed': {
						'count': total_completed,
						'percentage': round((total_completed / total_ojt * 100), 2) if total_ojt > 0 else 0
					},
					'ongoing': {
						'count': total_ongoing,
						'percentage': round((total_ongoing / total_ojt * 100), 2) if total_ojt > 0 else 0
					},
					'incomplete': {
						'count': total_incomplete,
						'percentage': round((total_incomplete / total_ojt * 100), 2) if total_ojt > 0 else 0
					}
				},
				'most_common_course': safe_mode_related(ojt_qs, 'academic_info__program'),
				'year': year,
				'course': course
			})
		else:
			return JsonResponse({
				'success': False,
				'error': 'Invalid statistics type. Use: ALL, status_tracking, academic_progress, or coordinator_summary'
			}, status=400)
	except Exception as e:
		logger.error(f"Error in generate_ojt_statistics_view: {e}")
		return JsonResponse({'success': False, 'message': 'Failed to generate detailed OJT statistics'}, status=500)

@api_view(["GET"]) 
@permission_classes([IsAuthenticated])
def export_detailed_ojt_data(request):
	"""
	Export detailed OJT user data filtered by year, course, and status.
	Query params:
	- year: graduation year or 'ALL'
	- course: course code or 'ALL'
	- status: OJT status or 'ALL'
	"""
	try:
		year = request.GET.get('year', 'ALL')
		course = request.GET.get('course', 'ALL')
		status_filter = request.GET.get('status', 'ALL')
		ojt_qs = User.objects.filter(account_type__ojt=True)
		if year and year != 'ALL':
			ojt_qs = ojt_qs.filter(academic_info__year_graduated=year)
		if course and course != 'ALL':
			ojt_qs = ojt_qs.filter(academic_info__program=course)
		if status_filter and status_filter != 'ALL':
			ojt_qs = ojt_qs.filter(ojtstatus=status_filter)
		export_data = []
		for ojt_user in ojt_qs:
			profile = getattr(ojt_user, 'profile', None)
			academic_info = getattr(ojt_user, 'academic_info', None)
			ojt_info = getattr(ojt_user, 'ojt_info', None)
			
			user_data = {
				'CTU_ID': ojt_user.user_id,
				'First_Name': ojt_user.f_name,
				'Middle_Name': ojt_user.m_name,
				'Last_Name': ojt_user.l_name,
				'Gender': ojt_user.gender,
				'Birthdate': getattr(profile, 'birthdate', None) if profile else None,
				'Phone_Number': getattr(profile, 'phone_num', None) if profile else None,
				'Social_Media': getattr(profile, 'email', None) if profile else None,
				'Address': getattr(profile, 'address', None) if profile else None,
				'Course': getattr(academic_info, 'program', None) if academic_info else None,
				'Ojt_Start_Date': getattr(ojt_info, 'ojt_start_date', None) if ojt_info else None,
				'Ojt_End_Date': getattr(ojt_info, 'ojt_end_date', None) if ojt_info else None,
				'Status': getattr(ojt_info, 'ojtstatus', None) if ojt_info else None,
				'Civil_Status': getattr(profile, 'civil_status', None) if profile else None,
			}
			export_data.append(user_data)
		return JsonResponse({
			'success': True,
			'data': export_data,
			'total_records': len(export_data),
			'year': year,
			'course': course,
			'status_filter': status_filter,
			'export_date': timezone.now().isoformat()
		})
	except Exception as e:
		logger.error(f"Error in export_detailed_ojt_data: {e}")
		return JsonResponse({'success': False, 'message': 'Failed to export OJT data'}, status=500)
