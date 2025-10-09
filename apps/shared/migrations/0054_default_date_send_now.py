from django.db import migrations


def set_default_date_send(apps, schema_editor):
    # Ensure existing rows have date_send; set to NOW() where missing
    with schema_editor.connection.cursor() as cursor:
        try:
            cursor.execute("UPDATE shared_message SET date_send = NOW() WHERE date_send IS NULL;")
        except Exception:
            pass


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0053_drop_not_null_receiver_and_alter_attachment'),
    ]

    operations = [
        migrations.RunPython(set_default_date_send, migrations.RunPython.noop),
    ]


