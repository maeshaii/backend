# Generated manually to fix database schema mismatch

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0083_add_missing_repost_fields'),
    ]

    operations = [
        migrations.RunSQL(
            # Remove the post_title column from the database table
            "ALTER TABLE shared_post DROP COLUMN IF EXISTS post_title;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]

