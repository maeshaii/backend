"""
Shared models for user, profile, academic info, employment, tracker, OJT, and related entities.
These models are used across multiple apps for reusability and consistency.
"""
from django.db import models
from datetime import datetime
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
from django.conf import settings
from typing import Optional
from cryptography.fernet import Fernet
import base64, hashlib


class AccountType(models.Model):
    """Account type flags for user roles (admin, peso, user, coordinator, ojt).

    Used by Mobile: role-gating for posts feed visibility and permissions.
    """
    account_type_id = models.AutoField(primary_key=True)
    admin = models.BooleanField()
    peso = models.BooleanField()
    user = models.BooleanField()
    coordinator = models.BooleanField()
    ojt = models.BooleanField(default=False)  # Added for OJT account type with default



# REMOVED: Legacy statistics models (deleted in migration 0091)
# These models had circular dependencies and were never populated or used
# - Aacup
# - Ched  
# Statistics now calculated directly from User -> EmploymentHistory -> TrackerData

class Comment(models.Model):
    """User comments on posts, forums, and donations.
    Used by Mobile: GET/POST/PUT/DELETE via /api/posts/{post_id}/comments/, /api/forum/{forum_id}/comments/, and /api/donations/{donation_id}/comments/
    """
    comment_id = models.AutoField(primary_key=True)
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='comments')
    post = models.ForeignKey('Post', on_delete=models.CASCADE, related_name='post_comments', null=True, blank=True)
    forum = models.ForeignKey('Forum', on_delete=models.CASCADE, related_name='forum_comments', null=True, blank=True)
    repost = models.ForeignKey('Repost', on_delete=models.CASCADE, related_name='comments', null=True, blank=True)
    donation_request = models.ForeignKey('DonationRequest', on_delete=models.CASCADE, related_name='donation_comments', null=True, blank=True)
    comment_content = models.TextField(null=True, blank=True)
    date_created = models.DateTimeField()
    
    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(models.Q(post__isnull=False, forum__isnull=True, repost__isnull=True, donation_request__isnull=True) | 
                      models.Q(post__isnull=True, forum__isnull=False, repost__isnull=True, donation_request__isnull=True) |
                      models.Q(post__isnull=True, forum__isnull=True, repost__isnull=False, donation_request__isnull=True) |
                      models.Q(post__isnull=True, forum__isnull=True, repost__isnull=True, donation_request__isnull=False)),
                name='comment_one_content_type_only'
            )
        ]

class Reply(models.Model):
    """User replies to comments on posts, forums, donations, and reposts"""
    reply_id = models.AutoField(primary_key=True)
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='replies')
    comment = models.ForeignKey('Comment', on_delete=models.CASCADE, related_name='replies')
    reply_content = models.TextField()
    date_created = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['date_created']
        db_table = 'shared_reply'
        indexes = [
            models.Index(fields=['comment', 'date_created']),
            models.Index(fields=['user', 'date_created']),
        ]
    
    def __str__(self):
        return f"Reply by {self.user.full_name} to comment {self.comment.comment_id}"

class ContentImage(models.Model):
    """Unified image model for posts, forums, and donations"""
    CONTENT_TYPE_CHOICES = [
        ('post', 'Post'),
        ('forum', 'Forum'),
        ('donation', 'Donation'),
    ]
    
    image_id = models.AutoField(primary_key=True)
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPE_CHOICES)
    content_id = models.PositiveIntegerField()  # ID of the post, forum, or donation
    image = models.ImageField(upload_to='content_images/')
    order = models.PositiveIntegerField(default=0)  # For ordering multiple images
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['order', 'created_at']
        db_table = 'shared_contentimage'
        indexes = [
            models.Index(fields=['content_type', 'content_id']),
            models.Index(fields=['content_type', 'content_id', 'order']),
        ]
        unique_together = [['content_type', 'content_id', 'order']]
    
    def __str__(self):
        return f"Image {self.image_id} for {self.content_type} {self.content_id}"

# REMOVED: Old job models with circular FK relationships (deleted in migration 0091)
# Replaced by SimpleCompTechJob, SimpleInfoTechJob, SimpleInfoSystemJob
# - CompTechJob
# - InfoTechJob  
# - InfoSystemJob

