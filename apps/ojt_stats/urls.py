from django.urls import path
from . import views

urlpatterns = [
    # Main OJT statistics overview for coordinators
    path('overview/', views.ojt_statistics_view, name='ojt_statistics_overview'),
    
    # Detailed statistics by type for coordinators
    path('detailed/', views.generate_ojt_statistics_view, name='generate_ojt_statistics'),
    
    # Export OJT data for reporting
    path('export/', views.export_detailed_ojt_data, name='export_ojt_data'),
    
    # Legacy endpoints for backward compatibility
    path('ojt-statistics/', views.ojt_statistics_view, name='ojt_statistics'),
    path('generate-ojt-statistics/', views.generate_ojt_statistics_view, name='generate_ojt_statistics'),
    path('export-ojt-data/', views.export_detailed_ojt_data, name='export_ojt_data'),
]
