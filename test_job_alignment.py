import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User

def test_job_alignment():
    print("=== TESTING UPDATED JOB ALIGNMENT LOGIC ===")
    
    # Test cases with different scenarios
    test_cases = [
        {
            'name': 'Test User 1',
            'course': 'BSIT',
            'position': 'Software Developer',
            'employment_type': 'Employed by company',
            'expected_alignment': 'aligned',
            'expected_category': 'info_tech'
        },
        {
            'name': 'Test User 2',
            'course': 'BSIS',
            'position': 'Computer Systems Analysts',
            'employment_type': 'Self-employed',
            'expected_alignment': 'aligned',
            'expected_category': 'info_system'
        },
        {
            'name': 'Test User 3',
            'course': 'BIT-CT',
            'position': 'Computer Hardware Engineers',
            'employment_type': 'Employed by company',
            'expected_alignment': 'aligned',
            'expected_category': 'comp_tech'
        },
        {
            'name': 'Test User 4',
            'course': 'BSIT',
            'position': 'Geological Technicians',
            'employment_type': 'Self-employed',
            'expected_alignment': 'not_aligned',
            'expected_category': None
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n--- Test Case {i}: {test_case['name']} ---")
        print(f"Course: {test_case['course']}")
        print(f"Position: {test_case['position']}")
        print(f"Employment Type: {test_case['employment_type']}")
        
        # Create a test user
        user = User()
        user.course = test_case['course']
        user.position_current = test_case['position']
        user.q_employment_type = test_case['employment_type']
        
        # Update job alignment
        user.update_job_alignment()
        
        # Check results
        print(f"Result - Alignment: {user.job_alignment_status}")
        print(f"Result - Category: {user.job_alignment_category}")
        print(f"Result - Title: {user.job_alignment_title}")
        print(f"Result - Self-employed: {user.self_employed}")
        
        # Verify expectations
        alignment_correct = user.job_alignment_status == test_case['expected_alignment']
        category_correct = user.job_alignment_category == test_case['expected_category']
        self_employed_correct = user.self_employed == ('self-employed' in test_case['employment_type'].lower())
        
        print(f"✓ Alignment correct: {alignment_correct}")
        print(f"✓ Category correct: {category_correct}")
        print(f"✓ Self-employed correct: {self_employed_correct}")
        
        if alignment_correct and category_correct and self_employed_correct:
            print("✅ Test PASSED")
        else:
            print("❌ Test FAILED")

if __name__ == '__main__':
    test_job_alignment() 