# REMOVED: Unused helper models (deleted in migration 0091)
# - ExportedFile (file tracking never implemented)
# - Feed (post feed uses direct Post queries)
# - Import (replaced by OJTImport)

class Forum(models.Model):
    """Forum posts stored separately from shared_post (identical structure).

    Used by Mobile: CRUD/like/comment/repost via /api/forum/... endpoints.
    Images are handled by ContentImage model.
    """
    forum_id = models.AutoField(primary_key=True)
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='forums')
    content = models.TextField(null=True, blank=True)
    type = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_column='date_send')
    
    @property
    def images(self):
        """Get all images for this forum post"""
        return ContentImage.objects.filter(content_type='forum', content_id=self.forum_id)
    
    def add_image(self, image_file, order=0):
        """Add an image to this forum post"""
        return ContentImage.objects.create(
            content_type='forum',
            content_id=self.forum_id,
            image=image_file,
            order=order
        )

# REMOVED: Legacy models deleted in migration 0091
# - HighPosition (functionality moved to EmploymentHistory.high_position boolean)
# - Import (replaced by OJTImport)
# - InfoTechJob (old version with circular FKs)
# - InfoSystemJob (old version with circular FKs)
# See SimpleInfoTechJob, SimpleInfoSystemJob for current implementation

# NEW: Simple job models for job alignment (no complex relationships)
class SimpleCompTechJob(models.Model):
    id = models.AutoField(primary_key=True)
    job_title = models.CharField(max_length=255, unique=True)
    
    def __str__(self):
        return self.job_title

class SimpleInfoTechJob(models.Model):
    id = models.AutoField(primary_key=True)
    job_title = models.CharField(max_length=255, unique=True)
    
    def __str__(self):
        return self.job_title

class SimpleInfoSystemJob(models.Model):
    id = models.AutoField(primary_key=True)
    job_title = models.CharField(max_length=255, unique=True)
    
    def __str__(self):
        return self.job_title

class Like(models.Model):
    like_id = models.AutoField(primary_key=True)
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='likes')
    post = models.ForeignKey('Post', on_delete=models.CASCADE, related_name='post_likes', null=True, blank=True)
    forum = models.ForeignKey('Forum', on_delete=models.CASCADE, related_name='forum_likes', null=True, blank=True)
    repost = models.ForeignKey('Repost', on_delete=models.CASCADE, related_name='likes', null=True, blank=True)
    donation_request = models.ForeignKey('DonationRequest', on_delete=models.CASCADE, related_name='donation_likes', null=True, blank=True)
    # Used by Mobile: toggled at /api/posts/{post_id}/like/, /api/forum/{forum_id}/like/, and /api/donations/{donation_id}/like/
    
    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(models.Q(post__isnull=False, forum__isnull=True, repost__isnull=True, donation_request__isnull=True) | 
                      models.Q(post__isnull=True, forum__isnull=False, repost__isnull=True, donation_request__isnull=True) |
                      models.Q(post__isnull=True, forum__isnull=True, repost__isnull=False, donation_request__isnull=True) |
                      models.Q(post__isnull=True, forum__isnull=True, repost__isnull=True, donation_request__isnull=False)),
                name='like_one_content_type_only'
            )
        ]

class Conversation(models.Model):
    conversation_id = models.AutoField(primary_key=True)
    participants = models.ManyToManyField('User', related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_message_request = models.BooleanField(default=False, help_text="True if this is a message request from non-mutual follow")
    # Track who initiated a message request so that only the recipient's reply can auto-accept
    request_initiator = models.ForeignKey(
        'User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='initiated_message_requests', help_text='User who initiated the message request'
    )
    
    class Meta:
        ordering = ['-updated_at']
        db_table = 'shared_conversation'
        
    def get_other_participant(self, current_user):
        """Get the other participant in a 1-on-1 conversation"""
        return self.participants.exclude(user_id=current_user.user_id).first()
    
    def get_last_message(self):
        """Get the last message in the conversation"""
        return self.messages.last()
    
    def get_unread_count(self, user):
        """Get unread message count for a specific user"""
        return self.messages.filter(is_read=False).exclude(sender=user).count()
    
    def __str__(self):
        participant_names = [f"{p.f_name} {p.l_name}" for p in self.participants.all()]
        return f"Conversation: {', '.join(participant_names)}"

class Message(models.Model):
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('file', 'File'),
        ('system', 'System'),
    ]

    message_id = models.AutoField(primary_key=True)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE,
        related_name='messages', null=True, blank=True
    )
    sender = models.ForeignKey('User', on_delete=models.CASCADE, related_name='sent_messages')
    # Some existing databases have a non-null receiver_id column. Reflect it here and populate on create.
    receiver = models.ForeignKey('User', on_delete=models.CASCADE, related_name='received_messages', null=True, blank=True)
    content = models.TextField(db_column='message_content', default="", blank=True)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        db_table = 'shared_message'
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['sender', 'created_at']),
            models.Index(fields=['is_read']),
        ]

    def __str__(self):
        return f"{self.sender.full_name}: {self.content[:50]}"

    @property
    def sender_name(self):
        return self.sender.full_name


