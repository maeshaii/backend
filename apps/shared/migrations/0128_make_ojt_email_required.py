# Generated manually to make OJT email field required

from django.db import migrations, models


def set_default_email_for_existing_records(apps, schema_editor):
    """Set a default email for any existing OJT records without email"""
    OJTInfo = apps.get_model('shared', 'OJTInfo')
    # For any existing records without email, use username@ctu.edu.ph as default
    for ojt_info in OJTInfo.objects.filter(email__isnull=True):
        if ojt_info.user:
            ojt_info.email = f"{ojt_info.user.acc_username}@ctu.edu.ph"
            ojt_info.save()


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
        # Then, make the field required (non-nullable)
        migrations.AlterField(
            model_name='ojtinfo',
            name='email',
            field=models.EmailField(help_text='Student email address for OJT purposes (required)'),
        ),
    ]


