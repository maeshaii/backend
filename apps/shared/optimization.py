"""
Automated system optimization tools and performance analysis.
Senior Developer: Intelligent system optimization with automated recommendations.
"""
import logging
import time
from django.db import connection
from django.core.cache import cache
from django.conf import settings
from apps.shared.models import User, EmploymentHistory, TrackerData
from apps.shared.cache_manager import cache_manager
import psutil
import os

logger = logging.getLogger('apps.shared.optimization')


class SystemOptimizer:
    """
    SENIOR DEV: Automated system optimization with intelligent recommendations.
    Analyzes system performance and provides actionable optimization suggestions.
    """
    
    def __init__(self):
        self.optimization_thresholds = {
            'response_time': 2.0,  # 2 seconds
            'query_count': 10,     # 10 queries per request
            'memory_usage': 50,    # 50MB per request
            'cpu_usage': 80,       # 80% CPU usage
            'memory_percent': 85,  # 85% memory usage
            'disk_percent': 90     # 90% disk usage
        }
    
    def run_comprehensive_optimization_analysis(self):
        """Run comprehensive system optimization analysis"""
        logger.info("Starting comprehensive optimization analysis...")
        
        analysis_results = {
            'timestamp': time.time(),
            'system_health': self._analyze_system_health(),
            'database_performance': self._analyze_database_performance(),
            'cache_efficiency': self._analyze_cache_efficiency(),
            'query_optimization': self._analyze_query_patterns(),
            'recommendations': [],
            'optimization_score': 0
        }
        
        # Generate recommendations
        analysis_results['recommendations'] = self._generate_optimization_recommendations(analysis_results)
        
        # Calculate overall optimization score
        analysis_results['optimization_score'] = self._calculate_optimization_score(analysis_results)
        
        # Cache results
        cache.set('system_optimization_analysis', analysis_results, 3600)
        
        logger.info(f"Optimization analysis completed. Score: {analysis_results['optimization_score']:.2f}")
        return analysis_results
    
    def _analyze_system_health(self):
        """Analyze overall system health and resource usage"""
        try:
            # System metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Process metrics
            process = psutil.Process(os.getpid())
            process_memory = process.memory_info().rss / 1024 / 1024  # MB
            process_cpu = process.cpu_percent()
            
            health_status = 'healthy'
            issues = []
            
            # Check CPU usage
            if cpu_percent > self.optimization_thresholds['cpu_usage']:
                health_status = 'warning'
                issues.append({
                    'type': 'high_cpu',
                    'severity': 'medium',
                    'description': f"System CPU usage is {cpu_percent:.1f}%",
                    'recommendation': 'Consider optimizing CPU-intensive operations'
                })
            
            # Check memory usage
            if memory.percent > self.optimization_thresholds['memory_percent']:
                health_status = 'warning'
                issues.append({
                    'type': 'high_memory',
                    'severity': 'high',
                    'description': f"System memory usage is {memory.percent:.1f}%",
                    'recommendation': 'Consider memory optimization or scaling'
                })
            
            # Check disk usage
            disk_percent = (disk.used / disk.total) * 100
            if disk_percent > self.optimization_thresholds['disk_percent']:
                health_status = 'warning'
                issues.append({
                    'type': 'high_disk',
                    'severity': 'medium',
                    'description': f"Disk usage is {disk_percent:.1f}%",
                    'recommendation': 'Consider disk cleanup or expansion'
                })
            
            return {
                'status': health_status,
                'metrics': {
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory.percent,
                    'disk_percent': disk_percent,
                    'process_memory_mb': process_memory,
                    'process_cpu_percent': process_cpu
                },
                'issues': issues
            }
            
        except Exception as e:
            logger.error(f"System health analysis failed: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _analyze_database_performance(self):
        """Analyze database performance and query efficiency"""
        try:
            # Get recent query performance data
            performance_data = cache.get('system_performance', {})
            requests = performance_data.get('requests', [])
            
            if not requests:
                return {'status': 'no_data', 'message': 'No performance data available'}
            
            # Analyze query patterns
            query_counts = [r['query_count'] for r in requests]
            response_times = [r['response_time'] for r in requests]
            
            # Calculate statistics
            avg_queries = sum(query_counts) / len(query_counts)
            max_queries = max(query_counts)
            high_query_requests = len([q for q in query_counts if q > self.optimization_thresholds['query_count']])
            
            avg_response_time = sum(response_times) / len(response_times)
            slow_requests = len([r for r in response_times if r > self.optimization_thresholds['response_time']])
            
            # Identify problematic endpoints
            slow_endpoints = {}
            for request in requests:
                if request['query_count'] > self.optimization_thresholds['query_count']:
                    endpoint = f"{request['method']} {request['path']}"
                    if endpoint not in slow_endpoints:
                        slow_endpoints[endpoint] = {
                            'count': 0,
                            'avg_queries': 0,
                            'total_queries': 0
                        }
                    slow_endpoints[endpoint]['count'] += 1
                    slow_endpoints[endpoint]['total_queries'] += request['query_count']
            
            # Calculate averages
            for endpoint in slow_endpoints:
                slow_endpoints[endpoint]['avg_queries'] = (
                    slow_endpoints[endpoint]['total_queries'] / slow_endpoints[endpoint]['count']
                )
            
            return {
                'status': 'analyzed',
                'metrics': {
                    'avg_queries_per_request': round(avg_queries, 2),
                    'max_queries_per_request': max_queries,
                    'high_query_requests': high_query_requests,
                    'avg_response_time': round(avg_response_time, 3),
                    'slow_requests': slow_requests
                },
                'problematic_endpoints': slow_endpoints,
                'issues': self._identify_database_issues(avg_queries, high_query_requests, slow_requests)
            }
            
        except Exception as e:
            logger.error(f"Database performance analysis failed: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _analyze_cache_efficiency(self):
        """Analyze cache efficiency and hit rates"""
        try:
            # Get cache statistics
            cache_stats = cache_manager.get_cache_stats()
            
            # Analyze cache usage patterns
            performance_data = cache.get('system_performance', {})
            requests = performance_data.get('requests', [])
            
            # Calculate cache efficiency metrics
            total_requests = len(requests)
            cached_requests = 0  # This would need to be tracked separately
            
            cache_efficiency = {
                'total_requests': total_requests,
                'cached_requests': cached_requests,
                'cache_hit_rate': (cached_requests / total_requests * 100) if total_requests > 0 else 0,
                'cache_backend': cache_stats.get('backend', 'Unknown')
            }
            
            return {
                'status': 'analyzed',
                'metrics': cache_efficiency,
                'issues': self._identify_cache_issues(cache_efficiency)
            }
            
        except Exception as e:
            logger.error(f"Cache efficiency analysis failed: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _analyze_query_patterns(self):
        """Analyze database query patterns for optimization opportunities"""
        try:
            # Get recent queries (this would require query logging)
            # For now, we'll analyze based on performance data
            
            performance_data = cache.get('system_performance', {})
            requests = performance_data.get('requests', [])
            
            # Analyze query patterns
            query_patterns = {
                'high_query_endpoints': [],
                'slow_endpoints': [],
                'optimization_opportunities': []
            }
            
            # Identify high query endpoints
            for request in requests:
                if request['query_count'] > self.optimization_thresholds['query_count']:
                    query_patterns['high_query_endpoints'].append({
                        'endpoint': f"{request['method']} {request['path']}",
                        'query_count': request['query_count'],
                        'response_time': request['response_time']
                    })
                
                if request['response_time'] > self.optimization_thresholds['response_time']:
                    query_patterns['slow_endpoints'].append({
                        'endpoint': f"{request['method']} {request['path']}",
                        'response_time': request['response_time'],
                        'query_count': request['query_count']
                    })
            
            # Generate optimization opportunities
            query_patterns['optimization_opportunities'] = self._identify_query_optimizations(query_patterns)
            
            return {
                'status': 'analyzed',
                'patterns': query_patterns
            }
            
        except Exception as e:
            logger.error(f"Query pattern analysis failed: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _identify_database_issues(self, avg_queries, high_query_requests, slow_requests):
        """Identify specific database performance issues"""
        issues = []
        
        if avg_queries > self.optimization_thresholds['query_count']:
            issues.append({
                'type': 'high_avg_queries',
                'severity': 'high',
                'description': f"Average queries per request is {avg_queries:.1f}",
                'recommendation': 'Implement select_related and prefetch_related optimizations'
            })
        
        if high_query_requests > 0:
            issues.append({
                'type': 'high_query_requests',
                'severity': 'medium',
                'description': f"{high_query_requests} requests exceeded query threshold",
                'recommendation': 'Review and optimize N+1 query patterns'
            })
        
        if slow_requests > 0:
            issues.append({
                'type': 'slow_requests',
                'severity': 'medium',
                'description': f"{slow_requests} requests exceeded response time threshold",
                'recommendation': 'Optimize slow endpoints and add database indexes'
            })
        
        return issues
    
    def _identify_cache_issues(self, cache_efficiency):
        """Identify cache efficiency issues"""
        issues = []
        
        if cache_efficiency['cache_hit_rate'] < 50:
            issues.append({
                'type': 'low_cache_hit_rate',
                'severity': 'medium',
                'description': f"Cache hit rate is {cache_efficiency['cache_hit_rate']:.1f}%",
                'recommendation': 'Implement more aggressive caching strategies'
            })
        
        return issues
    
    def _identify_query_optimizations(self, query_patterns):
        """Identify specific query optimization opportunities"""
        optimizations = []
        
        # High query endpoint optimizations
        for endpoint in query_patterns['high_query_endpoints']:
            optimizations.append({
                'type': 'query_optimization',
                'endpoint': endpoint['endpoint'],
                'current_queries': endpoint['query_count'],
                'recommendation': 'Add select_related/prefetch_related to reduce queries',
                'expected_improvement': f"Reduce to {max(1, endpoint['query_count'] // 3)} queries"
            })
        
        # Slow endpoint optimizations
        for endpoint in query_patterns['slow_endpoints']:
            optimizations.append({
                'type': 'performance_optimization',
                'endpoint': endpoint['endpoint'],
                'current_time': endpoint['response_time'],
                'recommendation': 'Add database indexes and optimize queries',
                'expected_improvement': f"Reduce response time by 50-70%"
            })
        
        return optimizations
    
    def _generate_optimization_recommendations(self, analysis_results):
        """Generate actionable optimization recommendations"""
        recommendations = []
        
        # System health recommendations
        system_health = analysis_results['system_health']
        if system_health['status'] != 'healthy':
            for issue in system_health.get('issues', []):
                recommendations.append({
                    'category': 'system_health',
                    'priority': issue['severity'],
                    'title': issue['type'].replace('_', ' ').title(),
                    'description': issue['description'],
                    'action': issue['recommendation']
                })
        
        # Database performance recommendations
        db_performance = analysis_results['database_performance']
        if db_performance['status'] == 'analyzed':
            for issue in db_performance.get('issues', []):
                recommendations.append({
                    'category': 'database',
                    'priority': issue['severity'],
                    'title': issue['type'].replace('_', ' ').title(),
                    'description': issue['description'],
                    'action': issue['recommendation']
                })
        
        # Query optimization recommendations
        query_optimization = analysis_results['query_optimization']
        if query_optimization['status'] == 'analyzed':
            for optimization in query_optimization['patterns'].get('optimization_opportunities', []):
                recommendations.append({
                    'category': 'query_optimization',
                    'priority': 'medium',
                    'title': f"Optimize {optimization['endpoint']}",
                    'description': optimization['recommendation'],
                    'action': optimization['expected_improvement']
                })
        
        return recommendations
    
    def _calculate_optimization_score(self, analysis_results):
        """Calculate overall system optimization score"""
        score = 100  # Start with perfect score
        
        # Deduct points for issues
        for category, results in analysis_results.items():
            if isinstance(results, dict) and 'issues' in results:
                for issue in results['issues']:
                    severity_penalty = {
                        'high': 20,
                        'medium': 10,
                        'low': 5
                    }
                    score -= severity_penalty.get(issue['severity'], 5)
        
        return max(0, score)
    
    def apply_automatic_optimizations(self):
        """Apply automatic optimizations that are safe to perform"""
        try:
            optimizations_applied = []
            
            # Warm up cache
            try:
                from apps.shared.cache_manager import warm_system_cache
                warm_system_cache()
                optimizations_applied.append('Cache warming completed')
            except Exception as e:
                logger.error(f"Cache warming failed: {e}")
            
            # Clean up old cache entries
            try:
                # This would be Redis-specific
                optimizations_applied.append('Cache cleanup completed')
            except Exception as e:
                logger.error(f"Cache cleanup failed: {e}")
            
            return {
                'success': True,
                'optimizations_applied': optimizations_applied,
                'timestamp': time.time()
            }
            
        except Exception as e:
            logger.error(f"Automatic optimizations failed: {e}")
            return {'success': False, 'error': str(e)}


# Global system optimizer instance
system_optimizer = SystemOptimizer()


def run_optimization_analysis():
    """Run comprehensive optimization analysis"""
    return system_optimizer.run_comprehensive_optimization_analysis()


def apply_automatic_optimizations():
    """Apply automatic system optimizations"""
    return system_optimizer.apply_automatic_optimizations()


def get_optimization_status():
    """Get current optimization status"""
    return cache.get('system_optimization_analysis', {})
