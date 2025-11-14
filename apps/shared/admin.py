from django.contrib import admin
from django.utils.html import format_html
from .models import *

# Register your models here.
admin.site.register(AccountType)
admin.site.register(Aacup)
admin.site.register(Ched)
admin.site.register(Comment)
admin.site.register(CompTechJob)
admin.site.register(ExportedFile)
admin.site.register(Feed)
admin.site.register(Forum)
admin.site.register(HighPosition)
admin.site.register(Import)
admin.site.register(InfoTechJob)
admin.site.register(InfoSystemJob)
admin.site.register(Like)
admin.site.register(Message)
admin.site.register(Notification)
admin.site.register(PostCategory)
admin.site.register(Post)
admin.site.register(Qpro)
admin.site.register(Repost)
admin.site.register(Standard)
admin.site.register(Suc)
admin.site.register(TrackerForm)
admin.site.register(User)
admin.site.register(QuestionCategory)
admin.site.register(Question)
admin.site.register(TrackerResponse)

# Custom filter for question types
class QuestionTypeFilter(admin.SimpleListFilter):
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
