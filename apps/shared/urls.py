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
    
    # Report preset endpoints
    path('report-settings/presets/', views.get_report_presets_view, name='get_report_presets'),
    path('report-settings/presets/save/', views.save_report_preset_view, name='save_report_preset'),
    path('report-settings/presets/apply/', views.apply_report_preset_view, name='apply_report_preset'),
    path('report-settings/presets/<str:preset_id>/delete/', views.delete_report_preset_view, name='delete_report_preset'),
]