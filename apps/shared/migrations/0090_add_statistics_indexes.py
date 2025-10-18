# Generated manually for Phase 2 optimizations
# Adds indexes for frequently queried fields in statistics

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shared', '0089_remove_course_field'),
    ]

    operations = [
        # Add index for TrackerData.q_sector_current (used in SUC statistics)
        migrations.AddIndex(
            model_name='trackerdata',
            index=models.Index(fields=['q_sector_current'], name='shared_trac_q_secto_idx'),
        ),
        
        # Add index for TrackerData.q_scope_current (used in SUC statistics)
        migrations.AddIndex(
            model_name='trackerdata',
            index=models.Index(fields=['q_scope_current'], name='shared_trac_q_scope_idx'),
        ),
        
        # Add index for EmploymentHistory.absorbed (used in AACUP statistics)
        migrations.AddIndex(
            model_name='employmenthistory',
            index=models.Index(fields=['absorbed'], name='shared_empl_absorbe_idx'),
        ),
        
        # Add index for OJTInfo.ojt_start_date (used in OJT queries)
        migrations.AddIndex(
            model_name='ojtinfo',
            index=models.Index(fields=['ojt_start_date'], name='shared_ojti_ojt_sta_idx'),
        ),
    ]



