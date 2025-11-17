from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class MilestoneSpec:
    """Definition for an engagement milestone that can award bonus points."""

    task_type: str
    title: str
    description: str
    points: int
    category: str
    metric: str
    threshold: int
    order: int
    icon_name: str


ENGAGEMENT_MILESTONES: List[MilestoneSpec] = [
    MilestoneSpec(
        task_type='milestone_post_10',
        title='Make 10 posts',
        description='Publish 10 posts on the platform.',
        points=1,
        category='Post Milestones',
        metric='post_count',
        threshold=10,
        order=10,
        icon_name='edit',
    ),
    MilestoneSpec(
        task_type='milestone_share_10',
        title='Share 10 posts',
        description='Share or repost 10 posts from other users.',
        points=5,
        category='Share Milestones',
        metric='share_count',
        threshold=10,
        order=20,
        icon_name='share',
    ),
    MilestoneSpec(
        task_type='milestone_like_10',
        title='Like 10 posts',
        description='Engage with the community by liking 10 posts.',
        points=1,
        category='Engagement Milestones',
        metric='like_count',
        threshold=10,
        order=30,
        icon_name='thumbs-up',
    ),
    MilestoneSpec(
        task_type='milestone_comment_5',
        title='Comment on 5 posts',
        description='Join the conversation by commenting on 5 posts.',
        points=2,
        category='Engagement Milestones',
        metric='comment_count',
        threshold=5,
        order=40,
        icon_name='message-circle',
    ),
    MilestoneSpec(
        task_type='milestone_follow_10',
        title='Follow 10 users',
        description='Grow your network by following 10 users.',
        points=2,
        category='Social Milestones',
        metric='follow_count',
        threshold=10,
        order=50,
        icon_name='user-plus',
    ),
    MilestoneSpec(
        task_type='milestone_image_post',
        title='Post with an image',
        description='Create a post that includes an image.',
        points=2,
        category='Content Quality',
        metric='post_with_photo_count',
        threshold=1,
        order=60,
        icon_name='image',
    ),
]





