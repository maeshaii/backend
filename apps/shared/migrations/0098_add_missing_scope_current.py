# Generated migration to add missing scope_current column

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0097_auto_20251018_2034'),
    ]

    operations = [
        migrations.AddField(
            model_name='employmenthistory',
            name='scope_current',
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
    ]




