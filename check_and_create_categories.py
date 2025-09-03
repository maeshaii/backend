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

def check_and_create_categories():
    """Check if post categories exist and create them if they don't"""
    
    # Check existing categories
    existing_categories = PostCategory.objects.all()
    print(f"Found {existing_categories.count()} existing categories:")
    
    for cat in existing_categories:
        category_type = "Events" if cat.events else "Announcements" if cat.announcements else "Donation" if cat.donation else "Personal"
        print(f"  - ID: {cat.post_cat_id} - Type: {category_type}")
    
    if existing_categories.count() == 0:
        print("\nNo categories found. Creating default categories...")
        
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
            category_type = "Events" if category.events else "Announcements" if category.announcements else "Donation" if category.donation else "Personal"
            print(f"  Created category: {category_type} (ID: {category.post_cat_id})")
        
        print(f"\n✅ Successfully created {len(created_categories)} post categories!")
    else:
        print(f"\n✅ Categories already exist. No action needed.")
    
    # Display all categories
    print("\n📋 All post categories:")
    all_categories = PostCategory.objects.all()
    for category in all_categories:
        category_type = "Events" if category.events else "Announcements" if category.announcements else "Donation" if category.donation else "Personal"
        print(f"  - ID: {category.post_cat_id} - Type: {category_type}")

if __name__ == '__main__':
    check_and_create_categories() 