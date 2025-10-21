"""
Serializers for shared app models: user, profile, academic info, employment, tracker, OJT, and related entities.
Consider splitting into multiple files if the number of serializers grows.
"""
from rest_framework import serializers
from .models import (
    User, UserProfile, AcademicInfo, EmploymentHistory, 
    TrackerData, OJTInfo, AccountType, Conversation, Message, MessageAttachment
)
from .security import ContentSanitizer


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for UserProfile model, including calculated age."""
    calculated_age = serializers.ReadOnlyField()
    
    class Meta:
        model = UserProfile
        fields = [
            'phone_num', 'email', 'address', 'home_address',
            'birthdate', 'age', 'calculated_age', 'civil_status',
            'social_media', 'profile_pic', 'profile_bio', 'profile_resume'
        ]


class AcademicInfoSerializer(serializers.ModelSerializer):
    """Serializer for AcademicInfo model."""
    class Meta:
        model = AcademicInfo
        fields = [
            'year_graduated', 'program', 'section', 'school_name',
            'pursue_further_study', 'q_pursue_study', 'q_study_start_date', 
            'q_post_graduate_degree', 'q_institution_name', 'q_units_obtained'
        ]


class EmploymentHistorySerializer(serializers.ModelSerializer):
    """Serializer for EmploymentHistory model."""
    class Meta:
        model = EmploymentHistory
        fields = [
            'company_name_current', 'position_current', 'sector_current',
            'employment_duration_current', 'salary_current', 'date_started',
            'company_address', 'job_alignment_status', 'job_alignment_category',
            'job_alignment_title', 'self_employed', 'high_position', 'absorbed',
            'awards_recognition_current', 'supporting_document_current',
            'supporting_document_awards_recognition', 'unemployment_reason'
        ]


class TrackerDataSerializer(serializers.ModelSerializer):
    """Serializer for TrackerData model."""
    class Meta:
        model = TrackerData
        fields = [
            'q_employment_status', 'q_employment_type', 'q_employment_permanent',
            'q_company_name', 'q_current_position', 'q_job_sector',
            'q_employment_duration', 'q_salary_range', 'q_awards_received',
            'q_awards_document', 'q_employment_document', 'q_unemployment_reason',
            'tracker_submitted_at', 'tracker_last_updated'
        ]


class OJTInfoSerializer(serializers.ModelSerializer):
    """Serializer for OJTInfo model."""
    class Meta:
        model = OJTInfo
        fields = [
            'ojt_end_date', 'job_code', 'ojtstatus'
        ]


class UserSerializer(serializers.ModelSerializer):
    """Full serializer for User model, including related models."""
    profile = UserProfileSerializer(read_only=True)
    academic_info = AcademicInfoSerializer(read_only=True)
    employment = EmploymentHistorySerializer(read_only=True)
    tracker_data = TrackerDataSerializer(read_only=True)
    ojt_info = OJTInfoSerializer(read_only=True)
    full_name = serializers.ReadOnlyField()
    
    class Meta:
        model = User
        fields = [
            'user_id', 'acc_username', 'user_status', 'f_name', 'm_name', 'l_name',
            'gender', 'full_name', 'profile', 'academic_info', 'employment',
            'tracker_data', 'ojt_info', 'created_at', 'updated_at'
        ]


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a User with nested related data."""
    profile_data = UserProfileSerializer(required=False)
    academic_data = AcademicInfoSerializer(required=False)
    employment_data = EmploymentHistorySerializer(required=False)
    tracker_data = TrackerDataSerializer(required=False)
    ojt_data = OJTInfoSerializer(required=False)
    
    class Meta:
        model = User
        fields = [
            'acc_username', 'acc_password', 'user_status', 'f_name', 'm_name', 'l_name',
            'gender', 'account_type', 'profile_data', 'academic_data', 
            'employment_data', 'tracker_data', 'ojt_data'
        ]
    
    def create(self, validated_data):
        from .services import UserService
        
        # Extract nested data
        profile_data = validated_data.pop('profile_data', {})
        academic_data = validated_data.pop('academic_data', {})
        employment_data = validated_data.pop('employment_data', None)
        tracker_data = validated_data.pop('tracker_data', {})
        ojt_data = validated_data.pop('ojt_data', None)
        
        # Create user with all related models
        user = UserService.create_complete_user(
            user_data=validated_data,
            profile_data=profile_data,
            academic_data=academic_data,
            employment_data=employment_data,
            tracker_data=tracker_data,
            ojt_data=ojt_data
        )
        
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating a User and related models."""
    profile = UserProfileSerializer(required=False)
    academic_info = AcademicInfoSerializer(required=False)
    tracker_data = TrackerDataSerializer(required=False)
    
    class Meta:
        model = User
        fields = [
            'user_status', 'f_name', 'm_name', 'l_name', 'gender',
            'profile', 'academic_info', 'tracker_data'
        ]
    
    def update(self, instance, validated_data):
        # Update core user fields
        for attr, value in validated_data.items():
            if attr not in ['profile', 'academic_info', 'tracker_data']:
                setattr(instance, attr, value)
        instance.save()
        
        # Update profile
        if 'profile' in validated_data:
            profile_data = validated_data['profile']
            profile, created = UserProfile.objects.get_or_create(user=instance)
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()
        
        # Update academic info
        if 'academic_info' in validated_data:
            academic_data = validated_data['academic_info']
            academic, created = AcademicInfo.objects.get_or_create(user=instance)
            for attr, value in academic_data.items():
                setattr(academic, attr, value)
            academic.save()
        
        # Update tracker data
        if 'tracker_data' in validated_data:
            tracker_data = validated_data['tracker_data']
            tracker, created = TrackerData.objects.get_or_create(user=instance)
            for attr, value in tracker_data.items():
                setattr(tracker, attr, value)
            tracker.save()
        
        return instance


class AlumniListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for alumni lists."""
    full_name = serializers.ReadOnlyField()
    email = serializers.CharField(source='profile.email', read_only=True)
    course = serializers.CharField(source='academic_info.program', read_only=True)
    year_graduated = serializers.IntegerField(source='academic_info.year_graduated', read_only=True)
    employment_status = serializers.CharField(source='tracker_data.q_employment_status', read_only=True)
    current_company = serializers.CharField(source='employment.company_name_current', read_only=True)
    current_position = serializers.CharField(source='employment.position_current', read_only=True)
    
    class Meta:
        model = User
        fields = [
            'user_id', 'acc_username', 'full_name', 'email', 'course',
            'year_graduated', 'employment_status', 'current_company', 'current_position'
        ]


