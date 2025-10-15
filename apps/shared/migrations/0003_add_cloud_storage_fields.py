# Generated migration for cloud storage support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0002_create_missing_recentsearch_table'),
    ]

    operations = [
        migrations.AddField(
            model_name='messageattachment',
            name='file_key',
            field=models.CharField(max_length=500, blank=True, null=True, help_text='S3 object key or local file path'),
        ),
        migrations.AddField(
            model_name='messageattachment',
            name='file_url',
            field=models.URLField(blank=True, null=True, help_text='Public URL for the file'),
        ),
        migrations.AddField(
            model_name='messageattachment',
            name='storage_type',
            field=models.CharField(
                max_length=20, 
                default='local',
                choices=[('local', 'Local Storage'), ('s3', 'AWS S3'), ('gcs', 'Google Cloud Storage')],
                help_text='Storage backend used for this file'
            ),
        ),
        migrations.AlterField(
            model_name='messageattachment',
            name='file',
            field=models.FileField(upload_to='message_attachments/%Y/%m/%d/', blank=True, null=True, help_text='Local file storage (deprecated, use file_key instead)'),
        ),
    ]
