from django.db import migrations, models


def drop_not_null_receiver(apps, schema_editor):
    # Make receiver_id nullable if the column already exists
    with schema_editor.connection.cursor() as cursor:
        try:
            cursor.execute("ALTER TABLE shared_message ALTER COLUMN receiver_id DROP NOT NULL;")
        except Exception:
            # Ignore if the column is already nullable or does not exist
            pass


def reverse_set_not_null_receiver(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        try:
            cursor.execute("ALTER TABLE shared_message ALTER COLUMN receiver_id SET NOT NULL;")
        except Exception:
            pass


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0052_message_receiver_alter_messageattachment_message'),
    ]

    operations = [
        migrations.RunPython(drop_not_null_receiver, reverse_set_not_null_receiver),
        migrations.AlterField(
            model_name='messageattachment',
            name='message',
            field=models.ForeignKey(
                on_delete=models.deletion.CASCADE,
                related_name='attachments',
                to='shared.message',
                null=True,
                blank=True,
            ),
        ),
    ]


