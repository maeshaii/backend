from django.db import models
from django.conf import settings
from cryptography.fernet import Fernet
from typing import Optional
import hashlib
import base64

class AccountType(models.Model):
    account_type_id = models.AutoField(primary_key=True)
    admin = models.BooleanField()
    peso = models.BooleanField()
    user = models.BooleanField()
    coordinator = models.BooleanField()

class Aacup(models.Model):
    aacup_id = models.AutoField(primary_key=True)
    standard = models.ForeignKey('Standard', on_delete=models.CASCADE, related_name='aacups')

class Ched(models.Model):
    ched_id = models.AutoField(primary_key=True)
    standard = models.ForeignKey('Standard', on_delete=models.CASCADE, related_name='cheds')

class Comment(models.Model):
    comment_id = models.AutoField(primary_key=True)
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='comments')
    post = models.ForeignKey('Post', on_delete=models.CASCADE, related_name='comments')
    comment_content = models.TextField(null=True, blank=True)
    date_created = models.DateTimeField()

class Reply(models.Model):
    reply_id = models.AutoField(primary_key=True)
    reply_content = models.TextField()
    date_created = models.DateTimeField(auto_now_add=True)
    comment = models.ForeignKey('Comment', on_delete=models.CASCADE, related_name='replies')
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='replies')
    
    class Meta:
        db_table = 'shared_reply'
        ordering = ['date_created']
    
    def __str__(self):
        return f"Reply {self.reply_id} by {self.user.full_name} on comment {self.comment.comment_id}"

class CompTechJob(models.Model):
    comp_tech_jobs_id = models.AutoField(primary_key=True)
    suc = models.ForeignKey('Suc', on_delete=models.CASCADE, related_name='comptechjob_sucs')
    info_system_jobs = models.ForeignKey('InfoSystemJob', on_delete=models.CASCADE, related_name='comptechjob_infosystemjobs')
    info_tech_jobs = models.ForeignKey('InfoTechJob', on_delete=models.CASCADE, related_name='comptechjob_infotechjobs')
    job_title = models.CharField(max_length=255)

class ExportedFile(models.Model):
    exported_file_id = models.AutoField(primary_key=True)
    standard = models.ForeignKey('Standard', on_delete=models.CASCADE, related_name='exported_files')
    file_name = models.CharField(max_length=255)
    exported_date = models.DateTimeField()

class Feed(models.Model):
    feed_id = models.AutoField(primary_key=True)
    post = models.ForeignKey('Post', on_delete=models.CASCADE, related_name='feeds')
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='feeds')

class Forum(models.Model):
    forum_id = models.AutoField(primary_key=True)
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='forums')
    post = models.ForeignKey('Post', on_delete=models.CASCADE, related_name='forums')
    comment = models.ForeignKey('Comment', on_delete=models.SET_NULL, null=True, related_name='forums')
    like = models.ForeignKey('Like', on_delete=models.SET_NULL, null=True, related_name='forums')

class HighPosition(models.Model):
    high_position_id = models.AutoField(primary_key=True)
    aacup = models.ForeignKey('Aacup', on_delete=models.CASCADE, related_name='high_positions')
    tracker_form = models.ForeignKey('TrackerForm', on_delete=models.CASCADE, related_name='high_positions')

class Import(models.Model):
    import_id = models.AutoField(primary_key=True)
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='imports')
    import_year = models.IntegerField()
    import_by = models.CharField(max_length=255)

class InfoTechJob(models.Model):
    info_tech_jobs_id = models.AutoField(primary_key=True)
    suc = models.ForeignKey('Suc', on_delete=models.CASCADE, related_name='infotechjob_sucs')
    info_systems_jobs = models.ForeignKey('InfoSystemJob', on_delete=models.CASCADE, related_name='infotechjob_infosystemjobs')
    comp_tech_jobs = models.ForeignKey('CompTechJob', on_delete=models.CASCADE, related_name='infotechjob_comptechjobs')
    job_title = models.CharField(max_length=255)

class InfoSystemJob(models.Model):
    info_system_jobs_id = models.AutoField(primary_key=True)
    suc = models.ForeignKey('Suc', on_delete=models.CASCADE, related_name='infosystemjob_sucs')
    info_tech_jobs = models.ForeignKey('InfoTechJob', on_delete=models.CASCADE, related_name='infosystemjob_infotechjobs')
    comp_tech_jobs = models.ForeignKey('CompTechJob', on_delete=models.CASCADE, related_name='infosystemjob_comptechjobs')
    job_title = models.CharField(max_length=255)

class Like(models.Model):
    like_id = models.AutoField(primary_key=True)
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='likes')
    post = models.ForeignKey('Post', on_delete=models.CASCADE, related_name='likes')

class Message(models.Model):
    message_id = models.AutoField(primary_key=True)
    sender_id = models.IntegerField()
    receiver_id = models.IntegerField()
    message_content = models.TextField()
    date_send = models.DateTimeField()

class Notification(models.Model):
    notification_id = models.AutoField(primary_key=True)
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='notifications')
    notif_type = models.CharField(max_length=100)
    subject = models.CharField(max_length=255, blank=True, null=True)  # Added subject field
    notifi_content = models.TextField()
    notif_date = models.DateTimeField()

class PostCategory(models.Model):
    post_cat_id = models.AutoField(primary_key=True)
    events = models.BooleanField()
    announcements = models.BooleanField()
    donation = models.BooleanField()
    personal = models.BooleanField()

class Post(models.Model):
    post_id = models.AutoField(primary_key=True)
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='posts')
    post_cat = models.ForeignKey('PostCategory', on_delete=models.CASCADE, related_name='posts')
    post_title = models.CharField(max_length=255)
    post_image = models.CharField(max_length=255)
    post_content = models.TextField()
    type = models.CharField(max_length=50, null=True, blank=True)

class Qpro(models.Model):
    qpro_id = models.AutoField(primary_key=True)
    standard = models.ForeignKey('Standard', on_delete=models.CASCADE, related_name='qpros')

class Repost(models.Model):
    repost_id = models.AutoField(primary_key=True)
    post = models.ForeignKey('Post', on_delete=models.CASCADE, related_name='reposts')
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='reposts')
    repost_date = models.DateTimeField()

class ContentImage(models.Model):
    """Stores images for posts, forums, comments, replies, and donations"""
    image_id = models.AutoField(primary_key=True)
    content_type = models.CharField(
        max_length=20,
        choices=[
            ('post', 'Post'),
            ('forum', 'Forum'),
            ('donation', 'Donation'),
            ('comment', 'Comment'),
            ('reply', 'Reply')
        ]
    )
    content_id = models.IntegerField()
    image = models.ImageField(upload_to='content_images/')
    order = models.IntegerField(default=0, help_text='Order of image when multiple images exist')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'shared_contentimage'
        ordering = ['content_type', 'content_id', 'order']
        indexes = [
            models.Index(fields=['content_type', 'content_id']),
            models.Index(fields=['content_type', 'content_id', 'order']),
        ]
    
    def __str__(self):
        return f"{self.content_type} {self.content_id} - Image {self.order}"