class MessageAttachment(models.Model):
    STORAGE_CHOICES = [
        ('local', 'Local Storage'),
        ('s3', 'AWS S3'),
        ('gcs', 'Google Cloud Storage'),
    ]
    
    attachment_id = models.AutoField(primary_key=True)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='attachments', null=True, blank=True)
    file = models.FileField(upload_to='message_attachments/%Y/%m/%d/', blank=True, null=True, help_text='Local file storage (deprecated, use file_key instead)')
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=255)
    file_size = models.IntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    # Cloud storage fields
    file_key = models.CharField(max_length=500, blank=True, null=True, help_text='S3 object key or local file path')
    file_url = models.URLField(blank=True, null=True, help_text='Public URL for the file')
    storage_type = models.CharField(
        max_length=20, 
        default='local',
        choices=STORAGE_CHOICES,
        help_text='Storage backend used for this file'
    )
    
    class Meta:
        db_table = 'shared_messageattachment'
        indexes = [
            models.Index(fields=['message', 'uploaded_at']),
        ]
    
    def __str__(self):
        return f"{self.file_name} ({self.file_type})"
    
    @property
    def file_size_mb(self):
        """Return file size in MB"""
        return round(self.file_size / (1024 * 1024), 2)
    
    @property
    def get_file_url(self):
        """Get file URL with fallback to local storage"""
        if self.file_url:
            return self.file_url
        elif self.file:
            return self.file.url
        else:
            return None
    
    def delete_file_from_storage(self):
        """Delete file from storage backend"""
        from apps.messaging.cloud_storage import cloud_storage
        
        if self.storage_type == 's3' and self.file_key:
            return cloud_storage.delete_file(self.file_key)
        elif self.file:
            try:
                return self.file.delete(save=False)
            except Exception:
                return False
        return False

class Notification(models.Model):
    notification_id = models.AutoField(primary_key=True)
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='notifications')
    notif_type = models.CharField(max_length=100)
    subject = models.CharField(max_length=255, blank=True, null=True)  # Added subject field
    notifi_content = models.TextField()
    notif_date = models.DateTimeField()
    is_read = models.BooleanField(default=False)
    # Used by Mobile: listed/deleted at /api/notifications/...

    # Used by Mobile: read via /api/post-categories/

# NOTE: The legacy PostImage table 'shared_postimage' does not exist in this database.
# To prevent ORM from attempting to access/delete from a missing table during Post deletes,
# we disable the PostImage model by renaming it (no relation registered) and not managing it.
class PostImageDisabled(models.Model):
    post_image_id = models.AutoField(primary_key=True)
    image = models.ImageField(upload_to='post_images/', null=True, blank=True)

    class Meta:
        managed = False  # do not touch the database

class Post(models.Model):
    post_id = models.AutoField(primary_key=True)
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='posts')
    post_content = models.TextField()
    type = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Used by Mobile: feed list/create/edit/delete/like/comment/repost
    # Images are handled by ContentImage model
    
    @property
    def images(self):
        """Get all images for this post"""
        return ContentImage.objects.filter(content_type='post', content_id=self.post_id)
    
    def add_image(self, image_file, order=0):
        """Add an image to this post"""
        return ContentImage.objects.create(
            content_type='post',
            content_id=self.post_id,
            image=image_file,
            order=order
        )

# PostImage model removed - replaced by ContentImage

# REMOVED: Qpro model (deleted in migration 0091)

