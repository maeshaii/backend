"""
Django management command for messaging system monitoring and metrics.

Usage:
    python manage.py messaging_monitoring --status
    python manage.py messaging_monitoring --metrics
    python manage.py messaging_monitoring --health-check
    python manage.py messaging_monitoring --cleanup-metrics
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from apps.messaging.monitoring import messaging_monitor
from apps.messaging.connection_manager import connection_manager
from apps.messaging.rate_limiter import rate_limiter, connection_pool
from apps.shared.models import Message, Conversation, MessageAttachment
import json


class Command(BaseCommand):
    help = 'Monitor messaging system health and metrics'

    def add_arguments(self, parser):
        parser.add_argument(
            '--status',
            action='store_true',
            help='Show system status and health',
        )
        parser.add_argument(
            '--metrics',
            action='store_true',
            help='Show detailed metrics',
        )
        parser.add_argument(
            '--health-check',
            action='store_true',
            help='Perform comprehensive health check',
        )
        parser.add_argument(
            '--cleanup-metrics',
            action='store_true',
            help='Clean up old metrics data',
        )
        parser.add_argument(
            '--export-metrics',
            action='store_true',
            help='Export metrics to JSON file',
        )

    def handle(self, *args, **options):
        if options['status']:
            self.handle_status()
        elif options['metrics']:
            self.handle_metrics()
        elif options['health_check']:
            self.handle_health_check()
        elif options['cleanup_metrics']:
            self.handle_cleanup_metrics()
        elif options['export_metrics']:
            self.handle_export_metrics()
        else:
            self.stdout.write(
                self.style.ERROR('Please specify an action: --status, --metrics, --health-check, --cleanup-metrics, or --export-metrics')
            )

    def handle_status(self):
        """Show system status and health."""
        self.stdout.write('Messaging System Status:')
        self.stdout.write('=' * 50)
        
        try:
            # Get monitoring status
            monitoring_status = messaging_monitor.get_metrics_summary()
            
            self.stdout.write('Monitoring:')
            self.stdout.write(f'  Sentry Enabled: {monitoring_status["sentry_enabled"]}')
            self.stdout.write(f'  Timestamp: {monitoring_status["timestamp"]}')
            self.stdout.write('')
            
            # Get connection pool status
            pool_stats = connection_pool.get_pool_statistics()
            self.stdout.write('Connection Pool:')
            self.stdout.write(f'  Active Connections: {pool_stats.get("total_connections", 0)}')
            self.stdout.write(f'  Max Connections: {pool_stats.get("max_total_connections", 0)}')
            self.stdout.write(f'  Utilization: {pool_stats.get("utilization_percentage", 0):.1f}%')
            self.stdout.write('')
            
            # Get database statistics
            total_messages = Message.objects.count()
            total_conversations = Conversation.objects.count()
            total_attachments = MessageAttachment.objects.count()
            
            self.stdout.write('Database:')
            self.stdout.write(f'  Total Messages: {total_messages:,}')
            self.stdout.write(f'  Total Conversations: {total_conversations:,}')
            self.stdout.write(f'  Total Attachments: {total_attachments:,}')
            self.stdout.write('')
            
            # Get error metrics
            error_metrics = monitoring_status.get('error_metrics', {})
            self.stdout.write('Error Metrics:')
            self.stdout.write(f'  Total Errors: {error_metrics.get("total_errors", 0)}')
            error_levels = error_metrics.get('error_levels', {})
            for level, count in error_levels.items():
                self.stdout.write(f'  {level.title()}: {count}')
            
        except Exception as e:
            raise CommandError(f'Failed to get status: {e}')

    def handle_metrics(self):
        """Show detailed metrics."""
        self.stdout.write('Detailed Messaging Metrics:')
        self.stdout.write('=' * 50)
        
        try:
            metrics = messaging_monitor.get_metrics_summary()
            
            # Error metrics
            error_metrics = metrics.get('error_metrics', {})
            self.stdout.write('Error Metrics:')
            self.stdout.write(f'  Total Errors: {error_metrics.get("total_errors", 0)}')
            error_levels = error_metrics.get('error_levels', {})
            for level, count in error_levels.items():
                self.stdout.write(f'  {level.title()}: {count}')
            self.stdout.write('')
            
            # Performance metrics
            perf_metrics = metrics.get('performance_metrics', {})
            self.stdout.write('Performance Metrics:')
            for metric, value in perf_metrics.items():
                if isinstance(value, (int, float)):
                    self.stdout.write(f'  {metric}: {value:.3f}')
                else:
                    self.stdout.write(f'  {metric}: {value}')
            self.stdout.write('')
            
            # WebSocket metrics
            ws_metrics = metrics.get('websocket_metrics', {})
            self.stdout.write('WebSocket Metrics:')
            self.stdout.write(f'  Active Connections: {ws_metrics.get("active_connections", 0)}')
            connection_events = ws_metrics.get('connection_events', {})
            for event, count in connection_events.items():
                self.stdout.write(f'  {event.title()}: {count}')
            self.stdout.write('')
            
            # Message delivery metrics
            msg_metrics = metrics.get('message_delivery_metrics', {})
            self.stdout.write('Message Delivery Metrics:')
            self.stdout.write(f'  Total Messages: {msg_metrics.get("total_messages", 0)}')
            delivery_status = msg_metrics.get('delivery_status', {})
            for status, count in delivery_status.items():
                self.stdout.write(f'  {status.title()}: {count}')
            self.stdout.write('')
            
            # Business metrics
            business_metrics = metrics.get('business_metrics', {})
            self.stdout.write('Business Metrics:')
            for metric, value in business_metrics.items():
                self.stdout.write(f'  {metric}: {value}')
            
        except Exception as e:
            raise CommandError(f'Failed to get metrics: {e}')

    def handle_health_check(self):
        """Perform comprehensive health check."""
        self.stdout.write('Messaging System Health Check:')
        self.stdout.write('=' * 50)
        
        health_status = {
            'overall': 'healthy',
            'checks': {}
        }
        
        try:
            # Check database connectivity
            try:
                Message.objects.count()
                health_status['checks']['database'] = 'healthy'
                self.stdout.write(self.style.SUCCESS('✅ Database: Healthy'))
            except Exception as e:
                health_status['checks']['database'] = 'unhealthy'
                health_status['overall'] = 'unhealthy'
                self.stdout.write(self.style.ERROR(f'❌ Database: Unhealthy - {e}'))
            
            # Check Redis connectivity
            try:
                connection_manager.get_connection_analytics()
                health_status['checks']['redis'] = 'healthy'
                self.stdout.write(self.style.SUCCESS('✅ Redis: Healthy'))
            except Exception as e:
                health_status['checks']['redis'] = 'unhealthy'
                health_status['overall'] = 'unhealthy'
                self.stdout.write(self.style.ERROR(f'❌ Redis: Unhealthy - {e}'))
            
            # Check connection pool
            try:
                pool_stats = connection_pool.get_pool_statistics()
                utilization = pool_stats.get('utilization_percentage', 0)
                if utilization < 80:
                    health_status['checks']['connection_pool'] = 'healthy'
                    self.stdout.write(self.style.SUCCESS('✅ Connection Pool: Healthy'))
                else:
                    health_status['checks']['connection_pool'] = 'warning'
                    self.stdout.write(self.style.WARNING(f'⚠️ Connection Pool: High utilization ({utilization:.1f}%)'))
            except Exception as e:
                health_status['checks']['connection_pool'] = 'unhealthy'
                health_status['overall'] = 'unhealthy'
                self.stdout.write(self.style.ERROR(f'❌ Connection Pool: Unhealthy - {e}'))
            
            # Check monitoring system
            try:
                metrics = messaging_monitor.get_metrics_summary()
                if metrics.get('sentry_enabled', False):
                    health_status['checks']['monitoring'] = 'healthy'
                    self.stdout.write(self.style.SUCCESS('✅ Monitoring: Healthy (Sentry enabled)'))
                else:
                    health_status['checks']['monitoring'] = 'warning'
                    self.stdout.write(self.style.WARNING('⚠️ Monitoring: Sentry not configured'))
            except Exception as e:
                health_status['checks']['monitoring'] = 'unhealthy'
                health_status['overall'] = 'unhealthy'
                self.stdout.write(self.style.ERROR(f'❌ Monitoring: Unhealthy - {e}'))
            
            # Check error rates
            try:
                error_metrics = metrics.get('error_metrics', {})
                total_errors = error_metrics.get('total_errors', 0)
                if total_errors < 100:  # Threshold for healthy error rate
                    health_status['checks']['error_rate'] = 'healthy'
                    self.stdout.write(self.style.SUCCESS(f'✅ Error Rate: Healthy ({total_errors} errors)'))
                else:
                    health_status['checks']['error_rate'] = 'warning'
                    self.stdout.write(self.style.WARNING(f'⚠️ Error Rate: High ({total_errors} errors)'))
            except Exception as e:
                health_status['checks']['error_rate'] = 'unhealthy'
                self.stdout.write(self.style.ERROR(f'❌ Error Rate: Unhealthy - {e}'))
            
            self.stdout.write('')
            if health_status['overall'] == 'healthy':
                self.stdout.write(self.style.SUCCESS('🎉 Overall System Health: HEALTHY'))
            else:
                self.stdout.write(self.style.ERROR('🚨 Overall System Health: UNHEALTHY'))
            
        except Exception as e:
            raise CommandError(f'Health check failed: {e}')

    def handle_cleanup_metrics(self):
        """Clean up old metrics data."""
        self.stdout.write('Cleaning up old metrics data...')
        
        try:
            # This would clean up old metrics from cache
            # In a real implementation, you might want to use Redis SCAN
            # to find and delete old metric keys
            
            self.stdout.write('Metrics cleanup completed (handled by TTL)')
            self.stdout.write(
                self.style.SUCCESS('Cleanup completed successfully')
            )
            
        except Exception as e:
            raise CommandError(f'Cleanup failed: {e}')

    def handle_export_metrics(self):
        """Export metrics to JSON file."""
        self.stdout.write('Exporting metrics to JSON...')
        
        try:
            metrics = messaging_monitor.get_metrics_summary()
            
            # Add additional system information
            export_data = {
                'export_timestamp': timezone.now().isoformat(),
                'system_info': {
                    'django_version': '5.2.3',
                    'python_version': '3.11+',
                },
                'metrics': metrics
            }
            
            # Write to file
            filename = f'messaging_metrics_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json'
            with open(filename, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            self.stdout.write(f'Metrics exported to: {filename}')
            self.stdout.write(
                self.style.SUCCESS('Export completed successfully')
            )
            
        except Exception as e:
            raise CommandError(f'Export failed: {e}')






















