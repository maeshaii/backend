# 📱 Tracker Questions - Mobile Compatibility

**Date:** 2025-10-30  
**Status:** ✅ Compatible - Mobile automatically syncs via API

---

## 🔍 How Mobile Fetches Questions

The mobile app **does NOT have a local database** for tracker questions. Instead, it fetches questions **dynamically from the backend API** when the form loads.

### Mobile Architecture:
```
Mobile App → API Call → Backend Database
   ↓
GET /api/tracker/questions/
   ↓
Fetches questions in real-time
```

### Code Reference:
- **Mobile API Service:** `mobile/services/api.ts`
  - Line 500-501: `getTrackerQuestions()` calls `/api/tracker/questions/`

- **Mobile Form Component:** `mobile/app/forms/forms.tsx`
  - Line 147: `const qs = await getTrackerQuestions();`
  - Questions are fetched dynamically when form opens

---

## ✅ Is the Sync Script Needed for Mobile?

### **Short Answer: NO** ❌

Mobile developers **do NOT need to run the sync script** because:
1. Mobile doesn't have a local database for questions
2. Mobile fetches questions via API from the backend
3. When backend database is synced, mobile automatically gets updated questions

### **What Mobile Developers Need:**
✅ **Backend must be synced** (by backend developers)  
✅ **Backend server must be running and accessible**  
✅ **Mobile app must have correct API_BASE_URL configured**

---

## 🔄 Complete Sync Workflow

### For Backend Developers:
1. **Update questions** in database (admin panel or API)
2. **Export to seed file:**
   ```bash
   cd backend
   python manage.py export_tracker_questions --overwrite
   ```
3. **Commit seed file:**
   ```bash
   git add apps/shared/management/commands/tracker_questions_seed.py
   git commit -m "Update tracker questions"
   git push
   ```

### For Frontend Developers (Web):
1. **Pull latest code**
2. **Sync local database:**
   ```bash
   cd backend
   python sync_tracker_questions.py
   ```

### For Mobile Developers:
✅ **Nothing to do!** 

Mobile automatically fetches the latest questions from the backend API. Just make sure:
- Backend is running
- Mobile has correct API_BASE_URL
- Questions have been synced in the backend

---

## 📊 Verification for Mobile

### How to Verify Mobile is Getting Correct Questions:

1. **Check Backend is Synced:**
   ```bash
   cd backend
   python verify_tracker_questions_sync.py
   ```
   Should show: ✅ Database matches seed file

2. **Test API Endpoint:**
   ```bash
   # From backend directory
   curl http://localhost:8000/api/tracker/questions/ -H "Authorization: Bearer YOUR_TOKEN"
   ```
   Should return JSON with all 39 questions in 6 categories

3. **Check Mobile Logs:**
   - Open mobile app
   - Navigate to tracker form
   - Check console logs for API call to `/api/tracker/questions/`
   - Verify questions are loaded

---

## 🔗 API Endpoint Details

### Endpoint Used by Mobile:
```
GET /api/tracker/questions/
```

### Backend Implementation:
- **File:** `backend/apps/tracker/views.py`
- **Function:** `tracker_questions_view()` (line 20)
- **Returns:** JSON with categories and questions

### Response Format:
```json
{
  "success": true,
  "categories": [
    {
      "id": 1,
      "title": "INTRODUCTION",
      "description": "...",
      "questions": [
        {
          "id": 1,
          "text": "Year Graduated",
          "type": "text",
          "options": [],
          "required": true,
          "order": 0
        },
        ...
      ]
    },
    ...
  ]
}
```

---

## 🎯 Key Differences: Web vs Mobile

| Aspect | Web Frontend | Mobile App |
|--------|--------------|------------|
| **Question Storage** | Fetched from backend API | Fetched from backend API |
| **Local Database** | ✅ Yes (for development) | ❌ No |
| **Sync Script Needed** | ✅ Yes (for local DB) | ❌ No |
| **Real-time Updates** | ✅ Yes (on page load) | ✅ Yes (on form load) |
| **Backend Dependency** | ✅ Required | ✅ Required |

---

## 📝 Summary

### ✅ Mobile Compatibility Status:
- **Compatible:** ✅ Yes
- **Sync Script Needed:** ❌ No
- **Update Mechanism:** ✅ Automatic via API
- **Action Required:** None (as long as backend is synced)

### 🎯 What This Means:

1. **Backend developers** run the sync script to ensure everyone's backend DB matches

2. **Frontend developers (web)** run the sync script to sync their local database

3. **Mobile developers** don't need to do anything - questions are fetched automatically

4. **Everyone** benefits when backend database is synced because:
   - ✅ Web frontend fetches from backend API
   - ✅ Mobile app fetches from backend API
   - ✅ Both are in sync automatically

---

## 🚀 Testing Mobile with Updated Questions

To test mobile with updated questions:

1. **Backend developer syncs questions:**
   ```bash
   python sync_tracker_questions.py
   ```

2. **Mobile developer:**
   - Restart backend server (if needed)
   - Reload mobile app
   - Open tracker form
   - Verify questions match what's in backend

3. **Verify in mobile console:**
   - Check API response logs
   - Verify questions array matches backend

---

**Bottom Line:** Mobile is **fully compatible** and automatically gets updated questions when the backend is synced. No additional work needed! ✅

