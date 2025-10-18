#!/usr/bin/env python
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, Post, Notification
from apps.api.views import notify_users_of_admin_peso_post

print("=== Testing Notification with Profile Info ===")

# Get admin user
admin_user = User.objects.filter(account_type__admin=True).first()
if admin_user:
    print(f"Admin user: {admin_user.full_name}")
    print(f"User ID: {admin_user.user_id}")
    
    # Check if user has profile
    has_profile = hasattr(admin_user, 'profile') and admin_user.profile
    print(f"Has profile: {has_profile}")
    
    if has_profile:
        print(f"Profile pic: {admin_user.profile.profile_pic}")
        if admin_user.profile.profile_pic:
            print(f"Profile pic URL: {admin_user.profile.profile_pic.url}")
    
    # Create a test post
    test_post = Post.objects.create(
        user=admin_user,
        post_content="Test post to verify notification with profile info",
        type="personal",
    )
    
    print(f"\nCreated test post: {test_post.post_id}")
    
    # Call notification function
    result = notify_users_of_admin_peso_post(admin_user, "post", test_post.post_id)
    print(f"Notifications created: {result}")
    
    # Check the notification content
    notif = Notification.objects.filter(
        notif_type='admin_peso_post',
        notifi_content__contains=f"POST_ID:{test_post.post_id}"
    ).first()
    
    if notif:
        print(f"\nNotification content:")
        print(notif.notifi_content)
        print(f"\nRecipient: {notif.user.full_name}")

print("\n=== Test Complete ===")


