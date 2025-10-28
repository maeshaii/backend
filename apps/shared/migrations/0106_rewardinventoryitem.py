# Generated manually for reward inventory system

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0100_userpoints'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "CREATE TABLE IF NOT EXISTS shared_rewardinventoryitem ("
                        "item_id serial PRIMARY KEY,"
                        "name varchar(255) NOT NULL,"
                        "type varchar(100) NOT NULL,"
                        "quantity integer NOT NULL DEFAULT 0,"
                        "value varchar(100) NOT NULL,"
                        "created_at timestamp with time zone NOT NULL DEFAULT now(),"
                        "updated_at timestamp with time zone NOT NULL DEFAULT now()"
                        ");"
                    ),
                    reverse_sql=(
                        "DROP TABLE IF EXISTS shared_rewardinventoryitem;"
                    ),
                ),
                migrations.RunSQL(
                    sql=(
                        "DO $$ BEGIN "
                        "IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'shared_rewardinv_type_idx') THEN "
                        "CREATE INDEX shared_rewardinv_type_idx ON shared_rewardinventoryitem (type); "
                        "END IF; END $$;"
                    ),
                    reverse_sql=(
                        "DROP INDEX IF EXISTS shared_rewardinv_type_idx;"
                    ),
                ),
                migrations.RunSQL(
                    sql=(
                        "DO $$ BEGIN "
                        "IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'shared_rewardinv_created_idx') THEN "
                        "CREATE INDEX shared_rewardinv_created_idx ON shared_rewardinventoryitem ((-extract(epoch from created_at))); "
                        "END IF; END $$;"
                    ),
                    reverse_sql=(
                        "DROP INDEX IF EXISTS shared_rewardinv_created_idx;"
                    ),
                ),
            ],
            state_operations=[
                migrations.CreateModel(
                    name='RewardInventoryItem',
                    fields=[
                        ('item_id', models.AutoField(primary_key=True, serialize=False)),
                        ('name', models.CharField(max_length=255)),
                        ('type', models.CharField(max_length=100)),
                        ('quantity', models.IntegerField(default=0)),
                        ('value', models.CharField(max_length=100)),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                    ],
                    options={
                        'verbose_name': 'Reward Inventory Item',
                        'verbose_name_plural': 'Reward Inventory Items',
                        'db_table': 'shared_rewardinventoryitem',
                    },
                ),
                migrations.AddIndex(
                    model_name='rewardinventoryitem',
                    index=models.Index(fields=['type'], name='shared_rewardinv_type_idx'),
                ),
                migrations.AddIndex(
                    model_name='rewardinventoryitem',
                    index=models.Index(fields=['-created_at'], name='shared_rewardinv_created_idx'),
                ),
            ],
        ),
    ]

