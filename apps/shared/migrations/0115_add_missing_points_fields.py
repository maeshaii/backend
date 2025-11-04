# Generated manually to fix missing database columns

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0114_engagementpointssettings_and_more'),
    ]

    operations = [
        # Add post_points to EngagementPointsSettings
        migrations.AddField(
            model_name='engagementpointssettings',
            name='post_points',
            field=models.IntegerField(default=0, help_text='Points for posting without photos'),
        ),
        # Add points_from_posts and post_count to UserPoints
        # Using SeparateDatabaseAndState since UserPoints table was created with raw SQL
        migrations.SeparateDatabaseAndState(
            database_operations=[
                # Add points_from_posts column to shared_userpoints table
                migrations.RunSQL(
                    sql=(
                        "DO $$ BEGIN "
                        "IF NOT EXISTS (SELECT 1 FROM information_schema.columns "
                        "WHERE table_name='shared_userpoints' AND column_name='points_from_posts') THEN "
                        "ALTER TABLE shared_userpoints ADD COLUMN points_from_posts integer NOT NULL DEFAULT 0; "
                        "END IF; END $$;"
                    ),
                    reverse_sql=(
                        "ALTER TABLE shared_userpoints DROP COLUMN IF EXISTS points_from_posts;"
                    ),
                ),
                # Add post_count column to shared_userpoints table
                migrations.RunSQL(
                    sql=(
                        "DO $$ BEGIN "
                        "IF NOT EXISTS (SELECT 1 FROM information_schema.columns "
                        "WHERE table_name='shared_userpoints' AND column_name='post_count') THEN "
                        "ALTER TABLE shared_userpoints ADD COLUMN post_count integer NOT NULL DEFAULT 0; "
                        "END IF; END $$;"
                    ),
                    reverse_sql=(
                        "ALTER TABLE shared_userpoints DROP COLUMN IF EXISTS post_count;"
                    ),
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='userpoints',
                    name='points_from_posts',
                    field=models.IntegerField(default=0),
                ),
                migrations.AddField(
                    model_name='userpoints',
                    name='post_count',
                    field=models.IntegerField(default=0),
                ),
            ],
        ),
    ]

