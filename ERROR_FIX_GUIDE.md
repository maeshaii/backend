# Error Fix Guide - Persistent Errors Explained

## 🔴 Two Persistent Errors

### 1. Redis Connection Error
**Error Message:**
```
ERROR: Failed to get cached user conversations: Error 10061 connecting to 127.0.0.1:6379. 
No connection could be made because the target machine actively refused it.
```

**Why It Persists:**
- Your Django app is configured to use Redis for caching
- Redis server is **not running** on your machine
- Every time the app tries to cache data, it fails and logs an error
- The app continues to work (just without caching), but the errors keep appearing

**Impact:** 
- ⚠️ **Non-critical** - App works but without caching (slower performance)
- Errors flood your logs

**Solutions:**

#### Option A: Start Redis (Recommended for Production)
```bash
# Windows (using WSL or Docker)
# Install Redis for Windows or use Docker:
docker run -d -p 6379:6379 redis:latest

# Or install Redis for Windows:
# Download from: https://github.com/microsoftarchive/redis/releases
# Then run: redis-server
```

#### Option B: Use Dummy Cache (Development Only)
Change your cache backend to use Django's dummy cache (no Redis needed):
```python
# In backend/backend/settings.py, change:
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}
```

---

### 2. Database Column Error
**Error Message:**
```
django.db.utils.ProgrammingError: column shared_messageattachment.file_key does not exist
```

**Why It Persists:**
- The `file_key` column is defined in your model (`MessageAttachment`)
- The migration file (`0001_initial.py`) includes this column
- **BUT** your database table doesn't have this column
- This means migrations haven't been run, or were run before this field was added

**Impact:**
- 🔴 **CRITICAL** - Breaks the `/api/messaging/conversations/` endpoint
- Returns 500 Internal Server Error
- Messaging features may not work

**Solution:**
Run database migrations to add the missing column:

```bash
cd backend
python manage.py migrate
```

If you get "Table already exists" errors, use:
```bash
python manage.py migrate shared 0001 --fake
python manage.py migrate
```

---

## 🚀 Quick Fix (Both Issues)

### Step 1: Fix Database (CRITICAL)
```bash
cd backend
python manage.py migrate
```

### Step 2: Fix Redis (Choose one)

**For Development (No Redis needed):**
Edit `backend/backend/settings.py`:
```python
# Replace the CACHES section with:
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}
```

**For Production (Start Redis):**
```bash
# Using Docker (easiest):
docker run -d -p 6379:6379 --name redis redis:latest

# Or install Redis for Windows
```

---

## ✅ Verification

After fixing:

1. **Check migrations:**
   ```bash
   python manage.py showmigrations shared
   ```
   Should show `[X] 0001_initial`

2. **Test messaging endpoint:**
   ```bash
   # Should return 200, not 500
   curl http://localhost:8000/api/messaging/conversations/
   ```

3. **Check logs:**
   - Redis errors should stop (if using dummy cache) or work (if Redis is running)
   - Database errors should be gone

---

## 📝 Why These Errors Keep Appearing

1. **Redis errors:** Every API call tries to cache data → Redis connection fails → Error logged → Repeats
2. **Database errors:** Every time someone accesses conversations → Django tries to query `file_key` → Column doesn't exist → 500 error → Repeats

Both are **configuration/setup issues**, not code bugs. The code is correct, but the environment isn't set up properly.

