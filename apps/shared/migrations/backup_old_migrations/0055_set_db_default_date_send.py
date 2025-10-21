from django.db import migrations, models
from django.db.models.functions import Now


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0054_default_date_send_now'),
    ]

    operations = [
        # Use db_default to set database-level default
        migrations.AlterField(
            model_name='message',
            name='date_send',
            field=models.DateTimeField(db_default=Now()),
        ),
    ]