class Follow(models.Model):
    """Represents a follow relationship between users"""
    follower = models.ForeignKey('User', on_delete=models.CASCADE, related_name='following')
    following = models.ForeignKey('User', on_delete=models.CASCADE, related_name='followers')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'shared_follow'
        unique_together = [['follower', 'following']]
        indexes = [
            models.Index(fields=['follower']),
            models.Index(fields=['following']),
            models.Index(fields=['follower', 'following']),
        ]
    
    def __str__(self):
        return f"{self.follower.full_name} follows {self.following.full_name}"

class Standard(models.Model):
    standard_id = models.AutoField(primary_key=True)
    tracker_form = models.ForeignKey('TrackerForm', on_delete=models.CASCADE, related_name='standards')
    qpro = models.ForeignKey('Qpro', on_delete=models.CASCADE, related_name='standards')
    suc = models.ForeignKey('Suc', on_delete=models.CASCADE, related_name='standards')
    aacup = models.ForeignKey('Aacup', on_delete=models.CASCADE, related_name='standards')
    ched = models.ForeignKey('Ched', on_delete=models.CASCADE, related_name='standards')

class Suc(models.Model):
    suc_id = models.AutoField(primary_key=True)
    standard = models.ForeignKey('Standard', on_delete=models.CASCADE, related_name='suc_sucs')
    info_tech_jobs = models.ForeignKey('InfoTechJob', on_delete=models.CASCADE, related_name='suc_infotechjobs')
    info_system_jobs = models.ForeignKey('InfoSystemJob', on_delete=models.CASCADE, related_name='suc_infosystemjobs')
    comp_tech_jobs = models.ForeignKey('CompTechJob', on_delete=models.CASCADE, related_name='suc_comptechjobs')

class TrackerForm(models.Model):
    tracker_form_id = models.AutoField(primary_key=True)
    standard = models.ForeignKey('Standard', on_delete=models.CASCADE, related_name='tracker_forms', null=True, blank=True)
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='tracker_forms')
    title = models.CharField(max_length=255, blank=True, null=True)  # Added title field
    accepting_responses = models.BooleanField(default=True)  # Controls if alumni can submit

