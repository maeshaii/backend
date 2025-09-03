import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, TrackerResponse, Question

def debug_position_mapping():
    print("=== DEBUGGING POSITION MAPPING ===")
    
    # Check questions
    print("\n1. Questions with 'position' in text:")
    for q in Question.objects.filter(text__icontains='position'):
        print(f"   ID: {q.id}, Text: {q.text}")
    
    # Check user 1337504
    try:
        user = User.objects.get(user_id='1337504')
        print(f"\n2. User: {user.f_name} {user.l_name} (ID: {user.user_id})")
        print(f"   Current position_current: '{user.position_current}'")
        
        resp = TrackerResponse.objects.filter(user=user).first()
        if resp:
            print(f"\n3. Tracker Response answers:")
            for k, v in resp.answers.items():
                if 'position' in str(k).lower() or str(k) in ['16', '26']:
                    print(f"   Key '{k}': '{v}'")
            
            # Check what question 16 and 26 actually contain
            q16 = Question.objects.filter(id=16).first()
            q26 = Question.objects.filter(id=26).first()
            if q16:
                print(f"\n4. Question 16: '{q16.text}'")
                print(f"   Answer: '{resp.answers.get('16') or resp.answers.get(16)}'")
            if q26:
                print(f"   Question 26: '{q26.text}'")
                print(f"   Answer: '{resp.answers.get('26') or resp.answers.get(26)}'")
        else:
            print("   No tracker response found")
    except User.DoesNotExist:
        print("   User 1337504 not found")

if __name__ == '__main__':
    debug_position_mapping() 