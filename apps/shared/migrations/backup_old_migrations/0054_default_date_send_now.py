from django.db import migrations
from django.utils import timezone


def set_default_date_send(apps, schema_editor):
    """Ensure existing rows have date_send; set to NOW() where missing"""
    Message = apps.get_model('shared', 'Message')
    
    # Update messages without date_send
    Message.objects.filter(date_send__isnull=True).update(date_send=timezone.now())


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0053_drop_not_null_receiver_and_alter_attachment'),
    ]

    operations = [
        migrations.RunPython(set_default_date_send, migrations.RunPython.noop),
    ]


