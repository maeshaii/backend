"""
Message Reaction API Views
Handles adding, removing, and listing reactions on messages
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging

from apps.shared.models import Message, MessageReaction, Conversation
from .permissions import IsAlumniOrOJT

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAlumniOrOJT])
def add_or_remove_reaction(request, conversation_id, message_id):
    """
    Add or remove a reaction to a message.
    
    POST /api/messaging/conversations/{conversation_id}/messages/{message_id}/reactions/
    
    Body:
    {
        "emoji": "😊",
        "action": "add" | "remove"  // Optional, defaults to "add"
    }
    
    Returns:
    {
        "status": "reaction_added" | "reaction_removed",
        "reaction": {
            "emoji": "😊",
            "user_id": 1376,
            "user_name": "Joshua Villaver",
            "created_at": "2025-11-21T17:30:00Z"
        }
    }
    """
    try:
        # Verify conversation access
        conversation = get_object_or_404(
            Conversation.objects.prefetch_related('participants'),
            conversation_id=conversation_id
        )
        
        if not conversation.participants.filter(user_id=request.user.user_id).exists():
            return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
        
        # Get message
        message = get_object_or_404(
            Message.objects.select_related('sender'),
            message_id=message_id,
            conversation=conversation
        )
        
        # Get emoji and action from request
        emoji = request.data.get('emoji')
        action_type = request.data.get('action', 'add').lower()
        
        if not emoji:
            return Response({'error': 'Emoji is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate emoji (basic check)
        if len(emoji) > 10:
            return Response({'error': 'Invalid emoji'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get channel layer for WebSocket broadcast
        channel_layer = get_channel_layer()
        
        if action_type == 'add':
            # Remove any existing reactions from this user on this message (enforce 1 reaction limit)
            MessageReaction.objects.filter(
                message=message,
                user=request.user
            ).delete()
            
            # Create new reaction
            reaction = MessageReaction.objects.create(
                message=message,
                user=request.user,
                emoji=emoji
            )
            
            # Broadcast via WebSocket
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    f"chat_{conversation_id}",
                    {
                        'type': 'reaction_update',
                        'action': 'add',
                        'message_id': message_id,
                        'emoji': emoji,
                        'user_id': request.user.user_id,
                        'user_name': getattr(request.user, 'full_name', ''),
                        'timestamp': timezone.now().isoformat()
                    }
                )
            
            return Response({
                'status': 'reaction_added',
                'created': True,
                'reaction': {
                    'emoji': emoji,
                    'user_id': request.user.user_id,
                    'user_name': getattr(request.user, 'full_name', ''),
                    'created_at': reaction.created_at.isoformat()
                }
            }, status=status.HTTP_201_CREATED)
            
        elif action_type == 'remove':
            # Remove reaction
            deleted_count, _ = MessageReaction.objects.filter(
                message=message,
                user=request.user,
                emoji=emoji
            ).delete()
            
            if deleted_count > 0:
                # Broadcast via WebSocket
                if channel_layer:
                    async_to_sync(channel_layer.group_send)(
                        f"chat_{conversation_id}",
                        {
                            'type': 'reaction_update',
                            'action': 'remove',
                            'message_id': message_id,
                            'emoji': emoji,
                            'user_id': request.user.user_id,
                            'timestamp': timezone.now().isoformat()
                        }
                    )
                
                return Response({
                    'status': 'reaction_removed'
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'status': 'reaction_not_found'
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({
                'error': 'Invalid action. Must be "add" or "remove"'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Error handling reaction: {e}", exc_info=True)
        return Response({
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAlumniOrOJT])
def list_reactions(request, conversation_id, message_id):
    """
    Get all reactions for a specific message.
    
    GET /api/messaging/conversations/{conversation_id}/messages/{message_id}/reactions/
    
    Returns:
    {
        "reactions": [
            {
                "emoji": "😊",
                "user_id": 1376,
                "user_name": "Joshua Villaver",
                "created_at": "2025-11-21T17:30:00Z"
            }
        ],
        "count": 1
    }
    """
    try:
        # Verify conversation access
        conversation = get_object_or_404(
            Conversation.objects.prefetch_related('participants'),
            conversation_id=conversation_id
        )
        
        if not conversation.participants.filter(user_id=request.user.user_id).exists():
            return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)
        
        # Get message
        message = get_object_or_404(
            Message.objects.select_related('sender'),
            message_id=message_id,
            conversation=conversation
        )
        
        # Get all reactions for this message
        reactions = MessageReaction.objects.filter(
            message=message
        ).select_related('user').order_by('created_at')
        
        reactions_data = [{
            'emoji': r.emoji,
            'user_id': r.user.user_id,
            'user_name': getattr(r.user, 'full_name', 'Unknown'),
            'created_at': r.created_at.isoformat()
        } for r in reactions]
        
        return Response({
            'reactions': reactions_data,
            'count': len(reactions_data)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error listing reactions: {e}", exc_info=True)
        return Response({
            'error': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