class AlumniStatsSerializer(serializers.Serializer):
    """Serializer for alumni statistics."""
    total_alumni = serializers.IntegerField()
    employed = serializers.IntegerField()
    unemployed = serializers.IntegerField()
    employment_rate = serializers.FloatField()
    job_aligned = serializers.IntegerField()
    pursuing_study = serializers.IntegerField()
    
    # Breakdown by year
    by_year = serializers.DictField(child=serializers.DictField(), required=False)
    
    # Breakdown by course
    by_course = serializers.DictField(child=serializers.DictField(), required=False)
    
    # Job alignment breakdown
    job_alignment_breakdown = serializers.DictField(child=serializers.IntegerField(), required=False)


# Messaging Serializers
class SmallUserSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='full_name', read_only=True)

    class Meta:
        model = User
        fields = ['user_id', 'name']

class MessageAttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    file_category = serializers.SerializerMethodField()
    
    class Meta:
        model = MessageAttachment
        fields = ['attachment_id', 'file', 'file_url', 'file_name', 'file_type', 'file_category', 'file_size', 'uploaded_at']
        read_only_fields = ['attachment_id', 'uploaded_at']
    
    def get_file_url(self, obj):
        """Get file URL with proper cloud storage support"""
        # Prioritize cloud storage URL (already absolute)
        if obj.file_url:
            # Check if it's already absolute
            if obj.file_url.startswith('http'):
                return obj.file_url
            # If relative, make it absolute
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file_url)
            else:
                from django.conf import settings
                return f"http://localhost:8000{obj.file_url}"
        
        # Fallback to local storage - ensure absolute URL
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            else:
                # If no request context, construct URL manually
                from django.conf import settings
                return f"http://localhost:8000{obj.file.url}"
        
        # If neither field has a URL, return None
        return None
    
    def get_file_category(self, obj):
        """Determine file category based on MIME type"""
        from apps.messaging.views import get_file_category
        return get_file_category(obj.file_type)

class MessageSerializer(serializers.ModelSerializer):
    sender = SmallUserSerializer(read_only=True)
    attachments = MessageAttachmentSerializer(many=True, read_only=True)
    sender_name = serializers.CharField(source='sender.full_name', read_only=True)
    
    class Meta:
        model = Message
        fields = [
            'message_id', 'sender', 'sender_name', 'content', 'message_type', 
            'is_read', 'created_at', 'attachments'
        ]
        read_only_fields = ['message_id', 'sender', 'created_at']

