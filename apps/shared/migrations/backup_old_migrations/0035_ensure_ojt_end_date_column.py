from django.db import migrations


def ensure_ojt_end_date_column(apps, schema_editor):
    """Ensure ojt_end_date column exists (idempotent)"""
    try:
        schema_editor.execute(
            "ALTER TABLE shared_user ADD COLUMN IF NOT EXISTS ojt_end_date DATE;"
        )
    except Exception:
        pass


class Migration(migrations.Migration):
    dependencies = [
        ('shared', '0034_merge_0003_add_ojt_end_date_0033_merge_20250810_1232'),
    ]
    operations = [
        # Ensure ojt_end_date column exists (repair migration)
        migrations.RunPython(ensure_ojt_end_date_column, migrations.RunPython.noop),
    ]
