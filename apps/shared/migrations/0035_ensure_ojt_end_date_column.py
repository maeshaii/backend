from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('shared', '0034_merge_0003_add_ojt_end_date_0033_merge_20250810_1232'),
    ]
    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    """
                    ALTER TABLE shared_user
                    ADD COLUMN IF NOT EXISTS ojt_end_date DATE;
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[],
        ),
    ]
