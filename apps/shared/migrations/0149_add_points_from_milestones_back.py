from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0148_merge_20251213_2031'),
    ]

    operations = [
        migrations.AddField(
            model_name='userpoints',
            name='points_from_milestones',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='userpoints',
            name='milestone_count',
            field=models.IntegerField(default=0),
        ),
    ]


