# Generated manually to fix repost constraint issue

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0081_fix_like_constraint'),
    ]

    operations = [
        # Drop the old constraint that doesn't include donation_request
        migrations.RunSQL(
            "ALTER TABLE shared_repost DROP CONSTRAINT IF EXISTS repost_post_or_forum_not_both;",
            reverse_sql="-- No reverse operation needed"
        ),
        # Ensure the correct constraint is applied
        migrations.RunSQL(
            """
            ALTER TABLE shared_repost DROP CONSTRAINT IF EXISTS repost_one_content_type_only;
            """,
            reverse_sql="-- No reverse operation needed"
        ),
        migrations.RunSQL(
            """
            ALTER TABLE shared_repost ADD CONSTRAINT repost_one_content_type_only 
            CHECK (
                (post_id IS NOT NULL AND forum_id IS NULL AND donation_request_id IS NULL) OR
                (post_id IS NULL AND forum_id IS NOT NULL AND donation_request_id IS NULL) OR
                (post_id IS NULL AND forum_id IS NULL AND donation_request_id IS NOT NULL)
            );
            """,
            reverse_sql="ALTER TABLE shared_repost DROP CONSTRAINT IF EXISTS repost_one_content_type_only;"
        ),
    ]
