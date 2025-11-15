# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0122_remove_rate_limiting'),
    ]

    operations = [
        migrations.AddField(
            model_name='engagementpointssettings',
            name='milestone_tasks_enabled',
            field=models.BooleanField(default=True, help_text='Enable or disable milestone tasks feature'),
        ),
    ]

