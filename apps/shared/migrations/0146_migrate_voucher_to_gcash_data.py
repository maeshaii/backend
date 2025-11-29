# Generated manually to migrate existing 'voucher' type data to 'gcash'

from django.db import migrations


def migrate_voucher_to_gcash(apps, schema_editor):
    """Update any existing 'voucher' type rewards to 'gcash' type"""
    RewardInventoryItem = apps.get_model('shared', 'RewardInventoryItem')
    
    # Update all items with type 'voucher' to 'gcash'
    updated_count = RewardInventoryItem.objects.filter(type='voucher').update(type='gcash')
    
    if updated_count > 0:
        print(f"Migrated {updated_count} reward items from 'voucher' to 'gcash' type")


def reverse_migration(apps, schema_editor):
    """Reverse migration - convert gcash back to voucher"""
    RewardInventoryItem = apps.get_model('shared', 'RewardInventoryItem')
    RewardInventoryItem.objects.filter(type='gcash').update(type='voucher')


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0145_update_reward_types_to_gcash'),
    ]

    operations = [
        migrations.RunPython(migrate_voucher_to_gcash, reverse_migration),
    ]



