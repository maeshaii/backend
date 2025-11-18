"""
Senior-level Django ORM queries for shared models.
These queries are optimized for performance using select_related, prefetch_related,
and proper indexing strategies.
"""
from django.db.models import (
    Q, F, Count, Sum, Avg, Max, Min, Case, When, Value, IntegerField,
    CharField, Prefetch, Exists, OuterRef, Subquery, Window, RowNumber
)
from django.db.models.functions import Coalesce, TruncDate, ExtractYear
from django.utils import timezone
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from .models import (
    User, UserProfile, AcademicInfo, EmploymentHistory, TrackerData,
    Post, Comment, Like, Repost, Forum, DonationRequest,
    Message, Conversation, Notification, Follow,
    UserPoints, EngagementPointsSettings, PointsTask, UserTaskCompletion,
    SimpleCompTechJob, SimpleInfoTechJob, SimpleInfoSystemJob,
    TrackerResponse, OJTInfo, OJTCompanyProfile,
    RewardRequest, RewardInventoryItem, RewardHistory
)


# ============================================================================
# USER & PROFILE QUERIES
# ============================================================================

def get_user_with_full_profile(user_id: int) -> Optional[User]:
    """
    Get user with all related profile data in a single optimized query.
    Uses select_related for ForeignKey and OneToOne relationships.
    """
    return User.objects.select_related(
        'account_type',
        'profile',
        'academic_info',
        'employment',
        'tracker_data',
        'ojt_info',
        'ojt_company_profile',
        'points'
    ).prefetch_related(
        'posts',
        'forums',
        'donation_requests'
    ).get(user_id=user_id)


def get_active_users_with_stats():
    """
    Get all active users with engagement statistics.
    Uses annotations to calculate counts without additional queries.
    """
    return User.objects.filter(
        user_status__iexact='active'
    ).select_related(
        'profile', 'academic_info', 'employment', 'points'
    ).annotate(
        post_count=Count('posts', distinct=True),
        comment_count=Count('comments', distinct=True),
        like_count=Count('likes', distinct=True),
        follower_count=Count('followers', distinct=True),
        following_count=Count('following', distinct=True),
        total_points=Coalesce(F('points__total_points'), 0)
    ).order_by('-total_points', '-post_count')


def search_users_by_name_or_username(query: str, limit: int = 20):
    """
    Full-text search for users by name or username.
    Optimized with proper indexing on f_name, l_name, acc_username.
    """
    query_terms = query.strip().split()
    q_objects = Q()
    
    for term in query_terms:
        q_objects |= (
            Q(f_name__icontains=term) |
            Q(l_name__icontains=term) |
            Q(m_name__icontains=term) |
            Q(acc_username__icontains=term)
        )
    
    return User.objects.filter(
        q_objects,
        user_status__iexact='active'
    ).select_related(
        'profile', 'account_type'
    ).annotate(
        # Calculate relevance score (simple - can be enhanced with full-text search)
        relevance=Case(
            When(acc_username__iexact=query, then=Value(100)),
            When(f_name__iexact=query, then=Value(90)),
            When(l_name__iexact=query, then=Value(90)),
            default=Value(50),
            output_field=IntegerField()
        )
    ).order_by('-relevance', 'f_name', 'l_name')[:limit]


# ============================================================================
# EMPLOYMENT & JOB ALIGNMENT QUERIES
# ============================================================================

def get_employment_statistics_by_program(program: Optional[str] = None):
    """
    Get comprehensive employment statistics grouped by program.
    Used for dashboard and reporting.
    """
    queryset = EmploymentHistory.objects.select_related(
        'user', 'user__academic_info'
    ).filter(
        position_current__isnull=False
    )
    
    if program:
        queryset = queryset.filter(user__academic_info__program__iexact=program)
    
    return queryset.aggregate(
        total_employed=Count('id', distinct=True),
        self_employed_count=Count('id', filter=Q(self_employed=True)),
        high_position_count=Count('id', filter=Q(high_position=True)),
        absorbed_count=Count('id', filter=Q(absorbed=True)),
        aligned_count=Count('id', filter=Q(job_alignment_status='aligned')),
        pending_count=Count('id', filter=Q(job_alignment_status='pending_user_confirmation')),
        not_aligned_count=Count('id', filter=Q(job_alignment_status='not_aligned'))
    )


