# Shared App Migrations

## Current Status
✅ **Clean Migration History**  
All migrations have been squashed into a single `0001_initial.py` for a fresh start.

## Migration Files

### Active:
- `0001_initial.py` - Complete database schema (squashed from 117 old migrations)

### Archived:
- `backup_old_migrations/` - Original 117 migration files (backed up, not deleted)

## Setup Instructions

### Fresh Database (New Clone):
```bash
cd backend
python manage.py migrate
```

### Existing Database (With Data):
```bash
cd backend
python manage.py migrate shared 0001 --fake
python manage.py migrate
```

Or use the helper scripts in `backend/` folder:
- `migrate_fresh_database.bat` / `.ps1`
- `migrate_existing_database.bat` / `.ps1`

## Documentation
📖 See `backend/MIGRATION_GUIDE.md` for complete instructions

## What Happened?

### Before (Problem):
- 117 migration files
- 16 duplicate migration numbers (0005, 0007, 0010, 0011, 0012, 0016, 0023, 0028, 0029, 0031, 0033, 0036, 0041, 0044, 0045, 0048)
- "Table already exists" errors on fresh clone
- Required manual intervention

### After (Solution):
- 1 clean migration file
- No duplicates
- Smooth setup for new team members
- All old migrations safely backed up

## Future Migrations

When you make model changes:
```bash
python manage.py makemigrations shared
python manage.py migrate
```

New migrations will be numbered sequentially: `0002_`, `0003_`, etc.

## Need Help?
- Read: `backend/MIGRATION_GUIDE.md`
- Test: `python backend/test_migration.py`
- Troubleshoot: Check the troubleshooting section in the guide

---
**Last Updated:** October 11, 2025  
**Migration Version:** 0001 (Squashed)  
**Status:** ✅ Tested and Working
























