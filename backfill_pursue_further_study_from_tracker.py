import os
import django

def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
    django.setup()
    from apps.shared.models import User, TrackerResponse

    updated = 0
    for user in User.objects.filter(account_type__user=True):
        latest_response = TrackerResponse.objects.filter(user=user).order_by('-submitted_at').first()
        if not latest_response:
            continue
        answers = latest_response.answers or {}
        q22 = answers.get('22') or answers.get(22)
        if not q22:
            continue
        val = str(q22).strip().lower()
        if val in ['yes', 'true', '1']:
            user.pursue_further_study = 'yes'
        elif val in ['no', 'false', '0']:
            user.pursue_further_study = 'no'
        else:
            user.pursue_further_study = val  # fallback to raw answer
        user.save()
        updated += 1
    print(f"Updated pursue_further_study for {updated} alumni.")

if __name__ == '__main__':
    main() 