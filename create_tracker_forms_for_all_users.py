#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, TrackerForm

def create_tracker_forms_for_all_users():
    """Create tracker forms for all alumni users who don't have them"""
    
    # Get all alumni users
    alumni_users = User.objects.filter(account_type__user=True)
    print(f"Total alumni users: {alumni_users.count()}")
    
    # Get existing tracker forms
    existing_forms = TrackerForm.objects.all()
    print(f"Existing tracker forms: {existing_forms.count()}")
    
    # Find users without tracker forms
    users_without_forms = []
    for user in alumni_users:
        if not TrackerForm.objects.filter(user=user).exists():
            users_without_forms.append(user)
    
    print(f"Users without tracker forms: {len(users_without_forms)}")
    
    if users_without_forms:
        print("Creating tracker forms for the following users:")
        for user in users_without_forms:
            print(f"- {user.f_name} {user.l_name} ({user.acc_username})")
        
        # Create tracker forms
        created_forms = []
        for user in users_without_forms:
            tracker_form = TrackerForm.objects.create(
                user=user,
                title=f"Tracker Form for {user.f_name} {user.l_name}",
                accepting_responses=True,
                standard=True
            )
            created_forms.append(tracker_form)
            print(f"✅ Created tracker form for {user.f_name} {user.l_name}")
        
        print(f"\n🎉 Successfully created {len(created_forms)} tracker forms!")
        
        # Verify the creation
        total_forms = TrackerForm.objects.count()
        print(f"Total tracker forms after creation: {total_forms}")
        
    else:
        print("✅ All alumni users already have tracker forms!")

if __name__ == "__main__":
    create_tracker_forms_for_all_users() 