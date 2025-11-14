from django.urls import path, include
from . import views
from rest_framework_simplejwt.views import TokenRefreshView
from .views import CustomTokenObtainPairView, send_reminder_view, notifications_view, delete_notifications_view
from apps.tracker.views import tracker_questions_view, tracker_responses_view, add_category_view, delete_category_view, delete_question_view, add_question_view, update_category_view, update_question_view, update_tracker_form_title_view, submit_tracker_response_view, tracker_responses_by_user_view, tracker_form_view, check_user_tracker_status_view, tracker_accepting_responses_view, update_tracker_accepting_responses_view, get_active_tracker_form, file_upload_stats_view
from apps.alumni_users.views import alumni_list_view, alumni_detail_view
from apps.shared.views import export_alumni_excel, import_alumni_excel, import_exported_alumni_excel

urlpatterns = [
    path('csrf/', views.get_csrf_token, name='get_csrf_token'),
    path('login/', views.login_view, name='login_view'),
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('import-alumni/', views.import_alumni_view, name='import_alumni'),
    path('alumni/statistics/', views.alumni_statistics_view, name='alumni_statistics'),
    path('alumni/list/', views.alumni_list_view, name='alumni_list'),
    path('alumni-list/', alumni_list_view, name='alumni_list_alias'),
    path('export-alumni/', export_alumni_excel, name='export_alumni_excel'),
    path('import-alumni/', import_alumni_excel, name='import_alumni_excel'),
    path('import-exported-alumni/', import_exported_alumni_excel, name='import_exported_alumni_excel'),
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
    path('notifications/delete/', delete_notifications_view, name='delete_notifications'),
    path('alumni/<int:user_id>/', alumni_detail_view, name='alumni_detail'),
    path('tracker/accepting/<int:tracker_form_id>/', tracker_accepting_responses_view, name='tracker_accepting_responses'),
    path('tracker/update-accepting/<int:tracker_form_id>/', update_tracker_accepting_responses_view, name='update_tracker_accepting_responses'),
    path('tracker/active-form/', get_active_tracker_form, name='get_active_tracker_form'),
]

