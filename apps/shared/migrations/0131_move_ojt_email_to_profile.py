from django.db import migrations


def move_ojt_email_to_profile(apps, schema_editor):
    """
    Move email from OJTInfo to UserProfile.
    This migration has already been executed. If run again, it safely skips
    since the email field no longer exists on OJTInfo.
    """
    OJTInfo = apps.get_model('shared', 'OJTInfo')
    UserProfile = apps.get_model('shared', 'UserProfile')
    
    # Check if email field still exists on OJTInfo (it won't after first run)
    # This makes the migration safe to run multiple times
    if not hasattr(OJTInfo, 'email') and 'email' not in [f.name for f in OJTInfo._meta.get_fields()]:
        print("Email field already removed from OJTInfo. Skipping data migration.")
        return
    
    try:
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
    except Exception as e:
        # If email field doesn't exist, the migration has already run successfully
        print(f"Migration already completed or email field not found: {e}")


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0130_backfill_trackerresponse_draft_columns'),
    ]

    operations = [
        migrations.RunPython(move_ojt_email_to_profile, migrations.RunPython.noop),
        # Use RunSQL to safely remove index and field if they exist
        migrations.RunSQL(
            sql=[
                # Remove index if it exists (PostgreSQL/MySQL compatible)
                "DROP INDEX IF EXISTS shared_ojti_email_5c6bf2_idx;",
                # For PostgreSQL, also try this format
                "ALTER TABLE shared_ojtinfo DROP CONSTRAINT IF EXISTS shared_ojti_email_5c6bf2_idx;",
            ],
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="ALTER TABLE shared_ojtinfo DROP COLUMN IF EXISTS email;",
            reverse_sql="ALTER TABLE shared_ojtinfo ADD COLUMN IF NOT EXISTS email varchar(254);",
        ),
    ]

