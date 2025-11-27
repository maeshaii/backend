# Generated manually to preserve claimed rewards when inventory items are deleted
# This migration changes RewardRequest.reward_item from CASCADE to SET_NULL
# This ensures that when an admin deletes a reward item, users who already claimed it
# can still view their claimed rewards in notifications and history

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0142_remove_ojtinfo_shared_ojti_email_5c6bf2_idx'),
    ]

    operations = [
        migrations.AlterField(
            model_name='rewardrequest',
            name='reward_item',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='requests',
                to='shared.rewardinventoryitem'
            ),
        ),
    ]