class User(models.Model):
    user_id = models.AutoField(primary_key=True)
    import_id = models.ForeignKey('Import', on_delete=models.CASCADE, related_name='users', null=True, blank=True)
    account_type = models.ForeignKey('AccountType', on_delete=models.CASCADE, related_name='users')
    acc_username = models.CharField(max_length=100, unique=True)
    acc_password = models.DateField()
    user_status = models.CharField(max_length=50)
    f_name = models.CharField(max_length=100)
    m_name = models.CharField(max_length=100, null=True, blank=True)
    l_name = models.CharField(max_length=100)
    gender = models.CharField(max_length=10)
    phone_num = models.CharField(max_length=20, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    profile_pic = models.CharField(max_length=255, null=True, blank=True)
    profile_bio = models.TextField(null=True, blank=True)
    profile_resume = models.CharField(max_length=255, null=True, blank=True)
    year_graduated = models.IntegerField(null=True, blank=True)
    course = models.CharField(max_length=100, null=True, blank=True)
    section = models.CharField(max_length=50, null=True, blank=True)
    civil_status = models.CharField(max_length=50, null=True, blank=True)
    social_media = models.CharField(max_length=255, null=True, blank=True)
    # Additional fields for full alumni info
    birthdate = models.DateField(null=True, blank=True)
    age = models.IntegerField(null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    program = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=50, null=True, blank=True)
    company_name_current = models.CharField(max_length=255, null=True, blank=True)
    position_current = models.CharField(max_length=255, null=True, blank=True)
    sector_current = models.CharField(max_length=255, null=True, blank=True)
    employment_duration_current = models.CharField(max_length=100, null=True, blank=True)
    salary_current = models.CharField(max_length=100, null=True, blank=True)
    supporting_document_current = models.CharField(max_length=255, null=True, blank=True)
    awards_recognition_current = models.CharField(max_length=255, null=True, blank=True)
    supporting_document_awards_recognition = models.CharField(max_length=255, null=True, blank=True)
    unemployment_reason = models.CharField(max_length=255, null=True, blank=True)
    pursue_further_study = models.CharField(max_length=10, null=True, blank=True)
    date_started = models.DateField(null=True, blank=True)
    school_name = models.CharField(max_length=255, null=True, blank=True)
    USERNAME_FIELD = 'acc_username'
    REQUIRED_FIELDS = []

    @property
    def is_anonymous(self):
        return False

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        try:
            return (self.user_status or '').lower() == 'active'
        except Exception:
            return True
    
    @property
    def full_name(self):
        """Return full name"""
        return f"{self.f_name} {self.m_name or ''} {self.l_name}".strip()
    
    def __str__(self):
        return f"{self.acc_username} - {self.full_name}"

    # Password helpers
    def set_password(self, raw_password: str) -> None:
        self.acc_password = make_password(raw_password)
        # Do not call save() here; caller decides when to persist

    def check_password(self, raw_password: str) -> bool:
        if not self.acc_password:
            return False
        # If the field contains a legacy un-hashed value (e.g., a date string), check_password will return False
        # In that case, caller can implement a legacy fallback
        try:
            return check_password(raw_password, self.acc_password)
        except Exception:
            return False



def _get_initial_password_fernet() -> Fernet:
    """Return a Fernet instance for encrypting initial passwords.
    Uses settings.INITIAL_PASSWORD_FERNET_KEY if provided; otherwise derives
    a stable key from SECRET_KEY via SHA-256.
    """
    key = getattr(settings, 'INITIAL_PASSWORD_FERNET_KEY', None)
    if not key:
        digest = hashlib.sha256(settings.SECRET_KEY.encode('utf-8')).digest()
        key = base64.urlsafe_b64encode(digest)
    elif not isinstance(key, (bytes, bytearray)):
        key = key.encode('utf-8')
    return Fernet(key)


class UserInitialPassword(models.Model):
    """Stores the original generated password for a user, encrypted at rest.

    This is intended solely for distribution to users (e.g., Excel exports)
    and should be cleared/expired per policy after onboarding.
    """
    user = models.OneToOneField('User', on_delete=models.CASCADE, related_name='initial_password')
    password_encrypted = models.TextField(null=False, blank=False)
    created_at = models.DateTimeField(auto_now_add=True)
    exported_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def set_plaintext(self, plaintext: str) -> None:
        f = _get_initial_password_fernet()
        token = f.encrypt(plaintext.encode('utf-8'))
        self.password_encrypted = token.decode('utf-8')

    def get_plaintext(self) -> Optional[str]:
        try:
            f = _get_initial_password_fernet()
            return f.decrypt(self.password_encrypted.encode('utf-8')).decode('utf-8')
        except Exception:
            return None

    def mark_exported(self) -> None:
        self.exported_at = timezone.now()
        self.save(update_fields=['exported_at'])


class UserPoints(models.Model):
    """Tracks engagement points for users (alumni and OJT students)."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='points')
    total_points = models.IntegerField(default=0)
    
    # Breakdown by action type
    points_from_likes = models.IntegerField(default=0)
    points_from_comments = models.IntegerField(default=0)
    points_from_shares = models.IntegerField(default=0)
    points_from_replies = models.IntegerField(default=0)
    points_from_posts = models.IntegerField(default=0)
    points_from_posts_with_photos = models.IntegerField(default=0)
    points_from_tracker_form = models.IntegerField(default=0)
    points_from_milestones = models.IntegerField(default=0)
    
    # Track counts for analytics
    like_count = models.IntegerField(default=0)
    comment_count = models.IntegerField(default=0)
    share_count = models.IntegerField(default=0)
    reply_count = models.IntegerField(default=0)
    post_count = models.IntegerField(default=0)
    post_with_photo_count = models.IntegerField(default=0)
    tracker_form_count = models.IntegerField(default=0)
    milestone_count = models.IntegerField(default=0)
    follow_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'shared_userpoints'
        indexes = [
            models.Index(fields=['-total_points']),  # For leaderboard queries
            models.Index(fields=['user']),
        ]
        verbose_name = 'User Points'
        verbose_name_plural = 'User Points'
    
    def __str__(self):
        return f"{self.user.full_name}: {self.total_points} pts"
    
    def _recalculate_total_points(self) -> None:
        self.total_points = (
            self.points_from_likes +
            self.points_from_comments +
            self.points_from_shares +
            self.points_from_replies +
            self.points_from_posts +
            self.points_from_posts_with_photos +
            self.points_from_tracker_form +
            self.points_from_milestones
        )
    
    def add_points(self, action_type: str, points: int = 0) -> None:
        """Add points for a specific action type and increment counts."""
        if action_type == 'like':
            self.points_from_likes += points
            self.like_count += 1
        elif action_type == 'comment':
            self.points_from_comments += points
            self.comment_count += 1
        elif action_type == 'share':
            self.points_from_shares += points
            self.share_count += 1
        elif action_type == 'reply':
            self.points_from_replies += points
            self.reply_count += 1
        elif action_type == 'post':
            self.points_from_posts += points
            self.post_count += 1
        elif action_type == 'post_with_photo':
            self.points_from_posts_with_photos += points
            self.post_with_photo_count += 1
        elif action_type == 'tracker_form':
            self.points_from_tracker_form += points
            self.tracker_form_count += 1
        elif action_type == 'milestone':
            self.points_from_milestones += points
            if points > 0:
                self.milestone_count += 1
        self._recalculate_total_points()
        self.save()
    
    def add_milestone_points(self, points: int) -> None:
        """Award milestone points and increment milestone counters."""
        if points <= 0:
            return
        self.points_from_milestones += points
        self.milestone_count += 1
        self._recalculate_total_points()
        self.save(update_fields=[
            'points_from_milestones',
            'milestone_count',
            'total_points',
            'updated_at',
        ])
    
    def deduct_points(self, action_type: str, points: int = 0) -> None:
        """Deduct points for a specific action type (e.g., when unliking)."""
        if action_type == 'like':
            self.points_from_likes = max(0, self.points_from_likes - points)
            self.like_count = max(0, self.like_count - 1)
        elif action_type == 'comment':
            self.points_from_comments = max(0, self.points_from_comments - points)
            self.comment_count = max(0, self.comment_count - 1)
        elif action_type == 'share':
            self.points_from_shares = max(0, self.points_from_shares - points)
            self.share_count = max(0, self.share_count - 1)
        elif action_type == 'reply':
            self.points_from_replies = max(0, self.points_from_replies - points)
            self.reply_count = max(0, self.reply_count - 1)
        elif action_type == 'post':
            self.points_from_posts = max(0, self.points_from_posts - points)
            self.post_count = max(0, self.post_count - 1)
        elif action_type == 'post_with_photo':
            self.points_from_posts_with_photos = max(0, self.points_from_posts_with_photos - points)
            self.post_with_photo_count = max(0, self.post_with_photo_count - 1)
        elif action_type == 'tracker_form':
            self.points_from_tracker_form = max(0, self.points_from_tracker_form - points)
            self.tracker_form_count = max(0, self.tracker_form_count - 1)
        self._recalculate_total_points()
        self.save()
    
    def set_follow_count(self, count: int) -> None:
        """Update cached follow count used when evaluating milestones."""
        if count < 0:
            count = 0
        if self.follow_count != count:
            self.follow_count = count
            self.save(update_fields=['follow_count', 'updated_at'])
    
    def get_breakdown(self) -> dict:
        """Return a standardized points breakdown for API consumers."""
        return {
            'likes': {
                'points': self.points_from_likes,
                'count': self.like_count,
            },
            'comments': {
                'points': self.points_from_comments,
                'count': self.comment_count,
            },
            'shares': {
                'points': self.points_from_shares,
                'count': self.share_count,
            },
            'replies': {
                'points': self.points_from_replies,
                'count': self.reply_count,
            },
            'posts': {
                'points': self.points_from_posts,
                'count': self.post_count,
            },
            'posts_with_photos': {
                'points': self.points_from_posts_with_photos,
                'count': self.post_with_photo_count,
            },
            'tracker_form': {
                'points': self.points_from_tracker_form,
                'count': self.tracker_form_count,
            },
            'milestones': {
                'points': self.points_from_milestones,
                'count': self.milestone_count,
            },
        }


class EngagementPointsSettings(models.Model):
    """Stores configurable engagement points settings for the system.
    
    Only one instance should exist (singleton pattern).
    """
    enabled = models.BooleanField(default=True, help_text="Enable or disable the points system")
    milestone_tasks_enabled = models.BooleanField(default=True, help_text="Enable or disable milestone tasks feature")
    tracker_form_enabled = models.BooleanField(default=True, help_text="Enable or disable tracker form rewards")
    
    # Points awarded per action
    like_points = models.IntegerField(default=1, help_text="Points for liking a post")
    comment_points = models.IntegerField(default=2, help_text="Points for commenting on a post")
    share_points = models.IntegerField(default=3, help_text="Points for sharing/reposting a post")
    reply_points = models.IntegerField(default=3, help_text="Points for replying to a comment")
    post_points = models.IntegerField(default=5, help_text="Points for posting without photos")
    post_with_photo_points = models.IntegerField(default=10, help_text="Points for posting with photos")
    tracker_form_points = models.IntegerField(default=10, help_text="Points for completing tracker form")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'shared_engagementpointssettings'
        verbose_name = 'Engagement Points Settings'
        verbose_name_plural = 'Engagement Points Settings'
    
    def __str__(self):
        return f"Points Settings (Enabled: {self.enabled})"
    
    @classmethod
    def get_settings(cls):
        """Get the current settings, creating default if none exist."""
        settings, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                'enabled': True,
                'milestone_tasks_enabled': True,
                'tracker_form_enabled': True,
                'like_points': 1,
                'comment_points': 3,
                'share_points': 5,
                'reply_points': 2,
                'post_points': 0,
                'post_with_photo_points': 15,
                'tracker_form_points': 10,
            }
        )
        return settings


# Refactored User Model Components
class UserProfile(models.Model):
    """Personal and contact information.

    Used by Mobile: profile view/update and avatar/bio display.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_num = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    home_address = models.TextField(null=True, blank=True)
    birthdate = models.DateField(null=True, blank=True)
    age = models.IntegerField(null=True, blank=True)
    civil_status = models.CharField(max_length=50, null=True, blank=True)
    social_media = models.CharField(max_length=255, null=True, blank=True)
    profile_pic = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    profile_bio = models.TextField(null=True, blank=True)
    profile_resume = models.FileField(upload_to='resumes/', null=True, blank=True)
    email_verified = models.BooleanField(default=False, help_text='Whether the user has verified their email address')
    preferences_completed = models.BooleanField(default=False, help_text='Whether the user has completed their preferences')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['civil_status']),
            models.Index(fields=['age']),
        ]
    
    @property
    def calculated_age(self):
        """Calculate age based on birthdate"""
        if self.birthdate:
            from datetime import date
            today = date.today()
            age = today.year - self.birthdate.year - ((today.month, today.day) < (self.birthdate.month, self.birthdate.day))
            return age
        return None
    
    def __str__(self):
        return f"Profile for {self.user.full_name}"


