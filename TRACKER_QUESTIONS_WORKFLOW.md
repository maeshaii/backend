# Tracker Questions Export/Import Workflow

## Quick Start

### When you update questions (Export)

1. Make your changes to tracker questions in the database (via admin panel or API)
2. Export the questions to a seed file:
   ```bash
   cd backend
   python manage.py export_tracker_questions
   ```
3. **Commit the generated file to git:**
   ```bash
   git add apps/shared/management/commands/tracker_questions_seed.py
   git commit -m "Update tracker questions seed file"
   git push
   ```

### When you pull updates (Import)

1. Pull the latest code from nat
2. Import the questions:
   ```bash
   cd backend
   python manage.py seed_tracker_questions
   ```
3. When prompted, type `yes` to confirm (existing questions will be replaced)

## Files Created

- ✅ `backend/apps/shared/management/commands/export_tracker_questions.py` - Export command
- ✅ `backend/apps/shared/management/commands/seed_tracker_questions.py` - Import command  
- ✅ `backend/apps/shared/management/commands/README_TRACKER_QUESTIONS.md` - Detailed documentation
- ⚠️ `backend/apps/shared/management/commands/tracker_questions_seed.py` - **Auto-generated** (will be created when you run export)

## What Gets Exported

The export includes everything needed to recreate questions exactly:
- ✅ Category titles and descriptions
- ✅ Category order
- ✅ Question text
- ✅ Question type (text, radio, checkbox, file, etc.)
- ✅ Question options (for radio/checkbox/multiple choice)
- ✅ Required flag
- ✅ Question order within category

## Important Notes

1. **The seed file is auto-generated** - Never edit it manually
2. **Always commit the seed file** after exporting so teammates can use it
3. **Import will DELETE existing questions** - Make sure you've committed any local changes first
4. **Use `--overwrite` flag** when exporting to skip confirmation:
   ```bash
   python manage.py export_tracker_questions --overwrite
   ```
5. **Use `--noinput` flag** when importing to skip confirmation:
   ```bash
   python manage.py seed_tracker_questions --noinput
   ```

## Example Workflow

```bash
# Person A updates questions in database, then exports:
python manage.py export_tracker_questions --overwrite
git add apps/shared/management/commands/tracker_questions_seed.py
git commit -m "Update tracker questions"
git push

# Person B pulls and imports:
git pull
python manage.py seed_tracker_questions
# Type 'yes' when prompted
```

## Troubleshooting

**"No categories found in the database"**
- Make sure questions exist in your database
- Check that migrations have been run: `python manage.py migrate`

**"Seed file not found"**
- Make sure someone has exported questions first
- Check that the file exists: `ls apps/shared/management/commands/tracker_questions_seed.py`

**Import fails with errors**
- Make sure migrations are up to date: `python manage.py migrate`
- Check database connection
- Verify the seed file syntax is valid

