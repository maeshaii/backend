from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("shared", "0129_remove_ojt_extra_fields"),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "ALTER TABLE IF EXISTS shared_trackerresponse "
                "ADD COLUMN IF NOT EXISTS is_draft BOOLEAN NOT NULL DEFAULT FALSE;"
            ),
            reverse_sql=(
                "ALTER TABLE IF EXISTS shared_trackerresponse "
                "DROP COLUMN IF EXISTS is_draft;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE IF EXISTS shared_trackerresponse "
                "ADD COLUMN IF NOT EXISTS last_saved_at TIMESTAMPTZ NOT NULL DEFAULT NOW();"
            ),
            reverse_sql=(
                "ALTER TABLE IF EXISTS shared_trackerresponse "
                "DROP COLUMN IF EXISTS last_saved_at;"
            ),
        ),
    ]

