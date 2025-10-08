"""
Comprehensive data quality monitoring and validation system.
Senior Developer: Advanced data quality checks with automated reporting and alerts.
"""
import logging
from django.db.models import Q, Count
from django.core.cache import cache
from apps.shared.models import User, EmploymentHistory, TrackerData, AcademicInfo
from datetime import datetime, timedelta
import time

logger = logging.getLogger('apps.shared.data_quality')


class DataQualityMonitor:
    """
    SENIOR DEV: Comprehensive data quality monitoring system.
    Provides real-time data quality assessment and automated issue detection.
    """
    
    def __init__(self):
        self.quality_thresholds = {
            'completeness': 0.95,  # 95% data completeness
            'consistency': 0.90,   # 90% data consistency
            'accuracy': 0.85,      # 85% data accuracy
            'validity': 0.98       # 98% data validity
        }
    
    def run_comprehensive_audit(self):
        """Run comprehensive data quality audit"""
        logger.info("Starting comprehensive data quality audit...")
        
        audit_results = {
            'timestamp': time.time(),
            'overall_score': 0,
            'dimensions': {},
            'issues': [],
            'recommendations': []
        }
        
        # Check each quality dimension
        audit_results['dimensions']['completeness'] = self._check_completeness()
        audit_results['dimensions']['consistency'] = self._check_consistency()
        audit_results['dimensions']['accuracy'] = self._check_accuracy()
        audit_results['dimensions']['validity'] = self._check_validity()
        
        # Calculate overall score
        dimension_scores = [d['score'] for d in audit_results['dimensions'].values()]
        audit_results['overall_score'] = sum(dimension_scores) / len(dimension_scores)
        
        # Generate recommendations
        audit_results['recommendations'] = self._generate_recommendations(audit_results)
        
        # Cache results
        cache.set('data_quality_audit', audit_results, 3600)
        
        logger.info(f"Data quality audit completed. Overall score: {audit_results['overall_score']:.2f}")
        return audit_results
    
    def _check_completeness(self):
        """Check data completeness across all tables"""
        issues = []
        total_records = 0
        complete_records = 0
        
        # Check User completeness
        total_users = User.objects.filter(account_type__user=True).count()
        complete_users = User.objects.filter(
            account_type__user=True,
            f_name__isnull=False,
            l_name__isnull=False,
            email__isnull=False
        ).count()
        
        total_records += total_users
        complete_records += complete_users
        
        if total_users > 0:
            completeness_rate = complete_users / total_users
            if completeness_rate < self.quality_thresholds['completeness']:
                issues.append({
                    'type': 'incomplete_users',
                    'severity': 'medium',
                    'description': f"{total_users - complete_users} users missing required fields",
                    'impact': f"Completeness rate: {completeness_rate:.2%}"
                })
        
        # Check Employment completeness
        total_employment = EmploymentHistory.objects.count()
        complete_employment = EmploymentHistory.objects.filter(
            position_current__isnull=False,
            company_name_current__isnull=False
        ).exclude(
            position_current='',
            company_name_current=''
        ).count()
        
        total_records += total_employment
        complete_records += complete_employment
        
        if total_employment > 0:
            completeness_rate = complete_employment / total_employment
            if completeness_rate < self.quality_thresholds['completeness']:
                issues.append({
                    'type': 'incomplete_employment',
                    'severity': 'high',
                    'description': f"{total_employment - complete_employment} employment records missing position/company",
                    'impact': f"Completeness rate: {completeness_rate:.2%}"
                })
        
        # Check TrackerData completeness
        total_tracker = TrackerData.objects.count()
        complete_tracker = TrackerData.objects.filter(
            q_employment_status__isnull=False
        ).exclude(
            q_employment_status=''
        ).count()
        
        total_records += total_tracker
        complete_records += total_tracker
        
        if total_tracker > 0:
            completeness_rate = complete_tracker / total_tracker
            if completeness_rate < self.quality_thresholds['completeness']:
                issues.append({
                    'type': 'incomplete_tracker',
                    'severity': 'medium',
                    'description': f"{total_tracker - complete_tracker} tracker records missing employment status",
                    'impact': f"Completeness rate: {completeness_rate:.2%}"
                })
        
        # Calculate overall completeness score
        overall_completeness = complete_records / total_records if total_records > 0 else 1.0
        
        return {
            'score': overall_completeness,
            'issues': issues,
            'metrics': {
                'total_records': total_records,
                'complete_records': complete_records,
                'completeness_rate': overall_completeness
            }
        }
    
    def _check_consistency(self):
        """Check data consistency across related tables"""
        issues = []
        
        # Check employment status consistency
        employed_but_no_position = TrackerData.objects.filter(
            q_employment_status__iexact='yes'
        ).exclude(
            user__employment__position_current__isnull=False
        ).exclude(
            user__employment__position_current=''
        ).count()
        
        if employed_but_no_position > 0:
            issues.append({
                'type': 'employment_status_inconsistency',
                'severity': 'high',
                'description': f"{employed_but_no_position} users marked as employed but have no position",
                'impact': 'Statistics accuracy affected'
            })
        
        # Check unemployed but has position
        unemployed_but_has_position = TrackerData.objects.filter(
            q_employment_status__iexact='no'
        ).filter(
            user__employment__position_current__isnull=False
        ).exclude(
            user__employment__position_current=''
        ).count()
        
        if unemployed_but_has_position > 0:
            issues.append({
                'type': 'unemployment_inconsistency',
                'severity': 'medium',
                'description': f"{unemployed_but_has_position} users marked as unemployed but have positions",
                'impact': 'Data integrity compromised'
            })
        
        # Check program consistency
        users_without_academic_info = User.objects.filter(
            account_type__user=True,
            academic_info__isnull=True
        ).count()
        
        if users_without_academic_info > 0:
            issues.append({
                'type': 'missing_academic_info',
                'severity': 'high',
                'description': f"{users_without_academic_info} users missing academic information",
                'impact': 'Program-based statistics affected'
            })
        
        # Calculate consistency score
        total_inconsistencies = sum([
            employed_but_no_position,
            unemployed_but_has_position,
            users_without_academic_info
        ])
        
        total_records = User.objects.filter(account_type__user=True).count()
        consistency_score = max(0, 1 - (total_inconsistencies / max(total_records, 1)))
        
        return {
            'score': consistency_score,
            'issues': issues,
            'metrics': {
                'total_inconsistencies': total_inconsistencies,
                'total_records': total_records,
                'consistency_rate': consistency_score
            }
        }
    
    def _check_accuracy(self):
        """Check data accuracy and reasonableness"""
        issues = []
        
        # Check for 'nan' values
        nan_positions = EmploymentHistory.objects.filter(
            position_current__iexact='nan'
        ).count()
        
        if nan_positions > 0:
            issues.append({
                'type': 'nan_values',
                'severity': 'high',
                'description': f"{nan_positions} employment records contain 'nan' values",
                'impact': 'Data quality severely affected'
            })
        
        # Check for future dates
        from django.utils import timezone
        future_dates = EmploymentHistory.objects.filter(
            date_started__gt=timezone.now().date()
        ).count()
        
        if future_dates > 0:
            issues.append({
                'type': 'future_dates',
                'severity': 'medium',
                'description': f"{future_dates} employment records have future start dates",
                'impact': 'Data accuracy questionable'
            })
        
        # Check for unrealistic salary ranges
        unrealistic_salaries = TrackerData.objects.filter(
            q_salary_range__icontains='999999'
        ).count()
        
        if unrealistic_salaries > 0:
            issues.append({
                'type': 'unrealistic_salaries',
                'severity': 'low',
                'description': f"{unrealistic_salaries} records have unrealistic salary values",
                'impact': 'Statistics may be skewed'
            })
        
        # Calculate accuracy score
        total_accuracy_issues = sum([
            nan_positions,
            future_dates,
            unrealistic_salaries
        ])
        
        total_records = EmploymentHistory.objects.count() + TrackerData.objects.count()
        accuracy_score = max(0, 1 - (total_accuracy_issues / max(total_records, 1)))
        
        return {
            'score': accuracy_score,
            'issues': issues,
            'metrics': {
                'total_accuracy_issues': total_accuracy_issues,
                'total_records': total_records,
                'accuracy_rate': accuracy_score
            }
        }
    
    def _check_validity(self):
        """Check data validity and format compliance"""
        issues = []
        
        # Check email format validity
        invalid_emails = User.objects.filter(
            account_type__user=True,
            email__isnull=False
        ).exclude(
            email__regex=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        ).count()
        
        if invalid_emails > 0:
            issues.append({
                'type': 'invalid_emails',
                'severity': 'medium',
                'description': f"{invalid_emails} users have invalid email formats",
                'impact': 'Communication issues possible'
            })
        
        # Check program validity
        valid_programs = ['BSIT', 'BSIS', 'BIT-CT', 'Computer Technology', 'Information Technology', 'Information System']
        invalid_programs = User.objects.filter(
            account_type__user=True
        ).exclude(
            academic_info__program__in=valid_programs
        ).count()
        
        if invalid_programs > 0:
            issues.append({
                'type': 'invalid_programs',
                'severity': 'high',
                'description': f"{invalid_programs} users have invalid program names",
                'impact': 'Program-based statistics affected'
            })
        
        # Check job alignment status validity
        valid_statuses = ['aligned', 'not_aligned', 'pending_user_confirmation']
        invalid_statuses = EmploymentHistory.objects.exclude(
            job_alignment_status__in=valid_statuses
        ).exclude(
            job_alignment_status__isnull=True
        ).count()
        
        if invalid_statuses > 0:
            issues.append({
                'type': 'invalid_alignment_status',
                'severity': 'medium',
                'description': f"{invalid_statuses} employment records have invalid alignment status",
                'impact': 'Job alignment statistics affected'
            })
        
        # Calculate validity score
        total_validity_issues = sum([
            invalid_emails,
            invalid_programs,
            invalid_statuses
        ])
        
        total_records = User.objects.filter(account_type__user=True).count() + EmploymentHistory.objects.count()
        validity_score = max(0, 1 - (total_validity_issues / max(total_records, 1)))
        
        return {
            'score': validity_score,
            'issues': issues,
            'metrics': {
                'total_validity_issues': total_validity_issues,
                'total_records': total_records,
                'validity_rate': validity_score
            }
        }
    
    def _generate_recommendations(self, audit_results):
        """Generate actionable recommendations based on audit results"""
        recommendations = []
        
        # Overall score recommendations
        if audit_results['overall_score'] < 0.8:
            recommendations.append({
                'priority': 'high',
                'category': 'overall',
                'title': 'Overall Data Quality Below Threshold',
                'description': 'Data quality score is below 80%. Immediate attention required.',
                'actions': [
                    'Review and fix critical data issues',
                    'Implement data validation rules',
                    'Schedule regular data quality audits'
                ]
            })
        
        # Dimension-specific recommendations
        for dimension, results in audit_results['dimensions'].items():
            if results['score'] < self.quality_thresholds[dimension]:
                recommendations.append({
                    'priority': 'medium' if results['score'] > 0.7 else 'high',
                    'category': dimension,
                    'title': f'{dimension.title()} Issues Detected',
                    'description': f'{dimension.title()} score is {results["score"]:.2%}',
                    'actions': self._get_dimension_actions(dimension, results)
                })
        
        return recommendations
    
    def _get_dimension_actions(self, dimension, results):
        """Get specific actions for each dimension"""
        actions_map = {
            'completeness': [
                'Implement required field validation',
                'Add data entry validation rules',
                'Schedule data completion campaigns'
            ],
            'consistency': [
                'Review data entry processes',
                'Implement cross-table validation',
                'Add consistency checks in forms'
            ],
            'accuracy': [
                'Clean up invalid data entries',
                'Implement data validation rules',
                'Add data verification processes'
            ],
            'validity': [
                'Update data format validation',
                'Implement format checking',
                'Add data type validation'
            ]
        }
        
        return actions_map.get(dimension, ['Review data quality issues'])
    
    def get_quality_dashboard(self):
        """Get data quality dashboard information"""
        try:
            # Get cached audit results
            audit_results = cache.get('data_quality_audit')
            
            if not audit_results:
                # Run fresh audit if no cached results
                audit_results = self.run_comprehensive_audit()
            
            # Add real-time metrics
            real_time_metrics = {
                'total_users': User.objects.filter(account_type__user=True).count(),
                'total_employment': EmploymentHistory.objects.count(),
                'total_tracker_data': TrackerData.objects.count(),
                'nan_values_count': EmploymentHistory.objects.filter(position_current__iexact='nan').count(),
                'empty_positions_count': EmploymentHistory.objects.filter(position_current__in=['', None]).count()
            }
            
            return {
                'audit_results': audit_results,
                'real_time_metrics': real_time_metrics,
                'last_updated': audit_results.get('timestamp', time.time())
            }
            
        except Exception as e:
            logger.error(f"Failed to get quality dashboard: {e}")
            return {'error': str(e)}


# Global data quality monitor instance
data_quality_monitor = DataQualityMonitor()


def run_data_quality_check():
    """Run a quick data quality check"""
    return data_quality_monitor.run_comprehensive_audit()


def get_data_quality_status():
    """Get current data quality status"""
    return data_quality_monitor.get_quality_dashboard()
