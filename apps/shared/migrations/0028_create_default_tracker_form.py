# Generated manually to create default TrackerForm

from django.db import migrations

def create_default_tracker_form(apps, schema_editor):
    TrackerForm = apps.get_model('shared', 'TrackerForm')
    
    # Only create if no TrackerForm exists
    if not TrackerForm.objects.exists():
        TrackerForm.objects.create(
            title="CTU MAIN ALUMNI TRACKER",
            description="Default tracker form for CTU alumni",
            accepting_responses=True
        )

def reverse_create_default_tracker_form(apps, schema_editor):
    TrackerForm = apps.get_model('shared', 'TrackerForm')
    TrackerForm.objects.filter(title="CTU MAIN ALUMNI TRACKER").delete()

class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0027_merge_20250803_1154'),
    ]

    operations = [
        migrations.RunPython(
            create_default_tracker_form,
            reverse_create_default_tracker_form
        ),
    ] 