from django.db import transaction
from .models import User, UserProfile, AcademicInfo, EmploymentHistory, TrackerData, OJTInfo


class UserService:
    """Service class for User model operations with refactored structure"""
    
    @staticmethod
    def create_complete_user(user_data, profile_data=None, academic_data=None, employment_data=None, tracker_data=None, ojt_data=None):
        """Create a user with all related models in a single transaction"""
        with transaction.atomic():
            # Create core User, hashing password if provided
            password = user_data.pop('acc_password', None)
            user = User(**user_data)
            if password:
                user.set_password(password)
            user.save()
            
            # Create UserProfile
            if profile_data:
                UserProfile.objects.create(user=user, **profile_data)
            else:
                UserProfile.objects.create(user=user)
            
            # Create AcademicInfo
            if academic_data:
                AcademicInfo.objects.create(user=user, **academic_data)
            else:
                AcademicInfo.objects.create(user=user)
            
            # Create TrackerData
            if tracker_data:
                TrackerData.objects.create(user=user, **tracker_data)
            else:
                TrackerData.objects.create(user=user)
            
            # Create EmploymentHistory if provided
            if employment_data:
                EmploymentHistory.objects.create(user=user, **employment_data)
            
            # Create OJTInfo if provided
            if ojt_data:
                OJTInfo.objects.create(user=user, **ojt_data)
            
            return user
    
    @staticmethod
    def get_user_with_related_data(user_id):
        """Get user with all related data"""
        try:
            user = User.objects.select_related(
                'profile', 'academic_info', 'tracker_data', 'ojt_info', 'employment'
            ).get(user_id=user_id)
            
            return {
                'user': user,
                'profile': getattr(user, 'profile', None),
                'academic_info': getattr(user, 'academic_info', None),
                'tracker_data': getattr(user, 'tracker_data', None),
                'ojt_info': getattr(user, 'ojt_info', None),
                'employment': getattr(user, 'employment', None),
            }
        except User.DoesNotExist:
            return None
    
    @staticmethod
    def update_employment_status(user, employment_data):
        """Update user's employment status"""
        with transaction.atomic():
            # Get or create employment record
            employment, created = EmploymentHistory.objects.get_or_create(user=user)
            
            # Update employment fields
            for field, value in employment_data.items():
                setattr(employment, field, value)
            employment.save()
            
            # Update job alignment
            employment.update_job_alignment()
            
            # Update tracker data
            tracker, created = TrackerData.objects.get_or_create(user=user)
            tracker.q_company_name = employment.company_name_current
            tracker.q_current_position = employment.position_current
            tracker.q_job_sector = employment.sector_current
            tracker.q_employment_status = 'employed' if employment.company_name_current else 'unemployed'
            tracker.save()
            
            return employment
    
    @staticmethod
    def get_alumni_statistics():
        """Get alumni statistics using refactored models"""
        from django.db.models import Count, Q
        
        total_alumni = User.objects.filter(account_type__user=True).count()
        
        # Employment statistics
        employed_count = TrackerData.objects.filter(
            q_employment_status='employed'
        ).count()
        
        unemployed_count = TrackerData.objects.filter(
            q_employment_status='unemployed'
        ).count()
        
        # Job alignment statistics
        aligned_jobs = EmploymentHistory.objects.filter(
            job_alignment_status='aligned'
        ).count()
        
        # Further study statistics
        pursuing_study = AcademicInfo.objects.filter(
            pursue_further_study='yes'
        ).count()
        
        return {
            'total_alumni': total_alumni,
            'employed': employed_count,
            'unemployed': unemployed_count,
            'employment_rate': (employed_count / total_alumni * 100) if total_alumni > 0 else 0,
            'job_aligned': aligned_jobs,
            'pursuing_study': pursuing_study,
        }
    
    @staticmethod
    def search_alumni(query, filters=None):
        """Search alumni with refactored model structure"""
        from django.db.models import Q
        
        queryset = User.objects.select_related(
            'profile', 'academic_info', 'tracker_data'
        ).filter(account_type__user=True)
        
        if query:
            queryset = queryset.filter(
                Q(f_name__icontains=query) |
                Q(l_name__icontains=query) |
                Q(acc_username__icontains=query) |
                Q(profile__email__icontains=query) |
                Q(academic_info__course__icontains=query)
            )
        
        if filters:
            if 'year_graduated' in filters:
                queryset = queryset.filter(academic_info__year_graduated=filters['year_graduated'])
            
            if 'course' in filters:
                queryset = queryset.filter(academic_info__course__icontains=filters['course'])
            
            if 'employment_status' in filters:
                queryset = queryset.filter(tracker_data__q_employment_status=filters['employment_status'])
        
        return queryset
    
    @staticmethod
    def migrate_legacy_user_data(user):
        """Migrate data from legacy User fields to refactored models"""
        with transaction.atomic():
            # Create or update UserProfile
            profile, created = UserProfile.objects.get_or_create(user=user)
            legacy_profile_fields = [
                'phone_num', 'email', 'address', 'home_address', 'birthdate', 
                'age', 'civil_status', 'social_media', 'profile_pic', 
                'profile_bio', 'profile_resume'
            ]
            for field in legacy_profile_fields:
                if hasattr(user, field):
                    setattr(profile, field, getattr(user, field))
            profile.save()
            
            # Create or update AcademicInfo
            academic, created = AcademicInfo.objects.get_or_create(user=user)
            legacy_academic_fields = [
                'year_graduated', 'course', 'program', 'section', 'school_name',
                'pursue_further_study'
            ]
            for field in legacy_academic_fields:
                if hasattr(user, field):
                    setattr(academic, field, getattr(user, field))
            academic.save()
            
            # Create or update EmploymentHistory
            employment, created = EmploymentHistory.objects.get_or_create(user=user)
            legacy_employment_fields = [
                'company_name_current', 'position_current', 'sector_current',
                'employment_duration_current', 'salary_current', 'date_started',
                'company_address', 'job_alignment_status', 'job_alignment_category',
                'job_alignment_title', 'self_employed', 'high_position', 'absorbed'
            ]
            for field in legacy_employment_fields:
                if hasattr(user, field):
                    setattr(employment, field, getattr(user, field))
            employment.save()
            
            # Create or update TrackerData
            tracker, created = TrackerData.objects.get_or_create(user=user)
            legacy_tracker_fields = [
                'q_employment_status', 'q_employment_type', 'q_employment_permanent',
                'q_company_name', 'q_current_position', 'q_job_sector',
                'q_employment_duration', 'q_salary_range', 'q_awards_received',
                'q_unemployment_reason', 'tracker_submitted_at'
            ]
            for field in legacy_tracker_fields:
                if hasattr(user, field):
                    setattr(tracker, field, getattr(user, field))
            tracker.save()
            
            # Create or update OJTInfo
            ojt, created = OJTInfo.objects.get_or_create(user=user)
            legacy_ojt_fields = ['ojt_end_date', 'job_code', 'ojtstatus']
            for field in legacy_ojt_fields:
                if hasattr(user, field):
                    setattr(ojt, field, getattr(user, field))
            ojt.save()
            
            return {
                'profile': profile,
                'academic': academic,
                'employment': employment,
                'tracker': tracker,
                'ojt': ojt
            }