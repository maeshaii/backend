from django.urls import path, include
from . import views
from rest_framework_simplejwt.views import TokenRefreshView
from .views import CustomTokenObtainPairView, send_reminder_view, notifications_view, delete_notifications_view, import_ojt_view, ojt_statistics_view, ojt_by_year_view, ojt_clear_view, ojt_clear_all_view, ojt_status_update_view
from apps.tracker.views import (
    tracker_questions_view,
    tracker_responses_view,
    add_category_view,
    delete_category_view,
    delete_question_view,
    add_question_view,
    update_category_view,
    update_question_view,
    update_tracker_form_title_view,
    submit_tracker_response_view,
    tracker_responses_by_user_view,
    tracker_form_view,
    check_user_tracker_status_view,
    tracker_accepting_responses_view,
    update_tracker_accepting_responses_view,
    get_active_tracker_form,
    file_upload_stats_view,
)
from apps.alumni_users.views import alumni_list_view, alumni_detail_view
from apps.shared.views import export_alumni_excel, import_alumni_excel, import_exported_alumni_excel, export_initial_passwords
from .views import *

urlpatterns = [
    path('csrf/', views.get_csrf_token, name='get_csrf_token'),
    path('login/', views.login_view, name='login_view'),
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('change-password/', views.change_password_view, name='change_password'),
    # Alumni import/export (keep single implementation)
    path('alumni/statistics/', views.alumni_statistics_view, name='alumni_statistics'),
    path('alumni/list/', views.alumni_list_view, name='alumni_list'),
    path('alumni-list/', alumni_list_view, name='alumni_list_alias'),
    path('export-alumni/', export_alumni_excel, name='export_alumni_excel'),
    path('export-initial-passwords/', export_initial_passwords, name='export_initial_passwords'),
    path('import-alumni/', import_alumni_excel, name='import_alumni_excel'),
    path('import-exported-alumni/', import_exported_alumni_excel, name='import_exported_alumni_excel'),
     
    # OJT-specific routes for coordinators
    path('ojt/import/', import_ojt_view, name='import_ojt'),
    path('ojt/statistics/', ojt_statistics_view, name='ojt_statistics'),
    path('ojt/by-year/', ojt_by_year_view, name='ojt_by_year'),
    path('ojt/clear/', ojt_clear_view, name='ojt_clear'),
    path('ojt/clear-all/', ojt_clear_all_view, name='ojt_clear_all'),
    path('ojt/status/', ojt_status_update_view, name='ojt_status_update'),

    path('users_list_view/', views.users_list_view, name='users_list_view'),
    
    path('tracker/questions/', tracker_questions_view, name='tracker_questions'),
    path('tracker/responses/', submit_tracker_response_view, name='submit_tracker_response'),  # POST for submission
    path('tracker/list-responses/', tracker_responses_view, name='tracker_responses'),         # GET for listing
    path('tracker/user-responses/<int:user_id>/', tracker_responses_by_user_view, name='tracker_responses_by_user'),
    path('tracker/check-status/', check_user_tracker_status_view, name='check_user_tracker_status'),
    path('tracker/add-category/', add_category_view, name='add_category'),
    path('tracker/delete-category/<int:category_id>/', delete_category_view, name='delete_category'),
    path('tracker/delete-question/<int:question_id>/', delete_question_view, name='delete_question'),
    path('tracker/add-question/', add_question_view, name='add_question'),
    path('tracker/update-category/<int:category_id>/', update_category_view, name='update_category'),
    path('tracker/update-question/<int:question_id>/', update_question_view, name='update_question'),
    path('tracker/update-form-title/<int:tracker_form_id>/', update_tracker_form_title_view, name='update_tracker_form_title'),
    path('tracker/form/<int:tracker_form_id>/', tracker_form_view, name='tracker_form_view'),
    path('tracker/file-stats/', file_upload_stats_view, name='file_upload_stats'),
    path('send-reminder/', send_reminder_view, name='send_reminder'),
    path('notifications/', notifications_view, name='notifications'),
    path('notifications/count/', views.notifications_count_view, name='notifications_count'),
    path('notifications/delete/', delete_notifications_view, name='delete_notifications'),
    path('alumni/<int:user_id>/', alumni_detail_view, name='alumni_detail'),
    path('alumni/<int:user_id>/followers/', views.alumni_followers_view, name='alumni_followers'),
    path('alumni/<int:user_id>/following/', views.alumni_following_view, name='alumni_following'),
    path('follow/<int:user_id>/', views.follow_user_view, name='follow_user'),
    path('follow/<int:user_id>/status/', views.check_follow_status_view, name='check_follow_status'),
    path('tracker/accepting/<int:tracker_form_id>/', tracker_accepting_responses_view, name='tracker_accepting_responses'),
    path('tracker/update-accepting/<int:tracker_form_id>/', update_tracker_accepting_responses_view, name='update_tracker_accepting_responses'),
    path('tracker/active-form/', get_active_tracker_form, name='get_active_tracker_form'),
    path('admin/<int:user_id>/profile_bio/', profile_bio_view, name='profile_bio_view'),
    path('resume/update/', update_resume, name='update_resume'),
    path('resume/delete/', delete_resume, name='delete_resume'),
    path('alumni/profile/update/', update_alumni_profile, name='update_alumni_profile'),
    path('alumni/profile/delete/', delete_alumni_profile_pic, name='delete_alumni_profile_pic'),
    path('search/', search_alumni, name='search_alumni'),
    path('alumni/search/', views.search_alumni, name='search_alumni'),
    path('alumni/all/', views.get_all_alumni, name='get_all_alumni'),
    
    # Posts API endpoints
    path('posts/', views.posts_view, name='posts'),
    path('posts/by-user-type/', views.posts_by_user_type_view, name='posts_by_user_type'),
    path('posts/<int:post_id>/like/', views.post_like_view, name='post_like'),
    path('posts/<int:post_id>/comments/', views.post_comments_view, name='post_comments'),
    path('posts/<int:post_id>/comments/<int:comment_id>/', views.comment_edit_view, name='comment_edit'),
    path('posts/<int:post_id>/', views.post_edit_view, name='post_edit'),
    path('posts/delete/<int:post_id>/', views.post_delete_view, name='post_delete'),
    path('posts/<int:post_id>/repost/', views.post_repost_view, name='post_repost'),
    path('reposts/<int:repost_id>/', views.repost_delete_view, name='repost_delete'),
    path('post-categories/', views.post_categories_view, name='post_categories'),
    
]

