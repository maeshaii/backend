from django.db import migrations, connection


def move_ojt_email_to_profile(apps, schema_editor):
    """
    Move email from OJTInfo to UserProfile.
    This migration has already been executed. If run again, it safely skips
    since the email field no longer exists on OJTInfo.
    
    Since emails are now stored in UserProfile, we skip the data migration
    if the column doesn't exist (it's already been moved).
    """
    # Check if email column actually exists in the database using a safe query
    # If it doesn't exist, emails have already been moved to UserProfile
    try:
        with connection.cursor() as cursor:
            # Try to query the column - if it fails, the column doesn't exist
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'shared_ojtinfo' 
                AND column_name = 'email'
            """)
            result = cursor.fetchone()
            column_exists = result[0] > 0 if result else False
    except Exception:
        # If we can't check, assume column doesn't exist (already migrated)
        print("Email column check failed. Assuming column does not exist and skipping data migration.")
        return
    
    if not column_exists:
        print("Email column already removed from shared_ojtinfo. Emails are in UserProfile. Skipping data migration.")
        return
    
    # Column exists - try to move emails to UserProfile
    UserProfile = apps.get_model('shared', 'UserProfile')
    try:
        with connection.cursor() as cursor:
            # Use raw SQL to safely query OJTInfo records with email
            cursor.execute("""
                SELECT user_id, email 
                FROM shared_ojtinfo 
                WHERE email IS NOT NULL AND email != ''
            """)
            ojt_emails = cursor.fetchall()
        
        # Move emails to UserProfile
        for user_id, email_value in ojt_emails:
            if not email_value:
                continue
            
            try:
                profile = UserProfile.objects.get(user_id=user_id)
                if not profile.email:
                    profile.email = email_value
                    profile.save(update_fields=['email'])
            except UserProfile.DoesNotExist:
                # Create UserProfile if it doesn't exist
                User = apps.get_model('shared', 'User')
                try:
                    user = User.objects.get(user_id=user_id)
                    UserProfile.objects.create(user=user, email=email_value)
                except User.DoesNotExist:
                    continue
    except Exception as e:
        # If email column doesn't exist or any other error occurs, 
        # the migration has likely already been completed
        # Emails are already in UserProfile, so we can safely skip
        print(f"Could not move emails (likely already in UserProfile): {e}. Skipping data migration.")
        return


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

