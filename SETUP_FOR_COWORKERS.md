# 🚀 Complete Setup Guide for Coworkers

**After pulling the latest code, you need to set up two things:**
1. ✅ Tracker Questions (sync from seed file)
2. ✅ Job Autocomplete (populate from all_jobs.json)

---

## 🎯 Quick Setup (Recommended)

Run this **one command** to set up everything:

```bash
cd backend
python setup_complete_local_dev.py
```

This will:
- ✅ Sync all tracker questions
- ✅ Populate job autocomplete tables
- ✅ Show you the status of everything

---

## 📋 Manual Setup (If Needed)

If you prefer to set them up separately:

### 1. Setup Tracker Questions

```bash
cd backend
python sync_tracker_questions.py
```

### 2. Setup Job Autocomplete

```bash
cd backend
python setup_job_autocomplete.py
```

---

## ❓ Why Do I Need This?

### Tracker Questions
- Questions are stored in the database (not in git)
- Each developer has their own local database
- You need to sync questions to match the team

### Job Autocomplete (Question 26)
- Job tables are stored in the database (not in git)
- The `all_jobs.json` file is in git, but data needs to be imported
- Question 26 autocomplete won't work without populated job tables

---

## 🔍 How to Verify Everything Works

### Check Tracker Questions:
```bash
cd backend
python verify_tracker_questions_sync.py
```

### Check Job Autocomplete:
1. Start your Django server
2. Open tracker form (Question 26: Current Position)
3. Start typing a job title (e.g., "software")
4. Autocomplete suggestions should appear

---

## 🐛 Troubleshooting

### "Job autocomplete not working"
- **Symptom:** When typing in Question 26, no suggestions appear
- **Solution:** Run `python setup_job_autocomplete.py`
- **Verify:** Check that job tables have data:
  ```bash
  python manage.py shell -c "from apps.shared.models import SimpleInfoTechJob, SimpleInfoSystemJob, SimpleCompTechJob; print(f'BSIT: {SimpleInfoTechJob.objects.count()}, BSIS: {SimpleInfoSystemJob.objects.count()}, BIT-CT: {SimpleCompTechJob.objects.count()}')"
  ```

### "Tracker questions don't match"
- **Symptom:** Different questions than teammates
- **Solution:** Run `python sync_tracker_questions.py`
- **Verify:** Run `python verify_tracker_questions_sync.py`

### "all_jobs.json not found"
- **Symptom:** Script says JSON file not found
- **Solution:** 
  - Make sure you pulled latest code: `git pull origin main`
  - Verify file exists: `ls frontend/src/all_jobs.json`
  - If missing, ask teammate to commit it

### "Seed file not found"
- **Symptom:** Sync script says seed file not found
- **Solution:**
  - Make sure you pulled latest code: `git pull origin main`
  - Verify file exists: `ls apps/shared/management/commands/tracker_questions_seed.py`
  - If missing, ask teammate to export and commit it

---

## 📊 What Gets Set Up

### Tracker Questions:
- 6 Categories
- 39 Questions
- All question types, options, required flags, order

### Job Autocomplete:
- ~286 jobs from `all_jobs.json`
- Jobs categorized into:
  - BSIT (Information Technology)
  - BSIS (Information Systems)  
  - BIT-CT (Computer Technology)
- Many jobs appear in multiple categories

---

## 🎯 Summary

**Every time you pull fresh code:**
```bash
cd backend
python setup_complete_local_dev.py
```

That's it! ✅ Everything will be set up and ready to go.

---

**Questions?** Check the detailed guides:
- `SYNC_QUESTIONS_README.md` - Tracker questions details
- `TRACKER_QUESTIONS_MOBILE_COMPATIBILITY.md` - Mobile info

