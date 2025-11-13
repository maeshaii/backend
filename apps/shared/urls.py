<<<<<<< HEAD
from django.urls import path
from . import views

urlpatterns = [
    # Job alignment confirmation endpoints
    path('check-job-alignment/', views.check_job_alignment, name='check_job_alignment'),
    path('confirm-job-alignment/', views.confirm_job_alignment, name='confirm_job_alignment'),
    path('job-alignment-suggestions/', views.get_job_alignment_suggestions, name='get_job_alignment_suggestions'),
    
    # Job autocomplete endpoint
    path('job-autocomplete/', views.get_job_autocomplete_suggestions, name='get_job_autocomplete_suggestions'),
    
    # Report settings endpoints
    path('report-settings/', views.get_report_settings_view, name='get_report_settings'),
    path('report-settings/update/', views.update_report_settings_view, name='update_report_settings'),
]
=======

>>>>>>> 746e601016fd6b6113a8116f65f35a08788c789a
