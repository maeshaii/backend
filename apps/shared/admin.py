from django.contrib import admin
from django.utils.html import format_html
from .models import *

# Register your models here.
admin.site.register(AccountType)
# admin.site.register(Aacup)  # Model not found
# admin.site.register(Ched)  # Model not found
admin.site.register(Comment)
# admin.site.register(CompTechJob)  # Model not found
# admin.site.register(ExportedFile)  # Model not found
# admin.site.register(Feed)  # Model not found
admin.site.register(Forum)
# admin.site.register(HighPosition)  # Model not found
# admin.site.register(Import)  # Model not found
# admin.site.register(InfoTechJob)  # Model not found
# admin.site.register(InfoSystemJob)  # Model not found
admin.site.register(Like)
admin.site.register(Notification)
admin.site.register(Post)
# admin.site.register(Qpro)  # Model not found
admin.site.register(Repost)
# admin.site.register(Standard)  # Model not found
# admin.site.register(Suc)  # Model not found
# admin.site.register(TrackerForm)  # Model not found
admin.site.register(User)
admin.site.register(QuestionCategory)
admin.site.register(Question)
admin.site.register(TrackerResponse)

# PHASE 3: Enhanced admin interface for job title management
from django.db.models import Count

@admin.register(SimpleCompTechJob)
class SimpleCompTechJobAdmin(admin.ModelAdmin):
    list_display = ['job_title', 'usage_count']
    search_fields = ['job_title']
    ordering = ['job_title']
    
    def usage_count(self, obj):
        """Show how many alumni are using this job title"""
        count = EmploymentHistory.objects.filter(
            job_alignment_title=obj.job_title,
            job_alignment_category='comp_tech'
        ).count()
        return count
    usage_count.short_description = 'Alumni Using This Title'

@admin.register(SimpleInfoTechJob)
class SimpleInfoTechJobAdmin(admin.ModelAdmin):
    list_display = ['job_title', 'usage_count']
    search_fields = ['job_title']
    ordering = ['job_title']
    
    def usage_count(self, obj):
        """Show how many alumni are using this job title"""
        count = EmploymentHistory.objects.filter(
            job_alignment_title=obj.job_title,
            job_alignment_category='info_tech'
        ).count()
        return count
    usage_count.short_description = 'Alumni Using This Title'

@admin.register(SimpleInfoSystemJob)
class SimpleInfoSystemJobAdmin(admin.ModelAdmin):
    list_display = ['job_title', 'usage_count']
    search_fields = ['job_title']
    ordering = ['job_title']
    
    def usage_count(self, obj):
        """Show how many alumni are using this job title"""
        count = EmploymentHistory.objects.filter(
            job_alignment_title=obj.job_title,
            job_alignment_category='info_system'
        ).count()
        return count
    usage_count.short_description = 'Alumni Using This Title'

# Enhanced EmploymentHistory admin with job alignment info
@admin.register(EmploymentHistory)
class EmploymentHistoryAdmin(admin.ModelAdmin):
    list_display = ['user_name', 'position_current', 'job_alignment_status', 'job_alignment_title', 'company_name_current']
    list_filter = ['job_alignment_status', 'job_alignment_category', 'absorbed']
    search_fields = ['user__f_name', 'user__l_name', 'position_current', 'company_name_current']
    readonly_fields = ['job_alignment_status', 'job_alignment_category', 'job_alignment_title']
    
    def user_name(self, obj):
        return f"{obj.user.f_name} {obj.user.l_name}"
    user_name.short_description = 'Alumni Name'
    
    actions = ['recalculate_job_alignment']
    
    def recalculate_job_alignment(self, request, queryset):
        """Recalculate job alignment for selected employment records"""
        updated_count = 0
        for employment in queryset:
            employment.update_job_alignment()
            employment.save()
            updated_count += 1
        
        self.message_user(
            request,
            f'Successfully recalculated job alignment for {updated_count} employment records.'
        )
    recalculate_job_alignment.short_description = 'Recalculate job alignment'

# Custom filter for question types
class QuestionTypeFilter(admin.SimpleListFilter):
    """Custom filter for filtering questions by document type in the admin interface."""
    title = 'Document Type'
    parameter_name = 'question_type'

    def lookups(self, request, model_admin):
        from apps.shared.models import Question
        questions = Question.objects.filter(type='file').distinct()
        return [(q.id, q.text[:50] + '...' if len(q.text) > 50 else q.text) for q in questions]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(question_id=self.value())
        return queryset

@admin.register(TrackerFileUpload)
class TrackerFileUploadAdmin(admin.ModelAdmin):
    """Admin interface for TrackerFileUpload with custom display and filters."""
    list_display = ('original_filename', 'user_name', 'question_text', 'question_id', 'file_size_mb', 'uploaded_at', 'download_link')
    list_filter = (QuestionTypeFilter, 'uploaded_at')
    search_fields = ('original_filename', 'response__user__f_name', 'response__user__l_name')
    readonly_fields = ('uploaded_at', 'file_size', 'question_text')
    
    def user_name(self, obj):
        return f"{obj.response.user.f_name} {obj.response.user.l_name}"
    user_name.short_description = 'User'
    
    def question_text(self, obj):
        # Try to get the question text from the response answers
        try:
            from apps.shared.models import Question
            question = Question.objects.filter(id=obj.question_id).first()
            if question:
                return question.text
            else:
                return f"Question ID: {obj.question_id}"
        except:
            return f"Question ID: {obj.question_id}"
    question_text.short_description = 'Question'
    
    def file_size_mb(self, obj):
        return f"{obj.file_size / 1024 / 1024:.2f} MB"
    file_size_mb.short_description = 'File Size'
    
    def download_link(self, obj):
        if obj.file:
            return format_html('<a href="{}" target="_blank">Download</a>', obj.file.url)
        return "No file"
    download_link.short_description = 'Download'

@admin.register(EngagementPointsSettings)
class EngagementPointsSettingsAdmin(admin.ModelAdmin):
    """Admin interface for Engagement Points Settings."""
    
    def has_add_permission(self, request):
        # Only allow one instance (singleton pattern)
        return not EngagementPointsSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Don't allow deletion of settings
        return False
    
    fieldsets = (
        ('Points System', {
            'fields': ('enabled',)
        }),
        ('Points Awarded Per Action', {
            'fields': (
                'like_points',
                'comment_points',
                'share_points',
                'reply_points',
                'post_points',
                'post_with_photo_points',
            ),
            'description': 'Configure how many points users earn for each action type.'
        }),
        ('Tracker Form Rewards', {
            'fields': (
                'tracker_form_enabled',
                'tracker_form_points',
            ),
            'description': 'Enable or disable tracker form rewards and configure points awarded for completing the tracker form.'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    list_display = ['enabled', 'updated_at']
    
    def get_object(self, request, object_id=None, from_field=None):
        # Always return the singleton instance
        obj, created = EngagementPointsSettings.objects.get_or_create(pk=1)
        return obj
    
    def changelist_view(self, request, extra_context=None):
        # Redirect to the edit page if settings exist
        if EngagementPointsSettings.objects.exists():
            from django.shortcuts import redirect
            settings = EngagementPointsSettings.objects.get(pk=1)
            return redirect(f'/admin/shared/engagementpointssettings/{settings.pk}/change/')
        return super().changelist_view(request, extra_context)