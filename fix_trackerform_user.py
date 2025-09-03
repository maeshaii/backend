import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, TrackerForm

def main():
    print("=== FIXING TRACKERFORM USER_ID ===")
    tracker_form = TrackerForm.objects.first()
    if not tracker_form:
        print("No tracker form found.")
        return
    first_user = User.objects.filter(account_type__user=True).first()
    if not first_user:
        print("No alumni user found.")
        return
    tracker_form.user = first_user
    tracker_form.save()
    print(f"Set tracker_form_id {tracker_form.tracker_form_id} user_id to {first_user.user_id} ({first_user.f_name} {first_user.l_name})")

if __name__ == '__main__':
    main() 