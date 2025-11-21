from __future__ import annotations

from typing import Dict, List

from django.db import transaction
from django.utils import timezone

from apps.shared.milestones import ENGAGEMENT_MILESTONES, MilestoneSpec
from apps.shared.models import PointsTask, UserPoints, UserTaskCompletion


def ensure_milestone_tasks() -> Dict[str, PointsTask]:
    """
    Ensure that all milestone tasks exist in the database and return a map keyed by task_type.
    """
    updated_tasks: Dict[str, PointsTask] = {}
    for spec in ENGAGEMENT_MILESTONES:
        defaults = {
            'title': spec.title,
            'description': spec.description,
            'points': spec.points,
            'icon_name': spec.icon_name,
            'is_active': True,
            'order': spec.order,
            'required_count': spec.threshold,
        }
        task, created = PointsTask.objects.get_or_create(
            task_type=spec.task_type, defaults=defaults
        )
        if not created:
            changed = False
            for field in ('title', 'description', 'icon_name', 'order'):
                if getattr(task, field) != defaults[field]:
                    setattr(task, field, defaults[field])
                    changed = True
            if task.is_active is False:
                # keep admin preference; do not override manual deactivation
                pass
            # Only set required_count if it's None (first time creation)
            # Don't override admin's custom settings - they can adjust it in the admin panel
            if task.required_count is None:
                task.required_count = spec.threshold
                changed = True
            if changed:
                task.save()
        updated_tasks[spec.task_type] = task
    return updated_tasks


def _get_metric_value(user_points: UserPoints, spec: MilestoneSpec) -> int:
    """Return the current value for the metric referenced by the milestone spec."""
    if spec.metric == 'follow_count':
        return max(0, user_points.follow_count)
    return max(0, getattr(user_points, spec.metric, 0))


def evaluate_and_award_milestones(user_points: UserPoints) -> List[dict]:
    """
    Evaluate milestone progress for a user and award any newly completed milestones.

    Returns a list describing each milestone that awarded points during this evaluation.
    """
    from apps.shared.models import EngagementPointsSettings
    
    # Check if milestone tasks feature is enabled
    settings = EngagementPointsSettings.get_settings()
    if not getattr(settings, 'milestone_tasks_enabled', True):
        return []  # Milestone tasks are disabled, don't award any
    
    user = user_points.user
    tasks = ensure_milestone_tasks()

    existing_completions = {
        completion.task.task_type: completion
        for completion in UserTaskCompletion.objects.filter(
            user=user, task__task_type__in=tasks.keys()
        )
    }

    awarded: List[dict] = []

    for spec in ENGAGEMENT_MILESTONES:
        task = tasks.get(spec.task_type)
        if not task or not task.is_active:
            continue
        if spec.task_type in existing_completions:
            continue

        current_value = _get_metric_value(user_points, spec)
        required = task.required_count if (task and task.required_count) else spec.threshold
        if current_value < required:
            continue

        with transaction.atomic():
            # Double-check completion inside the transaction to avoid race conditions.
            completion = (
                UserTaskCompletion.objects.select_for_update()
                .filter(user=user, task=task)
                .first()
            )
            if completion:
                continue

            completion = UserTaskCompletion.objects.create(
                user=user,
                task=task,
                points_awarded=task.points,
            )

            user_points.add_milestone_points(task.points)

            awarded.append(
                {
                    'task_type': spec.task_type,
                    'title': task.title,
                    'category': spec.category,
                    'points': task.points,
                    'completed_at': completion.completed_at or timezone.now(),
                }
            )

    return awarded


def _generate_dynamic_description(base_description: str, required_count: int, spec: MilestoneSpec) -> str:
    """
    Generate dynamic description based on required_count.
    Replaces hardcoded numbers in descriptions with the actual required_count.
    """
    import re
    
    # First, replace patterns like "10 posts", "5 posts", "10 users", etc.
    description = re.sub(r'\d+\s+(posts?|users?)', f'{required_count} \\1', base_description, flags=re.IGNORECASE)
    
    # If no replacement happened, try replacing standalone numbers that appear before "posts" or "users"
    if description == base_description:
        # Pattern: "10" followed by "posts" or "users" (with possible words in between)
        description = re.sub(r'\b\d+\b(?=\s*(?:posts?|users?))', str(required_count), base_description, flags=re.IGNORECASE)
    
    # If still no replacement, replace the first number found
    if description == base_description:
        description = re.sub(r'\b\d+\b', str(required_count), base_description, count=1)
    
    return description


