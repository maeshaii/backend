from django.core.management.base import BaseCommand
from apps.shared.models import TrackerForm

class Command(BaseCommand):
    help = 'Create a default TrackerForm if none exists'

    def handle(self, *args, **options):
        if TrackerForm.objects.exists():
            self.stdout.write(
                self.style.WARNING('TrackerForm already exists. Skipping creation.')
            )
            return

        try:
            form = TrackerForm.objects.create(
                title="CTU MAIN ALUMNI TRACKER",
                description="Default tracker form for CTU alumni",
                accepting_responses=True
            )
            self.stdout.write(
                self.style.SUCCESS(f'Successfully created TrackerForm with ID: {form.pk}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to create TrackerForm: {str(e)}')
            ) 