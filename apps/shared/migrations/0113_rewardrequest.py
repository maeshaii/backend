# Generated manually for reward request system
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0112_conversation_request_initiator'),
    ]

    operations = [
        migrations.CreateModel(
            name='RewardRequest',
            fields=[
                ('request_id', models.AutoField(primary_key=True, serialize=False)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('ready_for_pickup', 'Ready for Pickup'), ('claimed', 'Claimed'), ('expired', 'Expired'), ('rejected', 'Rejected')], default='pending', max_length=20)),
                ('points_cost', models.IntegerField(default=0)),
                ('voucher_code', models.CharField(blank=True, max_length=255, null=True)),
                ('voucher_file', models.FileField(blank=True, null=True, upload_to='vouchers/')),
                ('requested_at', models.DateTimeField(auto_now_add=True)),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('notes', models.TextField(blank=True, null=True)),
                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approved_rewards', to='shared.user')),
                ('reward_item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='requests', to='shared.rewardinventoryitem')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reward_requests', to='shared.user')),
            ],
            options={
                'verbose_name': 'Reward Request',
                'verbose_name_plural': 'Reward Requests',
                'db_table': 'shared_rewardrequest',
                'ordering': ['-requested_at'],
            },
        ),
        migrations.AddIndex(
            model_name='rewardrequest',
            index=models.Index(fields=['user'], name='shared_rewa_user_idx'),
        ),
        migrations.AddIndex(
            model_name='rewardrequest',
            index=models.Index(fields=['status'], name='shared_rewa_status_idx'),
        ),
        migrations.AddIndex(
            model_name='rewardrequest',
            index=models.Index(fields=['-requested_at'], name='shared_rewa_request_idx'),
        ),
        migrations.AddIndex(
            model_name='rewardrequest',
            index=models.Index(fields=['expires_at'], name='shared_rewa_expires_idx'),
        ),
    ]






