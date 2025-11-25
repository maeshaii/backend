# Generated manually to add voucher and merchandise as type choices for rewards

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0140_remove_ojtinfo_shared_ojti_email_5c6bf2_idx_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='rewardinventoryitem',
            name='type',
            field=models.CharField(
                choices=[
                    ('voucher', 'Voucher'),
                    ('merchandise', 'Merchandise'),
                ],
                max_length=100
            ),
        ),
    ]

