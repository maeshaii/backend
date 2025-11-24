from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.utils import timezone
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.http import HttpResponse, Http404
from django.conf import settings
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging
import os
from apps.shared.models import Conversation, Message, MessageAttachment, User, MessageReaction
from apps.shared.serializers import (
	ConversationSerializer,
	MessageSerializer,
	CreateConversationSerializer,
	MessageCreateSerializer,
)
from .permissions import IsAlumniOrOJT
from apps.shared.security import ContentSanitizer, SecurityValidator
from .message_cache import message_cache
from .cloud_storage import cloud_storage
from .monitoring import messaging_monitor, track_performance, PerformanceTracker
from .performance_metrics import performance_metrics, PerformanceTracker as PerfTracker
import os
import uuid
import mimetypes

logger = logging.getLogger(__name__)


def get_conversation_with_access_check(conversation_id, user):
    """
    Helper function to get conversation with prefetched participants and check user access.
    Reduces N+1 queries and code duplication.
    """
    conversation = get_object_or_404(
        Conversation.objects.prefetch_related('participants'),
        conversation_id=conversation_id
    )
    if not conversation.participants.filter(user_id=user.user_id).exists():
        return None, Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
    return conversation, None


def get_file_category(content_type):
    """Determine file category based on MIME type"""
    if content_type.startswith('image/'):
        return 'image'
    elif content_type.startswith('video/'):
        return 'video'
    elif content_type.startswith('audio/'):
        return 'audio'
    elif content_type in ['application/pdf']:
        return 'pdf'
    elif content_type in ['application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                          'application/vnd.oasis.opendocument.text']:
        return 'word'
    elif content_type in ['application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                          'application/vnd.oasis.opendocument.spreadsheet']:
        return 'excel'
    elif content_type in ['application/vnd.ms-powerpoint', 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                          'application/vnd.oasis.opendocument.presentation']:
        return 'powerpoint'
    elif content_type.startswith('text/'):
        return 'text'
    elif content_type in ['application/zip', 'application/x-rar-compressed', 'application/x-7z-compressed']:
        return 'archive'
    else:
        return 'document'


class ConversationListView(generics.ListCreateAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated, IsAlumniOrOJT]

    @track_performance('conversation_list')
    def get_queryset(self):
        user = self.request.user
        
        with PerformanceTracker('conversation_list_query', {'user_id': user.user_id}):
            # Try to get from cache first
            cached_conversations = message_cache.get_user_conversations(user.user_id)
            if cached_conversations:
                logger.debug(f"Retrieved {len(cached_conversations)} conversations from cache for user {user.user_id}")
            
            # Optimize queryset with select_related and prefetch_related
            # FIX: Removed empty select_related() and optimized prefetch for participants with nested data
            queryset = Conversation.objects.filter(
                participants=user
            ).prefetch_related(
                'participants__profile',  # Prefetch participant profiles
                'participants__academic_info',  # Prefetch academic info
                'messages__sender',
                'messages__attachments'
            ).distinct().order_by('-updated_at')
            
            # Cache the results for next time
            # FIX: Use prefetched data instead of calling .all()
            conversations_data = []
            for conv in queryset:
                conv_data = {
                    'conversation_id': conv.conversation_id,
                    'created_at': conv.created_at.isoformat(),
                    'updated_at': conv.updated_at.isoformat(),
                    'participants': [p.user_id for p in conv.participants.all()],
                }
                conversations_data.append(conv_data)
            
            message_cache.cache_user_conversations(user.user_id, conversations_data)
            
            # Track business metric
            messaging_monitor.track_business_metric(
                'conversations_accessed',
                1,
                {'user_id': str(user.user_id)}
            )
            
            return queryset

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateConversationSerializer
        return ConversationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conversation = serializer.save()
        response_serializer = ConversationSerializer(conversation, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class MessageListView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAlumniOrOJT]

    def get_queryset(self):
        conversation_id = self.kwargs['conversation_id']
        conversation = get_object_or_404(Conversation, conversation_id=conversation_id)
        if not conversation.participants.filter(user_id=self.request.user.user_id).exists():
            return Message.objects.none()

        qs = Message.objects.filter(conversation=conversation).select_related(
            'sender', 'conversation', 'reply_to', 'reply_to__sender'
        ).prefetch_related(
            'attachments',
            'reactions',
            'reactions__user'
        ).order_by('-created_at', '-message_id')

        # Cursor pagination: use `cursor` as message_id to fetch older messages
        cursor = self.request.query_params.get('cursor')
        if cursor:
            try:
                cursor_msg = Message.objects.get(message_id=int(cursor), conversation=conversation)
                qs = qs.filter(
                    Q(created_at__lt=cursor_msg.created_at) |
                    Q(created_at=cursor_msg.created_at, message_id__lt=cursor_msg.message_id)
                )
            except Exception as e:
                logger.warning("Invalid cursor parameter: %s, error: %s", cursor, e)

        limit = self.request.query_params.get('limit')
        try:
            limit_val = max(1, min(int(limit or 50), 100))
        except Exception as e:
            logger.warning("Invalid limit parameter: %s, using default 50, error: %s", limit, e)
            limit_val = 50

        return qs[:limit_val]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return MessageCreateSerializer
        return MessageSerializer

    def create(self, request, *args, **kwargs):
        conversation_id = self.kwargs['conversation_id']
        
        # Start performance tracking for message creation
        with PerfTracker('message_creation', {
            'user_id': request.user.user_id,
            'conversation_id': conversation_id
        }) as tracker:
            tracker.mark_stage('start')
            
            # FIX: Prefetch participants to avoid N+1 queries
            conversation = get_object_or_404(
                Conversation.objects.prefetch_related('participants'),
                conversation_id=conversation_id
            )
            if not conversation.participants.filter(user_id=request.user.user_id).exists():
                return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
            
            tracker.mark_stage('access_check')
            
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            tracker.mark_stage('validation')
            
            # Determine receiver for 1:1 conversations to satisfy legacy non-null column
            # FIX: Use prefetched participants
            receiver = conversation.participants.exclude(user_id=request.user.user_id).first()
            
            # Convert message request to regular conversation only if the non-initiator replies
            if conversation.is_message_request:
                try:
                    initiator_id = getattr(conversation.request_initiator, 'user_id', None)
                    if not initiator_id or initiator_id != request.user.user_id:
                        conversation.is_message_request = False
                        conversation.request_initiator = None
                        conversation.save(update_fields=['is_message_request', 'request_initiator', 'updated_at'])
                        logger.info(f"Converted message request {conversation_id} to regular conversation by non-initiator reply")
                except Exception:
                    # Fallback: keep previous behavior if field missing
                    conversation.is_message_request = False
                    conversation.save(update_fields=['is_message_request', 'updated_at'])
                    logger.info(f"Converted message request {conversation_id} to regular conversation (fallback)")
            
            # Ensure legacy DB columns are populated (e.g., date_send)
            message = serializer.save(
                conversation=conversation,
                sender=request.user,
                receiver=receiver,
                created_at=timezone.now(),
            )
            
            tracker.mark_stage('message_saved')
        # Link uploaded attachment if provided
        try:
            attachment_id = request.data.get('attachment_id')
            if attachment_id:
                attachment = get_object_or_404(MessageAttachment, attachment_id=int(attachment_id))
                attachment.message = message
                attachment.save()
        except Exception as e:
            logger.warning("Failed to link attachment %s to message: %s", attachment_id, e)
        # Ensure legacy columns are populated for existing schema using ORM
        try:
            # Backfill legacy date_send if DB still missing it (older schema)
            # Note: created_at field maps to date_send column in database
            Message.objects.filter(message_id=message.message_id, created_at__isnull=True).update(
                created_at=timezone.now()
            )
            # Backfill legacy 'content' column to mirror message_content for older schemas
            Message.objects.filter(message_id=message.message_id, content__isnull=True).update(
                content=message.content
            )
        except Exception as e:
            logger.warning("Failed to backfill legacy columns for message %s: %s", message.message_id, e)

        # Broadcast the new message to websocket listeners
        try:
            # Get attachment details if exists
            attachment_url = None
            attachment_info = None
            if hasattr(message, 'attachments') and message.attachments.exists():
                attachment = message.attachments.first()
                if attachment:
                    # Use cloud storage URL first, fallback to local storage with absolute URL
                    if attachment.file_url:
                        attachment_url = attachment.file_url
                    elif attachment.file:
                        # Build absolute URL for local storage
                        attachment_url = request.build_absolute_uri(attachment.file.url)
                    
                    # Include attachment info for frontend
                    attachment_info = {
                        'file_name': attachment.file_name,
                        'file_type': attachment.file_type,
                        'file_category': get_file_category(attachment.file_type),
                        'file_size': attachment.file_size,
                    }
            
            channel_layer = get_channel_layer()
            
            # Get sender avatar URL
            from apps.api.views import build_profile_pic_url
            sender_avatar_url = build_profile_pic_url(request.user)
            
            # Create the message data structure
            message_data = {
                'message_id': message.message_id,
                'content': message.content,
                'sender_id': request.user.user_id,
                'sender_name': getattr(request.user, 'full_name', ''),
                'sender_avatar': sender_avatar_url if sender_avatar_url else None,
                'message_type': message.message_type,
                'created_at': message.created_at.isoformat(),
                'timestamp': timezone.now().isoformat(),
                'attachment_url': attachment_url,
                'attachment_info': attachment_info,
                'attachments': [{
                    'file_url': attachment_url,
                    'file_name': attachment_info.get('file_name') if attachment_info else None,
                    'file_type': attachment_info.get('file_type') if attachment_info else None,
                    'file_category': attachment_info.get('file_category') if attachment_info else None,
                    'file_size': attachment_info.get('file_size') if attachment_info else None,
                }] if attachment_url and attachment_info else [],
            }
            
            # Send to WebSocket group
            group_name = f"chat_{conversation.conversation_id}"
            logger.info(f"[WebSocket] Broadcasting message {message.message_id} to group: {group_name}")
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'chat_message',
                    'message': message_data  # This is the key the consumer expects
                }
            )
            logger.info("WebSocket message %s broadcast successful", message.message_id)
        except Exception as e:
            logger.error(f"❌ [WebSocket] Failed to broadcast message {message.message_id}: {str(e)}")
            logger.exception(e)  # Log full traceback for debugging
        
        # Invalidate cache for this conversation
        message_cache.invalidate_conversation_messages(conversation_id)
        message_cache.invalidate_conversation_metadata(conversation_id)
        
        # Cache the new message
        message_data = {
            'message_id': message.message_id,
            'content': message.content,
            'message_type': message.message_type,
            'sender_id': message.sender.user_id,
            'sender_name': message.sender.full_name,
            'created_at': message.created_at.isoformat(),
            'is_read': message.is_read,
            'attachment_url': attachment_url,
            'attachment_info': attachment_info,
        }
        message_cache.cache_message(message_data)
        
        # Track message delivery
        messaging_monitor.track_message_delivery(
            message.message_id,
            'sent',
            request.user.user_id,
            conversation_id,
            {
                'message_type': message.message_type,
                'has_attachment': bool(attachment_url),
                'content_length': len(message.content)
            }
        )
        
        # Track business metric
        messaging_monitor.track_business_metric(
            'messages_sent',
            1,
            {'conversation_id': str(conversation_id)}
        )
        
        conversation.save()
        response_serializer = MessageSerializer(message, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = MessageSerializer(queryset, many=True, context={'request': request})

        # Compute next_cursor (older messages still exist?)
        conversation_id = self.kwargs['conversation_id']
        conversation = get_object_or_404(Conversation, conversation_id=conversation_id)
        next_cursor = None
        # Determine if more older messages remain using the last item on this page
        try:
            page_items = list(queryset)
            if page_items:
                last = page_items[-1]
                remaining = Message.objects.filter(conversation=conversation).filter(
                    Q(created_at__lt=last.created_at) |
                    Q(created_at=last.created_at, message_id__lt=last.message_id)
                ).exists()
                if remaining:
                    next_cursor = last.message_id
        except Exception as e:
            logger.warning("Failed to determine next cursor for conversation %s: %s", conversation_id, e)
            next_cursor = None

        return Response({
            'results': serializer.data[::-1],  # return ascending for UI
            'next_cursor': next_cursor,
        })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAlumniOrOJT])
