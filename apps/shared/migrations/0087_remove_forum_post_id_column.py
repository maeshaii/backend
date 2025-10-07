# Generated manually to fix Forum table schema - remove post_id column

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0086_fix_forum_table_schema'),
    ]

    operations = [
        migrations.RunSQL(
            # Remove the post_id column from the shared_forum table
            "ALTER TABLE shared_forum DROP COLUMN IF EXISTS post_id;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]