class AcademicInfo(models.Model):
    """Education and academic information"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='academic_info')
    year_graduated = models.IntegerField(null=True, blank=True)
    program = models.CharField(max_length=100, null=True, blank=True)
    section = models.CharField(max_length=50, null=True, blank=True)
    school_name = models.CharField(max_length=255, null=True, blank=True)
    
    # Further study information
    pursue_further_study = models.CharField(max_length=10, null=True, blank=True)
    q_pursue_study = models.CharField(max_length=10, null=True, blank=True)
    q_study_start_date = models.DateField(null=True, blank=True)
    q_post_graduate_degree = models.CharField(max_length=255, null=True, blank=True)
    q_institution_name = models.CharField(max_length=255, null=True, blank=True)
    q_units_obtained = models.CharField(max_length=50, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['year_graduated', 'program']),
            models.Index(fields=['pursue_further_study']),
        ]
    
    def __str__(self):
        return f"Academic info for {self.user.full_name} - {self.program} ({self.year_graduated})"


class EmploymentHistory(models.Model):
    """Employment and job information"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employment')
    
    # Current employment
    company_name_current = models.CharField(max_length=255, null=True, blank=True)
    position_current = models.CharField(max_length=255, null=True, blank=True)
    sector_current = models.CharField(max_length=255, null=True, blank=True)
    scope_current = models.CharField(max_length=255, null=True, blank=True)
    employment_duration_current = models.CharField(max_length=100, null=True, blank=True)
    salary_current = models.CharField(max_length=100, null=True, blank=True)
    date_started = models.DateField(null=True, blank=True)
    company_address = models.TextField(null=True, blank=True)
    company_email = models.EmailField(null=True, blank=True)
    company_contact = models.CharField(max_length=20, null=True, blank=True)
    contact_person = models.CharField(max_length=255, null=True, blank=True)
    position = models.CharField(max_length=255, null=True, blank=True)
    
    # Employment status and alignment
    job_alignment_status = models.CharField(max_length=50, null=True, blank=True, default='not_aligned')
    job_alignment_category = models.CharField(max_length=100, null=True, blank=True)
    job_alignment_title = models.CharField(max_length=255, null=True, blank=True)
    
    # PHASE 3: Cross-program alignment fields
    job_alignment_suggested_program = models.CharField(max_length=50, null=True, blank=True, 
                                                      help_text="Program suggested for cross-alignment")
    job_alignment_original_program = models.CharField(max_length=50, null=True, blank=True,
                                                     help_text="Original program of the graduate")
    self_employed = models.BooleanField(default=False)
    high_position = models.BooleanField(default=False)
    absorbed = models.BooleanField(default=False)
    
    # Awards and recognition
    awards_recognition_current = models.CharField(max_length=255, null=True, blank=True)
    supporting_document_current = models.CharField(max_length=255, null=True, blank=True)
    supporting_document_awards_recognition = models.CharField(max_length=255, null=True, blank=True)
    
    # Unemployment
    unemployment_reason = models.CharField(max_length=255, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['company_name_current', 'position_current']),
            models.Index(fields=['job_alignment_status']),
            models.Index(fields=['self_employed', 'high_position']),
        ]
    
    def _normalize_job_title(self, position: str) -> str:
        """Normalize a job title for consistent matching/storage."""
        if not position:
            return ''
        # Collapse whitespace then upper-case for canonical storage
        collapsed = ' '.join(position.strip().split())
        return collapsed.upper()

    def _normalize_job_title(self, position: str) -> str:
        normalized = _normalize_text(position)
        return normalized.upper() if normalized else ''

    def _normalize_company_name(self, company: Optional[str]) -> Optional[str]:
        normalized = _normalize_text(company)
        return normalized.upper() if normalized else None

    def _check_job_alignment_for_position(self, position, program):
        """Check job alignment for a specific position without saving to database
        Used during form completion for real-time alignment checking
        """
        if not position:
            self.job_alignment_status = 'not_aligned'
            self.job_alignment_category = None
            self.job_alignment_title = None
            return
        
        normalized_position = self._normalize_job_title(position)
        position_lower = normalized_position.lower()
        program_lower = (program or '').lower()
        
        # Check alignment against job tables
        alignment_found = False
        
        # Check SimpleInfoTechJob (BSIT)
        if 'bsit' in program_lower or 'information technology' in program_lower:
            if SimpleInfoTechJob.objects.filter(job_title__iexact=normalized_position).exists():
                self.job_alignment_status = 'aligned'
                self.job_alignment_category = 'BSIT'
                self.job_alignment_title = normalized_position
                alignment_found = True
        
        # Check SimpleInfoSystemJob (BSIS)
        if not alignment_found and ('bsis' in program_lower or 'information system' in program_lower):
            if SimpleInfoSystemJob.objects.filter(job_title__iexact=normalized_position).exists():
                self.job_alignment_status = 'aligned'
                self.job_alignment_category = 'BSIS'
                self.job_alignment_title = normalized_position
                alignment_found = True
        
        # Check SimpleCompTechJob (BIT-CT)
        if not alignment_found and ('bit-ct' in program_lower or 'computer technology' in program_lower):
            if SimpleCompTechJob.objects.filter(job_title__iexact=normalized_position).exists():
                self.job_alignment_status = 'aligned'
                self.job_alignment_category = 'BIT-CT'
                self.job_alignment_title = normalized_position
                alignment_found = True
        
        # Check cross-program alignment
        if not alignment_found:
            cross_program_match = self._find_cross_program_match(position_lower, program_lower)
            if cross_program_match:
                self.job_alignment_status = 'pending_user_confirmation'
                self.job_alignment_category = cross_program_match['category']
                self.job_alignment_title = self._normalize_job_title(cross_program_match['title'])
                self.job_alignment_suggested_program = cross_program_match['suggested_program']
                self.job_alignment_original_program = program
                self.match_method = cross_program_match.get('match_method')
                alignment_found = True
        
        # If no alignment found, mark as pending confirmation
        if not alignment_found:
            self.job_alignment_status = 'pending_user_confirmation'
            self.job_alignment_category = None
            self.job_alignment_title = normalized_position
            self.job_alignment_original_program = program
        
        return self.job_alignment_status

    def save(self, *args, **kwargs):
        if self.position_current:
            self.position_current = self._normalize_job_title(self.position_current)
        if self.company_name_current:
            self.company_name_current = self._normalize_company_name(self.company_name_current)
        super().save(*args, **kwargs)


    def update_job_alignment(self):
        """Update job alignment fields based on position_current and program
        This connects tracker answers to statistics types (CHED, SUC, AACUP)
        """
        if not self.position_current:
            self.job_alignment_status = 'not_aligned'
            self.job_alignment_category = None
            self.job_alignment_title = None
            return
        
        normalized_position = self._normalize_job_title(self.position_current)
        self.position_current = normalized_position
        position_lower = normalized_position.lower()
        course_lower = (self.user.academic_info.program or '').lower() if hasattr(self.user, 'academic_info') else ''
        
        # STEP 1: Self-employed status based on tracker answer Q23 (q_employment_type)
        # Check if user is self-employed based on tracker response
        tracker_data = getattr(self.user, 'tracker_data', None)
        if tracker_data and tracker_data.q_employment_type:
            employment_type_lower = tracker_data.q_employment_type.lower()
            if 'self-employed' in employment_type_lower or 'self employed' in employment_type_lower:
                self.self_employed = True
            else:
                self.self_employed = False
        else:
            self.self_employed = False
        
        # STEP 2: Check for high position status (for AACUP statistics)
        # More specific keywords and context-aware detection
        high_position_keywords = [
            'chief', 'director', 'president', 'vice president', 'ceo', 'cto', 'cfo', 'vp',
            'senior manager', 'senior director', 'executive', 'head of', 'lead'
        ]
        
        # Check for high position keywords
        is_high_position = any(keyword in position_lower for keyword in high_position_keywords)
        
        # Additional checks for management positions
        if 'manager' in position_lower:
            # Only consider "manager" as high position if it's not "assistant manager" or similar
            if not any(exclude in position_lower for exclude in ['assistant', 'junior', 'trainee', 'intern']):
                is_high_position = True
        
        self.high_position = is_high_position
        
        # STEP 3: Check for absorbed status (for AACUP) - typically first job after graduation
        # Priority 1: If current company matches OJT company, they were absorbed
        absorbed_by_ojt_match = False
        if self.company_name_current and hasattr(self.user, 'ojt_company_profile') and self.user.ojt_company_profile:
            ojt_company = getattr(self.user.ojt_company_profile, 'company_name', '')
            if ojt_company and self.company_name_current:
                # Case-insensitive comparison with normalization
                current_company_normalized = self.company_name_current.lower().strip()
                ojt_company_normalized = ojt_company.lower().strip()
                
                # Check for exact match or partial match (for variations in company names)
                if (current_company_normalized == ojt_company_normalized or 
                    current_company_normalized in ojt_company_normalized or
                    ojt_company_normalized in current_company_normalized):
                    absorbed_by_ojt_match = True
                    self.absorbed = True
        
        # Priority 2: If not absorbed by OJT match, check if hired within 6 months of graduation
        if not absorbed_by_ojt_match and self.date_started and hasattr(self.user, 'academic_info') and self.user.academic_info.year_graduated:
            # If hired within 6 months of graduation, consider absorbed
            from datetime import date
            graduation_date = date(self.user.academic_info.year_graduated, 6, 30)  # Assume June graduation
            
            # Ensure date_started is a date object for comparison
            if isinstance(self.date_started, str):
                try:
                    from datetime import datetime
                    self.date_started = datetime.strptime(self.date_started, '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    self.date_started = None
            
            if self.date_started and self.date_started <= graduation_date:
                self.absorbed = True
            else:
                self.absorbed = False
        elif not absorbed_by_ojt_match:
            # If no date started or graduation info, default to False
            self.absorbed = False
        
        # STEP 4: Smart Job Alignment with Database Expansion
        # SENIOR DEV: Intelligent job alignment with automatic database expansion
        import logging
        from django.contrib.postgres.search import TrigramSimilarity
        
        logger = logging.getLogger('apps.shared.models')
        job_aligned = False
        match_method = None
        
        # Helper function for multi-tier matching
        def find_job_match(job_model, position, position_lower):
            """
            Three-tier matching strategy:
            1. Exact match (case-insensitive)
            2. Substring match (contains)
            3. Fuzzy match (trigram similarity > 0.6)
            Returns: (matched_job, match_method)
            """
            # Tier 1: Exact match
            match = job_model.objects.filter(job_title__iexact=position).first()
            if match:
                return match, 'exact'
            
            # Tier 2: Substring match
            match = job_model.objects.filter(job_title__icontains=position_lower).first()
            if match:
                return match, 'substring'
            
            # Tier 3: Fuzzy match using trigram similarity
            try:
                match = job_model.objects.annotate(
                    similarity=TrigramSimilarity('job_title', position_lower)
                ).filter(similarity__gt=0.6).order_by('-similarity').first()
                if match:
                    return match, f'fuzzy (similarity: {match.similarity:.2f})'
            except Exception:
                pass  # Trigram not available, skip fuzzy matching
            
            return None, None
        
        # STEP 4A: Check user's own program first
        user_program_match = None
        user_program_category = None
        
        if 'bit-ct' in course_lower or 'computer technology' in course_lower:
            matched_job, match_method = find_job_match(SimpleCompTechJob, self.position_current, position_lower)
            if matched_job:
                user_program_match = matched_job
                user_program_category = 'comp_tech'
        
        elif 'bsit' in course_lower or 'information technology' in course_lower:
            matched_job, match_method = find_job_match(SimpleInfoTechJob, self.position_current, position_lower)
            if matched_job:
                user_program_match = matched_job
                user_program_category = 'info_tech'
        
        elif 'bsis' in course_lower or 'information system' in course_lower:
            matched_job, match_method = find_job_match(SimpleInfoSystemJob, self.position_current, position_lower)
            if matched_job:
                user_program_match = matched_job
                user_program_category = 'info_system'
        
        # STEP 4B: If found in user's program - align immediately
        if user_program_match:
            self.job_alignment_status = 'aligned'
            self.job_alignment_category = user_program_category
            self.job_alignment_title = user_program_match.job_title
            job_aligned = True
            
            # Log fuzzy matches for review
            if match_method and 'fuzzy' in match_method:
                logger.info(f"Fuzzy match in own program: '{self.position_current}' -> '{user_program_match.job_title}' ({match_method})")
        
        # STEP 4C: If NOT found in user's program - show radio button for potential expansion
        else:
            # SENIOR DEV: Show radio button immediately, don't check other programs yet
            self.job_alignment_status = 'pending_user_confirmation'
            self.job_alignment_category = None
            self.job_alignment_title = None
            self.job_alignment_original_program = course_lower
            
            logger.info(f"Job not found in user's program: '{self.position_current}' (Program: {course_lower}, User: {self.user.user_id}) - Awaiting user confirmation")
    
    def _find_cross_program_match(self, position_lower, original_program):
        """
        Find job matches in other programs when no match found in original program.
        Returns dict with match info or None if no cross-program match found.
        """
        # Define program mappings
        program_job_models = {
            'bit-ct': SimpleCompTechJob,
            'bsit': SimpleInfoTechJob, 
            'bsis': SimpleInfoSystemJob
        }
        
        # Get all programs except the original one
        other_programs = {k: v for k, v in program_job_models.items() if k not in original_program}
        
        for program_name, job_model in other_programs.items():
            matched_job, match_method = self._find_job_match_in_model(job_model, position_lower)
            
            if matched_job:
                return {
                    'title': matched_job.job_title,
                    'category': self._get_category_for_program(program_name),
                    'suggested_program': program_name,
                    'match_method': match_method
                }
        
        return None
    
    def _find_job_match_in_model(self, job_model, position_lower):
        """Helper to find job match in a specific model"""
        from django.contrib.postgres.search import TrigramSimilarity
        
        # Tier 1: Exact match
        match = job_model.objects.filter(job_title__iexact=position_lower).first()
        if match:
            return match, 'exact'
        
        # Tier 2: Substring match
        match = job_model.objects.filter(job_title__icontains=position_lower).first()
        if match:
            return match, 'substring'
        
        # Tier 3: Fuzzy match
        try:
            match = job_model.objects.annotate(
                similarity=TrigramSimilarity('job_title', position_lower)
            ).filter(similarity__gt=0.6).order_by('-similarity').first()
            if match:
                return match, f'fuzzy (similarity: {match.similarity:.2f})'
        except Exception:
            pass
        
        return None, None
    
    def _get_category_for_program(self, program_name):
        """Get job category string for program name"""
        category_map = {
            'bit-ct': 'comp_tech',
            'bsit': 'info_tech',
            'bsis': 'info_system'
        }
        return category_map.get(program_name, 'unknown')
    
    def confirm_job_alignment(self, confirmed=True):
        """
        SENIOR DEV: Smart job alignment confirmation with database expansion.
        Called when user responds to job alignment question.
        """
        import logging
        from django.contrib.postgres.search import TrigramSimilarity
        
        logger = logging.getLogger('apps.shared.models')
        
        if self.job_alignment_status == 'pending_user_confirmation':
            if confirmed:
                # User said YES - now check if it's a cross-course job
                cross_program_match = self._find_cross_program_match(
                    self.position_current.lower(), 
                    self.job_alignment_original_program
                )
                
                if cross_program_match:
                    # Found in another program - add to user's program table
                    self._add_job_to_user_program_table(cross_program_match)
                    
                    # Mark as aligned
                    self.job_alignment_status = 'aligned'
                    self.job_alignment_category = cross_program_match['category']
                    self.job_alignment_title = cross_program_match['title']
                    
                    logger.info(f"Cross-program job added to database: '{self.position_current}' added to {self.job_alignment_original_program} table")
                else:
                    # Not found in any program - add as new job type to user's program table
                    self.job_alignment_status = 'aligned'
                    self.job_alignment_category = self._get_category_for_program(self.job_alignment_original_program)
                    self.job_alignment_title = self.position_current
                    
                    # Add the new job to the user's program table
                    self._add_new_job_to_program_table(self.position_current, self.job_alignment_original_program)
                    
                    logger.info(f"New job type aligned: '{self.position_current}' added to {self.job_alignment_original_program} table")
            else:
                # User said NO - mark as not aligned
                self.job_alignment_status = 'not_aligned'
                self.job_alignment_category = None
                self.job_alignment_title = None
                
                logger.info(f"Job alignment rejected by user: '{self.position_current}'")
            
            # Clear temporary fields
            self.job_alignment_suggested_program = None
            self.job_alignment_original_program = None
            self.save()
    
    def _add_job_to_user_program_table(self, cross_program_match):
        """
        SENIOR DEV: Add cross-program job to user's program table for future use.
        """
        import logging
        logger = logging.getLogger('apps.shared.models')
        
        try:
            # Determine which table to add to based on user's program
            user_program = self.job_alignment_original_program
            job_title = self._normalize_job_title(cross_program_match['title'])
            
            # Add to appropriate table
            if 'bit-ct' in user_program or 'computer technology' in user_program:
                # Check if already exists
                if not SimpleCompTechJob.objects.filter(job_title__iexact=job_title).exists():
                    SimpleCompTechJob.objects.create(job_title=job_title)
                    logger.info("Added '%s' to BIT-CT job table", job_title)
            
            elif 'bsit' in user_program or 'information technology' in user_program:
                # Check if already exists
                if not SimpleInfoTechJob.objects.filter(job_title__iexact=job_title).exists():
                    SimpleInfoTechJob.objects.create(job_title=job_title)
                    logger.info("Added '%s' to BSIT job table", job_title)
            
            elif 'bsis' in user_program or 'information system' in user_program:
                # Check if already exists
                if not SimpleInfoSystemJob.objects.filter(job_title__iexact=job_title).exists():
                    SimpleInfoSystemJob.objects.create(job_title=job_title)
                    logger.info("Added '%s' to BSIS job table", job_title)
            
        except Exception as e:
            logger.error("Failed to add job to user program table: %s", e)
            # Don't let this break the main flow
    
    def _add_new_job_to_program_table(self, job_title, user_program):
        """
        SENIOR DEV: Add new job to user's program table for future use.
        """
        import logging
        logger = logging.getLogger('apps.shared.models')
        
        try:
            # Add to appropriate table based on user's program
            if 'bit-ct' in user_program.lower() or 'computer technology' in user_program.lower():
                # Check if already exists
                normalized = self._normalize_job_title(job_title)
                if not SimpleCompTechJob.objects.filter(job_title__iexact=normalized).exists():
                    SimpleCompTechJob.objects.create(job_title=normalized)
                    logger.info("Added new job '%s' to BIT-CT job table", normalized)
            
            elif 'bsit' in user_program.lower() or 'information technology' in user_program.lower():
                # Check if already exists
                normalized = self._normalize_job_title(job_title)
                if not SimpleInfoTechJob.objects.filter(job_title__iexact=normalized).exists():
                    SimpleInfoTechJob.objects.create(job_title=normalized)
                    logger.info("Added new job '%s' to BSIT job table", normalized)
            
            elif 'bsis' in user_program.lower() or 'information system' in user_program.lower():
                # Check if already exists
                normalized = self._normalize_job_title(job_title)
                if not SimpleInfoSystemJob.objects.filter(job_title__iexact=normalized).exists():
                    SimpleInfoSystemJob.objects.create(job_title=normalized)
                    logger.info("Added new job '%s' to BSIS job table", normalized)
            
        except Exception as e:
            logger.error("Failed to add new job to program table: %s", e)
            # Don't let this break the main flow
    
    def __str__(self):
        return f"Employment for {self.user.full_name} - {self.position_current} at {self.company_name_current}"


class TrackerData(models.Model):
    """Survey/tracker response data"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='tracker_data')
    
    # Employment tracker questions
    q_employment_status = models.CharField(max_length=50, null=True, blank=True)
    q_employment_type = models.CharField(max_length=100, null=True, blank=True)
    q_employment_permanent = models.CharField(max_length=20, null=True, blank=True)
    q_company_name = models.CharField(max_length=255, null=True, blank=True)
    q_current_position = models.CharField(max_length=255, null=True, blank=True)
    q_job_sector = models.CharField(max_length=50, null=True, blank=True)
    q_sector_current = models.CharField(max_length=50, null=True, blank=True)  # Public/Private
    q_scope_current = models.CharField(max_length=50, null=True, blank=True)   # Local/International
    q_employment_duration = models.CharField(max_length=100, null=True, blank=True)
    q_salary_range = models.CharField(max_length=100, null=True, blank=True)
    q_awards_received = models.CharField(max_length=10, null=True, blank=True)
    q_awards_document = models.FileField(upload_to='awards/', null=True, blank=True)
    q_employment_document = models.FileField(upload_to='employment/', null=True, blank=True)
    
    # Unemployment
    q_unemployment_reason = models.JSONField(null=True, blank=True)
    
    # Metadata
    tracker_submitted_at = models.DateTimeField(null=True, blank=True)
    tracker_last_updated = models.DateTimeField(auto_now=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['q_employment_status']),
            models.Index(fields=['tracker_submitted_at']),
        ]
    
    def __str__(self):
        return f"Tracker data for {self.user.full_name}"


class OJTInfo(models.Model):
    """On-the-job training and internship information"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='ojt_info')
    ojt_start_date = models.DateField(null=True, blank=True)
    ojt_end_date = models.DateField(null=True, blank=True)
    job_code = models.CharField(max_length=20, null=True, blank=True)
    ojtstatus = models.CharField(max_length=50, null=True, blank=True)
    is_sent_to_admin = models.BooleanField(default=False)  # Track if sent to admin for approval
    sent_to_admin_date = models.DateTimeField(null=True, blank=True)  # When it was sent
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['ojtstatus']),
            models.Index(fields=['ojt_end_date']),
            models.Index(fields=['ojt_start_date']),
        ]
    
    def __str__(self):
        return f"OJT info for {self.user.full_name} - Status: {self.ojtstatus}"


