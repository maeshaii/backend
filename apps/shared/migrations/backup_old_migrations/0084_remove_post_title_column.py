# Generated manually to fix database schema mismatch

from django.db import migrations


def drop_post_title_column(apps, schema_editor):
    """Remove the post_title column if it exists"""
    try:
        schema_editor.execute("ALTER TABLE shared_post DROP COLUMN IF EXISTS post_title;")
    except Exception:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0082_fix_repost_constraint'),
    ]

    operations = [
        # Remove the post_title column from the database table (cleanup)
        migrations.RunPython(drop_post_title_column, migrations.RunPython.noop),
    ]

