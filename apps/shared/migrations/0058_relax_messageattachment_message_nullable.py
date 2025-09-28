from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0046_add_sector_scope_fields'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "ALTER TABLE shared_messageattachment ALTER COLUMN message_id DROP NOT NULL;"
            ),
            reverse_sql=(
                "ALTER TABLE shared_messageattachment ALTER COLUMN message_id SET NOT NULL;"
            ),
        ),
    ]



