"""
Django management command for performance metrics analysis and reporting.

Usage:
    python manage.py performance_metrics --summary
    python manage.py performance_metrics --trends message_delivery
    python manage.py performance_metrics --alerts
    python manage.py performance_metrics --export
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from apps.messaging.performance_metrics import performance_metrics
import json


class Command(BaseCommand):
    help = 'Analyze and report performance metrics for the messaging system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--summary',
            action='store_true',
            help='Show performance summary',
        )
        parser.add_argument(
            '--trends',
            type=str,
            help='Show performance trends for a specific metric',
        )
        parser.add_argument(
            '--alerts',
            action='store_true',
            help='Show performance alerts and issues',
        )
        parser.add_argument(
            '--export',
            action='store_true',
            help='Export performance data to JSON',
        )
        parser.add_argument(
            '--time-window',
            type=int,
            default=60,
            help='Time window in minutes for analysis (default: 60)',
        )

    def handle(self, *args, **options):
        if options['summary']:
            self.handle_summary(options['time_window'])
        elif options['trends']:
            self.handle_trends(options['trends'])
        elif options['alerts']:
            self.handle_alerts()
        elif options['export']:
            self.handle_export()
        else:
            self.stdout.write(
                self.style.ERROR('Please specify an action: --summary, --trends, --alerts, or --export')
            )

    def handle_summary(self, time_window):
        """Show performance summary."""
        self.stdout.write(f'Performance Summary (Last {time_window} minutes):')
        self.stdout.write('=' * 60)
        
        try:
            summary = performance_metrics.get_performance_summary(time_window)
            
            # Message delivery performance
            msg_delivery = summary.get('message_delivery', {})
            self.stdout.write('Message Delivery:')
            self.stdout.write(f'  Average Delivery Time: {msg_delivery.get("average_delivery_time", 0):.3f}ms')
            self.stdout.write(f'  Total Messages: {msg_delivery.get("total_messages", 0):,}')
            self.stdout.write(f'  Slow Messages: {msg_delivery.get("slow_messages", 0):,}')
            self.stdout.write('')
            
            # WebSocket connection performance
            ws_connections = summary.get('websocket_connections', {})
            self.stdout.write('WebSocket Connections:')
            self.stdout.write(f'  Average Connection Time: {ws_connections.get("average_connection_time", 0):.3f}ms')
            self.stdout.write(f'  Total Connections: {ws_connections.get("total_connections", 0):,}')
            self.stdout.write(f'  Slow Connections: {ws_connections.get("slow_connections", 0):,}')
            self.stdout.write('')
            
            # Database performance
            db_operations = summary.get('database_operations', {})
            self.stdout.write('Database Operations:')
            self.stdout.write(f'  Average Query Time: {db_operations.get("average_query_time", 0):.3f}ms')
            self.stdout.write(f'  Total Queries: {db_operations.get("total_queries", 0):,}')
            self.stdout.write(f'  Cache Hit Ratio: {db_operations.get("cache_hit_ratio", 0):.1%}')
            self.stdout.write('')
            
            # Cache performance
            cache_operations = summary.get('cache_operations', {})
            self.stdout.write('Cache Operations:')
            self.stdout.write(f'  Average Operation Time: {cache_operations.get("average_operation_time", 0):.3f}ms')
            self.stdout.write(f'  Total Operations: {cache_operations.get("total_operations", 0):,}')
            self.stdout.write(f'  Hit Ratio: {cache_operations.get("hit_ratio", 0):.1%}')
            self.stdout.write('')
            
            # System health
            system_health = summary.get('system_health', {})
            self.stdout.write('System Health:')
            self.stdout.write(f'  Status: {system_health.get("status", "unknown")}')
            alerts = system_health.get("alerts", [])
            if alerts:
                self.stdout.write(f'  Alerts: {len(alerts)}')
                for alert in alerts:
                    self.stdout.write(f'    - {alert}')
            else:
                self.stdout.write('  Alerts: None')
            
        except Exception as e:
            raise CommandError(f'Failed to get performance summary: {e}')

    def handle_trends(self, metric_name):
        """Show performance trends for a specific metric."""
        self.stdout.write(f'Performance Trends for {metric_name}:')
        self.stdout.write('=' * 60)
        
        try:
            trends = performance_metrics.get_performance_trends(metric_name, 24)
            
            if not trends:
                self.stdout.write(self.style.WARNING('No trend data available'))
                return
            
            self.stdout.write('Hour | Average | Count | Min    | Max')
            self.stdout.write('-' * 50)
            
            for trend in trends[-12:]:  # Show last 12 hours
                hour = trend['timestamp'][11:13]  # Extract hour
                avg = trend['value']
                count = trend['count']
                min_val = trend['min']
                max_val = trend['max']
                
                self.stdout.write(f'{hour:4} | {avg:7.1f} | {count:5} | {min_val:6.1f} | {max_val:6.1f}')
            
            # Show trend direction
            if len(trends) >= 2:
                recent_avg = trends[-1]['value']
                previous_avg = trends[-2]['value']
                change = recent_avg - previous_avg
                change_pct = (change / previous_avg * 100) if previous_avg > 0 else 0
                
                self.stdout.write('')
                if change > 0:
                    self.stdout.write(self.style.WARNING(f'Trend: Increasing (+{change_pct:.1f}%)'))
                elif change < 0:
                    self.stdout.write(self.style.SUCCESS(f'Trend: Decreasing ({change_pct:.1f}%)'))
                else:
                    self.stdout.write('Trend: Stable')
            
        except Exception as e:
            raise CommandError(f'Failed to get performance trends: {e}')

    def handle_alerts(self):
        """Show performance alerts and issues."""
        self.stdout.write('Performance Alerts and Issues:')
        self.stdout.write('=' * 50)
        
        try:
            # Get current performance summary
            summary = performance_metrics.get_performance_summary(60)
            
            alerts = []
            
            # Check message delivery performance
            msg_delivery = summary.get('message_delivery', {})
            avg_delivery_time = msg_delivery.get('average_delivery_time', 0)
            if avg_delivery_time > 1000:  # 1 second threshold
                alerts.append({
                    'type': 'warning',
                    'message': f'High message delivery latency: {avg_delivery_time:.1f}ms',
                    'recommendation': 'Check database performance and WebSocket connection quality'
                })
            
            # Check WebSocket connection performance
            ws_connections = summary.get('websocket_connections', {})
            avg_connection_time = ws_connections.get('average_connection_time', 0)
            if avg_connection_time > 5000:  # 5 second threshold
                alerts.append({
                    'type': 'warning',
                    'message': f'Slow WebSocket connections: {avg_connection_time:.1f}ms',
                    'recommendation': 'Check server load and network connectivity'
                })
            
            # Check database performance
            db_operations = summary.get('database_operations', {})
            avg_query_time = db_operations.get('average_query_time', 0)
            if avg_query_time > 100:  # 100ms threshold
                alerts.append({
                    'type': 'warning',
                    'message': f'Slow database queries: {avg_query_time:.1f}ms',
                    'recommendation': 'Check database indexes and query optimization'
                })
            
            # Check cache performance
            cache_operations = summary.get('cache_operations', {})
            hit_ratio = cache_operations.get('hit_ratio', 0)
            if hit_ratio < 0.8:  # 80% threshold
                alerts.append({
                    'type': 'warning',
                    'message': f'Low cache hit ratio: {hit_ratio:.1%}',
                    'recommendation': 'Review caching strategy and TTL settings'
                })
            
            # Display alerts
            if alerts:
                for i, alert in enumerate(alerts, 1):
                    if alert['type'] == 'warning':
                        self.stdout.write(self.style.WARNING(f'{i}. ⚠️  {alert["message"]}'))
                    else:
                        self.stdout.write(self.style.ERROR(f'{i}. 🚨 {alert["message"]}'))
                    
                    self.stdout.write(f'   Recommendation: {alert["recommendation"]}')
                    self.stdout.write('')
            else:
                self.stdout.write(self.style.SUCCESS('✅ No performance alerts'))
            
        except Exception as e:
            raise CommandError(f'Failed to get performance alerts: {e}')

    def handle_export(self):
        """Export performance data to JSON."""
        self.stdout.write('Exporting performance data...')
        
        try:
            # Get comprehensive performance data
            summary = performance_metrics.get_performance_summary(1440)  # 24 hours
            
            # Add trend data
            summary['trends'] = {
                'message_delivery': performance_metrics.get_performance_trends('message_delivery', 24),
                'websocket_connections': performance_metrics.get_performance_trends('websocket_connections', 24),
                'database_operations': performance_metrics.get_performance_trends('database_operations', 24),
            }
            
            # Write to file
            filename = f'performance_metrics_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json'
            with open(filename, 'w') as f:
                json.dump(summary, f, indent=2, default=str)
            
            self.stdout.write(f'Performance data exported to: {filename}')
            self.stdout.write(
                self.style.SUCCESS('Export completed successfully')
            )
            
        except Exception as e:
            raise CommandError(f'Export failed: {e}')