class DonationRequest(models.Model):
    """Donation requests from alumni"""
    donation_id = models.AutoField(primary_key=True)
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='donation_requests')
    description = models.TextField()
    status = models.CharField(max_length=20, choices=[
        ('active', 'Active'),
        ('fulfilled', 'Fulfilled'),
        ('closed', 'Closed')
    ], default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        db_table = 'shared_donationrequest'
    
    @property
    def images(self):
        """Get all images for this donation request"""
        return ContentImage.objects.filter(content_type='donation', content_id=self.donation_id)
    
    def add_image(self, image_file, order=0):
        """Add an image to this donation request"""
        return ContentImage.objects.create(
            content_type='donation',
            content_id=self.donation_id,
            image=image_file,
            order=order
        )
    
    def __str__(self):
        return f"Donation Request {self.donation_id} by {self.user.f_name} {self.user.l_name}"

# DonationImage model removed - replaced by ContentImage

class Repost(models.Model):
    repost_id = models.AutoField(primary_key=True)
    post = models.ForeignKey('Post', on_delete=models.CASCADE, related_name='post_reposts', null=True, blank=True)
    forum = models.ForeignKey('Forum', on_delete=models.CASCADE, related_name='forum_reposts', null=True, blank=True)
    donation_request = models.ForeignKey('DonationRequest', on_delete=models.CASCADE, related_name='donation_reposts', null=True, blank=True)
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='reposts')
    repost_date = models.DateTimeField()
    caption = models.TextField(null=True, blank=True)
    # Used by Mobile: /api/posts/{post_id}/repost/, /api/forum/{forum_id}/repost/, /api/donations/{donation_id}/repost/ and /api/reposts/{repost_id}/
    
    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(models.Q(post__isnull=False, forum__isnull=True, donation_request__isnull=True) | 
                      models.Q(post__isnull=True, forum__isnull=False, donation_request__isnull=True) |
                      models.Q(post__isnull=True, forum__isnull=True, donation_request__isnull=False)),
                name='repost_one_content_type_only'
            )
        ]


class RecentSearch(models.Model):
    """Per-user recent search entries for user discovery.
    One row per searched user, deduped by (owner, searched_user).
    """
    id = models.AutoField(primary_key=True)
    owner = models.ForeignKey('User', on_delete=models.CASCADE, related_name='recent_searches')
    searched_user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='appears_in_recent_searches')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('owner', 'searched_user')
        ordering = ['-created_at']

# REMOVED: Standard and Suc models (deleted in migration 0091)
# These were part of an overly complex statistics hierarchy that was never implemented

class TrackerForm(models.Model):
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255, default="CTU Alumni Tracker Form")
    description = models.TextField(blank=True)
    accepting_responses = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        # Ensure only one tracker form exists
        constraints = [
            models.CheckConstraint(
                check=models.Q(id=1),
                name='single_tracker_form'
            )
        ]

