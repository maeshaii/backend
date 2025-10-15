# Statistics Display Fix - Why Imported Alumni Don't Show in Dashboard

## Problem Analysis

### Issue
After successfully importing alumni data, the imported alumni don't appear in:
1. **Dashboard bar charts** (employment statistics)
2. **Generate Statistics** modal
3. **Statistics overview**

### Root Cause
The imported alumni were missing **`TrackerData`** records, which are required for employment statistics.

## Technical Details

### What Gets Created During Import
✅ **User** record with `account_type__user=True`
✅ **UserProfile** record with personal information  
✅ **AcademicInfo** record with `year_graduated` and `program`
❌ **TrackerData** record (was missing - this is the issue!)

### What Statistics Views Require
The statistics views (`backend/apps/alumni_stats/views.py`) query:
```python
# Employment statistics require TrackerData
employment_stats = TrackerData.objects.filter(user__in=alumni_qs).aggregate(
    employed=Count('id', filter=Q(q_employment_status__iexact='yes')),
    unemployed=Count('id', filter=Q(q_employment_status__iexact='no'))
)
```

**Without `TrackerData` records, alumni don't appear in employment statistics!**

### Frontend Calls
1. **`fetchAlumniStatistics()`** → `alumni/statistics/` → Returns year counts (works)
2. **`fetchAlumniEmploymentStats()`** → `statistics/alumni/` → Returns employment stats (doesn't work without TrackerData)

## Solution Implemented

### Modified Import Function
Updated `backend/apps/api/views.py` - `import_alumni_view` function:

**BEFORE:**
```python
# Note: Don't create TrackerData records automatically
# Alumni should remain "untracked" until they fill out tracker forms
```

**AFTER:**
```python
# Create TrackerData record with "pending" status so alumni show up in statistics
TrackerData.objects.create(
    user=user,
    q_employment_status='pending',
    tracker_submitted_at=timezone.now()
)
```

### Result
Now when alumni are imported, they get:
- ✅ **User** record
- ✅ **UserProfile** record  
- ✅ **AcademicInfo** record
- ✅ **TrackerData** record with `q_employment_status='pending'`

## Expected Behavior

### Dashboard Statistics
Imported alumni will now appear in the **"Pending"** category of the bar chart, showing:
- **Employed**: Alumni with `q_employment_status='yes'`
- **Unemployed**: Alumni with `q_employment_status='no'`  
- **Pending**: Alumni with `q_employment_status='pending'` (imported alumni)
- **Absorb**: Alumni with employment absorption status

### Year Statistics
Imported alumni will appear in the year-based statistics based on their `year_graduated` from `AcademicInfo`.

### Generate Statistics
The "Generate Statistics" functionality will now include imported alumni in calculations.

## For Existing Imported Alumni

If you have alumni that were imported before this fix, they won't show up in statistics until they either:

1. **Fill out a tracker form** (creates TrackerData automatically)
2. **Run a fix script** to create TrackerData records for existing alumni

## Files Modified

- `backend/apps/api/views.py` - Added TrackerData creation during import (lines 508-513)

## Testing

1. **Import new alumni** - should appear in "Pending" category
2. **Check dashboard** - bar chart should show pending count
3. **Check year statistics** - should show alumni by graduation year
4. **Generate statistics** - should include imported alumni

## Status Categories Explained

- **Pending**: Imported alumni waiting to fill out tracker forms
- **Employed**: Alumni who filled tracker and marked as employed
- **Unemployed**: Alumni who filled tracker and marked as unemployed  
- **Absorb**: Alumni with employment absorption tracking

The imported alumni start as "Pending" and move to other categories when they complete tracker forms.

