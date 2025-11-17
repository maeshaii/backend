# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0125_add_coordinator_to_ojt_company_profile'),
    ]

    operations = [
        migrations.AddField(
            model_name='engagementpointssettings',
            name='tracker_form_enabled',
            field=models.BooleanField(default=True, help_text='Enable or disable tracker form rewards'),
        ),
    ]

