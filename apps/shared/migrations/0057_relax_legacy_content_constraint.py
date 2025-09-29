from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0056_alter_forum_created_at_alter_message_content'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "ALTER TABLE shared_message ALTER COLUMN content DROP NOT NULL;"
            ),
            reverse_sql=(
                "ALTER TABLE shared_message ALTER COLUMN content SET NOT NULL;"
            ),
        ),
    ]


