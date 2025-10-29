# Tracker Questions Export/Import Guide

This directory contains scripts to export and import tracker questions from the database.

## Overview

When you update tracker questions in the database (via admin panel or API), you can export them to a seed file that your coworkers can import into their local databases. This ensures everyone has the exact same questions.

## Workflow

### Step 1: Export Questions (by the person who updated questions)

After making changes to tracker questions in the database, run:

```bash
cd backend
python manage.py export_tracker_questions
```

This will:
- Read all questions and categories from your database
- Generate a seed file: `tracker_questions_seed.py`
- Save it in this directory

**Note:** The generated file will be automatically committed to git, so your coworkers can pull it.

### Step 2: Import Questions (by coworkers after pulling)

When you pull the latest code and see `tracker_questions_seed.py` has been updated, run:

```bash
cd backend
python manage.py seed_tracker_questions
```

This will:
- Read the seed file
- Delete existing questions (with confirmation)
- Create the exact questions from the seed file

**To skip confirmation prompt:**
```bash
python manage.py seed_tracker_questions --noinput
```

## File Structure

- `export_tracker_questions.py` - Management command to export questions
- `seed_tracker_questions.py` - Management command to import questions
- `tracker_questions_seed.py` - **Auto-generated** seed file (DO NOT EDIT MANUALLY)

## Important Notes

1. **Never edit `tracker_questions_seed.py` manually** - it's auto-generated
2. Always commit the seed file to git after exporting
3. The export preserves:
   - Category titles, descriptions, and order
   - Question text, type, options, required flag, and order
4. Existing questions will be **deleted** when importing - make sure to commit any local changes first

## Troubleshooting

### "Seed file not found" error
- Run `python manage.py export_tracker_questions` first to generate the seed file

### "Failed to import seed file" error
- Make sure the seed file syntax is valid Python
- Check that all required models exist in your database
- Run migrations: `python manage.py migrate`

### Questions are in wrong order
- The export preserves the `order` field from the database
- If order looks wrong, check that the `order` field is set correctly in the database before exporting