class OJTImport(models.Model):
    """Tracks OJT data imports by coordinators"""
    import_id = models.AutoField(primary_key=True)
    coordinator = models.CharField(max_length=100)
    batch_year = models.IntegerField()
    course = models.CharField(max_length=100)
    section = models.CharField(max_length=50, null=True, blank=True)
    import_date = models.DateTimeField(auto_now_add=True)
    file_name = models.CharField(max_length=255)
    records_imported = models.IntegerField(default=0)
    status = models.CharField(max_length=50, default='Completed')
    
    class Meta:
        db_table = 'shared_ojtimport'
        ordering = ['-import_date']
    
    def __str__(self):
        return f"OJT Import {self.import_id} - {self.course} {self.batch_year} ({self.section or 'No Section'})"


class OJTCompanyProfile(models.Model):
    """OJT Company Profile - Stores company information for OJT students"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='ojt_company_profile')
    coordinator = models.CharField(max_length=100, null=True, blank=True)  # Track which coordinator imported this profile
    company_name = models.CharField(max_length=255, null=True, blank=True)
    company_address = models.TextField(null=True, blank=True)
    company_email = models.EmailField(null=True, blank=True)
    company_contact = models.CharField(max_length=20, null=True, blank=True)
    contact_person = models.CharField(max_length=255, null=True, blank=True)
    position = models.CharField(max_length=255, null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['company_name']),
            models.Index(fields=['start_date']),
            models.Index(fields=['end_date']),
            models.Index(fields=['coordinator']),
        ]
    
    def __str__(self):
        return f"OJT Company Profile for {self.user.full_name} - {self.company_name}"

    def save(self, *args, **kwargs):
        if self.company_name:
            normalized = _normalize_text(self.company_name)
            self.company_name = normalized.upper() if normalized else None
        if self.position:
            normalized_pos = _normalize_text(self.position)
            self.position = normalized_pos.upper() if normalized_pos else None
        super().save(*args, **kwargs)


class QuestionCategory(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

class Question(models.Model):
    category = models.ForeignKey(QuestionCategory, related_name='questions', on_delete=models.CASCADE)
    text = models.CharField(max_length=255)
    type = models.CharField(max_length=50)
    options = models.JSONField(blank=True, null=True)  # For radio/multiple/checkbox

class TrackerResponse(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    answers = models.JSONField()  # {question_id: answer}
    submitted_at = models.DateTimeField(auto_now_add=True)

class TrackerFileUpload(models.Model):
    response = models.ForeignKey(TrackerResponse, on_delete=models.CASCADE, related_name='files')
    question_id = models.IntegerField()  # ID of the question this file answers
    file = models.FileField(upload_to='tracker_uploads/')
    original_filename = models.CharField(max_length=255)
    file_size = models.IntegerField()  # File size in bytes
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.original_filename} - {self.response.user.f_name} {self.response.user.l_name}"

# ==========================
# Forum-specific relations (now use shared tables)
# ==========================
# ForumRepost has been merged into Repost table

class RewardInventoryItem(models.Model):
    """Reward inventory items that can be redeemed with engagement points"""
    item_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=100)  # Gift Card, Certificate, Voucher, Merchandise, etc.
    quantity = models.IntegerField(default=0)
    value = models.CharField(max_length=100)  # e.g., "$25", "100 pts"
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'shared_rewardinventoryitem'
        verbose_name = 'Reward Inventory Item'
        verbose_name_plural = 'Reward Inventory Items'
        indexes = [
            models.Index(fields=['type']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.type}) - Stock: {self.quantity}"


class RewardHistory(models.Model):
    """Track rewards given to users"""
    history_id = models.AutoField(primary_key=True)
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='rewards_received')
    reward_name = models.CharField(max_length=255)
    reward_type = models.CharField(max_length=100)
    reward_value = models.CharField(max_length=100)
    points_deducted = models.IntegerField(default=0)
    given_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, related_name='rewards_given')
    given_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'shared_rewardhistory'
        verbose_name = 'Reward History'
        verbose_name_plural = 'Reward Histories'
        ordering = ['-given_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['-given_at']),
        ]
    
    def __str__(self):
        return f"{self.reward_name} given to {self.user.full_name} on {self.given_at.strftime('%Y-%m-%d')}"


class RewardRequest(models.Model):
    """Track user reward redemption requests"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('ready_for_pickup', 'Ready for Pickup'),
        ('claimed', 'Claimed'),
        ('expired', 'Expired'),
        ('rejected', 'Rejected'),
    ]
    
    request_id = models.AutoField(primary_key=True)
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='reward_requests')
    reward_item = models.ForeignKey('RewardInventoryItem', on_delete=models.CASCADE, related_name='requests')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    points_cost = models.IntegerField(default=0)
    voucher_code = models.CharField(max_length=255, null=True, blank=True)  # For voucher rewards
    voucher_file = models.FileField(upload_to='vouchers/', null=True, blank=True)  # For uploaded voucher files
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_rewards')
    expires_at = models.DateTimeField(null=True, blank=True)  # For voucher rewards (5 days from approval)
    notes = models.TextField(null=True, blank=True)
    
    class Meta:
        db_table = 'shared_rewardrequest'
        verbose_name = 'Reward Request'
        verbose_name_plural = 'Reward Requests'
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['status']),
            models.Index(fields=['-requested_at']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"{self.reward_item.name} request by {self.user.full_name} - {self.status}"


class ReportSettings(models.Model):
    """Settings for customizing report headers and footers"""
    
    HEADER_LAYOUT_CHOICES = [
        ('three_column', 'Three Column (Logo, Text, Logo)'),
        ('two_column', 'Two Column (Logo, Text)'),
        ('single_column', 'Single Column (Text only)'),
    ]
    
    settings_id = models.AutoField(primary_key=True)
    
    # Header settings
    header_enabled = models.BooleanField(default=True, help_text='Enable/disable header')
    header_layout_type = models.CharField(
        max_length=20, 
        choices=HEADER_LAYOUT_CHOICES, 
        default='three_column',
        help_text='Header layout type'
    )
    left_logo_enabled = models.BooleanField(default=True, help_text='Show left logo')
    left_logo = models.ImageField(upload_to='report_logos/', null=True, blank=True)
    right_logo_enabled = models.BooleanField(default=True, help_text='Show right logo')
    right_logo = models.ImageField(upload_to='report_logos/', null=True, blank=True)
    
    header_line1 = models.CharField(max_length=255, default='Republic of the Philippines', help_text='Header line 1')
    header_line2 = models.CharField(max_length=255, default='CEBU TECHNOLOGICAL UNIVERSITY', help_text='Header line 2')
    header_line2_color = models.CharField(max_length=7, default='#DC143C', help_text='Header line 2 color (hex)')
    header_line2_bold = models.BooleanField(default=True)
    header_line3 = models.CharField(max_length=255, default='M. J. Cuenco Avenue Cor. R. Palma Street, Cebu City, Philippines', help_text='Header line 3')
    header_line4 = models.CharField(max_length=255, default='Website: http://www.ctu.edu.ph', help_text='Header line 4')
    header_line5 = models.CharField(max_length=255, default='Phone: +6332 402 4060 loc. 1146', help_text='Header line 5')
    header_line6 = models.CharField(max_length=255, default='UNIVERSITY ALUMNI AFFAIRS OFFICE', help_text='Header line 6')
    header_line6_color = models.CharField(max_length=7, default='#DC143C', help_text='Header line 6 color (hex)')
    header_line6_bold = models.BooleanField(default=True)
    
    # Footer settings
    footer_enabled = models.BooleanField(default=True, help_text='Enable/disable footer')
    footer_image_enabled = models.BooleanField(default=True, help_text='Show footer image')
    footer_image = models.ImageField(upload_to='report_logos/', null=True, blank=True)
    footer_text1 = models.CharField(max_length=255, default='Generated by Cebu Technological University Alumni Affairs Office', help_text='Footer text 1')
    footer_text2 = models.CharField(max_length=255, default='This report is generated automatically by the Alumni Tracking System', help_text='Footer text 2')
    
    # Signature settings
    signature_enabled = models.BooleanField(default=True, help_text='Enable/disable signature section')
    prepared_by_name = models.CharField(max_length=255, default='MARIE JOY B. ALIT, Ph.D.', help_text='Prepared by name')
    prepared_by_title = models.CharField(max_length=255, default='University Director for Alumni Affairs', help_text='Prepared by title')
    approved_by_name = models.CharField(max_length=255, default='ROMEO P. MONTECILLO, Ph.D.', help_text='Approved by name')
    approved_by_title = models.CharField(max_length=255, default='Vice President for Student Affairs', help_text='Approved by title')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, related_name='report_settings_created')
    updated_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, related_name='report_settings_updated')
    custom_settings = models.JSONField(default=dict, blank=True, help_text='Additional custom settings')
    
    class Meta:
        db_table = 'shared_reportsettings'
        verbose_name = 'Header/Footer Settings'
        verbose_name_plural = 'Header/Footer Settings'
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"Header/Footer Settings (Updated: {self.updated_at.strftime('%Y-%m-%d %H:%M:%S')})"
    
    @classmethod
    def get_active_settings(cls):
        """Return the most recently updated settings"""
        return cls.objects.order_by('-updated_at').first()


