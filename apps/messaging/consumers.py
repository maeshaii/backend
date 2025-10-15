import json
import logging
import time
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from apps.shared.models import Message, Conversation, User
from apps.shared.security import ContentSanitizer
from .connection_manager import connection_manager
from .message_ordering import message_sequencer
from .rate_limiter import rate_limiter, connection_pool
from .monitoring import messaging_monitor, track_performance, PerformanceTracker
from .performance_metrics import performance_metrics, PerformanceTracker as PerfTracker

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
		
		# Start performance tracking for WebSocket connection
		connection_stages = {'connection_start': time.time()}
		
		# Log connection attempt
		logger.info(f"WebSocket connection attempt from user {getattr(self.user, 'user_id', None)} to conversation {self.conversation_id}")
		
		# Check connection rate limiting
		ip_address = self.scope.get('client', [None])[0] if self.scope.get('client') else None
		can_connect, rate_info = await database_sync_to_async(connection_pool.can_create_connection)(
			getattr(self.user, 'user_id', None)
		)
		
		connection_stages['rate_limit_check'] = time.time()
		
		if not can_connect:
			logger.warning(f"Connection rate limited for user {getattr(self.user, 'user_id', None)}: {rate_info}")
			# Accept connection first, then send error message
			await self.accept()
			await self.send(text_data=json.dumps({
				'type': 'connection_denied',
				'reason': rate_info.get('reason', 'rate_limit_exceeded'),
				'retry_after': rate_info.get('retry_after', 60),
				'message': 'Too many connections. Please try again later.'
			}))
			await self.close()
			return
		
		# Verify user has access and role
		if not await self.can_access_conversation():
			logger.warning(f"User {getattr(self.user, 'user_id', None)} denied access to conversation {self.conversation_id}")
			await self.close()
			return
		
		connection_stages['access_check'] = time.time()
		
		# Join conversation room
		await self.channel_layer.group_add(
			f"chat_{self.conversation_id}",
			self.channel_name
		)
		await self.accept()
		
		connection_stages['websocket_accepted'] = time.time()
		
		# Add connection to pool
		await database_sync_to_async(connection_pool.add_connection)(
			getattr(self.user, 'user_id', None),
			self.channel_name
		)
		
		# Add connection to Redis tracking
		connection_metadata = {
			'ip_address': self.scope.get('client', [None])[0] if self.scope.get('client') else None,
			'user_agent': dict(self.scope.get('headers', [])).get(b'user-agent', b'').decode('utf-8', errors='ignore'),
		}
		
		await database_sync_to_async(connection_manager.add_connection)(
			getattr(self.user, 'user_id', None),
			self.conversation_id,
			self.channel_name,
			connection_metadata
		)
		
		# Send connection confirmation
		await self.send(text_data=json.dumps({
			'type': 'connection_established',
			'conversation_id': self.conversation_id,
			'user_id': getattr(self.user, 'user_id', None),
			'timestamp': timezone.now().isoformat(),
		}))
		
		connection_stages['connection_complete'] = time.time()
		
		# Track WebSocket connection performance
		await database_sync_to_async(performance_metrics.track_websocket_connection_performance)(
			self.channel_name,
			connection_stages,
			getattr(self.user, 'user_id', None)
		)
		
		# Track WebSocket connection
		await database_sync_to_async(messaging_monitor.track_websocket_event)(
			'connected',
			getattr(self.user, 'user_id', None),
			self.conversation_id,
			{
				'channel_name': self.channel_name,
				'ip_address': connection_metadata.get('ip_address'),
				'user_agent': connection_metadata.get('user_agent')
			}
		)
		
		logger.info(f"WebSocket connected: user {getattr(self.user, 'user_id', None)} to conversation {self.conversation_id}")

	async def disconnect(self, close_code):
		"""Handle WebSocket disconnection"""
		# Remove connection from pool
		await database_sync_to_async(connection_pool.remove_connection)(
			getattr(self.user, 'user_id', None),
			self.channel_name
		)
		
		# Remove connection from Redis tracking
		await database_sync_to_async(connection_manager.remove_connection)(self.channel_name)
		
		# Leave conversation room
		await self.channel_layer.group_discard(
			f"chat_{self.conversation_id}",
			self.channel_name
		)
		
		# Track WebSocket disconnection
		await database_sync_to_async(messaging_monitor.track_websocket_event)(
			'disconnected',
			getattr(self.user, 'user_id', None),
			self.conversation_id,
			{
				'channel_name': self.channel_name,
				'close_code': close_code
			}
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
		try:
			# Start performance tracking for message handling
			message_stages = {'message_received': time.time()}
			
			# Check message rate limiting
			can_send, rate_info = await database_sync_to_async(rate_limiter.check_message_rate_limit)(
				getattr(self.user, 'user_id', None),
				self.conversation_id
			)
			
			message_stages['rate_limit_check'] = time.time()
			
			if not can_send:
				logger.warning(f"Message rate limited for user {getattr(self.user, 'user_id', None)}: {rate_info}")
				await self.send(text_data=json.dumps({
					'type': 'rate_limit_exceeded',
					'reason': rate_info.get('reason', 'message_rate_limit_exceeded'),
					'retry_after': rate_info.get('retry_after', 60),
					'message': 'Message rate limit exceeded. Please slow down.'
				}))
				return
			
			# Sanitize and validate message content
			raw_content = data.get('message', '')
			message_content = ContentSanitizer.sanitize_message_content(raw_content)
			
			# Sanitize and validate message type
			raw_message_type = data.get('message_type', 'text')
			message_type = ContentSanitizer.validate_message_type(raw_message_type)
			
		except Exception as e:
			await self.send(text_data=json.dumps({
				'type': 'error',
				'message': f'Invalid message: {str(e)}'
			}))
			return
		
		message_stages['validation_complete'] = time.time()
		
		# Save message to database
		message = await self.save_message(message_content, message_type)
		
		message_stages['message_saved'] = time.time()
		
		# Create message metadata with sequencing
		message_metadata = await database_sync_to_async(message_sequencer.create_message_metadata)(
			message.message_id,
			self.conversation_id,
			getattr(self.user, 'user_id', None),
			message.content,
			message.message_type
		)
		
		message_stages['sequencing_complete'] = time.time()
		
		# Broadcast to all users in the conversation with sequencing info
		await self.channel_layer.group_send(
			f"chat_{self.conversation_id}",
			{
				'type': 'chat_message',
				'message_id': message.message_id,
				'sequence_number': message_metadata.get('sequence_number'),
				'content': message.content,
				'sender_id': getattr(self.user, 'user_id', None),
				'sender_name': getattr(self.user, 'full_name', ''),
				'message_type': message.message_type,
				'created_at': message.created_at.isoformat(),
				'timestamp': timezone.now().isoformat(),
				'microsecond_timestamp': message_metadata.get('microsecond_timestamp'),
			}
		)
		
		message_stages['broadcast_complete'] = time.time()
		
		# Track message delivery performance
		await database_sync_to_async(performance_metrics.track_message_delivery_performance)(
			message.message_id,
			message_stages,
			getattr(self.user, 'user_id', None),
			self.conversation_id
		)
		
		logger.info(f"Message sent: {message.message_id} by user {getattr(self.user, 'user_id', None)}")

	async def handle_typing(self, data):
		"""Handle typing indicators"""
		is_typing = data.get('is_typing', False)
		
		# Check typing rate limiting
		can_type, rate_info = await database_sync_to_async(rate_limiter.check_typing_rate_limit)(
			getattr(self.user, 'user_id', None),
			self.conversation_id
		)
		
		if not can_type:
			logger.warning(f"Typing rate limited for user {getattr(self.user, 'user_id', None)}: {rate_info}")
			# Don't send error message for typing rate limits to avoid spam
			return
		
		# Update user presence in Redis
		status = 'typing' if is_typing else 'online'
		await database_sync_to_async(connection_manager.update_user_presence)(
			getattr(self.user, 'user_id', None),
			self.conversation_id,
			status
		)
		
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
			'attachment_url': event['attachment_url'],
			'attachment_info': event.get('attachment_info'),
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

	async def presence_update(self, event):
		"""Handle presence updates from Redis connection manager"""
		await self.send(text_data=json.dumps({
			'type': 'presence_update',
			'user_id': event['user_id'],
			'conversation_id': event['conversation_id'],
			'status': event['status'],
			'timestamp': event['timestamp'],
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
		"""Allow access if the user is a participant of the conversation."""
		try:
			conversation = Conversation.objects.get(conversation_id=self.conversation_id)
			return conversation.participants.filter(user_id=getattr(self.user, 'user_id', None)).exists()
		except Conversation.DoesNotExist:
			return False
