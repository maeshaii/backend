 #!/usr/bin/env python
"""
Script to delete all data from specified shared tables.
This script respects foreign key constraints by deleting in the correct order.

WARNING: This will permanently delete all data from the specified tables!
Make sure you have a backup before running this script.
"""

import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.db import transaction, connection
from apps.shared.models import (
    AcademicInfo, Comment, ContentImage, Conversation, DonationRequest,
    EmploymentHistory, EngagementPointsSettings, Follow, Forum, Like,
    Message, MessageAttachment, Notification, OJTCompanyProfile, OJTImport,
    OJTInfo, Post, RecentSearch, Reply, ReportSettings, Repost,
    RewardHistory, RewardInventoryItem, RewardRequest, SendDate, TrackerData,
    User, UserInitialPassword, UserPoints, UserProfile
)


def delete_all_data():
    """
    Delete all data from the specified tables in the correct order
    to respect foreign key constraints.
    """
    
    print("=" * 80)
    print("WARNING: This script will DELETE ALL DATA from the specified tables!")
    print("=" * 80)
    
    # Confirmation prompt
    response = input("\nAre you sure you want to proceed? Type 'YES' to continue: ")
    if response != 'YES':
        print("Operation cancelled.")
        return
    
    print("\nStarting deletion process...")
    print("-" * 80)
    
    deleted_counts = {}
    
    try:
        with transaction.atomic():
            # Step 1: Delete child tables first (those with foreign keys)
            print("\n[1] Deleting child records...")
            
            # Delete replies first (references Comment)
            count = Reply.objects.all().delete()[0]
            deleted_counts['Reply'] = count
            print(f"  ✓ Deleted {count} Reply records")
            
            # Delete comments (references Post, Forum, Repost, DonationRequest, User)
            count = Comment.objects.all().delete()[0]
            deleted_counts['Comment'] = count
            print(f"  ✓ Deleted {count} Comment records")
            
            # Delete likes (references Post, Forum, Repost, DonationRequest, User)
            count = Like.objects.all().delete()[0]
            deleted_counts['Like'] = count
            print(f"  ✓ Deleted {count} Like records")
            
            # Delete reposts (references Post, Forum, DonationRequest, User)
            count = Repost.objects.all().delete()[0]
            deleted_counts['Repost'] = count
            print(f"  ✓ Deleted {count} Repost records")
            
            # Delete content images (references Post, Forum, DonationRequest via content_type/content_id)
            count = ContentImage.objects.all().delete()[0]
            deleted_counts['ContentImage'] = count
            print(f"  ✓ Deleted {count} ContentImage records")
            
            # Delete message attachments (references Message)
            count = MessageAttachment.objects.all().delete()[0]
            deleted_counts['MessageAttachment'] = count
            print(f"  ✓ Deleted {count} MessageAttachment records")
            
            # Delete messages (references Conversation, User)
            count = Message.objects.all().delete()[0]
            deleted_counts['Message'] = count
            print(f"  ✓ Deleted {count} Message records")
            
            # Delete conversation participants (ManyToMany intermediate table)
            # This is handled via the Conversation model's participants field
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM shared_conversation_participants")
                count = cursor.rowcount
                deleted_counts['ConversationParticipants'] = count
                print(f"  ✓ Deleted {count} ConversationParticipants records")
            
            # Delete conversations (references User via ManyToMany)
            count = Conversation.objects.all().delete()[0]
            deleted_counts['Conversation'] = count
            print(f"  ✓ Deleted {count} Conversation records")
            
            # Delete notifications (references User)
            count = Notification.objects.all().delete()[0]
            deleted_counts['Notification'] = count
            print(f"  ✓ Deleted {count} Notification records")
            
            # Delete recent searches (references User)
            count = RecentSearch.objects.all().delete()[0]
            deleted_counts['RecentSearch'] = count
            print(f"  ✓ Deleted {count} RecentSearch records")
            
            # Delete follows (references User)
            count = Follow.objects.all().delete()[0]
            deleted_counts['Follow'] = count
            print(f"  ✓ Deleted {count} Follow records")
            
            # Delete reward requests (references User, RewardInventoryItem)
            count = RewardRequest.objects.all().delete()[0]
            deleted_counts['RewardRequest'] = count
            print(f"  ✓ Deleted {count} RewardRequest records")
            
            # Delete reward history (references User)
            count = RewardHistory.objects.all().delete()[0]
            deleted_counts['RewardHistory'] = count
            print(f"  ✓ Deleted {count} RewardHistory records")
            
            # Delete reward inventory items
            count = RewardInventoryItem.objects.all().delete()[0]
            deleted_counts['RewardInventoryItem'] = count
            print(f"  ✓ Deleted {count} RewardInventoryItem records")
            
            # Delete posts (references User)
            count = Post.objects.all().delete()[0]
            deleted_counts['Post'] = count
            print(f"  ✓ Deleted {count} Post records")
            
            # Delete forums (references User)
            count = Forum.objects.all().delete()[0]
            deleted_counts['Forum'] = count
            print(f"  ✓ Deleted {count} Forum records")
            
            # Delete donation requests (references User)
            count = DonationRequest.objects.all().delete()[0]
            deleted_counts['DonationRequest'] = count
            print(f"  ✓ Deleted {count} DonationRequest records")
            
            # Step 2: Delete user-related data (OneToOne and ForeignKey to User)
            print("\n[2] Deleting user-related records...")
            
            # Delete tracker data (OneToOne with User)
            count = TrackerData.objects.all().delete()[0]
            deleted_counts['TrackerData'] = count
            print(f"  ✓ Deleted {count} TrackerData records")
            
            # Delete employment history (OneToOne with User)
            count = EmploymentHistory.objects.all().delete()[0]
            deleted_counts['EmploymentHistory'] = count
            print(f"  ✓ Deleted {count} EmploymentHistory records")
            
            # Delete academic info (OneToOne with User)
            count = AcademicInfo.objects.all().delete()[0]
            deleted_counts['AcademicInfo'] = count
            print(f"  ✓ Deleted {count} AcademicInfo records")
            
            # Delete user profile (OneToOne with User)
            count = UserProfile.objects.all().delete()[0]
            deleted_counts['UserProfile'] = count
            print(f"  ✓ Deleted {count} UserProfile records")
            
            # Delete user points (OneToOne with User)
            count = UserPoints.objects.all().delete()[0]
            deleted_counts['UserPoints'] = count
            print(f"  ✓ Deleted {count} UserPoints records")
            
            # Delete user initial password (OneToOne with User)
            count = UserInitialPassword.objects.all().delete()[0]
            deleted_counts['UserInitialPassword'] = count
            print(f"  ✓ Deleted {count} UserInitialPassword records")
            
            # Delete OJT info (OneToOne with User)
            count = OJTInfo.objects.all().delete()[0]
            deleted_counts['OJTInfo'] = count
            print(f"  ✓ Deleted {count} OJTInfo records")
            
            # Delete OJT company profile (OneToOne with User)
            count = OJTCompanyProfile.objects.all().delete()[0]
            deleted_counts['OJTCompanyProfile'] = count
            print(f"  ✓ Deleted {count} OJTCompanyProfile records")
            
            # Step 3: Delete OJT-related tables
            print("\n[3] Deleting OJT-related records...")
            
            # Delete OJT imports
            count = OJTImport.objects.all().delete()[0]
            deleted_counts['OJTImport'] = count
            print(f"  ✓ Deleted {count} OJTImport records")
            
            # Delete send dates
            count = SendDate.objects.all().delete()[0]
            deleted_counts['SendDate'] = count
            print(f"  ✓ Deleted {count} SendDate records")
            
            # Step 4: Delete settings tables
            print("\n[4] Deleting settings records...")
            
            # Delete engagement points settings
            count = EngagementPointsSettings.objects.all().delete()[0]
            deleted_counts['EngagementPointsSettings'] = count
            print(f"  ✓ Deleted {count} EngagementPointsSettings records")
            
            # Delete report settings
            count = ReportSettings.objects.all().delete()[0]
            deleted_counts['ReportSettings'] = count
            print(f"  ✓ Deleted {count} ReportSettings records")
            
            # Step 5: Delete users last (since many tables reference User)
            print("\n[5] Deleting User records...")
            count = User.objects.all().delete()[0]
            deleted_counts['User'] = count
            print(f"  ✓ Deleted {count} User records")
            
            print("\n" + "=" * 80)
            print("DELETION COMPLETE!")
            print("=" * 80)
            print("\nSummary of deleted records:")
            print("-" * 80)
            total = 0
            for table_name, count in sorted(deleted_counts.items()):
                print(f"  {table_name:30} : {count:>10,} records")
                total += count
            print("-" * 80)
            print(f"  {'TOTAL':30} : {total:>10,} records")
            print("=" * 80)
            
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        print("Transaction rolled back. No data was deleted.")
        raise


if __name__ == '__main__':
    delete_all_data()

