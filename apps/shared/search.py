"""
Advanced search and filtering system with intelligent query processing.
Senior Developer: Comprehensive search capabilities with performance optimization.
"""
import logging
from django.db.models import Q, Count, Case, When, IntegerField, Value
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.core.paginator import Paginator
from apps.shared.models import User, EmploymentHistory, TrackerData, AcademicInfo
from apps.shared.cache_manager import cache_manager
import re

logger = logging.getLogger('apps.shared.search')


class AdvancedSearchEngine:
    """
    SENIOR DEV: Advanced search engine with intelligent filtering and ranking.
    Provides comprehensive search across all user data with performance optimization.
    """
    
    def __init__(self):
        self.search_fields = {
            'user': ['f_name', 'l_name', 'email'],
            'employment': ['position_current', 'company_name_current'],
            'academic': ['program', 'year_graduated'],
            'tracker': ['q_employment_status', 'q_sector_current', 'q_scope_current']
        }
    
    def search_users(self, query, filters=None, page=1, page_size=20):
        """
        Advanced user search with intelligent filtering and ranking.
        """
        try:
            # Start with base queryset
            queryset = User.objects.filter(account_type__user=True).select_related(
                'academic_info', 'employment', 'tracker_data'
            )
            
            # Apply text search
            if query:
                queryset = self._apply_text_search(queryset, query)
            
            # Apply filters
            if filters:
                queryset = self._apply_filters(queryset, filters)
            
            # Add search ranking
            if query:
                queryset = self._add_search_ranking(queryset, query)
            
            # Paginate results
            paginator = Paginator(queryset, page_size)
            page_obj = paginator.get_page(page)
            
            # Format results
            results = []
            for user in page_obj:
                result = self._format_user_result(user)
                results.append(result)
            
            return {
                'success': True,
                'results': results,
                'pagination': {
                    'current_page': page,
                    'total_pages': paginator.num_pages,
                    'total_results': paginator.count,
                    'has_next': page_obj.has_next(),
                    'has_previous': page_obj.has_previous()
                },
                'query': query,
                'filters_applied': filters or {}
            }
            
        except Exception as e:
            logger.error(f"User search failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _apply_text_search(self, queryset, query):
        """Apply intelligent text search across multiple fields"""
        # Clean and prepare query
        query = query.strip()
        if not query:
            return queryset
        
        # Create search conditions
        search_conditions = Q()
        
        # Name search (exact and partial)
        if len(query) >= 2:
            search_conditions |= Q(f_name__icontains=query)
            search_conditions |= Q(l_name__icontains=query)
            search_conditions |= Q(email__icontains=query)
        
        # Employment search
        search_conditions |= Q(employment__position_current__icontains=query)
        search_conditions |= Q(employment__company_name_current__icontains=query)
        
        # Academic search
        search_conditions |= Q(academic_info__program__icontains=query)
        
        # Tracker search
        search_conditions |= Q(tracker_data__q_employment_status__icontains=query)
        search_conditions |= Q(tracker_data__q_sector_current__icontains=query)
        
        return queryset.filter(search_conditions).distinct()
    
    def _apply_filters(self, queryset, filters):
        """Apply advanced filtering options"""
        filter_conditions = Q()
        
        # Program filter
        if filters.get('program'):
            programs = filters['program'].split(',')
            filter_conditions &= Q(academic_info__program__in=programs)
        
        # Employment status filter
        if filters.get('employment_status'):
            status = filters['employment_status']
            if status == 'employed':
                filter_conditions &= Q(tracker_data__q_employment_status__iexact='yes')
            elif status == 'unemployed':
                filter_conditions &= Q(tracker_data__q_employment_status__iexact='no')
        
        # Job alignment filter
        if filters.get('job_alignment'):
            alignment = filters['job_alignment']
            filter_conditions &= Q(employment__job_alignment_status=alignment)
        
        # Sector filter
        if filters.get('sector'):
            sectors = filters['sector'].split(',')
            filter_conditions &= Q(tracker_data__q_sector_current__in=sectors)
        
        # Scope filter
        if filters.get('scope'):
            scopes = filters['scope'].split(',')
            filter_conditions &= Q(tracker_data__q_scope_current__in=scopes)
        
        # Year graduated filter
        if filters.get('year_graduated'):
            year = filters['year_graduated']
            filter_conditions &= Q(academic_info__year_graduated=year)
        
        # Date range filters
        if filters.get('graduated_after'):
            filter_conditions &= Q(academic_info__year_graduated__gte=filters['graduated_after'])
        
        if filters.get('graduated_before'):
            filter_conditions &= Q(academic_info__year_graduated__lte=filters['graduated_before'])
        
        return queryset.filter(filter_conditions)
    
    def _add_search_ranking(self, queryset, query):
        """Add search ranking based on relevance"""
        # Simple ranking based on field matches
        queryset = queryset.annotate(
            search_rank=Case(
                # Exact name matches get highest rank
                When(f_name__iexact=query, then=Value(100)),
                When(l_name__iexact=query, then=Value(100)),
                When(email__iexact=query, then=Value(100)),
                
                # Partial name matches
                When(f_name__icontains=query, then=Value(80)),
                When(l_name__icontains=query, then=Value(80)),
                When(email__icontains=query, then=Value(70)),
                
                # Employment matches
                When(employment__position_current__icontains=query, then=Value(60)),
                When(employment__company_name_current__icontains=query, then=Value(50)),
                
                # Academic matches
                When(academic_info__program__icontains=query, then=Value(40)),
                
                # Default rank
                default=Value(10),
                output_field=IntegerField()
            )
        ).order_by('-search_rank', 'f_name', 'l_name')
        
        return queryset
    
    def _format_user_result(self, user):
        """Format user data for search results"""
        return {
            'user_id': user.user_id,
            'name': f"{user.f_name} {user.l_name}",
            'email': user.email,
            'program': getattr(user.academic_info, 'program', 'Unknown'),
            'year_graduated': getattr(user.academic_info, 'year_graduated', None),
            'employment_status': getattr(user.tracker_data, 'q_employment_status', 'Unknown'),
            'current_position': getattr(user.employment, 'position_current', 'Not specified'),
            'current_company': getattr(user.employment, 'company_name_current', 'Not specified'),
            'job_alignment_status': getattr(user.employment, 'job_alignment_status', 'Unknown'),
            'sector': getattr(user.tracker_data, 'q_sector_current', 'Unknown'),
            'scope': getattr(user.tracker_data, 'q_scope_current', 'Unknown')
        }
    
    def get_search_suggestions(self, query, limit=10):
        """Get search suggestions based on partial query"""
        try:
            suggestions = []
            
            if len(query) < 2:
                return {'suggestions': suggestions}
            
            # Name suggestions
            name_suggestions = User.objects.filter(
                account_type__user=True,
                f_name__icontains=query
            ).values_list('f_name', flat=True).distinct()[:limit//3]
            
            for name in name_suggestions:
                suggestions.append({
                    'type': 'name',
                    'text': name,
                    'category': 'First Name'
                })
            
            # Program suggestions
            program_suggestions = AcademicInfo.objects.filter(
                program__icontains=query
            ).values_list('program', flat=True).distinct()[:limit//3]
            
            for program in program_suggestions:
                suggestions.append({
                    'type': 'program',
                    'text': program,
                    'category': 'Program'
                })
            
            # Position suggestions
            position_suggestions = EmploymentHistory.objects.filter(
                position_current__icontains=query
            ).exclude(position_current__isnull=True).exclude(position_current='').values_list(
                'position_current', flat=True
            ).distinct()[:limit//3]
            
            for position in position_suggestions:
                suggestions.append({
                    'type': 'position',
                    'text': position,
                    'category': 'Job Position'
                })
            
            return {'suggestions': suggestions[:limit]}
            
        except Exception as e:
            logger.error(f"Search suggestions failed: {e}")
            return {'suggestions': []}
    
    def get_search_filters(self):
        """Get available search filters and their options"""
        try:
            filters = {
                'programs': list(AcademicInfo.objects.values_list('program', flat=True).distinct()),
                'employment_statuses': ['employed', 'unemployed'],
                'job_alignment_statuses': ['aligned', 'not_aligned', 'pending_user_confirmation'],
                'sectors': list(TrackerData.objects.exclude(
                    q_sector_current__isnull=True
                ).exclude(
                    q_sector_current=''
                ).values_list('q_sector_current', flat=True).distinct()),
                'scopes': list(TrackerData.objects.exclude(
                    q_scope_current__isnull=True
                ).exclude(
                    q_scope_current=''
                ).values_list('q_scope_current', flat=True).distinct()),
                'years': list(AcademicInfo.objects.exclude(
                    year_graduated__isnull=True
                ).values_list('year_graduated', flat=True).distinct().order_by('-year_graduated'))
            }
            
            return {'filters': filters}
            
        except Exception as e:
            logger.error(f"Get search filters failed: {e}")
            return {'filters': {}}
    
    def get_search_analytics(self):
        """Get search analytics and popular queries"""
        try:
            # This would typically come from a search log
            # For now, we'll return mock data
            analytics = {
                'popular_queries': [
                    {'query': 'software developer', 'count': 45},
                    {'query': 'BSIT', 'count': 38},
                    {'query': 'employed', 'count': 32},
                    {'query': '2023', 'count': 28},
                    {'query': 'private', 'count': 25}
                ],
                'search_stats': {
                    'total_searches': 1250,
                    'unique_users': 890,
                    'avg_results_per_search': 15.3,
                    'zero_result_searches': 45
                }
            }
            
            return {'analytics': analytics}
            
        except Exception as e:
            logger.error(f"Search analytics failed: {e}")
            return {'analytics': {}}


# Global search engine instance
search_engine = AdvancedSearchEngine()


def search_users(query, filters=None, page=1, page_size=20):
    """Search users with advanced filtering"""
    return search_engine.search_users(query, filters, page, page_size)


def get_search_suggestions(query, limit=10):
    """Get search suggestions"""
    return search_engine.get_search_suggestions(query, limit)


def get_search_filters():
    """Get available search filters"""
    return search_engine.get_search_filters()


def get_search_analytics():
    """Get search analytics"""
    return search_engine.get_search_analytics()