class User(models.Model):
    """Core User model - Authentication and basic identity only.

    Used by Mobile: auth via /api/token/, profile display, follow relationships.
    """
    user_id = models.AutoField(primary_key=True)
    # REMOVED: import_id FK to deleted Import model (replaced by OJTImport for OJT users)
    # import_id = models.ForeignKey('Import', on_delete=models.CASCADE, related_name='users', null=True, blank=True)
    account_type = models.ForeignKey('AccountType', on_delete=models.CASCADE, related_name='users')
    acc_username = models.CharField(max_length=100, unique=True)
    acc_password = models.CharField(max_length=128, null=True, blank=True)
    user_status = models.CharField(max_length=50)
    
    # Basic identity fields
    f_name = models.CharField(max_length=100)
    m_name = models.CharField(max_length=100, null=True, blank=True)
    l_name = models.CharField(max_length=100)
    gender = models.CharField(max_length=10)
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    USERNAME_FIELD = 'acc_username'
    REQUIRED_FIELDS = []
    
    class Meta:
        indexes = [
            models.Index(fields=['user_status']),
            models.Index(fields=['acc_username']),
            models.Index(fields=['f_name', 'l_name']),
        ]

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
    """Tracks engagement points for users (alumni and OJT students).
    
    Points are awarded for:
    - Like a post: +1 pt
    - Comment on a post: +3 pts
    - Share a post (repost): +5 pts
    - Reply to a comment: +2 pts
    - Post with photo: +15 pts
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='points')
    total_points = models.IntegerField(default=0)
    
    # Breakdown by action type
    points_from_likes = models.IntegerField(default=0)
    points_from_comments = models.IntegerField(default=0)
    points_from_shares = models.IntegerField(default=0)
    points_from_replies = models.IntegerField(default=0)
    points_from_posts_with_photos = models.IntegerField(default=0)
    points_from_tracker_form = models.IntegerField(default=0)
    
    # Track counts for analytics
    like_count = models.IntegerField(default=0)
    comment_count = models.IntegerField(default=0)
    share_count = models.IntegerField(default=0)
    reply_count = models.IntegerField(default=0)
    post_with_photo_count = models.IntegerField(default=0)
    tracker_form_count = models.IntegerField(default=0)
    
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
    
    def add_points(self, action_type: str, points: int = 0) -> None:
        """Add points for a specific action type"""
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
        elif action_type == 'post_with_photo':
            self.points_from_posts_with_photos += points
            self.post_with_photo_count += 1
        elif action_type == 'tracker_form':
            self.points_from_tracker_form += points
            self.tracker_form_count += 1
        
        # Update total points
        self.total_points = (
            self.points_from_likes +
            self.points_from_comments +
            self.points_from_shares +
            self.points_from_replies +
            self.points_from_posts_with_photos +
            self.points_from_tracker_form
        )
        self.save()


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
    
    def _check_job_alignment_for_position(self, position, program):
        """Check job alignment for a specific position without saving to database
        Used during form completion for real-time alignment checking
        """
        if not position:
            self.job_alignment_status = 'not_aligned'
            self.job_alignment_category = None
            self.job_alignment_title = None
            return
        
        position_lower = position.lower().strip()
        program_lower = (program or '').lower()
        
        # Check alignment against job tables
        alignment_found = False
        
        # Check SimpleInfoTechJob (BSIT)
        if 'bsit' in program_lower or 'information technology' in program_lower:
            if SimpleInfoTechJob.objects.filter(job_title__iexact=position).exists():
                self.job_alignment_status = 'aligned'
                self.job_alignment_category = 'BSIT'
                self.job_alignment_title = position
                alignment_found = True
        
        # Check SimpleInfoSystemJob (BSIS)
        if not alignment_found and ('bsis' in program_lower or 'information system' in program_lower):
            if SimpleInfoSystemJob.objects.filter(job_title__iexact=position).exists():
                self.job_alignment_status = 'aligned'
                self.job_alignment_category = 'BSIS'
                self.job_alignment_title = position
                alignment_found = True
        
        # Check SimpleCompTechJob (BIT-CT)
        if not alignment_found and ('bit-ct' in program_lower or 'computer technology' in program_lower):
            if SimpleCompTechJob.objects.filter(job_title__iexact=position).exists():
                self.job_alignment_status = 'aligned'
                self.job_alignment_category = 'BIT-CT'
                self.job_alignment_title = position
                alignment_found = True
        
        # Check cross-program alignment
        if not alignment_found:
            cross_program_match = self._find_cross_program_match(position_lower, program_lower)
            if cross_program_match:
                self.job_alignment_status = 'pending_user_confirmation'
                self.job_alignment_category = cross_program_match['category']
                self.job_alignment_title = cross_program_match['title']
                self.job_alignment_suggested_program = cross_program_match['program']
                self.job_alignment_original_program = program
                alignment_found = True
        
        # If no alignment found, mark as pending confirmation
        if not alignment_found:
            self.job_alignment_status = 'pending_user_confirmation'
            self.job_alignment_category = None
            self.job_alignment_title = position
            self.job_alignment_original_program = program
        
        return self.job_alignment_status


    def update_job_alignment(self):
        """Update job alignment fields based on position_current and program
        This connects tracker answers to statistics types (CHED, SUC, AACUP)
        """
        if not self.position_current:
            self.job_alignment_status = 'not_aligned'
            self.job_alignment_category = None
            self.job_alignment_title = None
            return
        
        position_lower = self.position_current.lower().strip()
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
            job_title = cross_program_match['title']
            
            # Add to appropriate table
            if 'bit-ct' in user_program or 'computer technology' in user_program:
                # Check if already exists
                if not SimpleCompTechJob.objects.filter(job_title__iexact=job_title).exists():
                    SimpleCompTechJob.objects.create(job_title=job_title)
                    logger.info(f"Added '{job_title}' to BIT-CT job table")
            
            elif 'bsit' in user_program or 'information technology' in user_program:
                # Check if already exists
                if not SimpleInfoTechJob.objects.filter(job_title__iexact=job_title).exists():
                    SimpleInfoTechJob.objects.create(job_title=job_title)
                    logger.info(f"Added '{job_title}' to BSIT job table")
            
            elif 'bsis' in user_program or 'information system' in user_program:
                # Check if already exists
                if not SimpleInfoSystemJob.objects.filter(job_title__iexact=job_title).exists():
                    SimpleInfoSystemJob.objects.create(job_title=job_title)
                    logger.info(f"Added '{job_title}' to BSIS job table")
            
        except Exception as e:
            logger.error(f"Failed to add job to user program table: {e}")
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
                if not SimpleCompTechJob.objects.filter(job_title__iexact=job_title).exists():
                    SimpleCompTechJob.objects.create(job_title=job_title)
                    logger.info(f"Added new job '{job_title}' to BIT-CT job table")
            
            elif 'bsit' in user_program.lower() or 'information technology' in user_program.lower():
                # Check if already exists
                if not SimpleInfoTechJob.objects.filter(job_title__iexact=job_title).exists():
                    SimpleInfoTechJob.objects.create(job_title=job_title)
                    logger.info(f"Added new job '{job_title}' to BSIT job table")
            
            elif 'bsis' in user_program.lower() or 'information system' in user_program.lower():
                # Check if already exists
                if not SimpleInfoSystemJob.objects.filter(job_title__iexact=job_title).exists():
                    SimpleInfoSystemJob.objects.create(job_title=job_title)
                    logger.info(f"Added new job '{job_title}' to BSIS job table")
            
        except Exception as e:
            logger.error(f"Failed to add new job to program table: {e}")
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


class OJTCompanyProfile(models.Model):
    """OJT Company Profile - Stores company information for OJT students"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='ojt_company_profile')
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
        ]
    
    def __str__(self):
        return f"OJT Company Profile for {self.user.full_name} - {self.company_name}"