def mark_conversation_as_read(request, conversation_id):
    # FIX: Use helper function to reduce N+1 queries
    conversation, error_response = get_conversation_with_access_check(conversation_id, request.user)
    if error_response:
        return error_response
    updated_count = Message.objects.filter(conversation=conversation, is_read=False).exclude(sender=request.user).update(is_read=True)
    return Response({'status': 'success', 'messages_marked_read': updated_count, 'timestamp': timezone.now().isoformat()})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAlumniOrOJT])
def search_users(request):
    query = request.GET.get('q', '').strip()
    if not query:
        return Response({'error': 'Query parameter required'}, status=status.HTTP_400_BAD_REQUEST)
    if len(query) < 2:
        return Response({'error': 'Query must be at least 2 characters'}, status=status.HTTP_400_BAD_REQUEST)
    users = User.objects.filter(
        Q(f_name__icontains=query) |
        Q(l_name__icontains=query) |
        Q(acc_username__icontains=query),
        Q(account_type__user=True) | 
        Q(account_type__ojt=True) | 
        Q(account_type__admin=True) | 
        Q(account_type__peso=True) | 
        Q(account_type__coordinator=True),
        user_status='active',
    ).exclude(user_id=request.user.user_id).distinct()[:10]
    from apps.shared.serializers import UserSerializer
    from django.conf import settings
    serializer = UserSerializer(users, many=True)
    
    # Enhance response with avatar_url for each user
    def get_profile_pic_url(user, request=None):
        """Get profile picture URL for a user"""
        if not user or not hasattr(user, 'profile'):
            return None
        try:
            profile = getattr(user, 'profile', None)
            if not profile:
                return None
            profile_pic = getattr(profile, 'profile_pic', None)
            if not profile_pic:
                return None
            
            # Get the URL
            pic_url = profile_pic.url if hasattr(profile_pic, 'url') else str(profile_pic)
            if not pic_url:
                return None
            
            # Build absolute URL
            if request and not str(pic_url).startswith('http'):
                return request.build_absolute_uri(pic_url)
            elif not str(pic_url).startswith('http'):
                # Use settings to build absolute URL
                base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
                if pic_url.startswith('/'):
                    return f"{base_url}{pic_url}"
                return f"{base_url}/{pic_url}"
            return pic_url
        except Exception:
            return None
    
    users_data = []
    for user_data in serializer.data:
        # Find the corresponding user object
        user_obj = next((u for u in users if u.user_id == user_data['user_id']), None)
        if user_obj:
            avatar_url = get_profile_pic_url(user_obj, request)
            user_data['avatar_url'] = avatar_url
            # Ensure m_name is included (UserSerializer should include it, but double-check)
            if 'm_name' not in user_data:
                user_data['m_name'] = getattr(user_obj, 'm_name', None)
        else:
            user_data['avatar_url'] = None
            if 'm_name' not in user_data:
                user_data['m_name'] = None
        users_data.append(user_data)
    
    logger.info(f"Search users API returning {len(users_data)} users for query '{query}'")
    return Response({'users': users_data, 'count': len(users_data), 'query': query})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAlumniOrOJT])
