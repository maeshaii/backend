# Migration Fix Guide - CTU Alumni Tracker System

## 📋 Problem Summary

The system had **117 migration files with 16 duplicate migration numbers**, causing errors when team members cloned the repository and tried to run migrations. This resulted in:
- "Already exists" errors
- Need to manually fake migrations
- Inconsistent database states across team members
- Difficult onboarding for new developers

## ✅ Solution Implemented

We've **squashed all migrations into a single clean `0001_initial.py`** that represents the current state of all models. This provides:
- ✓ Clean migration history
- ✓ No duplicate numbers
- ✓ Smooth setup for fresh clones
- ✓ Backward compatibility for existing databases

## 🗂️ What Changed

### Old Structure (REMOVED)
```
backend/apps/shared/migrations/
├── 0001_initial.py
├── 0002_...py
├── ... (117 files with duplicates)
└── 0100_...py
```

### New Structure (CURRENT)
```
backend/apps/shared/migrations/
├── __init__.py
├── 0001_initial.py  ← Single clean migration
└── backup_old_migrations/  ← Old files archived
    ├── 0001_initial.py (old)
    ├── 0002_...py
    └── ... (all 117 old migrations backed up)
```

## 🚀 Setup Instructions

### For NEW Team Members (Fresh Clone)

If you're setting up the system for the first time with a **NEW/EMPTY database**:

#### Windows (PowerShell):
```powershell
cd backend
.\migrate_fresh_database.ps1
```

#### Windows (Command Prompt):
```cmd
cd backend
migrate_fresh_database.bat
```

#### Manual Steps:
```bash
cd backend
python -m venv venv                    # Create virtual environment
venv\Scripts\activate                  # Windows
source venv/bin/activate              # Linux/Mac
pip install -r requirements.txt
python manage.py migrate              # Run migrations
python create_alumni_account_type.py  # Create account types
python create_admin_user.py           # Create admin user
python create_tracker_form.py         # Create tracker questions
```

### For EXISTING Team Members (Existing Database)

If you have an **EXISTING database with data** that needs to be updated:

#### Windows (PowerShell):
```powershell
cd backend
.\migrate_existing_database.ps1
```

#### Windows (Command Prompt):
```cmd
cd backend
migrate_existing_database.bat
```

#### Manual Steps:
```bash
cd backend
venv\Scripts\activate                          # Activate venv
python manage.py migrate shared 0001 --fake   # Fake-apply initial migration
python manage.py migrate                       # Apply any new migrations
```

**Important:** The `--fake` flag tells Django that the tables already exist, so it only records the migration without trying to create tables.

## 📊 Migration Status Verification

After running migrations, verify everything is correct:

```bash
# Check migration status
python manage.py showmigrations shared

# Expected output:
# shared
#  [X] 0001_initial
```

All future migrations will be numbered sequentially: `0002_`, `0003_`, etc.

## 🔧 Understanding the Fix

### What is Migration Squashing?

Migration squashing combines multiple migration files into one. We:
1. **Backed up** all 117 old migration files to `backup_old_migrations/`
2. **Generated** a fresh `0001_initial.py` from the current `models.py`
3. **Created** helper scripts for both scenarios (fresh vs existing)

### Why Use `--fake`?

When you have an existing database:
- Tables already exist in the database
- But Django thinks no migrations have been applied
- `--fake` tells Django: "Mark this migration as applied WITHOUT running it"
- This syncs Django's migration tracker with your actual database

## 🔄 Future Migrations

Going forward, when you make model changes:

```bash
# Create a new migration
python manage.py makemigrations shared

# Apply the migration
python manage.py migrate

# No more duplicate numbers or conflicts!
```

All new migrations will be numbered sequentially starting from `0002_`.

## 🐛 Troubleshooting

### Error: "Table already exists"
**Solution:** You need to use the **existing database** script with `--fake` flag.

### Error: "No such table"
**Solution:** You need to use the **fresh database** script without `--fake` flag.

### Error: "Migration shared.0001 already applied"
**Solution:** Your database is already migrated correctly. No action needed.

### Need to restore old migrations?
```bash
# Copy old migrations back from backup
cd backend/apps/shared/migrations/backup_old_migrations
copy *.py ..
```

## 📝 Models in 0001_initial.py

The squashed migration creates these tables:
- **User System**: AccountType, User, UserProfile, UserInitialPassword
- **Academic**: AcademicInfo
- **Employment**: EmploymentHistory
- **Job Alignment**: SimpleCompTechJob, SimpleInfoTechJob, SimpleInfoSystemJob
- **Social**: Post, PostImage, Comment, Like, Repost, Follow
- **Forum**: Forum
- **Donations**: DonationRequest, DonationImage
- **Messaging**: Conversation, Message, MessageAttachment
- **Notifications**: Notification
- **Tracker**: TrackerForm, Question, QuestionCategory, TrackerResponse, TrackerData, TrackerFileUpload
- **OJT**: OJTInfo, OJTImport
- **Search**: RecentSearch

## 📚 Additional Resources

- **Django Migrations Docs**: https://docs.djangoproject.com/en/stable/topics/migrations/
- **Squashing Migrations**: https://docs.djangoproject.com/en/stable/topics/migrations/#squashing-migrations
- **Migration Operations**: https://docs.djangoproject.com/en/stable/ref/migration-operations/

## 🤝 Team Communication

**When sharing the codebase:**
1. Inform team members about this migration fix
2. Share this guide
3. Remind them to use the appropriate script based on their situation:
   - **Fresh clone** → use `migrate_fresh_database.*`
   - **Existing database** → use `migrate_existing_database.*`

## ✨ Benefits

✅ **No more "already exists" errors**  
✅ **No more manual faking of migrations**  
✅ **Smooth onboarding for new team members**  
✅ **Clean, maintainable migration history**  
✅ **Single source of truth for database schema**  

---

## 📞 Support

If you encounter any issues:
1. Check the troubleshooting section above
2. Verify you're using the correct script for your situation
3. Check that your virtual environment is activated
4. Ensure your database credentials are correct in `settings.py`

**Last Updated:** October 11, 2025  
**Migration Version:** 0001_initial (Squashed from 0001-0100)








































