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



class Aacup(models.Model):
    """AACUP statistics and relationships."""
    aacup_id = models.AutoField(primary_key=True)
    standard = models.ForeignKey('Standard', on_delete=models.CASCADE, related_name='aacups')

class Ched(models.Model):
    """CHED statistics and job alignment count."""
    ched_id = models.AutoField(primary_key=True)
    standard = models.ForeignKey('Standard', on_delete=models.CASCADE, related_name='cheds')
    job_alignment_count = models.IntegerField(default=0)

class Comment(models.Model):
    """User comments on posts.

    Used by Mobile: GET/POST/PUT/DELETE via /api/posts/{post_id}/comments/...
    """
    comment_id = models.AutoField(primary_key=True)
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='comments')
    post = models.ForeignKey('Post', on_delete=models.CASCADE, related_name='comments')
    comment_content = models.TextField(null=True, blank=True)
    date_created = models.DateTimeField()

class CompTechJob(models.Model):
    """Computer Technology job titles and relationships."""
    comp_tech_jobs_id = models.AutoField(primary_key=True)
    suc = models.ForeignKey('Suc', on_delete=models.CASCADE, related_name='comptechjob_sucs', null=True, blank=True)
    info_system_jobs = models.ForeignKey('InfoSystemJob', on_delete=models.CASCADE, related_name='comptechjob_infosystemjobs', null=True, blank=True)
    info_tech_jobs = models.ForeignKey('InfoTechJob', on_delete=models.CASCADE, related_name='comptechjob_infotechjobs', null=True, blank=True)
    job_title = models.CharField(max_length=255)

class ExportedFile(models.Model):
    """Exported files for standards."""
    exported_file_id = models.AutoField(primary_key=True)
    standard = models.ForeignKey('Standard', on_delete=models.CASCADE, related_name='exported_files')
    file_name = models.CharField(max_length=255)
    exported_date = models.DateTimeField()

class Feed(models.Model):
    """Feed entries for user posts."""
    feed_id = models.AutoField(primary_key=True)
    post = models.ForeignKey('Post', on_delete=models.CASCADE, related_name='feeds')
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='feeds')

class Forum(models.Model):
    """Forum posts stored separately from shared_post (identical structure).

    Used by Mobile: CRUD/like/comment/repost via /api/forum/... endpoints.
    """
    forum_id = models.AutoField(primary_key=True)
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='forums')
    post_cat = models.ForeignKey('PostCategory', on_delete=models.CASCADE, related_name='forums', null=True, blank=True)
    image = models.ImageField(upload_to='forum_images/', null=True, blank=True)
    content = models.TextField(null=True, blank=True)
    type = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_column='date_send')

class HighPosition(models.Model):
    """High position statistics for AACUP and tracker forms."""
    high_position_id = models.AutoField(primary_key=True)
    aacup = models.ForeignKey('Aacup', on_delete=models.CASCADE, related_name='high_positions')
    tracker_form = models.ForeignKey('TrackerForm', on_delete=models.CASCADE, related_name='high_positions')

class Import(models.Model):
    """Import records for user data."""
    import_id = models.AutoField(primary_key=True)
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='imports')
    import_year = models.IntegerField()
    import_by = models.CharField(max_length=255)

class InfoTechJob(models.Model):
    """Information Technology job titles and relationships."""
    info_tech_jobs_id = models.AutoField(primary_key=True)
    suc = models.ForeignKey('Suc', on_delete=models.CASCADE, related_name='infotechjob_sucs', null=True, blank=True)
    info_systems_jobs = models.ForeignKey('InfoSystemJob', on_delete=models.CASCADE, related_name='infotechjob_infosystemjobs', null=True, blank=True)
    comp_tech_jobs = models.ForeignKey('CompTechJob', on_delete=models.CASCADE, related_name='infotechjob_comptechjobs', null=True, blank=True)
    job_title = models.CharField(max_length=255)

class InfoSystemJob(models.Model):
    """Information System job titles and relationships."""
    info_system_jobs_id = models.AutoField(primary_key=True)
    suc = models.ForeignKey('Suc', on_delete=models.CASCADE, related_name='infosystemjob_sucs', null=True, blank=True)
    info_tech_jobs = models.ForeignKey('InfoTechJob', on_delete=models.CASCADE, related_name='infosystemjob_infotechjobs', null=True, blank=True)
    comp_tech_jobs = models.ForeignKey('CompTechJob', on_delete=models.CASCADE, related_name='infosystemjob_comptechjobs', null=True, blank=True)
    job_title = models.CharField(max_length=255)

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
    post = models.ForeignKey('Post', on_delete=models.CASCADE, related_name='likes')
    # Used by Mobile: toggled at /api/posts/{post_id}/like/

