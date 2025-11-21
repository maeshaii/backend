from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0132_inventorytransaction_rewarditembatch_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE shared_ojtinfo DROP COLUMN IF EXISTS email;",
            reverse_sql="ALTER TABLE shared_ojtinfo ADD COLUMN email varchar(254);",
        ),
    ]

