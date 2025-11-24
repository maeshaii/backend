# Why Migration 0139 Kept Failing - Root Cause Analysis

## 🔍 The Problem

Migration `0139_remove_ojtinfo_email` kept failing with:
```
django.db.utils.ProgrammingError: column "email" of relation "shared_ojtinfo" does not exist
```

Every time you ran `python manage.py migrate`, it would fail at migration 0139.

---

## 📚 The Migration History (The Messy Timeline)

Here's what happened to the `email` field in `OJTInfo`:

### Timeline of Changes:

1. **Migration 0127** (Nov 16)
   - ✅ **Added** `email` field to `OJTInfo`

2. **Migration 0131** (Nov 18)
   - ✅ **Removed** `email` field (moved to UserProfile)
   - Used **safe** `RunSQL` with `DROP COLUMN IF EXISTS`
   - This worked fine ✅

3. **Migration 0132** (Nov 18)
   - ❌ **Tried to remove** `email` field again
   - Used **unsafe** `RemoveField` (no IF EXISTS check)
   - Would fail if 0131 already removed it

4. **Migration 0133** (Nov 18)
   - ✅ **Tried to remove** `email` field again
   - Used **safe** `RunSQL` with `DROP COLUMN IF EXISTS`
   - This worked fine ✅

5. **Migration 0134** (Nov 18) ⚠️ **CONFLICT!**
   - ❌ **ADDED** `email` field back to `OJTInfo`
   - This contradicts migrations 0131, 0132, 0133!

6. **Migration 0138** (Nov 21)
   - ✅ **Removed** `email` field again
   - Used **safe** `RunSQL` with `DROP COLUMN IF EXISTS`
   - This worked fine ✅

7. **Migration 0139** (Nov 24) ❌ **THE PROBLEM**
   - ❌ **Tried to remove** `email` field
   - Used **unsafe** `RemoveField` (no IF EXISTS check)
   - **FAILED** because 0138 already removed it

---

## 🎯 Root Causes

### 1. **Git Merge Conflicts** 🔀

Look at your migration files - you have **multiple merge migrations**:
- `0131_merge_20251118_1843.py`
- `0131_merge_20251118_2226.py` (duplicate 0131!)
- `0133_merge_20251118_2239.py`
- `0136_merge_20251121_2020.py`
- `0137_merge_20251121_2347.py`

**What happened:**
- Multiple developers worked on different branches
- Both branches modified the `OJTInfo` model
- When branches were merged, Git created merge migrations
- This created **conflicting migrations** that tried to do the same thing multiple times

### 2. **Django Auto-Generated Migration** 🤖

Migration 0139 was **auto-generated** by Django when you ran:
```bash
python manage.py makemigrations
```

**Why Django created it:**
- Django compared your `models.py` (which has NO `email` field) with the database
- It saw migration 0134 added the field back
- It detected the field shouldn't exist in the model
- So it auto-generated a migration to remove it

**The problem:**
- Django used `RemoveField` (unsafe - no IF EXISTS check)
- But migration 0138 already removed the column using safe SQL
- So 0139 tried to remove a non-existent column → **ERROR**

### 3. **Inconsistent Migration Operations** ⚠️

Some migrations used **safe** operations:
```python
migrations.RunSQL(
    sql="ALTER TABLE shared_ojtinfo DROP COLUMN IF EXISTS email;",
    # ✅ Safe - won't fail if column doesn't exist
)
```

Others used **unsafe** operations:
```python
migrations.RemoveField(
    model_name='ojtinfo',
    name='email',
    # ❌ Unsafe - will fail if field doesn't exist
)
```

### 4. **Migration State Mismatch** 🔄

**The cycle:**
1. Migration 0138 runs successfully (removes column with IF EXISTS)
2. Migration 0139 is in the migration history (waiting to run)
3. You run `python manage.py migrate`
4. Django tries to run 0139
5. 0139 tries to remove column that doesn't exist
6. **ERROR** - Migration fails
7. Migration 0139 is marked as "not applied" in database
8. Next time you run migrate → **same error repeats**

---

## 🔧 Why It Kept Happening

### The Vicious Cycle:

```
┌─────────────────────────────────────────┐
│ 1. Run: python manage.py migrate       │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ 2. Django checks migration history      │
│    - Sees 0139 is not applied          │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ 3. Tries to run migration 0139         │
│    - Uses RemoveField (unsafe)         │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ 4. RemoveField tries to drop column    │
│    - Column doesn't exist (removed by  │
│      0138)                              │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ 5. ERROR: Column does not exist        │
│    - Migration fails                   │
│    - 0139 remains "not applied"        │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ 6. Next time you run migrate...        │
│    → Back to step 1 (infinite loop!)   │
└─────────────────────────────────────────┘
```

---

## ✅ The Fix

I changed migration 0139 from:
```python
# ❌ UNSAFE - Fails if column doesn't exist
migrations.RemoveField(
    model_name='ojtinfo',
    name='email',
)
```

To:
```python
# ✅ SAFE - Won't fail if column doesn't exist
migrations.RunSQL(
    sql="ALTER TABLE shared_ojtinfo DROP COLUMN IF EXISTS email;",
    reverse_sql="ALTER TABLE shared_ojtinfo ADD COLUMN IF NOT EXISTS email varchar(254);",
)
```

Now migration 0139 can run successfully even if the column was already removed by 0138.

---

## 🛡️ How to Prevent This in the Future

### 1. **Always Use Safe Operations for Removals**

When removing fields/columns that might have been removed already:
```python
# ✅ GOOD - Safe
migrations.RunSQL(
    sql="ALTER TABLE table_name DROP COLUMN IF EXISTS column_name;",
    reverse_sql="ALTER TABLE table_name ADD COLUMN IF NOT EXISTS column_name type;",
)

# ❌ BAD - Unsafe
migrations.RemoveField(
    model_name='model_name',
    name='field_name',
)
```

### 2. **Coordinate Migrations in Team**

- **Communicate** before making model changes
- **Pull latest** before creating migrations
- **Review** migration files before committing
- **Test** migrations on a copy of production data

### 3. **Squash Migrations Periodically**

If you have many conflicting migrations:
```bash
python manage.py squashmigrations shared 0130 0140
```

This combines multiple migrations into one, reducing conflicts.

### 4. **Check Migration State Before Creating New Ones**

```bash
# Check what migrations are applied
python manage.py showmigrations shared

# Check for model changes
python manage.py makemigrations --dry-run
```

---

## 📊 Summary

| Issue | Cause | Solution |
|-------|-------|----------|
| Migration 0139 failing | Unsafe `RemoveField` on non-existent column | Changed to safe `RunSQL` with `IF EXISTS` |
| Multiple conflicting migrations | Git merge conflicts | Better team coordination, squash migrations |
| Auto-generated unsafe migration | Django default behavior | Manually edit auto-generated migrations when needed |
| Infinite error loop | Migration marked as "not applied" but can't run | Fixed the migration operation |

---

## 🎓 Key Takeaway

**The error kept happening because:**
1. Migration 0139 was in your migration history (waiting to run)
2. It used an unsafe operation (`RemoveField`) that fails if the column doesn't exist
3. The column was already removed by migration 0138
4. Every time you ran `migrate`, Django tried to run 0139 → failed → stayed in history → repeated

**The fix:**
- Changed 0139 to use a safe operation that won't fail if the column doesn't exist
- Now it runs successfully and is marked as "applied"
- The error won't happen again ✅

