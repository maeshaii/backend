from django.urls import path
from . import views

app_name = 'messaging'

urlpatterns = [
    # Conversation endpoints
    path('conversations/', views.ConversationListView.as_view(), name='conversation-list'),
    path('conversations/<int:conversation_id>/', views.conversation_detail, name='conversation-detail'),
    path('conversations/<int:conversation_id>/messages/', views.MessageListView.as_view(), name='message-list'),
    path('conversations/<int:conversation_id>/read/', views.mark_conversation_as_read, name='mark-read'),
    path('conversations/<int:conversation_id>/messages/<int:message_id>/', views.delete_message, name='delete-message'),
    
    # User search
    path('users/search/', views.search_users, name='search-users'),
    
    # Statistics
    path('stats/', views.messaging_stats, name='messaging-stats'),
    
    # Attachments
    path('attachments/', views.AttachmentUploadView.as_view(), name='attachment-upload'),
    
    # File serving with ngrok bypass
    path('files/<path:file_path>', views.serve_file_with_ngrok_bypass, name='serve-file-ngrok-bypass'),
]
