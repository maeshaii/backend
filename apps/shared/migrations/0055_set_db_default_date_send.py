from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0054_default_date_send_now'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "ALTER TABLE shared_message ALTER COLUMN date_send SET DEFAULT NOW();"
            ),
            reverse_sql=(
                "ALTER TABLE shared_message ALTER COLUMN date_send DROP DEFAULT;"
            ),
        ),
    ]


