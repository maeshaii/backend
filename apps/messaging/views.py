from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.utils import timezone
from apps.shared.models import Conversation, Message, User
from apps.shared.serializers import (
	ConversationSerializer,
	MessageSerializer,
	CreateConversationSerializer,
	MessageCreateSerializer,
)
from .permissions import IsAlumniOrOJT


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
		return Message.objects.filter(conversation=conversation)

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