def conversation_detail(request, conversation_id):
    # FIX: Use helper function to reduce N+1 queries
    conversation, error_response = get_conversation_with_access_check(conversation_id, request.user)
    if error_response:
        return error_response
    serializer = ConversationSerializer(conversation, context={'request': request})
    return Response(serializer.data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated, IsAlumniOrOJT])
def update_message(request, conversation_id, message_id):
    """Update/edit a message"""
    # FIX: Use helper function to reduce N+1 queries
    conversation, error_response = get_conversation_with_access_check(conversation_id, request.user)
    if error_response:
        return error_response
    message = get_object_or_404(Message, message_id=message_id, conversation=conversation)
    if message.sender.user_id != request.user.user_id:
        return Response({'error': 'You can only edit your own messages'}, status=status.HTTP_403_FORBIDDEN)
    
    # Update message content
    content = request.data.get('content')
    if not content or not content.strip():
        return Response({'error': 'Message content cannot be empty'}, status=status.HTTP_400_BAD_REQUEST)
    
    message.content = content.strip()
    message.save()
    
    # Return updated message
    from apps.shared.serializers import MessageSerializer
    serializer = MessageSerializer(message, context={'request': request})
    return Response(serializer.data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsAlumniOrOJT])
def delete_message(request, conversation_id, message_id):
    # FIX: Use helper function to reduce N+1 queries
    conversation, error_response = get_conversation_with_access_check(conversation_id, request.user)
    if error_response:
        return error_response
    message = get_object_or_404(Message, message_id=message_id, conversation=conversation)
    if message.sender.user_id != request.user.user_id:
        return Response({'error': 'You can only delete your own messages'}, status=status.HTTP_403_FORBIDDEN)
    message.delete()
    return Response({'status': 'success', 'message': 'Message deleted successfully'})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAlumniOrOJT])
