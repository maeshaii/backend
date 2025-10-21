# Generated manually to fix Forum table schema - remove post_id column

from django.db import migrations


def drop_forum_post_id_column(apps, schema_editor):
    """Remove the post_id column from the shared_forum table if it exists"""
    try:
        schema_editor.execute("ALTER TABLE shared_forum DROP COLUMN IF EXISTS post_id;")
    except Exception:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0086_fix_forum_table_schema'),
    ]

    operations = [
        # Remove the post_id column from the shared_forum table (cleanup)
        migrations.RunPython(drop_forum_post_id_column, migrations.RunPython.noop),
    ]

