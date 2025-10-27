import json
import logging
import time
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from apps.shared.models import Message, Conversation, User, Notification
from apps.shared.security import ContentSanitizer
from .connection_manager import connection_manager
from .message_ordering import message_sequencer
from .rate_limiter import rate_limiter, connection_pool
from .monitoring import messaging_monitor, track_performance, PerformanceTracker
from .performance_metrics import performance_metrics, PerformanceTracker as PerfTracker
from .views import get_file_category

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
		if not self.user or not hasattr(self.user, 'user_id'):
			logger.warning(f"Invalid user for WebSocket connection: {self.user}")
			await self.accept()
			await self.send(text_data=json.dumps({
				'type': 'connection_denied',
				'reason': 'invalid_user',
				'message': 'Invalid user session'
			}))
			await self.close()
			return
		
		# Check if user has access to this conversation
		has_access = await database_sync_to_async(self._check_conversation_access)()
		if not has_access:
			logger.warning(f"User {getattr(self.user, 'user_id', None)} denied access to conversation {self.conversation_id}")
			await self.accept()
			await self.send(text_data=json.dumps({
				'type': 'connection_denied',
				'reason': 'access_denied',
				'message': 'You do not have access to this conversation'
			}))
			await self.close()
			return
		
		# Accept the connection
		await self.accept()
		
		# Join conversation room
		await self.channel_layer.group_add(
			f"chat_{self.conversation_id}",
			self.channel_name
		)
		
		# Store connection metadata
		# Extract user-agent from headers (headers is a list of tuples)
		user_agent = b''
		headers = self.scope.get('headers', [])
		for header_name, header_value in headers:
			if header_name.lower() == b'user-agent':
				user_agent = header_value
				break
		
		connection_metadata = {
			'user_id': getattr(self.user, 'user_id', None),
			'conversation_id': self.conversation_id,
			'ip_address': ip_address,
			'user_agent': user_agent.decode('utf-8', errors='ignore'),
			'connected_at': timezone.now().isoformat()
		}
		
		# Add connection to pool
		await database_sync_to_async(connection_pool.add_connection)(
			getattr(self.user, 'user_id', None),
			self.channel_name
		)
		
		# Add connection to Redis tracking
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
		try:
			# Remove connection from pool
			await database_sync_to_async(connection_pool.remove_connection)(
				getattr(self.user, 'user_id', None),
				self.channel_name
			)
		except Exception as e:
			logger.warning(f"Failed to remove connection from pool: {e}")
		
		try:
			# Remove connection from Redis tracking
			await database_sync_to_async(connection_manager.remove_connection)(self.channel_name)
		except Exception as e:
			logger.warning(f"Failed to remove connection from manager: {e}")
		
		try:
			# Leave conversation room
			await self.channel_layer.group_discard(
				f"chat_{self.conversation_id}",
				self.channel_name
			)
		except Exception as e:
			logger.warning(f"Failed to leave conversation room: {e}")
		
		try:
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
		except Exception as e:
			logger.warning(f"Failed to track disconnection: {e}")
		
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
					'type': 'rate_limited',
					'reason': rate_info.get('reason', 'rate_limit_exceeded'),
					'retry_after': rate_info.get('retry_after', 60),
					'message': 'Message rate limit exceeded. Please slow down.'
				}))
				return
			
			# Validate and sanitize message content
			content = data.get('content', '').strip()
			if not content:
				await self.send(text_data=json.dumps({
					'type': 'error',
					'message': 'Message content cannot be empty'
				}))
				return
			
			# Sanitize content
			sanitizer = ContentSanitizer()
			content = sanitizer.sanitize_text(content)
			
			# Validate message type
			message_type = data.get('message_type', 'text')
			if not sanitizer.validate_message_type(message_type):
				await self.send(text_data=json.dumps({
					'type': 'error',
					'message': 'Invalid message type'
				}))
				return
			
			message_stages['validation_complete'] = time.time()
			
			# Create message in database
			message_data = await database_sync_to_async(self._create_message)(
				content, message_type, data.get('attachments', [])
			)
			
			message_stages['database_save'] = time.time()
			
			if not message_data:
				await self.send(text_data=json.dumps({
					'type': 'error',
					'message': 'Failed to save message'
				}))
				return
			
			# Broadcast message to conversation group
			await self.channel_layer.group_send(
				f"chat_{self.conversation_id}",
				{
					'type': 'chat_message',
					'message': message_data
				}
			)
			
			message_stages['broadcast_complete'] = time.time()
			
			# Track message performance
			await database_sync_to_async(performance_metrics.track_message_performance)(
				self.channel_name,
				message_stages,
				getattr(self.user, 'user_id', None),
				message_data.get('message_id')
			)
			
			# Track message event
			await database_sync_to_async(messaging_monitor.track_message_event)(
				'message_sent',
				getattr(self.user, 'user_id', None),
				self.conversation_id,
				{
					'message_id': message_data.get('message_id'),
					'message_type': message_type,
					'content_length': len(content)
				}
			)
			
		except Exception as e:
			logger.error(f"Error handling message: {e}")
			await self.send(text_data=json.dumps({
				'type': 'error',
				'message': 'Failed to process message'
			}))

	async def handle_typing(self, data):
		"""Handle typing indicators"""
		try:
			is_typing = data.get('is_typing', False)
			
			# Broadcast typing indicator to conversation group
			await self.channel_layer.group_send(
				f"chat_{self.conversation_id}",
				{
					'type': 'typing_indicator',
					'user_id': getattr(self.user, 'user_id', None),
					'user_name': getattr(self.user, 'full_name', 'Unknown'),
					'is_typing': is_typing
				}
			)
			
		except Exception as e:
			logger.error(f"Error handling typing indicator: {e}")

	async def handle_read_receipt(self, data):
		"""Handle read receipts"""
		try:
			message_id = data.get('message_id')
			if not message_id:
				return
			
			# Update read status in database
			await database_sync_to_async(self._mark_message_as_read)(message_id)
			
			# Broadcast read receipt to conversation group
			await self.channel_layer.group_send(
				f"chat_{self.conversation_id}",
				{
					'type': 'read_receipt',
					'message_id': message_id,
					'user_id': getattr(self.user, 'user_id', None),
					'read_at': timezone.now().isoformat()
				}
			)
			
		except Exception as e:
			logger.error(f"Error handling read receipt: {e}")

	async def handle_ping(self, data):
		"""Handle ping/pong for connection health"""
		await self.send(text_data=json.dumps({
			'type': 'pong',
			'timestamp': timezone.now().isoformat()
		}))

	async def chat_message(self, event):
		"""Handle chat message from group"""
		# Handle both old and new message formats
		message = event.get('message') or event.get('data', {})
		await self.send(text_data=json.dumps({
			'type': 'message',
			'message': message
		}))

	async def presence_update(self, event):
		"""Handle presence update from group"""
		await self.send(text_data=json.dumps({
			'type': 'presence_update',
			'user_id': event.get('user_id'),
			'status': event.get('status', 'online'),
			'timestamp': timezone.now().isoformat()
		}))

	async def typing_indicator(self, event):
		"""Handle typing indicator from group"""
		await self.send(text_data=json.dumps({
			'type': 'typing',
			'user_id': event['user_id'],
			'user_name': event['user_name'],
			'is_typing': event['is_typing']
		}))

	async def read_receipt(self, event):
		"""Handle read receipt from group"""
		await self.send(text_data=json.dumps({
			'type': 'read_receipt',
			'message_id': event['message_id'],
			'user_id': event['user_id'],
			'read_at': event['read_at']
		}))

	def _check_conversation_access(self):
		"""Check if user has access to conversation"""
		try:
			conversation = Conversation.objects.get(conversation_id=self.conversation_id)
			return conversation.participants.filter(user_id=self.user.user_id).exists()
		except Conversation.DoesNotExist:
			return False

	def _create_message(self, content, message_type, attachments):
		"""Create message in database"""
		try:
			conversation = Conversation.objects.get(conversation_id=self.conversation_id)
			
			# Convert message request to regular conversation when someone replies
			if conversation.is_message_request:
				conversation.is_message_request = False
				conversation.save()
				logger.info(f"Converted message request {self.conversation_id} to regular conversation via WebSocket")
			
			# Create message
			message = Message.objects.create(
				conversation=conversation,
				sender=self.user,
				content=content,
				message_type=message_type
			)
			
			# Handle attachments
			for attachment_data in attachments:
				# Process attachment logic here
				pass
			
			# Return message data for broadcasting
			return {
				'message_id': message.message_id,
				'sender_id': message.sender.user_id,
				'sender_name': message.sender.full_name,
				'content': message.content,
				'message_type': message.message_type,
				'created_at': message.created_at.isoformat(),
				'attachments': []
			}
			
		except Exception as e:
			logger.error(f"Error creating message: {e}")
			return None

	def _mark_message_as_read(self, message_id):
		"""Mark message as read"""
		try:
			message = Message.objects.get(message_id=message_id)
			# Update read status logic here
			pass
		except Message.DoesNotExist:
			pass


