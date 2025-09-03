import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, TrackerResponse

def backfill_position_current_from_tracker():
    """Backfill position_current from tracker responses, ensuring Question 26 is used"""
    users = User.objects.filter(account_type__user=True)
    updated = 0
    
    for user in users:
        latest_response = TrackerResponse.objects.filter(user=user).order_by('-submitted_at').first()
        if latest_response and latest_response.answers:
            answers = latest_response.answers
            
            # Get position from question 26 (Current Position) - PRIORITY
            position_answer = answers.get('26') or answers.get(26)
            
            if position_answer is None:
                # Fallback: look for question text containing "current position"
                for k, v in answers.items():
                    if isinstance(k, str) and 'current position' in k.lower():
                        position_answer = v
                        break
            
            if position_answer is not None:
                # Only update if the current value is different or empty
                current_value = getattr(user, 'position_current', '') or ''
                new_value = str(position_answer).strip()
                
                if current_value != new_value:
                    user.position_current = new_value
                    user.save()
                    updated += 1
                    print(f"Updated {user.f_name} {user.l_name}: position_current = '{new_value}' (was: '{current_value}')")
    
    print(f"Backfilled position_current for {updated} users.")

if __name__ == '__main__':
    backfill_position_current_from_tracker() 