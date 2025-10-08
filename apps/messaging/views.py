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
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging
from apps.shared.models import Conversation, Message, MessageAttachment, User
from apps.shared.serializers import (
	ConversationSerializer,
	MessageSerializer,
	CreateConversationSerializer,
	MessageCreateSerializer,
)
from .permissions import IsAlumniOrOJT
import os
import uuid
import mimetypes

logger = logging.getLogger(__name__)


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

    def get_queryset(self):
        return Conversation.objects.filter(participants=self.request.user)

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

        qs = Message.objects.filter(conversation=conversation).order_by('-created_at', '-message_id')

        # Cursor pagination: use `cursor` as message_id to fetch older messages
        cursor = self.request.query_params.get('cursor')
        if cursor:
            try:
                cursor_msg = Message.objects.get(message_id=int(cursor), conversation=conversation)
                qs = qs.filter(
                    Q(created_at__lt=cursor_msg.created_at) |
                    Q(created_at=cursor_msg.created_at, message_id__lt=cursor_msg.message_id)
                )
            except Exception:
                pass

        limit = self.request.query_params.get('limit')
        try:
            limit_val = max(1, min(int(limit or 50), 100))
        except Exception:
            limit_val = 50

        return qs[:limit_val]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return MessageCreateSerializer
        return MessageSerializer

    def create(self, request, *args, **kwargs):
        conversation_id = self.kwargs['conversation_id']
        conversation = get_object_or_404(Conversation, conversation_id=conversation_id)
        if not conversation.participants.filter(user_id=request.user.user_id).exists():
            return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Determine receiver for 1:1 conversations to satisfy legacy non-null column
        receiver = conversation.participants.exclude(user_id=request.user.user_id).first()
        # Ensure legacy DB columns are populated (e.g., date_send)
        message = serializer.save(
            conversation=conversation,
            sender=request.user,
            receiver=receiver,
            created_at=timezone.now(),
        )
        # Link uploaded attachment if provided
        try:
            attachment_id = request.data.get('attachment_id')
            if attachment_id:
                attachment = get_object_or_404(MessageAttachment, attachment_id=int(attachment_id))
                attachment.message = message
                attachment.save()
        except Exception:
            pass
        # Ensure legacy column date_send is populated for existing schema
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                # Backfill legacy date_send if DB still missing it (older schema)
                cursor.execute(
                    "UPDATE shared_message SET date_send = NOW() WHERE message_id = %s AND (date_send IS NULL)",
                    [message.message_id],
                )
                # Backfill legacy 'content' column to mirror message_content for older schemas
                cursor.execute(
                    "UPDATE shared_message SET content = %s WHERE message_id = %s AND (content IS NULL)",
                    [message.content, message.message_id],
                )
        except Exception:
            pass

        # Broadcast the new message to websocket listeners
        try:
            # Get attachment details if exists
            attachment_url = None
            attachment_info = None
            if hasattr(message, 'attachments') and message.attachments.exists():
                attachment = message.attachments.first()
                if attachment and attachment.file:
                    attachment_url = attachment.file.url
                    # Include attachment info for frontend
                    attachment_info = {
                        'file_name': attachment.file_name,
                        'file_type': attachment.file_type,
                        'file_category': get_file_category(attachment.file_type),
                        'file_size': attachment.file_size,
                    }
            
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"chat_{conversation.conversation_id}",
                {
                    'type': 'chat_message',
                    'message_id': message.message_id,
                    'content': message.content,
                    'sender_id': request.user.user_id,
                    'sender_name': getattr(request.user, 'full_name', ''),
                    'message_type': message.message_type,
                    'created_at': message.created_at.isoformat(),
                    'timestamp': timezone.now().isoformat(),
                    'attachment_url': attachment_url,
                    'attachment_info': attachment_info,
                },
            )
        except Exception:
            pass
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
        except Exception:
            next_cursor = None

        return Response({
            'results': serializer.data[::-1],  # return ascending for UI
            'next_cursor': next_cursor,
        })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAlumniOrOJT])
def mark_conversation_as_read(request, conversation_id):
	conversation = get_object_or_404(Conversation, conversation_id=conversation_id)
	if not conversation.participants.filter(user_id=request.user.user_id).exists():
		return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
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
		Q(account_type__user=True) | Q(account_type__ojt=True),
		user_status='active',
	).exclude(user_id=request.user.user_id).distinct()[:10]
	from apps.shared.serializers import UserSerializer
	serializer = UserSerializer(users, many=True)
	return Response({'users': serializer.data, 'count': len(users), 'query': query})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAlumniOrOJT])
def conversation_detail(request, conversation_id):
	conversation = get_object_or_404(Conversation, conversation_id=conversation_id)
	if not conversation.participants.filter(user_id=request.user.user_id).exists():
		return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
	serializer = ConversationSerializer(conversation, context={'request': request})
	return Response(serializer.data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsAlumniOrOJT])
def delete_message(request, conversation_id, message_id):
	conversation = get_object_or_404(Conversation, conversation_id=conversation_id)
	if not conversation.participants.filter(user_id=request.user.user_id).exists():
		return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
	message = get_object_or_404(Message, message_id=message_id, conversation=conversation)
	if message.sender.user_id != request.user.user_id:
		return Response({'error': 'You can only delete your own messages'}, status=status.HTTP_403_FORBIDDEN)
	message.delete()
	return Response({'status': 'success', 'message': 'Message deleted successfully'})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAlumniOrOJT])
def messaging_stats(request):
	user = request.user
	total_conversations = Conversation.objects.filter(participants=user).count()
	total_messages_sent = Message.objects.filter(sender=user).count()
	total_unread = 0
	for conversation in Conversation.objects.filter(participants=user):
		total_unread += conversation.get_unread_count(user)
	recent_conversations = Conversation.objects.filter(participants=user).order_by('-updated_at')[:5]
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

        # Additional security: Validate file extension matches MIME type
        file_extension = os.path.splitext(file.name)[1].lower()
        expected_mime = mimetypes.guess_type(file.name)[0]
        if expected_mime and expected_mime != file.content_type:
            logger.warning("File MIME type mismatch: %s vs expected %s for %s", file.content_type, expected_mime, file.name)
            # Use the expected MIME type for validation instead of the provided one
            file.content_type = expected_mime

        # Validate file size based on category (10MB for images, 25MB for other files, 50MB for videos)
        file_category = get_file_category(file.content_type)
        if file_category == 'image':
            max_size = 10 * 1024 * 1024  # 10MB for images
        elif file_category in ['video', 'audio']:
            max_size = 50 * 1024 * 1024  # 50MB for media files
        else:
            max_size = 25 * 1024 * 1024  # 25MB for documents and other files
            
        if file.size > max_size:
            return Response({'error': f'File too large. Max size: {max_size // (1024*1024)}MB for {file_category} files'}, 
                            status=status.HTTP_400_BAD_REQUEST)

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

        try:
            # Let FileField handle storage
            attachment = MessageAttachment.objects.create(
                file=file,
                file_name=file.name,
                file_type=file.content_type,
                file_size=file.size,
            )
            
            # Determine file category for frontend display
            file_category = get_file_category(file.content_type)
            
            return Response({
                'attachment_id': attachment.attachment_id,
                'file_name': attachment.file_name,
                'file_type': attachment.file_type,
                'file_category': file_category,
                'file_size': attachment.file_size,
                'file_url': attachment.file.url if attachment.file else None,
                'uploaded_at': attachment.uploaded_at.isoformat(),
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.exception("Attachment upload failed")
            return Response({'error': 'Upload failed', 'detail': str(e), 'type': e.__class__.__name__}, 
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
