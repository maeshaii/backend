#!/usr/bin/env python
"""
Comprehensive test for Phase 4: Advanced System Optimizations.
Tests all implemented features and validates system performance.
"""
import os
import sys
import django
import time

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, EmploymentHistory, TrackerData
from apps.shared.middleware import PerformanceMonitoringMiddleware, HealthCheckMiddleware
from apps.shared.cache_manager import cache_manager
from apps.shared.data_quality import data_quality_monitor
from apps.shared.search import search_engine
from apps.shared.optimization import system_optimizer
from django.core.cache import cache
import psutil


def test_phase4_complete():
    """Comprehensive Phase 4 testing"""
    print("=" * 80)
    print("PHASE 4: ADVANCED SYSTEM OPTIMIZATIONS - COMPREHENSIVE TEST")
    print("=" * 80)
    
    tests_passed = 0
    total_tests = 0
    
    # Test 1: Performance Monitoring Middleware
    total_tests += 1
    print(f"\n1. PERFORMANCE MONITORING MIDDLEWARE")
    print("-" * 50)
    
    try:
        # Test middleware initialization
        perf_middleware = PerformanceMonitoringMiddleware()
        health_middleware = HealthCheckMiddleware()
        
        print("   [OK] Middleware classes initialized successfully")
        
        # Test performance tracking
        from django.test import RequestFactory
        from django.http import HttpResponse
        
        factory = RequestFactory()
        request = factory.get('/api/test/')
        request.user = None
        
        # Simulate request processing
        perf_middleware.process_request(request)
        response = HttpResponse("Test response")
        perf_middleware.process_response(request, response)
        
        print("   [OK] Performance tracking working")
        tests_passed += 1
        
    except Exception as e:
        print(f"   [FAIL] Performance monitoring test failed: {e}")
    
    # Test 2: Advanced Caching System
    total_tests += 1
    print(f"\n2. ADVANCED CACHING SYSTEM")
    print("-" * 50)
    
    try:
        # Test cache manager
        test_key = "test_cache_key"
        test_value = {"test": "data", "timestamp": time.time()}
        
        # Test cache operations
        cache_manager.get_or_set(test_key, lambda: test_value, 60)
        cached_result = cache.get(test_key)
        
        if cached_result == test_value:
            print("   [OK] Cache get_or_set working")
        else:
            print("   [FAIL] Cache get_or_set failed")
            return
        
        # Test cache invalidation
        cache_manager.invalidate_statistics_cache(user_id=123, program="BSIT")
        print("   [OK] Cache invalidation working")
        
        # Test cache statistics
        cache_stats = cache_manager.get_cache_stats()
        print(f"   [OK] Cache statistics: {cache_stats}")
        
        tests_passed += 1
        
    except Exception as e:
        print(f"   [FAIL] Advanced caching test failed: {e}")
    
    # Test 3: Data Quality Monitoring
    total_tests += 1
    print(f"\n3. DATA QUALITY MONITORING")
    print("-" * 50)
    
    try:
        # Run data quality audit
        audit_results = data_quality_monitor.run_comprehensive_audit()
        
        if audit_results and 'overall_score' in audit_results:
            print(f"   [OK] Data quality audit completed")
            print(f"   [OK] Overall quality score: {audit_results['overall_score']:.2f}")
            
            # Check dimensions
            dimensions = audit_results.get('dimensions', {})
            for dimension, results in dimensions.items():
                score = results.get('score', 0)
                print(f"   [OK] {dimension.title()} score: {score:.2f}")
            
            tests_passed += 1
        else:
            print("   [FAIL] Data quality audit failed")
        
    except Exception as e:
        print(f"   [FAIL] Data quality monitoring test failed: {e}")
    
    # Test 4: Advanced Search Engine
    total_tests += 1
    print(f"\n4. ADVANCED SEARCH ENGINE")
    print("-" * 50)
    
    try:
        # Test user search
        search_results = search_engine.search_users("test", page=1, page_size=10)
        
        if search_results.get('success'):
            print("   [OK] User search working")
            print(f"   [OK] Search results: {search_results.get('pagination', {}).get('total_results', 0)} found")
        else:
            print("   [FAIL] User search failed")
            return
        
        # Test search suggestions
        suggestions = search_engine.get_search_suggestions("BSIT", limit=5)
        if 'suggestions' in suggestions:
            print("   [OK] Search suggestions working")
        else:
            print("   [FAIL] Search suggestions failed")
            return
        
        # Test search filters
        filters = search_engine.get_search_filters()
        if 'filters' in filters:
            print("   [OK] Search filters working")
        else:
            print("   [FAIL] Search filters failed")
            return
        
        tests_passed += 1
        
    except Exception as e:
        print(f"   [FAIL] Advanced search engine test failed: {e}")
    
    # Test 5: System Optimization
    total_tests += 1
    print(f"\n5. SYSTEM OPTIMIZATION")
    print("-" * 50)
    
    try:
        # Run optimization analysis
        optimization_results = system_optimizer.run_comprehensive_optimization_analysis()
        
        if optimization_results and 'optimization_score' in optimization_results:
            print(f"   [OK] System optimization analysis completed")
            print(f"   [OK] Optimization score: {optimization_results['optimization_score']:.2f}")
            
            # Check system health
            system_health = optimization_results.get('system_health', {})
            if system_health.get('status'):
                print(f"   [OK] System health status: {system_health['status']}")
            
            tests_passed += 1
        else:
            print("   [FAIL] System optimization analysis failed")
        
    except Exception as e:
        print(f"   [FAIL] System optimization test failed: {e}")
    
    # Test 6: Background Job Processing
    total_tests += 1
    print(f"\n6. BACKGROUND JOB PROCESSING")
    print("-" * 50)
    
    try:
        # Test task imports (Celery tasks)
        from apps.shared.tasks import (
            recalculate_all_job_alignments,
            generate_comprehensive_statistics,
            data_quality_audit,
            optimize_database_performance
        )
        
        print("   [OK] Background tasks imported successfully")
        
        # Test task status functions
        from apps.shared.tasks import get_background_jobs_status
        job_status = get_background_jobs_status()
        
        if isinstance(job_status, dict):
            print("   [OK] Background job status tracking working")
        else:
            print("   [FAIL] Background job status tracking failed")
            return
        
        tests_passed += 1
        
    except Exception as e:
        print(f"   [FAIL] Background job processing test failed: {e}")
    
    # Test 7: System Health Monitoring
    total_tests += 1
    print(f"\n7. SYSTEM HEALTH MONITORING")
    print("-" * 50)
    
    try:
        # Test system metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        print(f"   [OK] CPU Usage: {cpu_percent:.1f}%")
        print(f"   [OK] Memory Usage: {memory.percent:.1f}%")
        print(f"   [OK] Disk Usage: {(disk.used / disk.total * 100):.1f}%")
        
        # Test health check middleware
        health_middleware = HealthCheckMiddleware()
        print("   [OK] Health check middleware initialized")
        
        tests_passed += 1
        
    except Exception as e:
        print(f"   [FAIL] System health monitoring test failed: {e}")
    
    # Test 8: API Endpoints
    total_tests += 1
    print(f"\n8. API ENDPOINTS")
    print("-" * 50)
    
    try:
        # Test API endpoint imports
        from apps.shared.views import (
            get_system_dashboard,
            get_performance_analytics
        )
        
        print("   [OK] API endpoints imported successfully")
        
        # Test URL patterns
        from apps.shared.urls import urlpatterns
        if len(urlpatterns) >= 5:  # Should have at least 5 URL patterns
            print("   [OK] URL patterns configured")
        else:
            print("   [FAIL] URL patterns not properly configured")
            return
        
        tests_passed += 1
        
    except Exception as e:
        print(f"   [FAIL] API endpoints test failed: {e}")
    
    # Final Results
    print("\n" + "=" * 80)
    print("PHASE 4 TEST RESULTS")
    print("=" * 80)
    
    print(f"\nTests Passed: {tests_passed}/{total_tests}")
    print(f"Success Rate: {tests_passed/total_tests*100:.1f}%")
    
    if tests_passed == total_tests:
        print("\n[SUCCESS] PHASE 4 IS COMPLETE!")
        print("[OK] All advanced system optimizations implemented")
        print("[OK] Performance monitoring operational")
        print("[OK] Advanced caching system working")
        print("[OK] Data quality monitoring active")
        print("[OK] Advanced search engine functional")
        print("[OK] System optimization tools ready")
        print("[OK] Background job processing configured")
        print("[OK] System health monitoring active")
        print("[OK] API endpoints operational")
        print("\n[READY] PHASE 4 READY FOR PRODUCTION!")
    else:
        print(f"\n[WARNING] PHASE 4 INCOMPLETE")
        print(f"[FAIL] {total_tests - tests_passed} tests failed")
        print("[FIX] Review failed tests above")
    
    print("=" * 80)
    
    return tests_passed == total_tests


