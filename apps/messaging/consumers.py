import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from apps.shared.models import Message, Conversation, User

logger = logging.getLogger(__name__)

class ChatConsumer(AsyncWebsocketConsumer):
	"""
	WebSocket consumer for real-time chat functionality.
	Handles message sending, typing indicators, and read receipts.
	"""
	
	async def connect(self):
		"""Handle WebSocket connection"""
		self.user = self.scope['user']
		self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
		
		# Log connection attempt
		logger.info(f"WebSocket connection attempt from user {getattr(self.user, 'user_id', None)} to conversation {self.conversation_id}")
		
		# Verify user has access and role
		if not await self.can_access_conversation():
			logger.warning(f"User {getattr(self.user, 'user_id', None)} denied access to conversation {self.conversation_id}")
			await self.close()
			return
		
		# Join conversation room
		await self.channel_layer.group_add(
			f"chat_{self.conversation_id}",
			self.channel_name
		)
		await self.accept()
		
		# Send connection confirmation
		await self.send(text_data=json.dumps({
			'type': 'connection_established',
			'conversation_id': self.conversation_id,
			'user_id': getattr(self.user, 'user_id', None),
			'timestamp': timezone.now().isoformat(),
		}))
		
		logger.info(f"WebSocket connected: user {getattr(self.user, 'user_id', None)} to conversation {self.conversation_id}")

	async def disconnect(self, close_code):
		"""Handle WebSocket disconnection"""
		# Leave conversation room
		await self.channel_layer.group_discard(
			f"chat_{self.conversation_id}",
			self.channel_name
		)
		
		logger.info(f"WebSocket disconnected: user {getattr(self.user, 'user_id', None)} from conversation {self.conversation_id}")

	async def receive(self, text_data):
		"""Handle incoming WebSocket messages"""
		try:
			data = json.loads(text_data)
			message_type = data.get('type', 'message')
			
			if message_type == 'message':
				await self.handle_message(data)
			elif message_type == 'typing':
				await self.handle_typing(data)
			elif message_type == 'read_receipt':
				await self.handle_read_receipt(data)
			elif message_type == 'ping':
				await self.handle_ping(data)
			else:
				await self.send(text_data=json.dumps({
					'type': 'error',
					'message': f'Unknown message type: {message_type}'
				}))
				
		except json.JSONDecodeError as e:
			logger.error(f"JSON decode error: {e}")
			await self.send(text_data=json.dumps({
				'type': 'error',
				'message': 'Invalid JSON format'
			}))
		except Exception as e:
			logger.error(f"Error processing message: {e}")
			await self.send(text_data=json.dumps({
				'type': 'error',
				'message': 'Internal server error'
			}))

	async def handle_message(self, data):
		"""Handle incoming chat messages"""
		message_content = data.get('message', '').strip()
		message_type = data.get('message_type', 'text')
		
		if not message_content:
			await self.send(text_data=json.dumps({
				'type': 'error',
				'message': 'Message content cannot be empty'
			}))
			return
		
		# Validate message type
		valid_types = ['text', 'image', 'file', 'system']
		if message_type not in valid_types:
			await self.send(text_data=json.dumps({
				'type': 'error',
				'message': f'Invalid message type. Must be one of: {", ".join(valid_types)}'
			}))
			return
		
		# Save message to database
		message = await self.save_message(message_content, message_type)
		
		# Broadcast to all users in the conversation
		await self.channel_layer.group_send(
			f"chat_{self.conversation_id}",
			{
				'type': 'chat_message',
				'message_id': message.message_id,
				'content': message.content,
				'sender_id': getattr(self.user, 'user_id', None),
				'sender_name': getattr(self.user, 'full_name', ''),
				'message_type': message.message_type,
				'created_at': message.created_at.isoformat(),
				'timestamp': timezone.now().isoformat(),
			}
		)
		
		logger.info(f"Message sent: {message.message_id} by user {getattr(self.user, 'user_id', None)}")

	async def handle_typing(self, data):
		"""Handle typing indicators"""
		is_typing = data.get('is_typing', False)
		
		await self.channel_layer.group_send(
			f"chat_{self.conversation_id}",
			{
				'type': 'user_typing',
				'user_id': getattr(self.user, 'user_id', None),
				'user_name': getattr(self.user, 'full_name', ''),
				'is_typing': is_typing,
				'timestamp': timezone.now().isoformat(),
			}
		)

	async def handle_read_receipt(self, data):
		"""Handle read receipts"""
		message_id = data.get('message_id')
		if message_id:
			await self.mark_message_as_read(message_id)
			
			await self.channel_layer.group_send(
				f"chat_{self.conversation_id}",
				{
					'type': 'read_receipt',
					'message_id': message_id,
					'read_by': getattr(self.user, 'user_id', None),
					'read_at': timezone.now().isoformat(),
				}
			)

	async def handle_ping(self, data):
		"""Handle ping messages for connection health check"""
		await self.send(text_data=json.dumps({
			'type': 'pong',
			'timestamp': timezone.now().isoformat(),
		}))

	async def chat_message(self, event):
		"""Send message to WebSocket"""
		await self.send(text_data=json.dumps({
			'type': 'message',
			'message_id': event['message_id'],
			'content': event['content'],
			'sender_id': event['sender_id'],
			'sender_name': event['sender_name'],
			'message_type': event['message_type'],
			'created_at': event['created_at'],
			'timestamp': event['timestamp'],
		}))

	async def user_typing(self, event):
		"""Send typing indicator to WebSocket"""
		await self.send(text_data=json.dumps({
			'type': 'typing',
			'user_id': event['user_id'],
			'user_name': event['user_name'],
			'is_typing': event['is_typing'],
			'timestamp': event['timestamp'],
		}))

	async def read_receipt(self, event):
		"""Send read receipt to WebSocket"""
		await self.send(text_data=json.dumps({
			'type': 'read_receipt',
			'message_id': event['message_id'],
			'read_by': event['read_by'],
			'read_at': event['read_at'],
		}))

	@database_sync_to_async
	def save_message(self, content, message_type):
		"""Save message to database"""
		conversation = Conversation.objects.get(conversation_id=self.conversation_id)
		message = Message.objects.create(
			conversation=conversation,
			sender=self.user,
			content=content,
			message_type=message_type,
		)
		conversation.save()
		return message

	@database_sync_to_async
	def mark_message_as_read(self, message_id):
		"""Mark a message as read"""
		try:
			message = Message.objects.get(
				message_id=message_id,
				conversation__conversation_id=self.conversation_id,
			)
			message.is_read = True
			message.save()
		except Message.DoesNotExist:
			logger.warning(f"Message {message_id} not found")

	@database_sync_to_async
	def can_access_conversation(self):
		"""Check if user has access to the conversation and is alumni/OJT"""
		try:
			if not getattr(self.user, 'account_type', None):
				return False
			role_ok = bool(getattr(self.user.account_type, 'alumni', False) or getattr(self.user.account_type, 'ojt', False))
			if not role_ok:
				return False
			conversation = Conversation.objects.get(conversation_id=self.conversation_id)
			return conversation.participants.filter(user_id=getattr(self.user, 'user_id', None)).exists()
		except Conversation.DoesNotExist:
			return False
