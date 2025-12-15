from django.urls import path
from .views import (
    alumni_statistics_view, 
    generate_statistics_view, 
    export_detailed_alumni_data, 
    chart_statistics_by_year,
    ched_chart_statistics_by_year,
    suc_chart_statistics_by_year,
    aacup_chart_statistics_by_year,
    generate_ai_summary
)

urlpatterns = [
    path('alumni/', alumni_statistics_view, name='alumni_statistics'),
    path('generate/', generate_statistics_view, name='generate_statistics'),
    path('export-detailed/', export_detailed_alumni_data, name='export_detailed_alumni_data'),
    path('chart-by-year/', chart_statistics_by_year, name='chart_statistics_by_year'),
    path('ched-chart-by-year/', ched_chart_statistics_by_year, name='ched_chart_statistics_by_year'),
    path('suc-chart-by-year/', suc_chart_statistics_by_year, name='suc_chart_statistics_by_year'),
    path('aacup-chart-by-year/', aacup_chart_statistics_by_year, name='aacup_chart_statistics_by_year'),
    path('ai-summary/', generate_ai_summary, name='generate_ai_summary'),
] 