def get_job_alignment_breakdown():
    """
    Get job alignment breakdown by category and program.
    Critical for CHED/SUC/AACUP statistics.
    """
    return EmploymentHistory.objects.select_related(
        'user__academic_info'
    ).filter(
        job_alignment_status='aligned',
        job_alignment_category__isnull=False
    ).values(
        'job_alignment_category',
        'user__academic_info__program'
    ).annotate(
        count=Count('id'),
        job_titles=Count('job_alignment_title', distinct=True)
    ).order_by('user__academic_info__program', 'job_alignment_category')


def get_users_needing_job_alignment_confirmation():
    """
    Get users with pending job alignment that need admin/user confirmation.
    """
    return EmploymentHistory.objects.select_related(
        'user', 'user__academic_info', 'user__profile'
    ).filter(
        job_alignment_status='pending_user_confirmation',
        position_current__isnull=False
    ).annotate(
        days_pending=ExtractYear(
            timezone.now() - F('updated_at')
        )
    ).order_by('-updated_at')


def get_cross_program_job_matches():
    """
    Find jobs that exist in multiple program tables (cross-program alignment opportunities).
    """
    from django.db import connection
    
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                job_title,
                COUNT(DISTINCT source_table) as program_count,
                STRING_AGG(DISTINCT source_table, ', ') as programs
            FROM (
                SELECT job_title, 'comp_tech' as source_table FROM shared_simplecomptechjob
                UNION ALL
                SELECT job_title, 'info_tech' as source_table FROM shared_simpleinfotechjob
                UNION ALL
                SELECT job_title, 'info_system' as source_table FROM shared_simpleinfosystemjob
            ) all_jobs
            GROUP BY job_title
            HAVING COUNT(DISTINCT source_table) > 1
            ORDER BY program_count DESC, job_title
        """)
        
        return [
            {'job_title': row[0], 'program_count': row[1], 'programs': row[2]}
            for row in cursor.fetchall()
        ]


# ============================================================================
# TRACKER & SURVEY QUERIES
# ============================================================================

def get_tracker_completion_statistics():
    """
    Get comprehensive tracker form completion statistics.
    """
    total_users = User.objects.filter(
        account_type__user=True
    ).count()
    
    completed = TrackerResponse.objects.filter(
        is_draft=False
    ).count()
    
    drafts = TrackerResponse.objects.filter(
        is_draft=True
    ).count()
    
    return {
        'total_users': total_users,
        'completed': completed,
        'drafts': drafts,
        'completion_rate': round((completed / total_users * 100) if total_users > 0 else 0, 2),
        'pending': total_users - completed - drafts
    }


def get_tracker_responses_with_user_data():
    """
    Get all tracker responses with full user profile data.
    Optimized for export/reporting.
    """
    return TrackerResponse.objects.select_related(
        'user',
        'user__profile',
        'user__academic_info',
        'user__employment',
        'user__tracker_data'
    ).prefetch_related(
        'files'
    ).filter(
        is_draft=False
    ).order_by('-submitted_at')


def get_tracker_answers_by_question(question_id: int):
    """
    Get all answers for a specific tracker question.
    Useful for analytics and reporting.
    """
    return TrackerResponse.objects.filter(
        is_draft=False,
        answers__has_key=str(question_id)
    ).annotate(
        answer_value=Case(
            When(answers__contains={str(question_id): None}, then=Value('')),
            default=F(f'answers__{question_id}'),
            output_field=CharField()
        )
    ).values('answer_value').annotate(
        count=Count('id')
    ).order_by('-count')


# ============================================================================
# SOCIAL FEATURES QUERIES (POSTS, COMMENTS, LIKES)
# ============================================================================

def get_posts_feed(user: User, limit: int = 20, offset: int = 0):
    """
    Get personalized posts feed with engagement metrics.
    Optimized for mobile app feed.
    """
    # Get users the current user follows
    following_ids = Follow.objects.filter(
        follower=user
    ).values_list('following_id', flat=True)
    
    # Include own posts and posts from followed users
    return Post.objects.filter(
        Q(user_id__in=following_ids) | Q(user=user)
    ).select_related(
        'user', 'user__profile'
    ).prefetch_related(
        'post_likes',
        'post_comments',
        'post_reposts',
        Prefetch(
            'post_likes',
            queryset=Like.objects.filter(user=user),
            to_attr='user_likes'
        )
    ).annotate(
        like_count=Count('post_likes', distinct=True),
        comment_count=Count('post_comments', distinct=True),
        repost_count=Count('post_reposts', distinct=True),
        is_liked=Exists(
            Like.objects.filter(
                post_id=OuterRef('post_id'),
                user=user
            )
        ),
        is_reposted=Exists(
            Repost.objects.filter(
                post_id=OuterRef('post_id'),
                user=user
            )
        )
    ).order_by('-created_at')[offset:offset+limit]


def get_post_with_engagement(post_id: int, user: Optional[User] = None):
    """
    Get a single post with all engagement data.
    """
    queryset = Post.objects.select_related(
        'user', 'user__profile'
    ).prefetch_related(
        Prefetch(
            'post_comments',
            queryset=Comment.objects.select_related(
                'user', 'user__profile'
            ).prefetch_related(
                'replies__user__profile'
            ).order_by('-date_created')[:50]  # Limit comments
        ),
        'post_likes__user__profile',
        'post_reposts__user__profile'
    ).annotate(
        like_count=Count('post_likes', distinct=True),
        comment_count=Count('post_comments', distinct=True),
        repost_count=Count('post_reposts', distinct=True)
    )
    
    if user:
        queryset = queryset.annotate(
            is_liked=Exists(
                Like.objects.filter(
                    post_id=OuterRef('post_id'),
                    user=user
                )
            ),
            is_reposted=Exists(
                Repost.objects.filter(
                    post_id=OuterRef('post_id'),
                    user=user
                )
            )
        )
    
    return queryset.get(post_id=post_id)


def get_trending_posts(hours: int = 24, limit: int = 10):
    """
    Get trending posts based on engagement in the last N hours.
    Uses a scoring algorithm: (likes * 1) + (comments * 2) + (reposts * 3)
    """
    cutoff_time = timezone.now() - timedelta(hours=hours)
    
    return Post.objects.filter(
        created_at__gte=cutoff_time
    ).select_related(
        'user', 'user__profile'
    ).annotate(
        like_count=Count('post_likes', distinct=True),
        comment_count=Count('post_comments', distinct=True),
        repost_count=Count('post_reposts', distinct=True),
        engagement_score=(
            Count('post_likes', distinct=True) * 1 +
            Count('post_comments', distinct=True) * 2 +
            Count('post_reposts', distinct=True) * 3
        )
    ).order_by('-engagement_score', '-created_at')[:limit]


# ============================================================================
# MESSAGING QUERIES
# ============================================================================

def get_user_conversations(user: User, limit: int = 50):
    """
    Get all conversations for a user with last message and unread count.
    """
    return Conversation.objects.filter(
        participants=user
    ).prefetch_related(
        'participants__profile',
        Prefetch(
            'messages',
            queryset=Message.objects.select_related(
                'sender__profile'
            ).order_by('-created_at')[:1],
            to_attr='last_message_list'
        )
    ).annotate(
        unread_count=Count(
            'messages',
            filter=Q(messages__is_read=False) & ~Q(messages__sender=user),
            distinct=True
        ),
        last_message_time=Max('messages__created_at')
    ).order_by('-last_message_time')[:limit]


def get_conversation_messages(conversation_id: int, user: User, limit: int = 50, offset: int = 0):
    """
    Get messages for a conversation with pagination.
    """
    conversation = Conversation.objects.get(conversation_id=conversation_id)
    
    # Verify user is participant
    if user not in conversation.participants.all():
        raise PermissionError("User is not a participant in this conversation")
    
    messages = Message.objects.filter(
        conversation=conversation
    ).select_related(
        'sender__profile'
    ).prefetch_related(
        'attachments'
    ).order_by('-created_at')[offset:offset+limit]
    
    # Mark messages as read
    Message.objects.filter(
        conversation=conversation,
        sender__ne=user,
        is_read=False
    ).update(is_read=True)
    
    return list(reversed(messages))  # Return in chronological order


def get_unread_message_count(user: User):
    """
    Get total unread message count for a user.
    """
    return Message.objects.filter(
        conversation__participants=user,
        sender__ne=user,
        is_read=False
    ).count()


# ============================================================================
# POINTS & REWARDS QUERIES
# ============================================================================

def get_points_leaderboard(limit: int = 100, program: Optional[str] = None):
    """
    Get points leaderboard with user details.
    """
    queryset = UserPoints.objects.select_related(
        'user', 'user__profile', 'user__academic_info'
    ).filter(
        total_points__gt=0
    )
    
    if program:
        queryset = queryset.filter(user__academic_info__program__iexact=program)
    
    return queryset.annotate(
        rank=Window(
            expression=RowNumber(),
            order_by=F('total_points').desc()
        )
    ).order_by('-total_points', 'user__f_name')[:limit]


def get_user_points_breakdown(user_id: int):
    """
    Get detailed points breakdown for a user.
    """
    user_points = UserPoints.objects.select_related('user').get(user_id=user_id)
    return user_points.get_breakdown()


def get_available_rewards():
    """
    Get all available rewards with stock information.
    """
    return RewardInventoryItem.objects.filter(
        quantity__gt=0
    ).annotate(
        pending_requests=Count(
            'requests',
            filter=Q(requests__status='pending')
        )
    ).order_by('type', 'name')


def get_user_reward_history(user_id: int, limit: int = 50):
    """
    Get reward history for a user.
    """
    return RewardHistory.objects.filter(
        user_id=user_id
    ).select_related(
        'given_by__profile'
    ).order_by('-given_at')[:limit]


# ============================================================================
# STATISTICS & ANALYTICS QUERIES
# ============================================================================

def get_program_statistics():
    """
    Get comprehensive statistics grouped by program.
    Used for CHED/SUC/AACUP reporting.
    """
    return AcademicInfo.objects.filter(
        program__isnull=False,
        user__user_status__iexact='active'
    ).values('program').annotate(
        total_graduates=Count('user_id', distinct=True),
        employed_count=Count(
            'user_id',
            filter=Q(user__employment__position_current__isnull=False),
            distinct=True
        ),
        self_employed_count=Count(
            'user_id',
            filter=Q(user__employment__self_employed=True),
            distinct=True
        ),
        high_position_count=Count(
            'user_id',
            filter=Q(user__employment__high_position=True),
            distinct=True
        ),
        absorbed_count=Count(
            'user_id',
            filter=Q(user__employment__absorbed=True),
            distinct=True
        ),
        aligned_job_count=Count(
            'user_id',
            filter=Q(user__employment__job_alignment_status='aligned'),
            distinct=True
        ),
        pursuing_further_study=Count(
            'user_id',
            filter=Q(pursue_further_study__iexact='yes'),
            distinct=True
        )
    ).order_by('program')


def get_employment_by_sector():
    """
    Get employment statistics grouped by sector.
    """
    return EmploymentHistory.objects.filter(
        sector_current__isnull=False,
        position_current__isnull=False
    ).values('sector_current').annotate(
        count=Count('id'),
        avg_salary_range=Avg('salary_current')  # Note: salary_current is CharField, may need parsing
    ).order_by('-count')


def get_graduation_year_statistics():
    """
    Get statistics grouped by graduation year.
    """
    return AcademicInfo.objects.filter(
        year_graduated__isnull=False,
        user__user_status__iexact='active'
    ).values('year_graduated').annotate(
        total_graduates=Count('user_id', distinct=True),
        employed_count=Count(
            'user_id',
            filter=Q(user__employment__position_current__isnull=False),
            distinct=True
        ),
        tracker_completed=Count(
            'user_id',
            filter=Q(user__tracker_data__tracker_submitted_at__isnull=False),
            distinct=True
        )
    ).order_by('-year_graduated')


# ============================================================================
# OJT QUERIES
# ============================================================================

def get_ojt_students_by_coordinator(coordinator: str, batch_year: Optional[int] = None):
    """
    Get OJT students grouped by coordinator with company information.
    """
    queryset = User.objects.filter(
        account_type__ojt=True,
        ojt_company_profile__coordinator=coordinator
    ).select_related(
        'ojt_info',
        'ojt_company_profile',
        'academic_info'
    )
    
    if batch_year:
        queryset = queryset.filter(academic_info__year_graduated=batch_year)
    
    return queryset.annotate(
        ojt_duration_days=Case(
            When(
                ojt_info__ojt_end_date__isnull=False,
                ojt_info__ojt_start_date__isnull=False,
                then=F('ojt_info__ojt_end_date') - F('ojt_info__ojt_start_date')
            ),
            default=Value(0),
            output_field=IntegerField()
        )
    ).order_by('academic_info__section', 'l_name', 'f_name')


def get_ojt_company_statistics():
    """
    Get statistics about OJT companies.
    """
    return OJTCompanyProfile.objects.filter(
        company_name__isnull=False
    ).values('company_name').annotate(
        student_count=Count('user_id', distinct=True),
        coordinators=Count('coordinator', distinct=True)
    ).order_by('-student_count', 'company_name')


# ============================================================================
# NOTIFICATION QUERIES
# ============================================================================

def get_user_notifications(user: User, limit: int = 50, unread_only: bool = False):
    """
    Get notifications for a user.
    """
    queryset = Notification.objects.filter(user=user)
    
    if unread_only:
        queryset = queryset.filter(is_read=False)
    
    return queryset.order_by('-notif_date')[:limit]


def get_unread_notification_count(user: User):
    """
    Get count of unread notifications.
    """
    return Notification.objects.filter(
        user=user,
        is_read=False
    ).count()


# ============================================================================
# ADVANCED ANALYTICS QUERIES
# ============================================================================

def get_engagement_metrics(start_date: datetime, end_date: datetime):
    """
    Get engagement metrics for a date range.
    """
    return {
        'posts': Post.objects.filter(
            created_at__range=[start_date, end_date]
        ).count(),
        'comments': Comment.objects.filter(
            date_created__range=[start_date, end_date]
        ).count(),
        'likes': Like.objects.filter(
            post__created_at__range=[start_date, end_date]
        ).count(),
        'reposts': Repost.objects.filter(
            repost_date__range=[start_date, end_date]
        ).count(),
        'new_users': User.objects.filter(
            created_at__range=[start_date, end_date]
        ).count(),
        'tracker_submissions': TrackerResponse.objects.filter(
            submitted_at__range=[start_date, end_date],
            is_draft=False
        ).count()
    }


def get_user_engagement_timeline(user_id: int, days: int = 30):
    """
    Get user engagement activity over time.
    """
    start_date = timezone.now() - timedelta(days=days)
    
    return {
        'posts': Post.objects.filter(
            user_id=user_id,
            created_at__gte=start_date
        ).values('created_at__date').annotate(
            count=Count('post_id')
        ).order_by('created_at__date'),
        'comments': Comment.objects.filter(
            user_id=user_id,
            date_created__gte=start_date
        ).values('date_created__date').annotate(
            count=Count('comment_id')
        ).order_by('date_created__date'),
        'likes': Like.objects.filter(
            user_id=user_id,
            post__created_at__gte=start_date
        ).values('post__created_at__date').annotate(
            count=Count('like_id')
        ).order_by('post__created_at__date')
    }

