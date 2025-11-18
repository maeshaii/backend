"""
Usage examples for senior_queries.py
Demonstrates how to use these queries in views, services, and API endpoints.
"""
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from .senior_queries import (
    get_user_with_full_profile,
    get_active_users_with_stats,
    search_users_by_name_or_username,
    get_employment_statistics_by_program,
    get_job_alignment_breakdown,
    get_tracker_completion_statistics,
    get_posts_feed,
    get_post_with_engagement,
    get_user_conversations,
    get_points_leaderboard,
    get_program_statistics,
    get_engagement_metrics,
)
from .models import User
from datetime import datetime, timedelta


# ============================================================================
# API VIEW EXAMPLES
# ============================================================================

@login_required
@require_http_methods(["GET"])
def user_profile_api(request, user_id):
    """
    Example API endpoint using senior queries.
    Returns complete user profile with all related data.
    """
    try:
        user = get_user_with_full_profile(user_id)
        
        return JsonResponse({
            'user_id': user.user_id,
            'username': user.acc_username,
            'full_name': user.full_name,
            'email': user.profile.email if hasattr(user, 'profile') else None,
            'phone': user.profile.phone_num if hasattr(user, 'profile') else None,
            'program': user.academic_info.program if hasattr(user, 'academic_info') else None,
            'year_graduated': user.academic_info.year_graduated if hasattr(user, 'academic_info') else None,
            'current_position': user.employment.position_current if hasattr(user, 'employment') else None,
            'company': user.employment.company_name_current if hasattr(user, 'employment') else None,
            'total_points': user.points.total_points if hasattr(user, 'points') else 0,
        })
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)


@login_required
@require_http_methods(["GET"])
def search_users_api(request):
    """
    Example search endpoint with pagination.
    """
    query = request.GET.get('q', '').strip()
    limit = int(request.GET.get('limit', 20))
    
    if not query:
        return JsonResponse({'error': 'Query parameter required'}, status=400)
    
    users = search_users_by_name_or_username(query, limit=limit)
    
    return JsonResponse({
        'results': [
            {
                'user_id': u.user_id,
                'username': u.acc_username,
                'full_name': u.full_name,
                'profile_pic': u.profile.profile_pic.url if hasattr(u, 'profile') and u.profile.profile_pic else None,
            }
            for u in users
        ],
        'count': len(users)
    })


@login_required
@require_http_methods(["GET"])
def posts_feed_api(request):
    """
    Example posts feed endpoint with pagination.
    """
    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', 20))
    offset = (page - 1) * limit
    
    posts = get_posts_feed(request.user, limit=limit, offset=offset)
    
    return JsonResponse({
        'posts': [
            {
                'post_id': p.post_id,
                'content': p.post_content,
                'author': {
                    'user_id': p.user.user_id,
                    'full_name': p.user.full_name,
                    'profile_pic': p.user.profile.profile_pic.url if hasattr(p.user, 'profile') and p.user.profile.profile_pic else None,
                },
                'like_count': p.like_count,
                'comment_count': p.comment_count,
                'repost_count': p.repost_count,
                'is_liked': p.is_liked,
                'is_reposted': p.is_reposted,
                'created_at': p.created_at.isoformat(),
            }
            for p in posts
        ],
        'page': page,
        'limit': limit,
    })


@login_required
@require_http_methods(["GET"])
def leaderboard_api(request):
    """
    Example leaderboard endpoint.
    """
    limit = int(request.GET.get('limit', 100))
    program = request.GET.get('program', None)
    
    leaderboard = get_points_leaderboard(limit=limit, program=program)
    
    return JsonResponse({
        'leaderboard': [
            {
                'rank': idx + 1,
                'user_id': entry.user.user_id,
                'full_name': entry.user.full_name,
                'total_points': entry.total_points,
                'program': entry.user.academic_info.program if hasattr(entry.user, 'academic_info') else None,
            }
            for idx, entry in enumerate(leaderboard)
        ]
    })


