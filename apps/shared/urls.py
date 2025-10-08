from django.urls import path
from . import views

urlpatterns = [
    # Job alignment confirmation endpoints
    path('check-job-alignment/', views.check_job_alignment, name='check_job_alignment'),
    path('confirm-job-alignment/', views.confirm_job_alignment, name='confirm_job_alignment'),
    path('job-alignment-suggestions/', views.get_job_alignment_suggestions, name='get_job_alignment_suggestions'),
    
    # Job autocomplete endpoint
    path('job-autocomplete/', views.get_job_autocomplete_suggestions, name='get_job_autocomplete_suggestions'),
    
    # Phase 4: Advanced system endpoints
    path('system-dashboard/', views.get_system_dashboard, name='get_system_dashboard'),
    path('performance-analytics/', views.get_performance_analytics, name='get_performance_analytics'),
]