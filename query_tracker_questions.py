#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import QuestionCategory, Question

def query_tracker_questions():
    """Query and display all tracker questions from database"""
    print("=" * 80)
    print("TRACKER QUESTIONS ANALYSIS - DATABASE QUERY")
    print("=" * 80)
    print()
    
    categories = QuestionCategory.objects.prefetch_related('questions').order_by('order')
    
    if not categories.exists():
        print("⚠️  No categories found in database!")
        print("\nThis means questions need to be seeded using:")
        print("  python manage.py seed_tracker_questions")
        return
    
    total_questions = 0
    for i, cat in enumerate(categories, 1):
        questions = cat.questions.all().order_by('order')
        total_questions += questions.count()
        
        print(f"{'='*80}")
        print(f"CATEGORY {i}: {cat.title}")
        print(f"{'='*80}")
        print(f"ID: {cat.id}")
        print(f"Order: {cat.order}")
        print(f"Description: {cat.description}")
        print(f"Questions in category: {questions.count()}")
        print()
        
        for idx, q in enumerate(questions, 1):
            print(f"  {idx}. Question ID: {q.id}")
            print(f"     Text: {q.text}")
            print(f"     Type: {q.type}")
            print(f"     Options: {q.options or 'None'}")
            print(f"     Required: {q.required}")
            print(f"     Order: {q.order}")
            print()
    
    print(f"{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    print(f"Total Categories: {categories.count()}")
    print(f"Total Questions: {total_questions}")
    print()

if __name__ == '__main__':
    query_tracker_questions()

