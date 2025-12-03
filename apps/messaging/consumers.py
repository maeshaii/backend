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
		logger.info("WebSocket connection accepted - User: %s", getattr(self.user, 'user_id', None))
		
		# Join conversation room
		group_name = f"chat_{self.conversation_id}"
		await self.channel_layer.group_add(
			group_name,
			self.channel_name
		)
		logger.info("WebSocket joined group '%s' - real-time messaging active", group_name)
		
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
			elif message_type == 'reaction':
				await self.handle_reaction(data)
			elif message_type == 'edit':
				await self.handle_edit(data)
			elif message_type == 'delete':
				await self.handle_delete(data)
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

	async def handle_reaction(self, data):
		"""Handle reaction add/remove via WebSocket"""
		try:
			message_id = data.get('message_id')
			emoji = data.get('emoji')
			action = data.get('action', 'add')
			
			if not message_id or not emoji:
				await self.send(text_data=json.dumps({
					'type': 'error',
					'message': 'message_id and emoji are required'
				}))
				return
			
			user_id = getattr(self.user, 'user_id', None)
			
			# Save to database
			if action == 'add':
				await database_sync_to_async(self._add_reaction_to_db)(message_id, user_id, emoji)
			elif action == 'remove':
				await database_sync_to_async(self._remove_reaction_from_db)(message_id, user_id, emoji)
			
			# Broadcast to conversation group (including sender for confirmation)
			await self.channel_layer.group_send(
				f"chat_{self.conversation_id}",
				{
					'type': 'reaction_update',
					'action': action,
					'message_id': message_id,
					'emoji': emoji,
					'user_id': user_id,
					'user_name': getattr(self.user, 'full_name', ''),
					'timestamp': timezone.now().isoformat()
				}
			)
			
			logger.info(f"Reaction {action} for message {message_id} by user {user_id}")
			
		except Exception as e:
			logger.error(f"Error handling reaction: {e}")

	async def handle_edit(self, data):
		"""Handle message edit via WebSocket"""
		try:
			message_id = data.get('message_id')
			content = data.get('content')
			
			if not message_id or not content:
				await self.send(text_data=json.dumps({
					'type': 'error',
					'message': 'message_id and content are required'
				}))
				return
			
			# Broadcast to conversation group
			await self.channel_layer.group_send(
				f"chat_{self.conversation_id}",
				{
					'type': 'message_edit',
					'message_id': message_id,
					'content': content,
					'timestamp': timezone.now().isoformat()
				}
			)
			
			logger.info(f"Message {message_id} edited by user {getattr(self.user, 'user_id', None)}")
			
		except Exception as e:
			logger.error(f"Error handling edit: {e}")

	async def handle_delete(self, data):
		"""Handle message delete via WebSocket"""
		try:
			message_id = data.get('message_id')
			
			if not message_id:
				await self.send(text_data=json.dumps({
					'type': 'error',
					'message': 'message_id is required'
				}))
				return
			
			# Broadcast to conversation group
			await self.channel_layer.group_send(
				f"chat_{self.conversation_id}",
				{
					'type': 'message_delete',
					'message_id': message_id,
					'timestamp': timezone.now().isoformat()
				}
			)
			
			logger.info(f"Message {message_id} deleted by user {getattr(self.user, 'user_id', None)}")
			
		except Exception as e:
			logger.error(f"Error handling delete: {e}")

	async def chat_message(self, event):
		"""Handle chat message from group"""
		# Handle both old and new message formats
		message = event.get('message') or event.get('data', {})
		logger.info(f"[WebSocket] Broadcasting message {message.get('message_id')} to channel {self.channel_name}")
		await self.send(text_data=json.dumps({
			'type': 'message',
			'message': message
		}))
		logger.info("WebSocket message sent to channel %s", self.channel_name)

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

	async def reaction_update(self, event):
		"""Handle reaction update from group"""
		await self.send(text_data=json.dumps({
			'type': 'reaction',
			'action': event['action'],
			'message_id': event['message_id'],
			'emoji': event['emoji'],
			'user_id': event['user_id'],
			'user_name': event.get('user_name', ''),
			'timestamp': event.get('timestamp', timezone.now().isoformat())
		}))

	async def message_edit(self, event):
		"""Handle message edit from group"""
		await self.send(text_data=json.dumps({
			'type': 'edit',
			'message_id': event['message_id'],
			'content': event['content'],
			'timestamp': event.get('timestamp', timezone.now().isoformat())
		}))

	async def message_delete(self, event):
		"""Handle message delete from group"""
		await self.send(text_data=json.dumps({
			'type': 'delete',
			'message_id': event['message_id'],
			'timestamp': event.get('timestamp', timezone.now().isoformat())
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
			
			# Convert message request to regular conversation only if the non-initiator replies
			# This matches the REST API logic for consistency
			if conversation.is_message_request:
				try:
					initiator_id = getattr(conversation.request_initiator, 'user_id', None)
					if not initiator_id or initiator_id != self.user.user_id:
						# Non-initiator is replying, convert to regular conversation
						conversation.is_message_request = False
						conversation.request_initiator = None
						conversation.save(update_fields=['is_message_request', 'request_initiator', 'updated_at'])
						logger.info(f"Converted message request {self.conversation_id} to regular conversation via WebSocket (non-initiator reply)")
				except Exception as e:
					# Fallback: keep previous behavior if field missing
					logger.warning(f"Error checking request_initiator in WebSocket: {e}, using fallback")
					conversation.is_message_request = False
					conversation.save(update_fields=['is_message_request', 'updated_at'])
					logger.info(f"Converted message request {self.conversation_id} to regular conversation via WebSocket (fallback)")
			
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
		except Exception as e:
			logger.error(f"Error marking message as read: {e}")
	
	def _add_reaction_to_db(self, message_id, user_id, emoji):
		"""Add reaction to database - enforces 1 reaction per user per message"""
		try:
			from apps.shared.models import MessageReaction
			
			# Check if message exists
			message = Message.objects.get(message_id=message_id)
			
			# Remove any existing reactions from this user on this message (enforce 1 reaction limit)
			MessageReaction.objects.filter(
				message_id=message_id,
				user_id=user_id
			).delete()
			
			# Create new reaction
			reaction = MessageReaction.objects.create(
				message_id=message_id,
				user_id=user_id,
				emoji=emoji
			)
			
			logger.info(f"Reaction created: {emoji} on message {message_id} by user {user_id} (replaced any existing reactions)")
			return reaction
			
		except Message.DoesNotExist:
			logger.error(f"Message {message_id} not found")
			return None
		except Exception as e:
			logger.error(f"Error adding reaction to database: {e}")
			return None
	
	def _remove_reaction_from_db(self, message_id, user_id, emoji):
		"""Remove reaction from database"""
		try:
			from apps.shared.models import MessageReaction
			
			# Delete the reaction
			deleted_count, _ = MessageReaction.objects.filter(
				message_id=message_id,
				user_id=user_id,
				emoji=emoji
			).delete()
			
			logger.info(f"Removed {deleted_count} reaction(s): {emoji} from message {message_id} by user {user_id}")
			return deleted_count > 0
			
		except Exception as e:
			logger.error(f"Error removing reaction from database: {e}")
			return False
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
		
		# Log connection attempt with detailed info
		user_id = getattr(self.user, 'user_id', None)
		logger.info(f"Notification WebSocket connection attempt from user {user_id}")
		logger.info(f"User object: {self.user}")
		logger.info(f"User type: {type(self.user)}")
		logger.info(f"User is authenticated: {self.user.is_authenticated if hasattr(self.user, 'is_authenticated') else 'N/A'}")
		logger.info(f"User has user_id attribute: {hasattr(self.user, 'user_id')}")
		
		# Check if user is authenticated
		if not self.user or not hasattr(self.user, 'user_id') or not user_id:
			logger.warning(f"Invalid user for notification WebSocket: {self.user}, type: {type(self.user)}")
			# Check if it's an AnonymousUser
			from django.contrib.auth.models import AnonymousUser
			if isinstance(self.user, AnonymousUser):
				logger.warning("User is AnonymousUser - authentication failed or token invalid/expired")
			await self.accept()
			await self.send(text_data=json.dumps({
				'type': 'connection_denied',
				'reason': 'invalid_user',
				'message': 'Invalid user session. Please log in again.'
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
		
		# Register this connection for global presence/online detection
		try:
			from apps.messaging.connection_manager import connection_manager
			# Use conversation_id = 0 to indicate a non-conversation global connection
			# Use database_sync_to_async to properly handle the sync call in async context
			await database_sync_to_async(connection_manager.add_connection)(
				user_id=user_id,
				conversation_id=0,
				channel_name=self.channel_name,
				# Only include JSON-serializable metadata
				connection_metadata={
					'ip_address': str(self.scope.get('client', [None, None])[0]) if self.scope.get('client', [None, None])[0] else None,
				}
			)
			logger.info(f"Successfully registered notification WebSocket for user {user_id} in connection manager")
		except Exception as e:
			logger.error(f"Failed to register notification WS in connection manager: {e}", exc_info=True)

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

		# Unregister from global presence
		try:
			from apps.messaging.connection_manager import connection_manager
			await database_sync_to_async(connection_manager.remove_connection)(self.channel_name)
			logger.info(f"Successfully unregistered notification WebSocket for user {user_id} from connection manager")
		except Exception as e:
			logger.error(f"Failed to unregister notification WS: {e}", exc_info=True)
		
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

	async def conversation_deleted(self, event):
		"""Handle conversation deletion event from group"""
		logger.info(f"NotificationConsumer: Received conversation_deleted event: {event}")
		conversation_id = event.get('conversation_id')
		fully_deleted = event.get('fully_deleted', False)
		
		if conversation_id:
			await self.send(text_data=json.dumps({
				'type': 'conversation_deleted',
				'conversation_id': conversation_id,
				'fully_deleted': fully_deleted,
				'timestamp': timezone.now().isoformat()
			}))
			logger.info(f"NotificationConsumer: Sent conversation_deleted event to WebSocket client for conversation {conversation_id}")
		else:
			logger.warning(f"NotificationConsumer: Received conversation_deleted event without conversation_id: {event}")

	async def presence_update(self, event):
		"""Handle presence update from group (ignore for notification consumer)"""
		# NotificationConsumer doesn't need to handle presence updates
		# This handler exists to prevent "No handler" errors
		pass

	async def notification_count_update(self, event):
		"""Handle notification count update from group"""
		logger.info(f"NotificationConsumer: Received notification_count_update event: {event}")
		await self.send(text_data=json.dumps({
			'type': 'notification_count_update',
			'count': event['count']
		}))
		logger.info(f"NotificationConsumer: Sent count update to WebSocket client")

	async def points_update(self, event):
		"""Handle points update from group"""
		logger.info(f"NotificationConsumer: Received points_update event: {event}")
		await self.send(text_data=json.dumps({
			'type': 'points_update',
			'points': event['points']
		}))
		logger.info(f"NotificationConsumer: Sent points update to WebSocket client")
	
	async def message_request_count_update(self, event):
		"""Handle message request count update from group"""
		logger.info(f"NotificationConsumer: Received message_request_count_update event: {event}")
		await self.send(text_data=json.dumps({
			'type': 'message_request_count',
			'count': event['count']
		}))
		logger.info(f"NotificationConsumer: Sent message request count {event['count']} to WebSocket client")

	async def recent_search_update(self, event):
		"""Handle recent search updates from group"""
		logger.info(f"NotificationConsumer: Received recent_search_update event: {event}")
		await self.send(text_data=json.dumps({
			'type': 'recent_search_update',
			'recent_searches': event.get('recent_searches', []),
			'recent': event.get('recent', [])
		}))
	
	async def chat_message_notification(self, event):
		"""Handle chat message sent via notification channel (for users who deleted conversation)"""
		logger.info(f"NotificationConsumer: Received chat_message_notification event for conversation {event.get('conversation_id')}")
		await self.send(text_data=json.dumps({
			'type': 'chat_message',
			'message': event.get('message'),
			'conversation_id': event.get('conversation_id')
		}))
		logger.info(f"NotificationConsumer: Sent chat message to user via notification channel")
		logger.info("NotificationConsumer: Sent recent search update to WebSocket client")


class UserManagementConsumer(AsyncWebsocketConsumer):
	"""WebSocket consumer that streams admin user management updates."""

	async def connect(self):
		self.user = self.scope.get('user')
		if not await self._has_admin_access():
			await self.accept()
			await self.send(text_data=json.dumps({
				'type': 'connection_denied',
				'reason': 'access_denied',
				'message': 'Admin privileges required'
			}))
			await self.close()
			return

		await self.accept()
		self.group_name = 'user_management_updates'
		await self.channel_layer.group_add(self.group_name, self.channel_name)

		await self.send(text_data=json.dumps({
			'type': 'connection_established',
			'user_id': getattr(self.user, 'user_id', None),
			'timestamp': timezone.now().isoformat()
		}))
		logger.info(
			"UserManagementConsumer connected for user %s (channel=%s)",
			getattr(self.user, 'user_id', None),
			self.channel_name
		)

	async def disconnect(self, close_code):
		if hasattr(self, 'group_name'):
			await self.channel_layer.group_discard(self.group_name, self.channel_name)
			logger.info(
				"UserManagementConsumer disconnected for user %s",
				getattr(self.user, 'user_id', None)
			)

	async def receive(self, text_data):
		try:
			data = json.loads(text_data)
		except json.JSONDecodeError:
			data = {}

		if data.get('type') == 'ping':
			await self.send(text_data=json.dumps({
				'type': 'pong',
				'timestamp': timezone.now().isoformat()
			}))
		else:
			await self.send(text_data=json.dumps({
				'type': 'error',
				'message': 'Unsupported message type'
			}))

	async def user_management_update(self, event):
		await self.send(text_data=json.dumps({
			'type': 'user_management_update',
			'payload': event.get('payload')
		}))

	@database_sync_to_async
	def _check_admin_access(self):
		"""Check admin access in sync context to avoid async database issues"""
		if not self.user:
			return False
		try:
			# Check if user has user_id attribute (avoid hasattr to prevent DB queries)
			user_id = getattr(self.user, 'user_id', None)
			if not user_id:
				return False
			
			# Check staff and superuser flags
			is_staff = getattr(self.user, 'is_staff', False)
			is_superuser = getattr(self.user, 'is_superuser', False)
			
			# Get account_type (this may trigger a DB query, but we're in sync context)
			account_type = None
			try:
				account_type = self.user.account_type
			except Exception:
				pass
			
			# Check account type permissions
			has_admin = account_type and getattr(account_type, 'admin', False)
			has_peso = account_type and getattr(account_type, 'peso', False)
			has_coordinator = account_type and getattr(account_type, 'coordinator', False)
			
			return bool(is_staff or is_superuser or has_admin or has_peso or has_coordinator)
		except Exception:
			return False

	async def _has_admin_access(self):
		"""Async wrapper for admin access check"""
		return await self._check_admin_access()


class RecentSearchConsumer(AsyncWebsocketConsumer):
	"""Standalone WebSocket consumer for recent search updates."""

	async def connect(self):
		self.user = self.scope.get('user')
		user_id = getattr(self.user, 'user_id', None)

		if not user_id:
			logger.warning("RecentSearchConsumer connection denied: unauthenticated user %s", self.user)
			await self.close()
			return

		await self.accept()
		self.group_name = f"recent_searches_{user_id}"
		await self.channel_layer.group_add(self.group_name, self.channel_name)
		logger.info("RecentSearchConsumer connected for user %s (channel=%s)", user_id, self.channel_name)

		await self.send(text_data=json.dumps({
			'type': 'connection_established',
			'user_id': user_id,
			'timestamp': timezone.now().isoformat()
		}))

	async def disconnect(self, close_code):
		if hasattr(self, 'group_name'):
			await self.channel_layer.group_discard(self.group_name, self.channel_name)
			logger.info("RecentSearchConsumer disconnected (channel=%s)", self.channel_name)

	async def receive(self, text_data):
		# This consumer is currently read-only; respond with pong for keep-alive.
		try:
			payload = json.loads(text_data)
		except json.JSONDecodeError:
			payload = {}

		if payload.get('type') == 'ping':
			await self.send(text_data=json.dumps({
				'type': 'pong',
				'timestamp': timezone.now().isoformat()
			}))
		else:
			await self.send(text_data=json.dumps({
				'type': 'error',
				'message': 'Unsupported message type'
			}))

	async def recent_search_update(self, event):
		await self.send(text_data=json.dumps({
			'type': 'recent_search_update',
			'recent_searches': event.get('recent_searches', []),
			'recent': event.get('recent', [])
		}))