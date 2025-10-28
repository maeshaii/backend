# Generated manually for reward inventory system

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0100_userpoints'),
    ]

    operations = [
        migrations.CreateModel(
            name='RewardInventoryItem',
            fields=[
                ('item_id', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('type', models.CharField(max_length=100)),
                ('quantity', models.IntegerField(default=0)),
                ('value', models.CharField(max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Reward Inventory Item',
                'verbose_name_plural': 'Reward Inventory Items',
                'db_table': 'shared_rewardinventoryitem',
            },
        ),
        migrations.AddIndex(
            model_name='rewardinventoryitem',
            index=models.Index(fields=['type'], name='shared_rewardinv_type_idx'),
        ),
        migrations.AddIndex(
            model_name='rewardinventoryitem',
            index=models.Index(fields=['-created_at'], name='shared_rewardinv_created_idx'),
        ),
    ]

