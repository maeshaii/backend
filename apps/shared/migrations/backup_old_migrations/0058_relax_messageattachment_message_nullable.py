from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0057_relax_legacy_content_constraint'),
    ]

    operations = [
        # Make message_id nullable (already done in 0053, this ensures DB is in sync)
        migrations.AlterField(
            model_name='messageattachment',
            name='message',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=models.CASCADE,
                related_name='attachments',
                to='shared.message',
            ),
        ),
    ]



