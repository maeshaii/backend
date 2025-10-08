# Generated manually for Phase 3 - Fuzzy job matching
# Adds PostgreSQL trigram extension and indexes for similarity searches

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
        migrations.RunSQL(
            sql="""
                CREATE INDEX IF NOT EXISTS simplecomptechjob_job_title_trgm_idx 
                ON shared_simplecomptechjob 
                USING gin (job_title gin_trgm_ops);
            """,
            reverse_sql="DROP INDEX IF EXISTS simplecomptechjob_job_title_trgm_idx;"
        ),
        migrations.RunSQL(
            sql="""
                CREATE INDEX IF NOT EXISTS simpleinfotechjob_job_title_trgm_idx 
                ON shared_simpleinfotechjob 
                USING gin (job_title gin_trgm_ops);
            """,
            reverse_sql="DROP INDEX IF EXISTS simpleinfotechjob_job_title_trgm_idx;"
        ),
        migrations.RunSQL(
            sql="""
                CREATE INDEX IF NOT EXISTS simpleinfosystemjob_job_title_trgm_idx 
                ON shared_simpleinfosystemjob 
                USING gin (job_title gin_trgm_ops);
            """,
            reverse_sql="DROP INDEX IF EXISTS simpleinfosystemjob_job_title_trgm_idx;"
        ),
    ]

