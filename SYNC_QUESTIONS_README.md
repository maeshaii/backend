# 📋 Tracker Questions Sync Guide

This guide helps team members sync tracker questions to ensure everyone has the same questions in their local database.

---

## 🚀 Quick Start (For Team Members)

### Step 1: Pull Latest Code
```bash
git pull origin main
```

### Step 2: Run Sync Script
```bash
cd backend
python sync_tracker_questions.py
```

That's it! ✅ The script will:
- Check if you have questions already
- Ask for confirmation (if needed)
- Sync all questions from the seed file
- Show you a summary of what was created

---

## 📝 Detailed Steps

### Option 1: Simple Python Script (Recommended)

1. **Navigate to backend directory:**
   ```bash
   cd backend
   ```

2. **Run the sync script:**
   ```bash
   python sync_tracker_questions.py
   ```

3. **Follow the prompts:**
   - If you have existing questions, it will ask for confirmation
   - Type `yes` to replace them with the latest questions
   - Type `no` to keep your existing questions

### Option 2: Django Management Command

1. **Navigate to backend directory:**
   ```bash
   cd backend
   ```

2. **Run the seed command:**
   ```bash
   python manage.py seed_tracker_questions
   ```

3. **Follow the prompts** (same as above)

---

## 🔄 Workflow for Question Updates

### When Questions Are Updated:

1. **The person who updates questions:**
   ```bash
   cd backend
   python manage.py export_tracker_questions --overwrite
   ```
   
2. **Commit the generated seed file:**
   ```bash
   git add apps/shared/management/commands/tracker_questions_seed.py
   git commit -m "Update tracker questions seed file"
   git push
   ```

### When You Pull Updates:

1. **Pull the latest code:**
   ```bash
   git pull origin main
   ```

2. **Sync your database:**
   ```bash
   cd backend
   python sync_tracker_questions.py
   ```

---

## ❓ Troubleshooting

### Error: "Seed file not found"

**Problem:** The seed file doesn't exist in your repository.

**Solution:**
1. Make sure you've pulled the latest code
2. Check if `apps/shared/management/commands/tracker_questions_seed.py` exists
3. If not, ask a teammate to export and commit the seed file

### Error: "Failed to import seed file"

**Problem:** The seed file has syntax errors or is corrupted.

**Solution:**
1. Make sure you've pulled the latest code
2. Check if the seed file is valid Python
3. If still having issues, ask the team lead to re-export the questions

### Error: Django Setup Failed

**Problem:** Django can't find the settings module.

**Solution:**
1. Make sure you're in the `backend` directory
2. Make sure your virtual environment is activated:
   ```bash
   # Windows
   venv\Scripts\activate
   
   # Mac/Linux
   source venv/bin/activate
   ```
3. Make sure Django is installed:
   ```bash
   pip install -r requirements.txt
   ```

### Warning: Already Have Questions

**Problem:** You already have questions in your database.

**What to do:**
- **If you made local changes:** Export your questions first:
  ```bash
  python manage.py export_tracker_questions
  ```
  Then decide if you want to keep yours or sync with the team.
  
- **If you want the latest:** Type `yes` to replace your questions with the team's version.

---

## 📊 What Gets Synced?

The sync process imports:
- ✅ All question categories (titles, descriptions, order)
- ✅ All questions (text, type, options, required flag, order)
- ✅ Question relationships (which questions belong to which category)

---

## 🎯 Summary

**For daily development:**
```bash
cd backend
python sync_tracker_questions.py
```

**For updating questions (team leads only):**
```bash
cd backend
python manage.py export_tracker_questions --overwrite
git add apps/shared/management/commands/tracker_questions_seed.py
git commit -m "Update tracker questions"
git push
```

---

## 📞 Need Help?

If you encounter any issues:
1. Check this README first
2. Ask in team chat
3. Contact the team lead

Happy syncing! 🎉

