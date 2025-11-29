# Generated manually to add gcash_receipt field to RewardRequest

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0146_migrate_voucher_to_gcash_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='rewardrequest',
            name='gcash_receipt',
            field=models.ImageField(upload_to='gcash_receipts/', null=True, blank=True),
        ),
    ]



