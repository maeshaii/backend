# Generated manually to update reward types from voucher to gcash
# and add gcash fields to RewardRequest

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0144_add_calendar_event_and_post_event_fields'),
    ]

    operations = [
        # Update RewardInventoryItem type choices from voucher to gcash
        migrations.AlterField(
            model_name='rewardinventoryitem',
            name='type',
            field=models.CharField(
                choices=[
                    ('gcash', 'Gcash'),
                    ('merchandise', 'Merchandise'),
                ],
                max_length=100
            ),
        ),
        # Add gcash_number field to RewardRequest
        migrations.AddField(
            model_name='rewardrequest',
            name='gcash_number',
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
        # Add gcash_name field to RewardRequest
        migrations.AddField(
            model_name='rewardrequest',
            name='gcash_name',
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
    ]