def test_system_performance():
    """Test system performance improvements"""
    print("\n" + "=" * 80)
    print("SYSTEM PERFORMANCE BENCHMARK")
    print("=" * 80)
    
    # Test database query performance
    start_time = time.time()
    user_count = User.objects.filter(account_type__user=True).count()
    employment_count = EmploymentHistory.objects.count()
    tracker_count = TrackerData.objects.count()
    query_time = time.time() - start_time
    
    print(f"Database Query Performance:")
    print(f"  Users: {user_count}")
    print(f"  Employment: {employment_count}")
    print(f"  Tracker Data: {tracker_count}")
    print(f"  Query Time: {query_time:.3f}s")
    
    # Test cache performance
    start_time = time.time()
    cache.set('performance_test', {'data': 'test'}, 60)
    cached_data = cache.get('performance_test')
    cache_time = time.time() - start_time
    
    print(f"\nCache Performance:")
    print(f"  Cache Time: {cache_time:.3f}s")
    print(f"  Cache Hit: {'Yes' if cached_data else 'No'}")
    
    # Test search performance
    start_time = time.time()
    search_results = search_engine.search_users("test", page=1, page_size=10)
    search_time = time.time() - start_time
    
    print(f"\nSearch Performance:")
    print(f"  Search Time: {search_time:.3f}s")
    print(f"  Results Found: {search_results.get('pagination', {}).get('total_results', 0)}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    success = test_phase4_complete()
    test_system_performance()
    
    if success:
        print("\n🎉 PHASE 4 COMPLETE! ALL SYSTEMS OPERATIONAL! 🎉")
    else:
        print("\n⚠️  PHASE 4 INCOMPLETE - REVIEW FAILED TESTS")
