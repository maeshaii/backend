from django.urls import path
from . import views

urlpatterns = [
    # List and search OJT users
    path('list/', views.list_ojt_users, name='list_ojt_users'),
    
    # Individual OJT user operations
    path('details/<int:user_id>/', views.get_ojt_user_details, name='get_ojt_user_details'),
    path('update-status/<int:user_id>/', views.update_ojt_status, name='update_ojt_status'),
    path('update/<int:user_id>/', views.update_ojt_user, name='update_ojt_user'),
    path('delete/<int:user_id>/', views.delete_ojt_user, name='delete_ojt_user'),
    
    # Create new OJT user
    path('create/', views.create_ojt_user, name='create_ojt_user'),
    
    # Summary and statistics
    path('summary/', views.ojt_users_summary, name='ojt_users_summary'),
] 