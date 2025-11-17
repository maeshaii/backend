from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0123_add_milestone_tasks_enabled'),
    ]

    operations = [
        migrations.AddField(
            model_name='pointstask',
            name='required_count',
            field=models.IntegerField(blank=True, help_text='Number of actions required to complete this task', null=True),
        ),
    ]