class NotificationConsumer(AsyncWebsocketConsumer):
	"""
	WebSocket consumer for real-time notifications.
	Handles notification broadcasting and real-time updates.
	"""
	
	async def connect(self):
		"""Handle WebSocket connection for notifications"""
		self.user = self.scope['user']
		
		# Log connection attempt
		logger.info(f"Notification WebSocket connection attempt from user {getattr(self.user, 'user_id', None)}")
		logger.info(f"User object: {self.user}")
		logger.info(f"User type: {type(self.user)}")
		
		# Check if user is authenticated
		if not self.user or not hasattr(self.user, 'user_id'):
			logger.warning(f"Invalid user for notification WebSocket: {self.user}")
			await self.accept()
			await self.send(text_data=json.dumps({
				'type': 'connection_denied',
				'reason': 'invalid_user',
				'message': 'Invalid user session'
			}))
			await self.close()
			return
		
		# Accept the connection
		await self.accept()
		
		# Join user-specific notification room
		user_id = getattr(self.user, 'user_id', None)
		group_name = f"notifications_{user_id}"
		logger.info(f"Adding user {user_id} to notification group: {group_name}")
		
		await self.channel_layer.group_add(
			group_name,
			self.channel_name
		)
		
		# Send connection confirmation
		await self.send(text_data=json.dumps({
			'type': 'connection_established',
			'user_id': user_id,
			'timestamp': timezone.now().isoformat(),
		}))
		
		logger.info(f"Notification WebSocket connected: user {user_id}, channel: {self.channel_name}")

	async def disconnect(self, close_code):
		"""Handle WebSocket disconnection"""
		user_id = getattr(self.user, 'user_id', None)
		
		# Leave notification room
		await self.channel_layer.group_discard(
			f"notifications_{user_id}",
			self.channel_name
		)
		
		logger.info(f"Notification WebSocket disconnected: user {user_id}")

	async def receive(self, text_data):
		"""Handle incoming WebSocket messages"""
		try:
			data = json.loads(text_data)
			message_type = data.get('type', 'ping')
			
			if message_type == 'ping':
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
			logger.error(f"Error processing notification message: {e}")
			await self.send(text_data=json.dumps({
				'type': 'error',
				'message': 'Internal server error'
			}))

	async def handle_ping(self, data):
		"""Handle ping/pong for connection health"""
		await self.send(text_data=json.dumps({
			'type': 'pong',
			'timestamp': timezone.now().isoformat()
		}))

	async def notification_update(self, event):
		"""Handle notification update from group"""
		logger.info(f"NotificationConsumer: Received notification_update event: {event}")
		await self.send(text_data=json.dumps({
			'type': 'notification_update',
			'notification': event['notification']
		}))
		logger.info(f"NotificationConsumer: Sent notification to WebSocket client")

	async def notification_count_update(self, event):
		"""Handle notification count update from group"""
		logger.info(f"NotificationConsumer: Received notification_count_update event: {event}")
		await self.send(text_data=json.dumps({
			'type': 'notification_count_update',
			'count': event['count']
		}))
		logger.info(f"NotificationConsumer: Sent count update to WebSocket client")