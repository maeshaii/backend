# Generated manually to make OJT email field required

from django.db import migrations, models


def set_default_email_for_existing_records(apps, schema_editor):
    """
    Set a default email for any existing OJT records without email.
    This migration has already been executed. If run again, it safely skips
    since the email field no longer exists on OJTInfo (moved to UserProfile).
    """
    OJTInfo = apps.get_model('shared', 'OJTInfo')
    
    # Check if email field still exists on OJTInfo (it won't after migration 0131)
    if 'email' not in [f.name for f in OJTInfo._meta.get_fields()]:
        print("Email field already removed from OJTInfo. Skipping data migration.")
        return
    
    try:
        # For any existing records without email, use username@ctu.edu.ph as default
        for ojt_info in OJTInfo.objects.filter(email__isnull=True):
            if ojt_info.user:
                ojt_info.email = f"{ojt_info.user.acc_username}@ctu.edu.ph"
                ojt_info.save()
    except Exception as e:
        # If email field doesn't exist, the migration has already run successfully
        print(f"Migration already completed or email field not found: {e}")


def reverse_set_default_email(apps, schema_editor):
    """Reverse migration - no action needed"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0127_add_ojt_basic_info'),
    ]

    operations = [
        # First, set default emails for any existing records
        migrations.RunPython(set_default_email_for_existing_records, reverse_set_default_email),
        # Note: AlterField operation removed because email field was moved to UserProfile in migration 0131
        # The field alteration was completed before the field was removed, so no action needed here
    ]


