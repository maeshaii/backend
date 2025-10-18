"""
Django management command for WebSocket connection analytics and cleanup.

Usage:
    python manage.py websocket_analytics --cleanup
    python manage.py websocket_analytics --stats
    python manage.py websocket_analytics --conversation 123
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from apps.messaging.connection_manager import connection_manager
import json


class Command(BaseCommand):
    help = 'Manage WebSocket connections and view analytics'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Clean up stale WebSocket connections',
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Show global WebSocket connection statistics',
        )
        parser.add_argument(
            '--conversation',
            type=int,
            help='Show statistics for a specific conversation ID',
        )
        parser.add_argument(
            '--users',
            action='store_true',
            help='Show active users across all conversations',
        )

    def handle(self, *args, **options):
        if options['cleanup']:
            self.handle_cleanup()
        elif options['stats']:
            self.handle_stats()
        elif options['conversation']:
            self.handle_conversation_stats(options['conversation'])
        elif options['users']:
            self.handle_active_users()
        else:
            self.stdout.write(
                self.style.ERROR('Please specify an action: --cleanup, --stats, --conversation, or --users')
            )

    def handle_cleanup(self):
        """Clean up stale WebSocket connections."""
        self.stdout.write('Cleaning up stale WebSocket connections...')
        
        try:
            cleaned_count = connection_manager.cleanup_stale_connections()
            self.stdout.write(
                self.style.SUCCESS(f'Successfully cleaned up {cleaned_count} stale connections')
            )
        except Exception as e:
            raise CommandError(f'Failed to cleanup connections: {e}')

    def handle_stats(self):
        """Show global WebSocket connection statistics."""
        self.stdout.write('WebSocket Connection Statistics:')
        self.stdout.write('=' * 50)
        
        try:
            analytics = connection_manager.get_connection_analytics()
            
            if not analytics:
                self.stdout.write(self.style.WARNING('No analytics data available'))
                return
            
            # Display events
            if 'events' in analytics:
                self.stdout.write('Events:')
                for event_type, count in analytics['events'].items():
                    self.stdout.write(f'  {event_type}: {count}')
                self.stdout.write('')
            
            # Display last activity
            if 'last_activity' in analytics:
                last_activity = analytics['last_activity']
                self.stdout.write(f'Last Activity: {last_activity}')
            
        except Exception as e:
            raise CommandError(f'Failed to get statistics: {e}')

    def handle_conversation_stats(self, conversation_id):
        """Show statistics for a specific conversation."""
        self.stdout.write(f'WebSocket Statistics for Conversation {conversation_id}:')
        self.stdout.write('=' * 60)
        
        try:
            # Get conversation analytics
            analytics = connection_manager.get_connection_analytics(conversation_id)
            
            if not analytics:
                self.stdout.write(self.style.WARNING('No analytics data available for this conversation'))
                return
            
            # Display events
            if 'events' in analytics:
                self.stdout.write('Events:')
                for event_type, count in analytics['events'].items():
                    self.stdout.write(f'  {event_type}: {count}')
                self.stdout.write('')
            
            # Display last activity
            if 'last_activity' in analytics:
                last_activity = analytics['last_activity']
                self.stdout.write(f'Last Activity: {last_activity}')
            
            # Get active users
            users = connection_manager.get_conversation_users(conversation_id)
            if users:
                self.stdout.write('\nActive Users:')
                for user in users:
                    status = user.get('status', 'unknown')
                    last_seen = user.get('last_seen', 'unknown')
                    self.stdout.write(f'  User {user["user_id"]}: {status} (last seen: {last_seen})')
            else:
                self.stdout.write('\nNo active users in this conversation')
            
        except Exception as e:
            raise CommandError(f'Failed to get conversation statistics: {e}')

    def handle_active_users(self):
        """Show active users across all conversations."""
        self.stdout.write('Active Users Across All Conversations:')
        self.stdout.write('=' * 50)
        
        try:
            # This is a simplified version - in production you might want to
            # implement a method to get all active users across conversations
            self.stdout.write(self.style.WARNING('Active users feature requires additional implementation'))
            self.stdout.write('Use --conversation <id> to see users for a specific conversation')
            
        except Exception as e:
            raise CommandError(f'Failed to get active users: {e}')





