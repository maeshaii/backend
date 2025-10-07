# Generated manually to fix database schema mismatch for post_cat_id

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0084_remove_post_title_column'),
    ]

    operations = [
        migrations.RunSQL(
            # Remove the post_cat_id column from the database table
            "ALTER TABLE shared_post DROP COLUMN IF EXISTS post_cat_id;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]

