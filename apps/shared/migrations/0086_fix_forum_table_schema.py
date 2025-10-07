# Generated manually to fix Forum table schema mismatch

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0085_remove_post_cat_id_column'),
    ]

    operations = [
        migrations.RunSQL(
            # Add missing columns to the shared_forum table
            """
            ALTER TABLE shared_forum 
            ADD COLUMN IF NOT EXISTS image VARCHAR(100),
            ADD COLUMN IF NOT EXISTS content TEXT,
            ADD COLUMN IF NOT EXISTS type VARCHAR(50),
            ADD COLUMN IF NOT EXISTS date_send TIMESTAMPTZ DEFAULT NOW();
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]

