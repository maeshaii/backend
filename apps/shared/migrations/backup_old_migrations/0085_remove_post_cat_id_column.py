# Generated manually to fix database schema mismatch for post_cat_id

from django.db import migrations


def drop_post_cat_id_column(apps, schema_editor):
    """Remove the post_cat_id column if it exists"""
    try:
        schema_editor.execute("ALTER TABLE shared_post DROP COLUMN IF EXISTS post_cat_id;")
    except Exception:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0084_remove_post_title_column'),
    ]

    operations = [
        # Remove the post_cat_id column from the database table (cleanup)
        migrations.RunPython(drop_post_cat_id_column, migrations.RunPython.noop),
    ]