class QuestionCategory(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)  # Added for ordering

class Question(models.Model):
    category = models.ForeignKey(QuestionCategory, related_name='questions', on_delete=models.CASCADE)
    text = models.CharField(max_length=255)
    type = models.CharField(max_length=50)
    options = models.JSONField(blank=True, null=True)  # For radio/multiple/checkbox
    required = models.BooleanField(default=False)  # Added required field
    order = models.PositiveIntegerField(default=0)  # Added for ordering questions within category

class TrackerResponse(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    answers = models.JSONField()  # {question_id: answer} - for temporary storage during form submission
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        # Ensure only one response per user
        unique_together = ['user']
    
    def save(self, *args, **kwargs):
        # When saving, also update the User model fields
        super().save(*args, **kwargs)
        self.update_user_fields()
    
    def update_user_fields(self):
        """Update domain models from tracker JSON answers (no legacy User field writes)"""
        if not self.answers:
            return

        user = self.user
        answers = self.answers

        # Ensure related model instances exist
        profile, _ = UserProfile.objects.get_or_create(user=user)
        academic, _ = AcademicInfo.objects.get_or_create(user=user)
        employment, _ = EmploymentHistory.objects.get_or_create(user=user)
        tracker, _ = TrackerData.objects.get_or_create(user=user)

        def parse_date_value(value):
            if not value:
                return None
            try:
                if '/' in str(value):
                    return datetime.strptime(str(value), '%m/%d/%Y').date()
                return datetime.strptime(str(value), '%Y-%m-%d').date()
            except (ValueError, TypeError):
                return None

        # Map numeric question IDs to target fields in domain models
        for question_id_str, answer in answers.items():
            try:
                if not str(question_id_str).isdigit():
                    continue
                question_id = int(question_id_str)

                # Skip file answers (file uploads are handled elsewhere)
                if isinstance(answer, dict) and answer.get('type') == 'file':
                    continue

                # Part 1: Personal Information
                if question_id == 1:  # Year Graduated
                    academic.year_graduated = int(answer) if str(answer).isdigit() else academic.year_graduated
                elif question_id == 2:  # Program Graduated
                    academic.program = str(answer) if answer else academic.program
                elif question_id == 3:  # Email
                    profile.email = str(answer) if answer else profile.email
                elif question_id == 4:  # Last Name
                    user.l_name = str(answer) if answer else user.l_name
                elif question_id == 5:  # First Name
                    user.f_name = str(answer) if answer else user.f_name
                elif question_id == 6:  # Middle Name
                    user.m_name = str(answer) if answer else user.m_name
                elif question_id == 7:  # Age
                    try:
                        profile.age = int(answer)
                    except (ValueError, TypeError):
                        pass
                elif question_id == 8:  # Birthdate
                    bd = parse_date_value(answer)
                    if bd:
                        profile.birthdate = bd
                elif question_id == 9:  # Phone Number
                    profile.phone_num = str(answer) if answer else profile.phone_num
                elif question_id == 10:  # Social Media
                    profile.social_media = str(answer) if answer else profile.social_media
                elif question_id == 11:  # Address
                    profile.address = str(answer) if answer else profile.address
                elif question_id == 12:  # Home Address
                    profile.home_address = str(answer) if answer else profile.home_address
                elif question_id == 13:  # Civil Status
                    profile.civil_status = str(answer) if answer else profile.civil_status

                # Part 2: First Employment
                elif question_id == 14:  # First employer name
                    employment.company_name_current = str(answer) if answer else employment.company_name_current
                elif question_id == 15:  # Date hired (first employer)
                    ds = parse_date_value(answer)
                    if ds:
                        employment.date_started = ds
                elif question_id == 16:  # Position (first employer)
                    employment.position_current = str(answer) if answer else employment.position_current
                elif question_id == 17:  # Employment status (perm/contract)
                    tracker.q_employment_permanent = str(answer) if answer else tracker.q_employment_permanent
                elif question_id == 18:  # Company Address (first employer)
                    employment.company_address = str(answer) if answer else employment.company_address
                elif question_id == 19:  # Sector (first employer)
                    employment.sector_current = str(answer) if answer else employment.sector_current
                elif question_id == 20:  # First Employment Supporting Document (string ref)
                    employment.supporting_document_current = str(answer) if answer else employment.supporting_document_current

                # Part 3: Current Employment
                elif question_id == 21:
                    tracker.q_employment_status = str(answer) if answer else tracker.q_employment_status
                elif question_id == 22:
                    academic.q_pursue_study = str(answer) if answer else academic.q_pursue_study
                    # Keep normalized boolean yes/no in pursue_further_study
                    if answer is not None:
                        val = str(answer).strip().lower()
                        academic.pursue_further_study = 'yes' if val in ('yes', 'y', 'true', '1') else 'no' if val in ('no', 'n', 'false', '0') else academic.pursue_further_study
                elif question_id == 23:
                    tracker.q_employment_type = str(answer) if answer else tracker.q_employment_type
                elif question_id == 24:
                    tracker.q_employment_permanent = str(answer) if answer else tracker.q_employment_permanent
                elif question_id == 25:
                    tracker.q_company_name = str(answer) if answer else tracker.q_company_name
                    if answer:
                        employment.company_name_current = str(answer)
                elif question_id == 26:
                    tracker.q_current_position = str(answer) if answer else tracker.q_current_position
                    if answer:
                        employment.position_current = str(answer)
                elif question_id == 27:  # Current Sector of your Job (Public/Private)
                    tracker.q_sector_current = str(answer) if answer else tracker.q_sector_current
                    if answer:
                        employment.sector_current = str(answer)
                elif question_id == 39:  # Employment Sector (Local/International)
                    tracker.q_scope_current = str(answer) if answer else tracker.q_scope_current
                elif question_id == 29:  # How long have you been employed?
                    tracker.q_employment_duration = str(answer) if answer else tracker.q_employment_duration
                    if answer:
                        employment.employment_duration_current = str(answer)
                elif question_id == 30:  # Current Salary range (was 29)
                    tracker.q_salary_range = str(answer) if answer else tracker.q_salary_range
                    if answer:
                        employment.salary_current = str(answer)
                elif question_id == 31:  # Have you received any awards... (was 30)
                    tracker.q_awards_received = str(answer) if answer else tracker.q_awards_received

                # 32 and 33 are file uploads; skipped above

                # Part 4: Unemployment & Further Study
                elif question_id == 34:  # Reason for unemployment (was 33)
                    if isinstance(answer, list):
                        tracker.q_unemployment_reason = answer
                    else:
                        tracker.q_unemployment_reason = [answer] if answer else []
                elif question_id == 35:  # Date Started (was 34)
                    sd = parse_date_value(answer)
                    if sd:
                        academic.q_study_start_date = sd
                elif question_id == 36:  # Post graduate degree (was 35)
                    academic.q_post_graduate_degree = str(answer) if answer else academic.q_post_graduate_degree
                elif question_id == 37:  # Institution name (was 36)
                    academic.q_institution_name = str(answer) if answer else academic.q_institution_name
                elif question_id == 38:  # Units obtained (was 37)
                    academic.q_units_obtained = str(answer) if answer else academic.q_units_obtained

            except Exception:
                continue

        # Save all models
        user.save()
        profile.save()
        academic.save()
        # Update job alignment and related derived employment fields
        employment.update_job_alignment()
        employment.save()
        tracker.tracker_submitted_at = self.submitted_at
        tracker.save()
        
        # PHASE 3: Invalidate statistics cache after tracker submission
        self._invalidate_statistics_cache()

    def _invalidate_statistics_cache(self):
        """PHASE 3: Invalidate statistics cache when tracker data changes"""
        try:
            from django.core.cache import cache
            
            # Clear all statistics-related cache keys
            cache_patterns = [
                'stats:*',  # All statistics cache
                f'stats:user:{self.user.user_id}:*',  # User-specific stats
                f'stats:program:{self.user.academic_info.program}:*',  # Program-specific stats
            ]
            
            for pattern in cache_patterns:
                # Note: Django's cache doesn't support wildcard deletion by default
                # In production, consider using Redis with pattern-based deletion
                # For now, we'll clear common cache keys
                common_keys = [
                    'stats:ALL:ALL:ALL',
                    f'stats:ALL:{self.user.academic_info.program}:ALL',
                    f'stats:ALL:ALL:QPRO',
                    f'stats:ALL:ALL:CHED',
                    f'stats:ALL:ALL:SUC',
                    f'stats:ALL:ALL:AACUP',
                ]
                
                for key in common_keys:
                    cache.delete(key)
            
            # Log cache invalidation
            import logging
            logger = logging.getLogger('apps.shared.models')
            logger.info(f"Statistics cache invalidated for user {self.user.user_id} after tracker submission")
            
        except Exception as e:
            # Don't let cache invalidation errors break the main flow
            import logging
            logger = logging.getLogger('apps.shared.models')
            logger.warning(f"Failed to invalidate statistics cache: {e}")

# OJT-specific models
class Follow(models.Model):
    follow_id = models.AutoField(primary_key=True)
    follower = models.ForeignKey('User', on_delete=models.CASCADE, related_name='following')
    following = models.ForeignKey('User', on_delete=models.CASCADE, related_name='followers')
    followed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('follower', 'following')
        db_table = 'shared_follow'

class OJTImport(models.Model):
    import_id = models.AutoField(primary_key=True)
    coordinator = models.CharField(max_length=100)  # Coordinator who imported
    batch_year = models.IntegerField()
    course = models.CharField(max_length=100)
    section = models.CharField(max_length=50, blank=True, null=True)  # Section like 4-1, 4-A (optional)
    import_date = models.DateTimeField(auto_now_add=True)
    file_name = models.CharField(max_length=255)
    records_imported = models.IntegerField(default=0)
    status = models.CharField(max_length=50, default='Completed')  # Completed, Failed, Partial

class SendDate(models.Model):
    """Model to store scheduled send dates for OJT students"""
    coordinator = models.CharField(max_length=100)  # Coordinator who set the date
    batch_year = models.IntegerField()
    section = models.CharField(max_length=50, blank=True, null=True)
    send_date = models.DateField()  # The scheduled date
    is_processed = models.BooleanField(default=False)  # Whether it has been processed
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['coordinator', 'batch_year', 'section']
    
    def __str__(self):
        return f"{self.coordinator} - {self.batch_year} {self.section or 'All'} - {self.send_date}"

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