class Conversation(models.Model):
    conversation_id = models.AutoField(primary_key=True)
    participants = models.ManyToManyField('User', related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
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
    attachment_id = models.AutoField(primary_key=True)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='attachments', null=True, blank=True)
    file = models.FileField(upload_to='message_attachments/%Y/%m/%d/')
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=50)
    file_size = models.IntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
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

class Notification(models.Model):
    notification_id = models.AutoField(primary_key=True)
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='notifications')
    notif_type = models.CharField(max_length=100)
    subject = models.CharField(max_length=255, blank=True, null=True)  # Added subject field
    notifi_content = models.TextField()
    notif_date = models.DateTimeField()
    # Used by Mobile: listed/deleted at /api/notifications/...

class PostCategory(models.Model):
    post_cat_id = models.AutoField(primary_key=True)
    events = models.BooleanField()
    announcements = models.BooleanField()
    donation = models.BooleanField()
    personal = models.BooleanField()
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
    post_cat = models.ForeignKey('PostCategory', on_delete=models.CASCADE, related_name='posts')
    post_title = models.CharField(max_length=255)
    post_image = models.ImageField(upload_to='post_images/', null=True, blank=True)  # Keep for backward compatibility
    post_content = models.TextField()
    type = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Used by Mobile: feed list/create/edit/delete/like/comment/repost

class Qpro(models.Model):
    qpro_id = models.AutoField(primary_key=True)
    standard = models.ForeignKey('Standard', on_delete=models.CASCADE, related_name='qpros')

class Repost(models.Model):
    repost_id = models.AutoField(primary_key=True)
    post = models.ForeignKey('Post', on_delete=models.CASCADE, related_name='reposts')
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='reposts')
    repost_date = models.DateTimeField()
    caption = models.TextField(null=True, blank=True)
    # Used by Mobile: /api/posts/{post_id}/repost/ and /api/reposts/{repost_id}/

class RepostLike(models.Model):
    """Used by Mobile: likes attached to a specific Repost (not the original Post).

    Endpoints to be exposed under /api/reposts/{repost_id}/like/ and /likes/.
    """
    repost_like_id = models.AutoField(primary_key=True)
    repost = models.ForeignKey('Repost', on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='repost_likes')

    class Meta:
        unique_together = ('repost', 'user')
        db_table = 'shared_repostlike'

class RepostComment(models.Model):
    """Used by Mobile: comments attached to a specific Repost.

    Endpoints to be exposed under /api/reposts/{repost_id}/comments/ ...
    """
    repost_comment_id = models.AutoField(primary_key=True)
    repost = models.ForeignKey('Repost', on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='repost_comments')
    comment_content = models.TextField(null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'shared_repostcomment'

class Standard(models.Model):
    standard_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, default="CTU Standard")
    description = models.TextField(blank=True)
    qpro = models.ForeignKey('Qpro', on_delete=models.CASCADE, related_name='standards', null=True, blank=True)
    suc = models.ForeignKey('Suc', on_delete=models.CASCADE, related_name='standards', null=True, blank=True)
    aacup = models.ForeignKey('Aacup', on_delete=models.CASCADE, related_name='standards', null=True, blank=True)
    ched = models.ForeignKey('Ched', on_delete=models.CASCADE, related_name='standards', null=True, blank=True)

class Suc(models.Model):
    suc_id = models.AutoField(primary_key=True)
    standard = models.ForeignKey('Standard', on_delete=models.CASCADE, related_name='suc_sucs')
    info_tech_jobs = models.ForeignKey('InfoTechJob', on_delete=models.CASCADE, related_name='suc_infotechjobs')
    info_system_jobs = models.ForeignKey('InfoSystemJob', on_delete=models.CASCADE, related_name='suc_infosystemjobs')
    comp_tech_jobs = models.ForeignKey('CompTechJob', on_delete=models.CASCADE, related_name='suc_comptechjobs')

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
    import_id = models.ForeignKey('Import', on_delete=models.CASCADE, related_name='users', null=True, blank=True)
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
    course = models.CharField(max_length=100, null=True, blank=True)
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
            models.Index(fields=['year_graduated', 'course']),
            models.Index(fields=['pursue_further_study']),
        ]
    
    def __str__(self):
        return f"Academic info for {self.user.full_name} - {self.course} ({self.year_graduated})"


