# Generated manually for engagement points system

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0098_question_order'),
        ('shared', '0099_add_section_to_ojtimport'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "CREATE TABLE IF NOT EXISTS shared_userpoints ("
                        "id bigserial PRIMARY KEY,"
                        "user_id integer UNIQUE NOT NULL REFERENCES shared_user(user_id) ON DELETE CASCADE,"
                        "total_points integer NOT NULL DEFAULT 0,"
                        "points_from_likes integer NOT NULL DEFAULT 0,"
                        "points_from_comments integer NOT NULL DEFAULT 0,"
                        "points_from_shares integer NOT NULL DEFAULT 0,"
                        "points_from_replies integer NOT NULL DEFAULT 0,"
                        "points_from_posts_with_photos integer NOT NULL DEFAULT 0,"
                        "points_from_tracker_form integer NOT NULL DEFAULT 0,"
                        "like_count integer NOT NULL DEFAULT 0,"
                        "comment_count integer NOT NULL DEFAULT 0,"
                        "share_count integer NOT NULL DEFAULT 0,"
                        "reply_count integer NOT NULL DEFAULT 0,"
                        "post_with_photo_count integer NOT NULL DEFAULT 0,"
                        "tracker_form_count integer NOT NULL DEFAULT 0,"
                        "created_at timestamp with time zone NOT NULL DEFAULT now(),"
                        "updated_at timestamp with time zone NOT NULL DEFAULT now()"
                        ");"
                    ),
                    reverse_sql=(
                        "DROP TABLE IF EXISTS shared_userpoints;"
                    ),
                ),
                migrations.RunSQL(
                    sql=(
                        "DO $$ BEGIN "
                        "IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'shared_user_total_p_idx') THEN "
                        "CREATE INDEX shared_user_total_p_idx ON shared_userpoints ((-total_points)); "
                        "END IF; END $$;"
                    ),
                    reverse_sql=(
                        "DROP INDEX IF EXISTS shared_user_total_p_idx;"
                    ),
                ),
                migrations.RunSQL(
                    sql=(
                        "DO $$ BEGIN "
                        "IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'shared_user_user_id_idx') THEN "
                        "CREATE INDEX shared_user_user_id_idx ON shared_userpoints (user_id); "
                        "END IF; END $$;"
                    ),
                    reverse_sql=(
                        "DROP INDEX IF EXISTS shared_user_user_id_idx;"
                    ),
                ),
            ],
            state_operations=[
                migrations.CreateModel(
                    name='UserPoints',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('total_points', models.IntegerField(default=0)),
                        ('points_from_likes', models.IntegerField(default=0)),
                        ('points_from_comments', models.IntegerField(default=0)),
                        ('points_from_shares', models.IntegerField(default=0)),
                        ('points_from_replies', models.IntegerField(default=0)),
                        ('points_from_posts_with_photos', models.IntegerField(default=0)),
                        ('points_from_tracker_form', models.IntegerField(default=0)),
                        ('like_count', models.IntegerField(default=0)),
                        ('comment_count', models.IntegerField(default=0)),
                        ('share_count', models.IntegerField(default=0)),
                        ('reply_count', models.IntegerField(default=0)),
                        ('post_with_photo_count', models.IntegerField(default=0)),
                        ('tracker_form_count', models.IntegerField(default=0)),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='points', to='shared.user')),
                    ],
                    options={
                        'verbose_name': 'User Points',
                        'verbose_name_plural': 'User Points',
                        'db_table': 'shared_userpoints',
                    },
                ),
                migrations.AddIndex(
                    model_name='userpoints',
                    index=models.Index(fields=['-total_points'], name='shared_user_total_p_idx'),
                ),
                migrations.AddIndex(
                    model_name='userpoints',
                    index=models.Index(fields=['user'], name='shared_user_user_id_idx'),
                ),
            ],
        ),
    ]