# ============================================================================
# SERVICE LAYER EXAMPLES
# ============================================================================

class StatisticsService:
    """
    Example service class using senior queries for business logic.
    """
    
    @staticmethod
    def get_dashboard_statistics(program: str = None):
        """
        Get comprehensive dashboard statistics.
        """
        stats = {
            'employment': get_employment_statistics_by_program(program),
            'tracker': get_tracker_completion_statistics(),
            'programs': list(get_program_statistics()),
        }
        
        # Calculate percentages
        if stats['employment']['total_employed'] > 0:
            stats['employment']['self_employed_percentage'] = round(
                (stats['employment']['self_employed_count'] / stats['employment']['total_employed']) * 100,
                2
            )
            stats['employment']['aligned_percentage'] = round(
                (stats['employment']['aligned_count'] / stats['employment']['total_employed']) * 100,
                2
            )
        
        return stats
    
    @staticmethod
    def get_job_alignment_report():
        """
        Generate job alignment report for admin.
        """
        breakdown = get_job_alignment_breakdown()
        
        report = {
            'summary': {
                'total_aligned': sum(item['count'] for item in breakdown),
                'unique_job_titles': sum(item['job_titles'] for item in breakdown),
            },
            'by_category': {},
            'by_program': {},
        }
        
        for item in breakdown:
            category = item['job_alignment_category']
            program = item['user__academic_info__program']
            
            if category not in report['by_category']:
                report['by_category'][category] = 0
            report['by_category'][category] += item['count']
            
            if program not in report['by_program']:
                report['by_program'][program] = 0
            report['by_program'][program] += item['count']
        
        return report


# ============================================================================
# BULK OPERATIONS EXAMPLES
# ============================================================================

@transaction.atomic
def bulk_update_job_alignments():
    """
    Example bulk operation to update job alignments for all users.
    This would typically be run as a management command or scheduled task.
    """
    from .models import EmploymentHistory
    
    employments = EmploymentHistory.objects.select_related(
        'user__academic_info'
    ).filter(
        position_current__isnull=False
    )
    
    updated_count = 0
    for employment in employments:
        old_status = employment.job_alignment_status
        employment.update_job_alignment()
        if employment.job_alignment_status != old_status:
            employment.save()
            updated_count += 1
    
    return {
        'total_processed': employments.count(),
        'updated': updated_count
    }


# ============================================================================
# ANALYTICS EXAMPLES
# ============================================================================

def get_weekly_engagement_report():
    """
    Example analytics report using senior queries.
    """
    end_date = timezone.now()
    start_date = end_date - timedelta(days=7)
    
    metrics = get_engagement_metrics(start_date, end_date)
    
    # Calculate growth (would need previous week's data for comparison)
    return {
        'period': {
            'start': start_date.isoformat(),
            'end': end_date.isoformat(),
        },
        'metrics': metrics,
        'insights': {
            'avg_posts_per_day': round(metrics['posts'] / 7, 2),
            'avg_comments_per_post': round(
                metrics['comments'] / metrics['posts'] if metrics['posts'] > 0 else 0,
                2
            ),
            'engagement_rate': round(
                (metrics['likes'] + metrics['comments'] + metrics['reposts']) / metrics['posts'] if metrics['posts'] > 0 else 0,
                2
            ),
        }
    }


# ============================================================================
# CACHING EXAMPLES
# ============================================================================

from django.core.cache import cache

def get_cached_program_statistics(program: str = None):
    """
    Example of caching expensive queries.
    """
    cache_key = f'program_stats:{program or "all"}'
    cached_result = cache.get(cache_key)
    
    if cached_result is None:
        cached_result = get_program_statistics()
        # Cache for 1 hour
        cache.set(cache_key, cached_result, 3600)
    
    return cached_result


def invalidate_statistics_cache():
    """
    Invalidate statistics cache when data changes.
    """
    cache.delete_many([
        'program_stats:all',
        'program_stats:BSIT',
        'program_stats:BSIS',
        'program_stats:BIT-CT',
    ])

