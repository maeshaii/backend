# Generated manually for Phase 2 cleanup
# Removes legacy unused models that were never populated or used

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0090_add_statistics_indexes'),
    ]

    operations = [
        # First, remove FK from User to Import
        migrations.RemoveField(
            model_name='user',
            name='import_id',
        ),
        
        # Then remove legacy statistics hierarchy models (circular dependencies, never used)
        migrations.DeleteModel(
            name='Standard',
        ),
        migrations.DeleteModel(
            name='Aacup',
        ),
        migrations.DeleteModel(
            name='Ched',
        ),
        migrations.DeleteModel(
            name='Qpro',
        ),
        migrations.DeleteModel(
            name='Suc',
        ),
        
        # Remove old job models with circular FK relationships (replaced by Simple* models)
        migrations.DeleteModel(
            name='CompTechJob',
        ),
        migrations.DeleteModel(
            name='InfoTechJob',
        ),
        migrations.DeleteModel(
            name='InfoSystemJob',
        ),
        
        # Remove other unused models
        migrations.DeleteModel(
            name='HighPosition',
        ),
        migrations.DeleteModel(
            name='ExportedFile',
        ),
        migrations.DeleteModel(
            name='Feed',
        ),
        migrations.DeleteModel(
            name='Import',
        ),
    ]