class PointsTask(models.Model):
    """Tasks that users can complete to earn points."""
    task_id = models.AutoField(primary_key=True)
    task_type = models.CharField(
        max_length=50,
        unique=True,
        help_text='Unique identifier for the task (e.g., verify_email, milestone_post_10)',
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    points = models.IntegerField(help_text='Points awarded for completing this task')
    max_points = models.IntegerField(null=True, blank=True, help_text='Maximum points (for variable point tasks like "up to X points")')
    icon_name = models.CharField(max_length=100, default='envelope', help_text='Icon identifier for frontend')
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0, help_text='Display order')
    required_count = models.IntegerField(null=True, blank=True, help_text='Number of actions required to complete this task')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'shared_pointstask'
        verbose_name = 'Points Task'
        verbose_name_plural = 'Points Tasks'
        ordering = ['order', 'task_id']
    
    def __str__(self):
        return f"{self.title} ({self.points} points)"


class UserTaskCompletion(models.Model):
    """Track which tasks users have completed"""
    completion_id = models.AutoField(primary_key=True)
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='task_completions')
    task = models.ForeignKey('PointsTask', on_delete=models.CASCADE, related_name='completions')
    points_awarded = models.IntegerField()
    completed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'shared_usertaskcompletion'
        verbose_name = 'User Task Completion'
        verbose_name_plural = 'User Task Completions'
        unique_together = [['user', 'task']]
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['task']),
            models.Index(fields=['-completed_at']),
        ]
    
    def __str__(self):
        return f"{self.user.full_name} completed {self.task.title} ({self.points_awarded} points)"
