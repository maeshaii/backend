from django.urls import path, include
from . import views
from .views import CustomTokenObtainPairView, CustomTokenRefreshView, send_reminder_view, notifications_view, delete_notifications_view, import_ojt_view, ojt_statistics_view, ojt_by_year_view, ojt_clear_view, ojt_clear_all_view, ojt_status_update_view, approve_ojt_to_alumni_view, approve_individual_ojt_to_alumni_view
from apps.tracker.views import *
from apps.alumni_users.views import alumni_list_view, alumni_detail_view
from apps.shared.views import import_exported_alumni_excel, export_initial_passwords
from apps.alumni_stats.views import export_detailed_alumni_data
from .views import *

urlpatterns = [
    path('csrf/', views.get_csrf_token, name='get_csrf_token'),
    # Used by Mobile: legacy login (mobile primarily uses /api/token/)
    path('login/', views.login_view, name='login_view'),
    # Used by Mobile: forgot password flow (secure token-based)
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('reset-password/', views.reset_password_view, name='reset_password'),
    # Used by Mobile: JWT obtain (POST acc_username, acc_password)
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    # Used by Mobile: JWT refresh (POST refresh)
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    # Used by Mobile: change password
    path('change-password/', views.change_password_view, name='change_password'),
    # Alumni import/export (keep single implementation)
    path('alumni/statistics/', views.alumni_statistics_view, name='alumni_statistics'),
    path('alumni/graduation-years/', views.graduation_years_view, name='graduation_years'),
    path('alumni/list/', views.alumni_list_view, name='alumni_list'),
    path('alumni-list/', alumni_list_view, name='alumni_list_alias'),
    path('export-alumni/', export_detailed_alumni_data, name='export_alumni_excel'),
    path('export-initial-passwords/', export_initial_passwords, name='export_initial_passwords'),
    path('import-alumni/', views.import_alumni_view, name='import_alumni_excel'),
    path('import-exported-alumni/', import_exported_alumni_excel, name='import_exported_alumni_excel'),
     
    # OJT-specific routes for coordinators
    path('ojt/import/', import_ojt_view, name='import_ojt'),
    path('ojt/statistics/', ojt_statistics_view, name='ojt_statistics'),
    path('ojt/company-statistics/', views.ojt_company_statistics_view, name='ojt_company_statistics'),
    path('ojt/students-by-company/', views.ojt_students_by_company_view, name='ojt_students_by_company'),
    path('ojt/students/', views.get_ojt_students_view, name='get_ojt_students'),
    path('ojt/by-year/', ojt_by_year_view, name='ojt_by_year'),
    path('ojt/clear/', ojt_clear_view, name='ojt_clear'),
    path('ojt/clear-all/', ojt_clear_all_view, name='ojt_clear_all'),
    path('ojt/status/', ojt_status_update_view, name='ojt_status_update'),
    path('ojt/send-to-admin/', send_completed_to_admin_view, name='ojt_send_to_admin'),
    path('ojt/coordinator-requests/', coordinator_requests_count_view, name='ojt_coordinator_requests'),
    path('ojt/coordinator-requests/list/', coordinator_requests_list_view, name='ojt_coordinator_requests_list'),
    path('ojt/coordinator-requests/approve/', approve_coordinator_request_view, name='ojt_coordinator_requests_approve'),
    path('ojt/approve-to-alumni/', approve_ojt_to_alumni_view, name='ojt_approve_to_alumni'),
    path('ojt/approve-individual-to-alumni/', approve_individual_ojt_to_alumni_view, name='ojt_approve_individual_to_alumni'),
    path('ojt/coordinator-sections/', get_coordinator_sections_view, name='get_coordinator_sections'),
    path('ojt/available-years/', views.available_years_view, name='available_years'),
    path('ojt/set-send-date/', views.set_send_date_view, name='set_send_date'),
    path('ojt/get-send-dates/', views.get_send_dates_view, name='get_send_dates'),
    path('ojt/delete-send-date/', views.delete_send_date_view, name='delete_send_date'),
    path('ojt/check-all-sent/', views.check_all_sent_status_view, name='check_all_sent_status'),
    # path('download-excel/<str:filename>/', views.download_excel_file, name='download_excel_file'),
    
    path('users_list_view/', views.users_list_view, name='users_list_view'),
    path('admin-peso-users/', views.admin_peso_users_view, name='admin_peso_users_view'),
    
    path('tracker/questions/', tracker_questions_view, name='tracker_questions'),
    path('tracker/responses/', submit_tracker_response_view, name='submit_tracker_response'),  # POST for submission
    path('tracker/list-responses/', tracker_responses_view, name='tracker_responses'),         # GET for listing
    path('tracker/employment-respondents/', employment_history_respondents_view, name='employment_history_respondents'),  # GET for users with employment history
    path('tracker/user-responses/<int:user_id>/', tracker_responses_by_user_view, name='tracker_responses_by_user'),
    path('tracker/check-status/', check_user_tracker_status_view, name='check_user_tracker_status'),
    path('tracker/save-draft/', save_tracker_draft_view, name='save_tracker_draft'),  # POST for auto-save draft
    path('tracker/load-draft/', load_tracker_draft_view, name='load_tracker_draft'),  # GET to load saved draft
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
    path('send-email-reminder/', views.send_email_reminder_view, name='send_email_reminder'),
    path('send-sms-reminder/', views.send_sms_reminder_view, name='send_sms_reminder'),
    path('globe/callback/', views.globe_callback_view, name='globe_callback'),
    path('notifications/', notifications_view, name='notifications'),
    path('notifications/count/', views.notifications_count_view, name='notifications_count'),
    path('notifications/delete/', delete_notifications_view, name='delete_notifications'),
    path('notifications/mark-read/', views.mark_notification_as_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_as_read, name='mark_all_notifications_read'),
    path('alumni/employment/<int:user_id>/', views.alumni_employment_view, name='alumni_employment'),
    path('alumni/employment-reminder/<int:user_id>/', views.check_employment_update_reminder, name='check_employment_update_reminder'),
    path('alumni/profile/<int:user_id>/', views.alumni_profile_view, name='alumni_profile'),
    path('alumni/<int:user_id>/', alumni_detail_view, name='alumni_detail'),
    path('alumni/<int:user_id>/followers/', views.alumni_followers_view, name='alumni_followers'),
    path('alumni/<int:user_id>/following/', views.alumni_following_view, name='alumni_following'),
    path('follow/<int:user_id>/', views.follow_user_view, name='follow_user'),
    path('follow/<int:user_id>/status/', views.check_follow_status_view, name='check_follow_status'),
    path('follow/<int:user_id>/mutual/', views.mutual_follows_view, name='mutual_follows'),
    path('online-users/', views.online_users_view, name='online_users'),
    path('tracker/accepting/<int:tracker_form_id>/', tracker_accepting_responses_view, name='tracker_accepting_responses'),
    path('tracker/update-accepting/<int:tracker_form_id>/', update_tracker_accepting_responses_view, name='update_tracker_accepting_responses'),
    path('tracker/active-form/', get_active_tracker_form, name='get_active_tracker_form'),
    path('admin/<int:user_id>/profile_bio/', profile_bio_view, name='profile_bio_view'),
    path('alumni/profile/update/', update_alumni_profile, name='update_alumni_profile'),
    path('alumni/profile/delete/', delete_alumni_profile_pic, name='delete_alumni_profile_pic'),
    path('search/', search_alumni, name='search_alumni'),
    path('alumni/search/', views.search_alumni, name='search_alumni'),
    path('alumni/all/', views.get_all_alumni, name='get_all_alumni'),
    path('following/mentions/', views.get_following_for_mentions, name='get_following_for_mentions'),
    path('comments/<int:comment_id>/post/', views.get_post_from_comment, name='get_post_from_comment'),
    path('replies/<int:reply_id>/comment/', views.get_comment_from_reply, name='get_comment_from_reply'),
    path('users/alumni/', views.users_alumni_view, name='users_alumni'),
    
    # Used by Mobile: Posts API endpoints
    path('posts/', views.posts_view, name='posts'),
    path('posts/debug/', views.debug_posts_view, name='debug_posts'),
    path('posts/by-user-type/', views.posts_by_user_type_view, name='posts_by_user_type'),
    path('posts/<int:post_id>/like/', views.post_like_view, name='post_like'),
    path('posts/<int:post_id>/comments/', views.post_comments_view, name='post_comments'),
    path('posts/<int:post_id>/comments/<int:comment_id>/', views.comment_edit_view, name='comment_edit'),
    # Reply API endpoints - Handle comment replies
    path('comments/<int:comment_id>/replies/', views.comment_replies_view, name='comment_replies'),
    path('comments/<int:comment_id>/replies/<int:reply_id>/', views.reply_edit_view, name='reply_edit'),
    # Recent Search API endpoints
    path('recent-searches/', views.recent_searches_view, name='recent_searches'),
    path('recent-searches/<int:search_id>/', views.recent_search_delete_view, name='recent_search_delete'),
    path('posts/<int:post_id>/likes/', views.post_likes_view, name='post_likes'),
    # Used by Mobile: Repost interactions
    path('reposts/<int:repost_id>/', views.repost_delete_view, name='repost_delete'),
    path('reposts/<int:repost_id>/detail/', views.repost_detail_view, name='repost_detail'),
    path('reposts/<int:repost_id>/like/', views.repost_like_view, name='repost_like'),
    path('reposts/<int:repost_id>/likes/', views.repost_likes_list_view, name='repost_likes_list'),
    path('reposts/<int:repost_id>/comments/', views.repost_comments_view, name='repost_comments'),
    path('reposts/<int:repost_id>/comments/<int:comment_id>/', views.repost_comment_edit_view, name='repost_comment_edit'),
    path('posts/<int:post_id>/', views.post_edit_view, name='post_edit'),
    path('posts/<int:post_id>/detail/', views.post_detail_view, name='post_detail'),
    path('posts/delete/<int:post_id>/', views.post_delete_view, name='post_delete'),
    path('posts/<int:post_id>/repost/', views.post_repost_view, name='post_repost'),
    # path('posts/user/<int:user_id>/', views.user_posts_view, name='user_posts'),
    
    # Used by Mobile: Forum API endpoints (separate storage)
    path('forum/', views.forum_list_create_view, name='forum_list_create'),
    path('forum/<int:forum_id>/', views.forum_detail_edit_view, name='forum_detail'),
    path('forum/<int:forum_id>/like/', views.forum_like_view, name='forum_like'),
    path('forum/<int:forum_id>/comments/', views.forum_comments_view, name='forum_comments'),
    path('forum/<int:forum_id>/comments/<int:comment_id>/', views.forum_comment_edit_view, name='forum_comment_edit'),
    path('forum/<int:forum_id>/repost/', views.forum_repost_view, name='forum_repost'),
    # Used by Mobile: Donation repost endpoint
    path('donations/<int:donation_id>/repost/', views.donation_repost_view, name='donation_repost'),
    # Removed duplicate route - reposts/<int:repost_id>/ is already defined above in line 110
    
    # User profile social media and email endpoints
    path('userprofile/<int:user_id>/social_media/', views.userprofile_social_media_view, name='userprofile_social_media'),
    path('userprofile/<int:user_id>/email/', views.userprofile_email_view, name='userprofile_email'),
    
    # Donation API endpoints
    path('donations/', views.donation_requests_view, name='donation_requests'),
    path('donations/<int:donation_id>/', views.donation_detail_edit_view, name='donation_detail'),
    path('donations/<int:donation_id>/like/', views.donation_like_view, name='donation_like'),
    path('donations/<int:donation_id>/comments/', views.donation_comments_view, name='donation_comments'),
    path('donations/<int:donation_id>/comments/<int:comment_id>/', views.donation_comment_edit_view, name='donation_comment_edit'),
    path('donations/<int:donation_id>/repost/', views.donation_repost_view, name='donation_repost'),
    
    # User Management API endpoints (Admin only)
    path('admin/users/', views.fetch_all_users_view, name='fetch_all_users'),  # GET - list all users
    path('admin/users/create/', views.create_user_view, name='create_user'),  # POST - create new user
    path('admin/users/<int:user_id>/password/', views.update_user_password_view, name='update_user_password'),
    path('admin/users/<int:user_id>/status/', views.update_user_status_view, name='update_user_status'),
    path('admin/verify-password/', views.verify_admin_password_view, name='verify_admin_password'),
    
    # Engagement Points & Leaderboard
    path('engagement/leaderboard/', views.engagement_leaderboard_view, name='engagement_leaderboard'),
    path('engagement/tasks/', views.engagement_tasks_view, name='engagement_tasks'),
    path('engagement/points-tasks/', views.points_tasks_view, name='points_tasks'),
    path('engagement/points-settings/', views.engagement_points_settings_view, name='engagement_points_settings'),
    path('engagement/milestone-tasks-points/', views.milestone_tasks_points_view, name='milestone_tasks_points'),
    
    # Reward Inventory Management
    path('inventory/', views.inventory_items_view, name='inventory_items'),
    path('inventory/analytics/', views.inventory_analytics_view, name='inventory_analytics'),
    path('inventory/<int:item_id>/', views.inventory_item_detail_view, name='inventory_item_detail'),
    path('rewards/give/', views.give_reward_view, name='give_reward'),
    path('rewards/history/', views.reward_history_view, name='reward_history'),
    path('rewards/request/', views.request_reward_view, name='request_reward'),
    path('rewards/requests/', views.reward_requests_list_view, name='reward_requests'),
    path('rewards/requests/<int:request_id>/approve/', views.approve_reward_request_view, name='approve_reward_request'),
    path('rewards/requests/<int:request_id>/claim/', views.claim_reward_request_view, name='claim_reward_request'),
    path('rewards/requests/<int:request_id>/cancel/', views.cancel_reward_request_view, name='cancel_reward_request'),
    path('rewards/requests/<int:request_id>/cancel', views.cancel_reward_request_view, name='cancel_reward_request_no_slash'),
    path('rewards/requests/<int:request_id>/upload-voucher/', views.upload_voucher_file_view, name='upload_voucher_file'),
    
    # Calendar Event API endpoints
    path('calendar-events/', views.calendar_events_view, name='calendar_events'),
    path('calendar-events/<int:event_id>/', views.calendar_event_detail_view, name='calendar_event_detail'),
    path('calendar-events/month/<int:year>/<int:month>/', views.calendar_events_by_month_view, name='calendar_events_by_month'),
    
]