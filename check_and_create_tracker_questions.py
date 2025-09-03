#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import QuestionCategory, Question

def check_and_create_tracker_questions():
    """Check if tracker questions exist and create them if they don't"""
    
    # Check if questions already exist
    existing_questions = Question.objects.count()
    existing_categories = QuestionCategory.objects.count()
    
    print(f"Existing questions: {existing_questions}")
    print(f"Existing categories: {existing_categories}")
    
    if existing_questions > 0:
        print("✅ Tracker questions already exist!")
        return
    
    print("Creating tracker questions...")
    
    # Define categories and questions
    categories = [
        {
            'title': 'INTRODUCTION',
            'description': 'To our Dear Graduates,\nKindly complete this questionnaire accurately and truthfully. Your responses will be used for research purposes to assess employability and, ultimately, improve the curriculum programs offered at Cebu Technological University (CTU). Rest assured that your answers to this survey will be treated with the utmost confidentiality. Thank you very much!\nIf you have any questions, you may contact the office of the Alumni Director through email address gts@ctu.edu.ph or Contact no: (032) 402 4060.',
            'questions': [
                {'text': 'Year Graduated', 'type': 'text', 'options': []},
                {'text': 'Course Graduated', 'type': 'text', 'options': []},
                {'text': 'Email', 'type': 'text', 'options': []},
            ]
        },
        {
            'title': 'PART I : PERSONAL PROFILE',
            'description': 'Basic personal information',
            'questions': [
                {'text': 'First Name', 'type': 'text', 'options': []},
                {'text': 'Middle Name', 'type': 'text', 'options': []},
                {'text': 'Last Name', 'type': 'text', 'options': []},
                {'text': 'Gender', 'type': 'radio', 'options': ['Male', 'Female']},
                {'text': 'Birthdate', 'type': 'date', 'options': []},
                {'text': 'Phone Number', 'type': 'text', 'options': []},
                {'text': 'Address', 'type': 'text', 'options': []},
                {'text': 'Civil Status', 'type': 'radio', 'options': ['Single', 'Married', 'Widowed', 'Divorced']},
            ]
        },
        {
            'title': 'PART II : EMPLOYMENT STATUS',
            'description': 'Current employment information',
            'questions': [
                {'text': 'Are you currently employed?', 'type': 'radio', 'options': ['Yes', 'No']},
                {'text': 'Company Name', 'type': 'text', 'options': []},
                {'text': 'Position/Job Title', 'type': 'text', 'options': []},
                {'text': 'Monthly Salary', 'type': 'text', 'options': []},
                {'text': 'Date Started', 'type': 'date', 'options': []},
                {'text': 'Is your job related to your course?', 'type': 'radio', 'options': ['Yes', 'No', 'Partially']},
            ]
        },
        {
            'title': 'PART III : FURTHER EDUCATION',
            'description': 'Additional education and training',
            'questions': [
                {'text': 'Are you pursuing further studies?', 'type': 'radio', 'options': ['Yes', 'No']},
                {'text': 'Date Started', 'type': 'date', 'options': []},
                {'text': 'Post Graduate Degree', 'type': 'text', 'options': []},
                {'text': 'Institution/University', 'type': 'text', 'options': []},
                {'text': 'Units Obtained', 'type': 'text', 'options': []},
            ]
        }
    ]
    
    created_count = 0
    for cat_data in categories:
        # Create category
        category = QuestionCategory.objects.create(
            title=cat_data['title'],
            description=cat_data['description']
        )
        print(f"✅ Created category: {category.title}")
        
        # Create questions for this category
        for q_data in cat_data['questions']:
            question = Question.objects.create(
                category=category,
                text=q_data['text'],
                type=q_data['type'],
                options=q_data['options'] if q_data['options'] else None
            )
            print(f"  ✅ Created question: {question.text}")
            created_count += 1
    
    print(f"\n🎉 Successfully created {len(categories)} categories and {created_count} questions!")
    
    # Verify creation
    final_questions = Question.objects.count()
    final_categories = QuestionCategory.objects.count()
    print(f"Final count - Questions: {final_questions}, Categories: {final_categories}")

if __name__ == '__main__':
    check_and_create_tracker_questions()

















