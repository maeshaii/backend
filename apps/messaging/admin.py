from django.contrib import admin
from apps.shared.models import Conversation, Message, MessageAttachment

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['conversation_id', 'get_participants', 'created_at', 'updated_at', 'get_message_count']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['participants__f_name', 'participants__l_name', 'participants__acc_username']
    readonly_fields = ['conversation_id', 'created_at', 'updated_at']
    filter_horizontal = ['participants']
    
    def get_participants(self, obj):
        return ", ".join([f"{p.f_name} {p.l_name}" for p in obj.participants.all()])
    get_participants.short_description = 'Participants'
    
    def get_message_count(self, obj):
        return obj.messages.count()
    get_message_count.short_description = 'Messages'

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['message_id', 'sender', 'conversation', 'content_preview', 'message_type', 'is_read', 'created_at']
    list_filter = ['message_type', 'is_read', 'created_at', 'sender']
    search_fields = ['content', 'sender__f_name', 'sender__l_name', 'conversation__conversation_id']
    readonly_fields = ['message_id', 'created_at']
    date_hierarchy = 'created_at'
    
    def content_preview(self, obj):
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('sender', 'conversation')

@admin.register(MessageAttachment)
class MessageAttachmentAdmin(admin.ModelAdmin):
    list_display = ['attachment_id', 'message', 'file_name', 'file_type', 'file_size_mb', 'uploaded_at']
    list_filter = ['file_type', 'uploaded_at']
    search_fields = ['file_name', 'message__content', 'message__sender__f_name']
    readonly_fields = ['attachment_id', 'uploaded_at']
    date_hierarchy = 'uploaded_at'
    
    def file_size_mb(self, obj):
        return f"{obj.file_size_mb} MB"
    file_size_mb.short_description = 'File Size'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('message__sender')