class ConversationSerializer(serializers.ModelSerializer):
    participants = UserSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    other_participant = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversation
        fields = [
            'conversation_id', 'participants', 'last_message', 'unread_count', 
            'other_participant', 'updated_at'
        ]
        read_only_fields = ['conversation_id', 'created_at', 'updated_at']
    
    def get_last_message(self, obj):
        last_msg = obj.get_last_message()
        if last_msg:
            return {
                'message_id': last_msg.message_id,
                'content': last_msg.content,
                'sender_name': last_msg.sender.full_name,
                'sender_id': last_msg.sender.user_id,
                'created_at': last_msg.created_at,
                'is_read': last_msg.is_read,
                'message_type': last_msg.message_type,
            }
        return None
    
    def get_unread_count(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.get_unread_count(request.user)
        return 0
    
    def get_other_participant(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            other_user = obj.get_other_participant(request.user)
            if other_user:
                return {
                    'user_id': other_user.user_id,
                    'name': other_user.full_name,
                    'f_name': other_user.f_name,
                    'l_name': other_user.l_name,
                    'acc_username': other_user.acc_username,
                }
        return None

class CreateConversationSerializer(serializers.ModelSerializer):
    participant_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        help_text="List of user IDs to include in the conversation"
    )
    participant_id = serializers.IntegerField(write_only=True, required=False, help_text="Single participant id convenience")
    
    class Meta:
        model = Conversation
        fields = ['participant_ids', 'participant_id']
    
    def validate_participant_ids(self, value):
        """Validate that participant IDs exist and are valid users"""
        if not value:
            raise serializers.ValidationError("At least one participant is required.")
        
        # Check if users exist and have messaging access
        users = User.objects.filter(user_id__in=value)
        
        if len(users) != len(value):
            raise serializers.ValidationError("Some users do not exist.")
        
        # Check if users have messaging access (regular user or ojt)
        invalid_users = []
        for user in users:
            account_type = user.account_type
            if not (getattr(account_type, 'user', False) or getattr(account_type, 'ojt', False)):
                invalid_users.append(user.full_name)
        
        if invalid_users:
            raise serializers.ValidationError(
                f"Users {', '.join(invalid_users)} do not have messaging access."
            )
        
        return value

    def validate(self, attrs):
        # Ensure at least one participant id is provided via either field
        if not attrs.get('participant_ids') and not attrs.get('participant_id'):
            raise serializers.ValidationError({'participant_ids': 'Provide participant_id or participant_ids.'})
        return attrs
    
    def create(self, validated_data):
        # Accept either participant_id or participant_ids
        if 'participant_id' in validated_data and not validated_data.get('participant_ids'):
            participant_ids = [validated_data.pop('participant_id')]
        else:
            participant_ids = validated_data.pop('participant_ids')

        current_user = self.context['request'].user
        other_users = list(User.objects.filter(user_id__in=participant_ids))

        # Ensure uniqueness and remove potential self from list
        other_users = [u for u in other_users if u.user_id != current_user.user_id]

        # If a 1:1 already exists, return it
        if len(other_users) == 1:
            other = other_users[0]
            existing = (
                Conversation.objects
                .filter(participants=current_user)
                .filter(participants=other)
                .first()
            )
            if existing:
                return existing

        conversation = Conversation.objects.create()
        conversation.participants.set([current_user, *other_users])
        return conversation

class MessageCreateSerializer(serializers.ModelSerializer):
    attachment_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    class Meta:
        model = Message
        fields = ['content', 'message_type', 'attachment_id']
    
    def validate_message_type(self, value):
        """Validate and sanitize message type"""
        try:
            return ContentSanitizer.validate_message_type(value)
        except Exception as e:
            raise serializers.ValidationError(str(e))
    
    def validate_content(self, value):
        """Validate and sanitize message content"""
        try:
            return ContentSanitizer.sanitize_message_content(value)
        except Exception as e:
            raise serializers.ValidationError(str(e))

    def create(self, validated_data):
        attachment_id = validated_data.pop('attachment_id', None)
        message: Message = super().create(validated_data)
        # Attach uploaded file, if provided
        if attachment_id:
            from .models import MessageAttachment
            try:
                attachment = MessageAttachment.objects.get(attachment_id=attachment_id)
                attachment.message = message
                attachment.save()
            except MessageAttachment.DoesNotExist:
                pass
        return message