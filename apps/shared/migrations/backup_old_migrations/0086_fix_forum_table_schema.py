# Generated manually to fix Forum table schema mismatch

from django.db import migrations


def ensure_forum_columns(apps, schema_editor):
    """Add missing columns to the shared_forum table if they don't exist"""
    try:
        schema_editor.execute("""
            ALTER TABLE shared_forum 
            ADD COLUMN IF NOT EXISTS image VARCHAR(100),
            ADD COLUMN IF NOT EXISTS content TEXT,
            ADD COLUMN IF NOT EXISTS type VARCHAR(50),
            ADD COLUMN IF NOT EXISTS date_send TIMESTAMPTZ DEFAULT NOW();
        """)
    except Exception:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0085_remove_post_cat_id_column'),
    ]

    operations = [
        # Add missing columns to the shared_forum table (repair migration)
        migrations.RunPython(ensure_forum_columns, migrations.RunPython.noop),
    ]

