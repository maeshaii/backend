This directory contains one-off administrative scripts for data maintenance and backfills.

Guidelines:
- Scripts should be idempotent where possible.
- Use Django ORM, not raw SQL, unless necessary for performance.
- Document required environment variables and usage at the top of each script.
- Run scripts via: `python manage.py shell < scripts/your_script.py` or build a custom management command under `apps/shared/management/commands/` for reusable tasks.

Moved from project root to keep `backend-wny/` tidy.

## Scripts to Move Here
- delete_2023_alumni.py
- check_user_data.py
- update_alumni_status.py
- delete_all_alumni.py
- temp_user_creation.py
- temp_create_user.py
- fix_user_model.py
- check_superuser.py
- update_all_job_alignments.py
- migrate_tracker_data.py
- check_and_create_categories.py
- check_users.py