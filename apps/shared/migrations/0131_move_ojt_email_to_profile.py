from django.db import migrations


def move_ojt_email_to_profile(apps, schema_editor):
    OJTInfo = apps.get_model('shared', 'OJTInfo')
    UserProfile = apps.get_model('shared', 'UserProfile')

    for ojt_info in OJTInfo.objects.exclude(email__isnull=True).exclude(email=''):
        email_value = ojt_info.email
        if not email_value:
            continue

        try:
            profile = UserProfile.objects.get(user=ojt_info.user)
        except UserProfile.DoesNotExist:
            UserProfile.objects.create(user=ojt_info.user, email=email_value)
            continue

        if not profile.email:
            profile.email = email_value
            profile.save(update_fields=['email'])


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0130_backfill_trackerresponse_draft_columns'),
    ]

    operations = [
        migrations.RunPython(move_ojt_email_to_profile, migrations.RunPython.noop),
        migrations.RemoveIndex(
            model_name='ojtinfo',
            name='shared_ojti_email_5c6bf2_idx',
        ),
        migrations.RemoveField(
            model_name='ojtinfo',
            name='email',
        ),
    ]

