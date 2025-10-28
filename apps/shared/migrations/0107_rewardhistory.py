# Generated manually for reward history tracking

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0106_rewardinventoryitem'),
    ]

    operations = [
        migrations.CreateModel(
            name='RewardHistory',
            fields=[
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('reward_name', models.CharField(max_length=255)),
                ('reward_type', models.CharField(max_length=100)),
                ('reward_value', models.CharField(max_length=100)),
                ('points_deducted', models.IntegerField(default=0)),
                ('given_at', models.DateTimeField(auto_now_add=True)),
                ('given_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rewards_given', to='shared.user')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rewards_received', to='shared.user')),
            ],
            options={
                'verbose_name': 'Reward History',
                'verbose_name_plural': 'Reward Histories',
                'db_table': 'shared_rewardhistory',
                'ordering': ['-given_at'],
            },
        ),
        migrations.AddIndex(
            model_name='rewardhistory',
            index=models.Index(fields=['user'], name='shared_rewardhistory_user_idx'),
        ),
        migrations.AddIndex(
            model_name='rewardhistory',
            index=models.Index(fields=['-given_at'], name='shared_rewardhistory_given_idx'),
        ),
    ]