def _generate_dynamic_title(base_title: str, required_count: int) -> str:
    """
    Generate dynamic title based on required_count.
    Replaces hardcoded numbers in titles with the actual required_count.
    """
    import re
    
    # First, replace patterns like "10 posts", "5 posts", "10 users", etc.
    title = re.sub(r'\d+\s+(posts?|users?)', f'{required_count} \\1', base_title, flags=re.IGNORECASE)
    
    # If no replacement happened, try replacing standalone numbers that appear before "posts" or "users"
    if title == base_title:
        # Pattern: "10" followed by "posts" or "users" (with possible words in between)
        title = re.sub(r'\b\d+\b(?=\s*(?:posts?|users?))', str(required_count), base_title, flags=re.IGNORECASE)
    
    # If still no replacement, replace the first number found
    if title == base_title:
        title = re.sub(r'\b\d+\b', str(required_count), base_title, count=1)
    
    return title


def get_milestone_status(user_points: UserPoints) -> List[dict]:
    """
    Build a milestone status payload for API consumers.
    """
    from apps.shared.models import EngagementPointsSettings
    
    # Check if milestone tasks feature is enabled
    settings = EngagementPointsSettings.get_settings()
    if not getattr(settings, 'milestone_tasks_enabled', True):
        return []  # Milestone tasks are disabled, return empty list
    
    tasks = ensure_milestone_tasks()

    completions = {
        completion.task.task_type: completion
        for completion in UserTaskCompletion.objects.filter(
            user=user_points.user, task__task_type__in=tasks.keys()
        )
    }

    status_list: List[dict] = []
    for spec in ENGAGEMENT_MILESTONES:
        task = tasks.get(spec.task_type)
        if not task or not task.is_active:
            continue

        completion = completions.get(spec.task_type)
        current_value = _get_metric_value(user_points, spec)
        required = task.required_count if task.required_count else spec.threshold
        percent_complete = 100 if required == 0 else min(
            100, int((current_value / required) * 100)
        )
        
        # Generate dynamic title and description based on required_count
        dynamic_title = _generate_dynamic_title(task.title, required)
        dynamic_description = _generate_dynamic_description(task.description, required, spec)

        status_list.append(
            {
                'task_type': spec.task_type,
                'title': dynamic_title,
                'description': dynamic_description,
                'category': spec.category,
                'points': task.points,
                'icon': task.icon_name,
                'order': spec.order,
                'status': 'complete' if completion else 'pending',
                'progress': {
                    'current': current_value,
                    'required': required,
                    'percent': percent_complete,
                },
                'completed_at': (
                    completion.completed_at.isoformat() if completion else None
                ),
                'points_awarded': completion.points_awarded if completion else 0,
            }
        )

    # Ensure deterministic ordering
    status_list.sort(key=lambda item: item['order'])
    return status_list


def reset_daily_task_progress():
    """
    Reset daily task progress for all users.
    
    This function:
    1. Resets count fields in UserPoints to 0 (like_count, comment_count, share_count, etc.)
    2. Deletes UserTaskCompletion records for milestone tasks so they can be earned again
    3. Keeps all points intact (points are not deducted)
    
    This should be called daily (e.g., at midnight) to allow users to earn milestone
    task points again each day.
    """
    from django.db import transaction
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        tasks = ensure_milestone_tasks()
        milestone_task_types = set(tasks.keys())
        
        with transaction.atomic():
            # Reset count fields for all users
            # These are the progress counters that need to reset daily
            reset_count = UserPoints.objects.update(
                like_count=0,
                comment_count=0,
                share_count=0,
                reply_count=0,
                post_count=0,
                post_with_photo_count=0,
            )
            logger.info("Reset progress counts for %s users", reset_count)
            
            # Delete milestone task completions so they can be earned again
            # Only delete completions for milestone tasks, not other tasks like verify_email
            milestone_task_ids = [task.task_id for task in tasks.values()]
            deleted_count = UserTaskCompletion.objects.filter(
                task_id__in=milestone_task_ids
            ).delete()[0]
            logger.info("Deleted %s milestone task completions", deleted_count)
            
            logger.info("🎉 Daily task progress reset completed successfully")
            return {
                'success': True,
                'users_reset': reset_count,
                'completions_deleted': deleted_count,
            }
    except Exception as e:
        logger.error(f"❌ Error resetting daily task progress: {e}", exc_info=True)
        raise



