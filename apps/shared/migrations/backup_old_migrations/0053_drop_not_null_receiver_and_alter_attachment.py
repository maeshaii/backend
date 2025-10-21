from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0052_message_receiver_alter_messageattachment_message'),
    ]

    operations = [
        # Make receiver nullable in database and state
        migrations.AlterField(
            model_name='message',
            name='receiver',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=models.CASCADE,
                related_name='received_messages',
                to='shared.user',
            ),
        ),
        migrations.AlterField(
            model_name='messageattachment',
            name='message',
            field=models.ForeignKey(
                on_delete=models.CASCADE,
                related_name='attachments',
                to='shared.message',
                null=True,
                blank=True,
            ),
        ),
    ]


