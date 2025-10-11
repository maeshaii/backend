# Generated manually for Phase 3 - Cross-program job alignment
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0092_add_trigram_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='employmenthistory',
            name='job_alignment_suggested_program',
            field=models.CharField(blank=True, help_text='Program suggested for cross-alignment', max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='employmenthistory',
            name='job_alignment_original_program',
            field=models.CharField(blank=True, help_text='Original program of the graduate', max_length=50, null=True),
        ),
    ]


