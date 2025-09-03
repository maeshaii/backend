from django.urls import path
from .views import alumni_statistics_view, generate_statistics_view, export_detailed_alumni_data

urlpatterns = [
    path('alumni/', alumni_statistics_view, name='alumni_statistics'),
    path('generate/', generate_statistics_view, name='generate_statistics'),
    path('export-detailed/', export_detailed_alumni_data, name='export_detailed_alumni_data'),
] 