class EmploymentHistory(models.Model):
    """Employment and job information"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employment')
    
    # Current employment
    company_name_current = models.CharField(max_length=255, null=True, blank=True)
    position_current = models.CharField(max_length=255, null=True, blank=True)
    sector_current = models.CharField(max_length=255, null=True, blank=True)
    employment_duration_current = models.CharField(max_length=100, null=True, blank=True)
    salary_current = models.CharField(max_length=100, null=True, blank=True)
    date_started = models.DateField(null=True, blank=True)
    company_address = models.TextField(null=True, blank=True)
    
    # Employment status and alignment
    job_alignment_status = models.CharField(max_length=50, null=True, blank=True, default='not_aligned')
    job_alignment_category = models.CharField(max_length=100, null=True, blank=True)
    job_alignment_title = models.CharField(max_length=255, null=True, blank=True)
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
    
    def update_job_alignment(self):
        """Update job alignment fields based on position_current and course
        This connects tracker answers to statistics types (CHED, SUC, AACUP)
        """
        if not self.position_current:
            self.job_alignment_status = 'not_aligned'
            self.job_alignment_category = None
            self.job_alignment_title = None
            return
        
        position_lower = self.position_current.lower().strip()
        course_lower = (self.user.academic_info.course or '').lower() if hasattr(self.user, 'academic_info') else ''
        
        # STEP 1: Self-employed status based on tracker answer Q23 (q_employment_type)
        # Check if user is self-employed based on tracker response
        tracker_data = getattr(self.user, 'tracker_data', None)
        if tracker_data and tracker_data.q_employment_type and 'self-employed' in tracker_data.q_employment_type.lower():
            self.self_employed = True
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
        if self.date_started and hasattr(self.user, 'academic_info') and self.user.academic_info.year_graduated:
            # If hired within 6 months of graduation, consider absorbed
            from datetime import date
            graduation_date = date(self.user.academic_info.year_graduated, 6, 30)  # Assume June graduation
            if self.date_started <= graduation_date:
                self.absorbed = True
            else:
                self.absorbed = False
        
        # STEP 4: Job alignment logic using simple job models
        # This determines if the job aligns with the course, regardless of employment type
        job_aligned = False
        
        # Import simple job models
        from django.db import connection
        
        # Check based on course type using simple job models
        if 'bit-ct' in course_lower or 'computer technology' in course_lower:
            # Computer Technology jobs
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT job_title FROM shared_simplecomptechjob WHERE LOWER(job_title) LIKE %s",
                    [f'%{position_lower}%']
                )
                result = cursor.fetchone()
                if result:
                    self.job_alignment_status = 'aligned'
                    self.job_alignment_category = 'comp_tech'
                    self.job_alignment_title = result[0]
                    job_aligned = True
        
        elif 'bsit' in course_lower or 'information technology' in course_lower:
            # Information Technology jobs
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT job_title FROM shared_simpleinfotechjob WHERE LOWER(job_title) LIKE %s",
                    [f'%{position_lower}%']
                )
                result = cursor.fetchone()
                if result:
                    self.job_alignment_status = 'aligned'
                    self.job_alignment_category = 'info_tech'
                    self.job_alignment_title = result[0]
                    job_aligned = True
        
        elif 'bsis' in course_lower or 'information system' in course_lower:
            # Information System jobs
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT job_title FROM shared_simpleinfosystemjob WHERE LOWER(job_title) LIKE %s",
                    [f'%{position_lower}%']
                )
                result = cursor.fetchone()
                if result:
                    self.job_alignment_status = 'aligned'
                    self.job_alignment_category = 'info_system'
                    self.job_alignment_title = result[0]
                    job_aligned = True
        
        # REMOVED: Fallback logic that allowed cross-course alignment
        # This was causing BSIT graduates to be marked as aligned for BSIS-exclusive jobs
        # Job alignment should only be based on the graduate's specific course
        
        # If still not aligned
        if not job_aligned:
            self.job_alignment_status = 'not_aligned'
            self.job_alignment_category = None
            self.job_alignment_title = None
    
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

class QuestionCategory(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)  # Added for ordering

class Question(models.Model):
    category = models.ForeignKey(QuestionCategory, related_name='questions', on_delete=models.CASCADE)
    text = models.CharField(max_length=255)
    type = models.CharField(max_length=50)
    options = models.JSONField(blank=True, null=True)  # For radio/multiple/checkbox

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
                elif question_id == 2:  # Course Graduated
                    academic.course = str(answer) if answer else academic.course
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
                elif question_id == 28:  # How long have you been employed?
                    tracker.q_employment_duration = str(answer) if answer else tracker.q_employment_duration
                    if answer:
                        employment.employment_duration_current = str(answer)
                elif question_id == 38:  # Employment Sector (Local/International)
                    tracker.q_scope_current = str(answer) if answer else tracker.q_scope_current
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
    import_date = models.DateTimeField(auto_now_add=True)
    file_name = models.CharField(max_length=255)
    records_imported = models.IntegerField(default=0)
    status = models.CharField(max_length=50, default='Completed')  # Completed, Failed, Partial
class TrackerFileUpload(models.Model):
    response = models.ForeignKey(TrackerResponse, on_delete=models.CASCADE, related_name='files')
    question_id = models.IntegerField()  # ID of the question this file answers
    file = models.FileField(upload_to='tracker_uploads/')
    original_filename = models.CharField(max_length=255)
    file_size = models.IntegerField()  # File size in bytes
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.original_filename} - {self.response.user.f_name} {self.response.user.l_name}"