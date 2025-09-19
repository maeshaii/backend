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
					models.Q(created_at__lt=cursor_msg.created_at) |
					models.Q(created_at=cursor_msg.created_at, message_id__lt=cursor_msg.message_id)
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
		message = serializer.save(conversation=conversation, sender=request.user)
		conversation.save()
		response_serializer = MessageSerializer(message)
		return Response(response_serializer.data, status=status.HTTP_201_CREATED)

	def list(self, request, *args, **kwargs):
		queryset = self.get_queryset()
		serializer = MessageSerializer(queryset, many=True)

		# Compute next_cursor (older messages still exist?)
		conversation_id = self.kwargs['conversation_id']
		conversation = get_object_or_404(Conversation, conversation_id=conversation_id)
		next_cursor = None
		if queryset:
			last = queryset[-1]
			remaining = Message.objects.filter(conversation=conversation).filter(
				models.Q(created_at__lt=last.created_at) |
				models.Q(created_at=last.created_at, message_id__lt=last.message_id)
			).exists()
			if remaining:
				next_cursor = last.message_id

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
		Q(account_type__alumni=True) | Q(account_type__ojt=True),
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

		# Validate file size (10MB for images, 25MB for other files)
		max_size = 10 * 1024 * 1024 if file.content_type.startswith('image/') else 25 * 1024 * 1024
		if file.size > max_size:
			return Response({'error': f'File too large. Max size: {max_size // (1024*1024)}MB'}, 
							status=status.HTTP_400_BAD_REQUEST)

		# Validate file type
		allowed_types = [
			'image/jpeg', 'image/png', 'image/gif', 'image/webp',
			'application/pdf', 'text/plain', 'application/msword',
			'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
		]
		if file.content_type not in allowed_types:
			return Response({'error': 'File type not allowed'}, status=status.HTTP_400_BAD_REQUEST)

		try:
			# Generate unique filename
			file_extension = os.path.splitext(file.name)[1]
			unique_filename = f"{uuid.uuid4()}{file_extension}"
			
			# Save file
			file_path = default_storage.save(f'message_attachments/{unique_filename}', file)
			file_url = default_storage.url(file_path)

			# Create attachment record
			attachment = MessageAttachment.objects.create(
				file=file_path,
				file_name=file.name,
				file_type=file.content_type,
				file_size=file.size,
			)

			return Response({
				'attachment_id': attachment.attachment_id,
				'file_name': attachment.file_name,
				'file_type': attachment.file_type,
				'file_size': attachment.file_size,
				'file_url': file_url,
				'uploaded_at': attachment.uploaded_at.isoformat(),
			}, status=status.HTTP_201_CREATED)

		except Exception as e:
			return Response({'error': f'Upload failed: {str(e)}'}, 
							status=status.HTTP_500_INTERNAL_SERVER_ERROR)
