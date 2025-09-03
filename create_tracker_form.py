from apps.shared.models import TrackerForm, User

def run():
    user = User.objects.first()
    if not user:
        print('No users found. Please create a user first.')
        return
    form, created = TrackerForm.objects.get_or_create(
        user=user,
        defaults={
            'title': 'CTU MAIN ALUMNI TRACKER',
            'accepting_responses': True
        }
    )
    if created:
        print(f'TrackerForm created with id {form.pk} for user {user.user_id}')
    else:
        print(f'TrackerForm already exists with id {form.pk} for user {user.user_id}') 