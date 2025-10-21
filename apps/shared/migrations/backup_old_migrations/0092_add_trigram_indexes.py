# Generated manually for Phase 3 - Fuzzy job matching
# Adds PostgreSQL trigram extension and indexes for similarity searches

from django.contrib.postgres.indexes import GinIndex, OpClass
from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0091_remove_legacy_models'),
    ]

    operations = [
        # Enable PostgreSQL trigram extension for fuzzy matching
        TrigramExtension(),
        
        # Add trigram indexes to job title fields for fast similarity searches
        # These enable fast LIKE queries and similarity() functions
        migrations.AddIndex(
            model_name='simplecomptechjob',
            index=GinIndex(
                OpClass('job_title', name='gin_trgm_ops'),
                name='simplecomptechjob_job_title_trgm_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='simpleinfotechjob',
            index=GinIndex(
                OpClass('job_title', name='gin_trgm_ops'),
                name='simpleinfotechjob_job_title_trgm_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='simpleinfosystemjob',
            index=GinIndex(
                OpClass('job_title', name='gin_trgm_ops'),
                name='simpleinfosystemjob_job_title_trgm_idx'
            ),
        ),
    ]



