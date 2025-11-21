from django.urls import path
from . import views, health, reaction_views

app_name = 'messaging'

urlpatterns = [
    # Health check endpoints (for load balancers and monitoring)
    path('health/', health.health_check, name='health-check'),
    path('health/detailed/', health.health_check_detailed, name='health-check-detailed'),
    path('health/ready/', health.readiness_check, name='readiness-check'),
    path('health/live/', health.liveness_check, name='liveness-check'),
    path('metrics/', health.metrics_endpoint, name='metrics'),
    
    # Conversation endpoints
    path('conversations/', views.ConversationListView.as_view(), name='conversation-list'),
    path('conversations/<int:conversation_id>/', views.conversation_detail, name='conversation-detail'),
    path('conversations/<int:conversation_id>/messages/', views.MessageListView.as_view(), name='message-list'),
    path('conversations/<int:conversation_id>/read/', views.mark_conversation_as_read, name='mark-read'),
    
    # Message operations (update must come before delete to handle both)
    path('conversations/<int:conversation_id>/messages/<int:message_id>/', views.update_message, name='update-message'),
    path('conversations/<int:conversation_id>/messages/<int:message_id>/delete/', views.delete_message, name='delete-message'),
    
    # Message reactions
    path('conversations/<int:conversation_id>/messages/<int:message_id>/reactions/', reaction_views.add_or_remove_reaction, name='message-reactions'),
    path('conversations/<int:conversation_id>/messages/<int:message_id>/reactions/list/', reaction_views.list_reactions, name='list-reactions'),
    
    # User search
    path('users/search/', views.search_users, name='search-users'),
    
    # Statistics
    path('stats/', views.messaging_stats, name='messaging-stats'),
    
    # Attachments
    path('attachments/', views.AttachmentUploadView.as_view(), name='attachment-upload'),
    
    # File serving with ngrok bypass
    path('files/<path:file_path>', views.serve_file_with_ngrok_bypass, name='serve-file-ngrok-bypass'),
]
