# Generated migration to add is_read field to Notification model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0040_add_messaging_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='is_read',
            field=models.BooleanField(default=False),
        ),
    ]

