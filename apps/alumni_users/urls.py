from django.urls import path
from .views import alumni_list_view, alumni_detail_view

urlpatterns = [
    path('alumni/', alumni_list_view, name='alumni_list'),
    path('alumni/<int:user_id>/', alumni_detail_view, name='alumni_detail'),
] 