def messaging_stats(request):
    user = request.user
    
    # Optimize database queries using aggregation and select_related
    total_conversations = Conversation.objects.filter(participants=user).count()
    total_messages_sent = Message.objects.filter(sender=user).count()
    
    # Use single query with aggregation instead of N+1 queries
    total_unread = Message.objects.filter(
        conversation__participants=user,
        is_read=False
    ).exclude(sender=user).count()
    
    # Optimize recent conversations query with select_related
    # FIX: Removed empty select_related() and added proper prefetch
    recent_conversations = Conversation.objects.filter(
        participants=user
    ).prefetch_related(
        'participants__profile',
        'participants__academic_info',
        'messages__sender'
    ).distinct().order_by('-updated_at')[:5]
    
    recent_serializer = ConversationSerializer(recent_conversations, many=True, context={'request': request})
    return Response({
        'total_conversations': total_conversations,
        'total_messages_sent': total_messages_sent,
        'total_unread_messages': total_unread,
        'recent_conversations': recent_serializer.data,
        'timestamp': timezone.now().isoformat(),
    })


class AttachmentUploadView(APIView):
    """Handle file uploads for message attachments"""
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated, IsAlumniOrOJT]

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

        # Extract conversation_id from form data (for validation purposes)
        conversation_id = request.data.get('conversation_id')
        if conversation_id:
            try:
                # FIX: Use helper function to reduce N+1 queries
                conversation, error_response = get_conversation_with_access_check(int(conversation_id), request.user)
                if error_response:
                    return error_response
            except (ValueError, TypeError):
                return Response({'error': 'Invalid conversation_id'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Sanitize filename
            original_filename = file.name
            sanitized_filename = ContentSanitizer.sanitize_filename(original_filename)
            
            # Additional security: Validate file extension matches MIME type
            file_extension = os.path.splitext(sanitized_filename)[1].lower()
            expected_mime = mimetypes.guess_type(sanitized_filename)[0]
            if expected_mime and expected_mime != file.content_type:
                logger.warning("File MIME type mismatch: %s vs expected %s for %s", file.content_type, expected_mime, sanitized_filename)
                # Use the expected MIME type for validation instead of the provided one
                file.content_type = expected_mime
        except Exception as e:
            logger.error("Filename sanitization failed: %s", e)
            return Response({'error': 'Invalid filename'}, status=status.HTTP_400_BAD_REQUEST)

        # Enhanced file size validation with security checks
        file_category = get_file_category(file.content_type)
        if file_category == 'image':
            max_size = 10 * 1024 * 1024  # 10MB for images
        elif file_category in ['video', 'audio']:
            max_size = 50 * 1024 * 1024  # 50MB for media files
        else:
            max_size = 25 * 1024 * 1024  # 25MB for documents and other files
            
        # Validate file size
        if not SecurityValidator.validate_file_size(file.size, max_size // (1024*1024)):
            return Response({'error': f'File too large. Max size: {max_size // (1024*1024)}MB for {file_category} files'}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        # Additional security: Check for empty files
        if file.size == 0:
            return Response({'error': 'Empty files are not allowed'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate file content matches MIME type (magic number validation)
        try:
            file.seek(0)
            file_content = file.read(1024)  # Read first 1KB for signature check
            file.seek(0)  # Reset file pointer
            
            if not SecurityValidator.validate_file_content(file_content, file.content_type):
                logger.warning("File content validation failed for %s: MIME type %s", sanitized_filename, file.content_type)
                return Response({'error': 'File content does not match file type'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error("File content validation error: %s", e)
            return Response({'error': 'File validation failed'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate file type - Comprehensive list of supported document and media types
        allowed_types = [
            # Images
            'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp', 'image/bmp', 'image/tiff',
            
            # Documents - PDF
            'application/pdf',
            
            # Documents - Microsoft Word
            'application/msword',  # .doc
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # .docx
            
            # Documents - Microsoft Excel
            'application/vnd.ms-excel',  # .xls
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # .xlsx
            
            # Documents - Microsoft PowerPoint
            'application/vnd.ms-powerpoint',  # .ppt
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',  # .pptx
            
            # Text files
            'text/plain', 'text/csv', 'text/rtf',
            
            # OpenDocument formats
            'application/vnd.oasis.opendocument.text',  # .odt
            'application/vnd.oasis.opendocument.spreadsheet',  # .ods
            'application/vnd.oasis.opendocument.presentation',  # .odp
            
            # Compressed files
            'application/zip', 'application/x-rar-compressed', 'application/x-7z-compressed',
            
            # Audio files (for voice messages/documentation)
            'audio/mpeg', 'audio/wav', 'audio/mp3', 'audio/mp4', 'audio/ogg',
            
            # Video files (for documentation)
            'video/mp4', 'video/avi', 'video/quicktime', 'video/x-msvideo'
        ]
        if file.content_type not in allowed_types:
            return Response({'error': 'File type not allowed'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate file extension matches content type
        allowed_extensions = {
            'image/jpeg': ['.jpg', '.jpeg'],
            'image/png': ['.png'],
            'image/gif': ['.gif'],
            'image/webp': ['.webp'],
            'image/bmp': ['.bmp'],
            'image/tiff': ['.tiff', '.tif'],
            'application/pdf': ['.pdf'],
            'application/msword': ['.doc'],
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
            'application/vnd.ms-excel': ['.xls'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
            'application/vnd.ms-powerpoint': ['.ppt'],
            'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
            'text/plain': ['.txt'],
            'text/csv': ['.csv'],
            'text/rtf': ['.rtf'],
            'application/zip': ['.zip'],
            'application/x-rar-compressed': ['.rar'],
            'application/x-7z-compressed': ['.7z'],
            'audio/mpeg': ['.mp3'],
            'audio/wav': ['.wav'],
            'audio/mp4': ['.m4a'],
            'audio/ogg': ['.ogg'],
            'video/mp4': ['.mp4'],
            'video/avi': ['.avi'],
            'video/quicktime': ['.mov'],
            'video/x-msvideo': ['.avi'],
        }
        
        if file.content_type in allowed_extensions:
            if not SecurityValidator.validate_file_extension(sanitized_filename, allowed_extensions[file.content_type]):
                return Response({'error': 'File extension does not match file type'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Read file content for cloud storage
            file_content = file.read()
            file.seek(0)  # Reset file pointer
            
            # Upload to cloud storage
            upload_result = cloud_storage.upload_file(
                file_content=file_content,
                file_name=sanitized_filename,
                content_type=file.content_type,
                user_id=request.user.user_id
            )
            
            if not upload_result.get('success', False):
                logger.error(f"Cloud storage upload failed: {upload_result.get('error', 'Unknown error')}")
                return Response({'error': 'File upload failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Create attachment record with cloud storage info
            attachment = MessageAttachment.objects.create(
                file_name=sanitized_filename,
                file_type=file.content_type,
                file_size=file.size,
                file_key=upload_result['file_key'],  # Store S3 key or local path
                file_url=upload_result['file_url'],  # Store public URL
                storage_type=upload_result['storage_type'],  # 's3' or 'local'
            )
            
            # For local storage, also populate the legacy file field
            if upload_result['storage_type'] == 'local':
                # Save file to legacy FileField for compatibility
                file.seek(0)  # Reset file pointer
                attachment.file.save(sanitized_filename, file, save=True)
            
            # Determine file category for frontend display
            file_category = get_file_category(file.content_type)
            
            # Ensure proper URL construction
            file_url = attachment.file_url
            if not file_url and attachment.file:
                # Build absolute URL for local storage
                file_url = request.build_absolute_uri(attachment.file.url)
            
            return Response({
                'attachment_id': attachment.attachment_id,
                'file_name': attachment.file_name,
                'file_type': attachment.file_type,
                'file_category': file_category,
                'file_size': attachment.file_size,
                'file_url': file_url,
                'uploaded_at': attachment.uploaded_at.isoformat(),
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.exception("Attachment upload failed")
            return Response({'error': 'Upload failed', 'detail': str(e), 'type': e.__class__.__name__}, 
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def serve_file_with_ngrok_bypass(request, file_path):
    """
    Serve files with ngrok-skip-browser-warning header to bypass ngrok warning page
    """
    try:
        # Construct the full file path
        full_path = os.path.join(settings.MEDIA_ROOT, file_path)
        
        # Check if file exists
        if not os.path.exists(full_path):
            raise Http404("File not found")
        
        # Read the file
        with open(full_path, 'rb') as f:
            file_content = f.read()
        
        # Determine content type
        import mimetypes
        content_type, _ = mimetypes.guess_type(full_path)
        if not content_type:
            content_type = 'application/octet-stream'
        
        # Create response with ngrok bypass header
        response = HttpResponse(file_content, content_type=content_type)
        response['ngrok-skip-browser-warning'] = 'true'
        
        # Check for mobile download parameters
        download_param = request.GET.get('download')
        bypass_param = request.GET.get('bypass')
        ua_param = request.GET.get('ua')
        
        if download_param == '1' or bypass_param == '1' or ua_param == 'mobile':
            # Force download for mobile devices
            response['Content-Disposition'] = f'attachment; filename="{os.path.basename(full_path)}"'
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        else:
            # Default behavior
            response['Content-Disposition'] = f'attachment; filename="{os.path.basename(full_path)}"'
        
        return response
        
    except Exception as e:
        logger.exception(f"Error serving file {file_path}")
        raise Http404("File not found")
