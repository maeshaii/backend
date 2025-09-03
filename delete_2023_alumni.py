import os
import django
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, TrackerResponse, TrackerFileUpload, Notification

def delete_2023_alumni():
    """
    Delete all alumni from batch 2023 and their related data
    """
    print("Starting deletion of 2023 alumni batch...")
    
    # Get all 2023 alumni
    alumni_2023 = User.objects.filter(year_graduated=2023, account_type__user=True)
    alumni_count = alumni_2023.count()
    
    if alumni_count == 0:
        print("No 2023 alumni found to delete.")
        return
    
    print(f"Found {alumni_count} alumni from 2023 batch.")
    
    # Get alumni details for confirmation
    alumni_details = []
    for alumni in alumni_2023:
        alumni_details.append({
            'id': alumni.user_id,
            'name': f"{alumni.f_name} {alumni.l_name}",
            'ctu_id': alumni.acc_username,
            'course': alumni.course
        })
    
    print("\nAlumni to be deleted:")
    for detail in alumni_details:
        print(f"  - {detail['name']} (CTU ID: {detail['ctu_id']}, Course: {detail['course']})")
    
    # Auto-confirm deletion since user wants to start fresh
    print(f"\nProceeding with deletion of {alumni_count} alumni from 2023...")
    
    # Delete related data first (foreign key relationships)
    deleted_count = 0
    
    for alumni in alumni_2023:
        print(f"Deleting alumni: {alumni.f_name} {alumni.l_name} (CTU ID: {alumni.acc_username})")
        
        # Delete tracker responses and related files
        tracker_responses = TrackerResponse.objects.filter(user=alumni)
        for response in tracker_responses:
            # Delete associated file uploads
            file_uploads = TrackerFileUpload.objects.filter(response=response)
            file_count = file_uploads.count()
            file_uploads.delete()
            if file_count > 0:
                print(f"  - Deleted {file_count} file uploads")
        
        # Delete tracker responses
        response_count = tracker_responses.count()
        tracker_responses.delete()
        if response_count > 0:
            print(f"  - Deleted {response_count} tracker responses")
        
        # Delete notifications
        notifications = Notification.objects.filter(user=alumni)
        notification_count = notifications.count()
        notifications.delete()
        if notification_count > 0:
            print(f"  - Deleted {notification_count} notifications")
        
        # Delete the alumni user
        alumni.delete()
        deleted_count += 1
        print(f"  - Deleted alumni user")
    
    print(f"\n✅ Successfully deleted {deleted_count} alumni from 2023 batch and all related data.")
    print("You can now start fresh with your 2023 data!")

if __name__ == "__main__":
    delete_2023_alumni() 