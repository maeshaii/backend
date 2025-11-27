"""
Django management command for WebSocket rate limiting monitoring and management.

Usage:
    python manage.py websocket_rate_limits --status
    python manage.py websocket_rate_limits --user 123
    python manage.py websocket_rate_limits --pool-stats
    python manage.py websocket_rate_limits --cleanup
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from apps.messaging.rate_limiter import rate_limiter, connection_pool
import json


class Command(BaseCommand):
    help = 'Monitor and manage WebSocket rate limits and connection pool'

    def add_arguments(self, parser):
        parser.add_argument(
            '--status',
            action='store_true',
            help='Show general rate limiting status',
        )
        parser.add_argument(
            '--user',
            type=int,
            help='Show rate limit status for a specific user ID',
        )
        parser.add_argument(
            '--pool-stats',
            action='store_true',
            help='Show connection pool statistics',
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Clean up old rate limit data',
        )
        parser.add_argument(
            '--test-rate-limit',
            type=int,
            help='Test rate limiting for a specific user ID',
        )

    def handle(self, *args, **options):
        if options['status']:
            self.handle_status()
        elif options['user']:
            self.handle_user_status(options['user'])
        elif options['pool_stats']:
            self.handle_pool_stats()
        elif options['cleanup']:
            self.handle_cleanup()
        elif options['test_rate_limit']:
            self.handle_test_rate_limit(options['test_rate_limit'])
        else:
            self.stdout.write(
                self.style.ERROR('Please specify an action: --status, --user, --pool-stats, --cleanup, or --test-rate-limit')
            )

    def handle_status(self):
        """Show general rate limiting status."""
        self.stdout.write('WebSocket Rate Limiting Status:')
        self.stdout.write('=' * 50)
        
        try:
            # Get pool statistics
            pool_stats = connection_pool.get_pool_statistics()
            
            if 'error' in pool_stats:
                self.stdout.write(self.style.ERROR(f'Error getting pool stats: {pool_stats["error"]}'))
                return
            
            self.stdout.write('Connection Pool:')
            self.stdout.write(f'  Total Connections: {pool_stats["total_connections"]}')
            self.stdout.write(f'  Max Total Connections: {pool_stats["max_total_connections"]}')
            self.stdout.write(f'  Max Per User: {pool_stats["max_connections_per_user"]}')
            self.stdout.write(f'  Utilization: {pool_stats["utilization_percentage"]:.1f}%')
            self.stdout.write('')
            
            # Rate limit configurations
            self.stdout.write('Rate Limit Configurations:')
            self.stdout.write(f'  Message Rate: {rate_limiter.message_rate} messages/minute')
            self.stdout.write(f'  Connection Rate: {rate_limiter.connection_rate} connections/minute')
            self.stdout.write(f'  Typing Rate: {rate_limiter.typing_rate} events/minute')
            self.stdout.write('')
            
            self.stdout.write(f'Last Updated: {pool_stats["timestamp"]}')
            
        except Exception as e:
            raise CommandError(f'Failed to get status: {e}')

    def handle_user_status(self, user_id):
        """Show rate limit status for a specific user."""
        self.stdout.write(f'Rate Limit Status for User {user_id}:')
        self.stdout.write('=' * 50)
        
        try:
            status = rate_limiter.get_user_rate_limit_status(user_id)
            
            if 'error' in status:
                self.stdout.write(self.style.ERROR(f'Error getting user status: {status["error"]}'))
                return
            
            # Message rate status
            msg_rate = status['message_rate']
            self.stdout.write('Message Rate:')
            self.stdout.write(f'  Current: {msg_rate["current"]}/{msg_rate["limit"]}')
            self.stdout.write(f'  Remaining: {msg_rate["remaining"]}')
            if msg_rate["reset_in"] > 0:
                self.stdout.write(f'  Resets in: {msg_rate["reset_in"]} seconds')
            self.stdout.write('')
            
            # Connection rate status
            conn_rate = status['connection_rate']
            self.stdout.write('Connection Rate:')
            self.stdout.write(f'  Current: {conn_rate["current"]}/{conn_rate["limit"]}')
            self.stdout.write(f'  Remaining: {conn_rate["remaining"]}')
            if conn_rate["reset_in"] > 0:
                self.stdout.write(f'  Resets in: {conn_rate["reset_in"]} seconds')
            self.stdout.write('')
            
            # Typing rate status
            typing_rate = status['typing_rate']
            self.stdout.write('Typing Rate:')
            self.stdout.write(f'  Current: {typing_rate["current"]}/{typing_rate["limit"]}')
            self.stdout.write(f'  Remaining: {typing_rate["remaining"]}')
            if typing_rate["reset_in"] > 0:
                self.stdout.write(f'  Resets in: {typing_rate["reset_in"]} seconds')
            self.stdout.write('')
            
            self.stdout.write(f'Status Time: {status["timestamp"]}')
            
        except Exception as e:
            raise CommandError(f'Failed to get user status: {e}')

    def handle_pool_stats(self):
        """Show connection pool statistics."""
        self.stdout.write('Connection Pool Statistics:')
        self.stdout.write('=' * 50)
        
        try:
            stats = connection_pool.get_pool_statistics()
            
            if 'error' in stats:
                self.stdout.write(self.style.ERROR(f'Error getting pool stats: {stats["error"]}'))
                return
            
            self.stdout.write(f'Total Active Connections: {stats["total_connections"]}')
            self.stdout.write(f'Maximum Total Connections: {stats["max_total_connections"]}')
            self.stdout.write(f'Maximum Connections Per User: {stats["max_connections_per_user"]}')
            self.stdout.write(f'Pool Utilization: {stats["utilization_percentage"]:.1f}%')
            self.stdout.write('')
            
            # Show utilization bar
            utilization = stats["utilization_percentage"]
            bar_length = 50
            filled_length = int(bar_length * utilization / 100)
            bar = '█' * filled_length + '░' * (bar_length - filled_length)
            
            self.stdout.write(f'Utilization: [{bar}] {utilization:.1f}%')
            self.stdout.write('')
            
            if utilization > 80:
                self.stdout.write(self.style.WARNING('⚠️  High utilization! Consider scaling up.'))
            elif utilization > 60:
                self.stdout.write(self.style.WARNING('⚠️  Moderate utilization. Monitor closely.'))
            else:
                self.stdout.write(self.style.SUCCESS('✅ Pool utilization is healthy.'))
            
            self.stdout.write(f'Last Updated: {stats["timestamp"]}')
            
        except Exception as e:
            raise CommandError(f'Failed to get pool stats: {e}')

    def handle_cleanup(self):
        """Clean up old rate limit data."""
        self.stdout.write('Cleaning up old rate limit data...')
        
        try:
            # Clean up rate limiter data
            rate_cleanup_count = rate_limiter.cleanup_old_requests()
            self.stdout.write(f'Cleaned up {rate_cleanup_count} rate limit entries')
            
            # Note: Connection pool cleanup is handled automatically by TTL
            self.stdout.write('Connection pool cleanup handled automatically by TTL')
            
            self.stdout.write(
                self.style.SUCCESS('Cleanup completed successfully')
            )
            
        except Exception as e:
            raise CommandError(f'Failed to cleanup: {e}')

    def handle_test_rate_limit(self, user_id):
        """Test rate limiting for a specific user."""
        self.stdout.write(f'Testing Rate Limits for User {user_id}:')
        self.stdout.write('=' * 50)
        
        try:
            # Test message rate limit
            can_send, msg_info = rate_limiter.check_message_rate_limit(user_id, 1)  # Use conversation 1 for test
            self.stdout.write('Message Rate Test:')
            self.stdout.write(f'  Allowed: {can_send}')
            if not can_send:
                self.stdout.write(f'  Reason: {msg_info.get("reason", "unknown")}')
                self.stdout.write(f'  Retry After: {msg_info.get("retry_after", 0)} seconds')
            else:
                self.stdout.write(f'  User Requests: {msg_info.get("user_requests", 0)}')
                self.stdout.write(f'  User Limit: {msg_info.get("user_limit", 0)}')
            self.stdout.write('')
            
            # Test connection rate limit
            can_connect, conn_info = rate_limiter.check_connection_rate_limit(user_id)
            self.stdout.write('Connection Rate Test:')
            self.stdout.write(f'  Allowed: {can_connect}')
            if not can_connect:
                self.stdout.write(f'  Reason: {conn_info.get("reason", "unknown")}')
                self.stdout.write(f'  Retry After: {conn_info.get("retry_after", 0)} seconds')
            else:
                self.stdout.write(f'  User Connections: {conn_info.get("user_connections", 0)}')
                self.stdout.write(f'  User Limit: {conn_info.get("user_limit", 0)}')
            self.stdout.write('')
            
            # Test typing rate limit
            can_type, typing_info = rate_limiter.check_typing_rate_limit(user_id, 1)  # Use conversation 1 for test
            self.stdout.write('Typing Rate Test:')
            self.stdout.write(f'  Allowed: {can_type}')
            if not can_type:
                self.stdout.write(f'  Reason: {typing_info.get("reason", "unknown")}')
                self.stdout.write(f'  Retry After: {typing_info.get("retry_after", 0)} seconds')
            else:
                self.stdout.write(f'  Typing Events: {typing_info.get("typing_events", 0)}')
                self.stdout.write(f'  Limit: {typing_info.get("limit", 0)}')
            
        except Exception as e:
            raise CommandError(f'Failed to test rate limits: {e}')























































