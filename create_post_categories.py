#!/usr/bin/env python
import os
import sys
import django

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import PostCategory

def create_post_categories():
    """Create the default post categories for the mobile app"""
    
    # Check if categories already exist
    if PostCategory.objects.exists():
        print("Post categories already exist. Skipping creation.")
        return
    
    # Create the default categories
    categories = [
        {
            'events': True,
            'announcements': False,
            'donation': False,
            'personal': False,
        },
        {
            'events': False,
            'announcements': True,
            'donation': False,
            'personal': False,
        },
        {
            'events': False,
            'announcements': False,
            'donation': True,
            'personal': False,
        },
        {
            'events': False,
            'announcements': False,
            'donation': False,
            'personal': True,
        },
    ]
    
    created_categories = []
    for category_data in categories:
        category = PostCategory.objects.create(**category_data)
        created_categories.append(category)
        print(f"Created category: {category_data}")
    
    print(f"\nSuccessfully created {len(created_categories)} post categories!")
    
    # Display all categories
    print("\nAll post categories:")
    for category in PostCategory.objects.all():
        category_type = "Events" if category.events else "Announcements" if category.announcements else "Donation" if category.donation else "Personal"
        print(f"ID: {category.post_cat_id} - Type: {category_type}")

if __name__ == '__main__':
    create_post_categories() 