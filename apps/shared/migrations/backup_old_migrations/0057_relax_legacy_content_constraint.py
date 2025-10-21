from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0056_alter_forum_created_at_alter_message_content'),
    ]

    operations = [
        # Make content nullable
        migrations.AlterField(
            model_name='message',
            name='content',
            field=models.TextField(null=True, blank=True),
        ),
    ]


