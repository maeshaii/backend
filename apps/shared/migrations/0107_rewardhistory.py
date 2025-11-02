# Generated manually for reward history tracking

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0106_rewardinventoryitem'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "CREATE TABLE IF NOT EXISTS shared_rewardhistory ("
                        "history_id serial PRIMARY KEY,"
                        "user_id integer NOT NULL REFERENCES shared_user(user_id) ON DELETE CASCADE,"
                        "given_by_id integer REFERENCES shared_user(user_id) ON DELETE SET NULL,"
                        "reward_name varchar(255) NOT NULL,"
                        "reward_type varchar(100) NOT NULL,"
                        "reward_value varchar(100) NOT NULL,"
                        "points_deducted integer NOT NULL DEFAULT 0,"
                        "given_at timestamp with time zone NOT NULL DEFAULT now()"
                        ");"
                    ),
                    reverse_sql=(
                        "DROP TABLE IF EXISTS shared_rewardhistory;"
                    ),
                ),
                migrations.RunSQL(
                    sql=(
                        "DO $$ BEGIN "
                        "IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'shared_rewardhistory_user_idx') THEN "
                        "CREATE INDEX shared_rewardhistory_user_idx ON shared_rewardhistory (user_id); "
                        "END IF; END $$;"
                    ),
                    reverse_sql=(
                        "DROP INDEX IF EXISTS shared_rewardhistory_user_idx;"
                    ),
                ),
                migrations.RunSQL(
                    sql=(
                        "DO $$ BEGIN "
                        "IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'shared_rewardhistory_given_idx') THEN "
                        "CREATE INDEX shared_rewardhistory_given_idx ON shared_rewardhistory (given_at DESC); "
                        "END IF; END $$;"
                    ),
                    reverse_sql=(
                        "DROP INDEX IF EXISTS shared_rewardhistory_given_idx;"
                    ),
                ),
            ],
            state_operations=[
                migrations.CreateModel(
                    name='RewardHistory',
                    fields=[
                        ('history_id', models.AutoField(primary_key=True, serialize=False)),
                        ('reward_name', models.CharField(max_length=255)),
                        ('reward_type', models.CharField(max_length=100)),
                        ('reward_value', models.CharField(max_length=100)),
                        ('points_deducted', models.IntegerField(default=0)),
                        ('given_at', models.DateTimeField(auto_now_add=True)),
                        ('given_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rewards_given', to='shared.user')),
                        ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rewards_received', to='shared.user')),
                    ],
                    options={
                        'verbose_name': 'Reward History',
                        'verbose_name_plural': 'Reward Histories',
                        'db_table': 'shared_rewardhistory',
                        'ordering': ['-given_at'],
                    },
                ),
                migrations.AddIndex(
                    model_name='rewardhistory',
                    index=models.Index(fields=['user'], name='shared_rewardhistory_user_idx'),
                ),
                migrations.AddIndex(
                    model_name='rewardhistory',
                    index=models.Index(fields=['-given_at'], name='shared_rewardhistory_given_idx'),
                ),
            ],
        ),
    ]

