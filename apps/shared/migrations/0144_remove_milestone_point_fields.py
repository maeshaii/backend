from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0143_preserve_claimed_rewards_on_item_delete'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='userpoints',
            name='points_from_milestones',
        ),
        migrations.RemoveField(
            model_name='userpoints',
            name='milestone_count',
        ),
    ]


