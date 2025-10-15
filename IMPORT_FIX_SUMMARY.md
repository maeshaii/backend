# Import Alumni Fix - Summary

## Problem
The import alumni functionality was requiring `batch_year` and `program` as mandatory form parameters, even when importing an exported Excel file that **already contains** `Year_Graduated` and `Program` columns.

This caused the error: **"Batch year and course are required"**

## Root Cause
The backend `import_alumni_view` function was designed to:
1. Accept Excel files with minimal columns (CTU_ID, First_Name, Last_Name, Gender)
2. Require `batch_year` and `program` as form parameters to apply to ALL rows

However, when exporting alumni data via `export-alumni/` endpoint, the Excel includes:
- `Year_Graduated` column (per alumni)
- `Program` column (per alumni)
- `Section` column (per alumni)

## Solution Implemented

### Modified: `backend/apps/api/views.py` - `import_alumni_view` function

The import function now intelligently handles **both scenarios**:

### Scenario 1: Exported Excel (with Year_Graduated and Program columns)
- ✅ Reads `Year_Graduated` from each row
- ✅ Reads `Program` from each row
- ✅ Reads `Section` from each row (if present)
- ✅ Form parameters are **optional**
- ✅ Validates per-row to ensure each alumni has year and program

### Scenario 2: Minimal Excel (without Year_Graduated and Program columns)
- ✅ Requires `batch_year` and `program` form parameters
- ✅ Applies these values to ALL rows (backward compatible)

## Key Changes

### 1. Optional Form Parameters (Lines 311-328)
```python
batch_year_param = request.POST.get('batch_year', '')
course_param = request.POST.get('course', '') or request.POST.get('program', '')

# Check if Excel has Year_Graduated and Program columns (exported format)
has_year_column = 'Year_Graduated' in df.columns
has_program_column = 'Program' in df.columns

# If Excel doesn't have these columns, require form parameters
if not has_year_column and not has_program_column:
    if not batch_year_param or not course_param:
        return JsonResponse({'success': False, 'message': 'Batch year and course are required'}, status=400)
```

### 2. Per-Row Data Extraction (Lines 399-416)
```python
# Determine batch_year and course: use row values if available, else form parameters
if has_year_column and pd.notna(row.get('Year_Graduated')):
    batch_year = str(int(row['Year_Graduated'])) if isinstance(row['Year_Graduated'], (int, float)) else str(row['Year_Graduated']).strip()
else:
    batch_year = batch_year_param

if has_program_column:
    if 'Program' in df.columns and pd.notna(row.get('Program')):
        course = str(row['Program']).strip()
    # Legacy support for Course column (will be removed)
    elif 'Course' in df.columns and pd.notna(row.get('Course')):
        course = str(row['Course']).strip()
    else:
        course = course_param
else:
    course = course_param

# Get section if available in Excel
section = str(row.get('Section', '')).strip() if 'Section' in df.columns and pd.notna(row.get('Section')) else ''
```

### 3. Per-Row Validation (Lines 423-429)
```python
# Validate batch_year and course for this row
if not batch_year:
    errors.append(f"Row {index + 2}: Missing Year_Graduated/Batch Year")
    continue
if not course:
    errors.append(f"Row {index + 2}: Missing Program")
    continue
```

## Benefits
1. ✅ **Export-Import Cycle Works**: Can export alumni data and re-import without errors
2. ✅ **Backward Compatible**: Original import with form parameters still works
3. ✅ **Better Error Messages**: Shows which row is missing data
4. ✅ **Per-Row Flexibility**: Each alumni can have different year/program
5. ✅ **Section Support**: Automatically reads section column if present

## Testing
To test the fix:

1. **Export alumni data** from ViewStats page (select batch year and export)
2. **Import the exported file** - should work without requiring batch_year/program selection
3. **Import minimal Excel** - should still require batch_year/program form fields

## Files Modified
- `backend/apps/api/views.py` - Modified `import_alumni_view` function (lines 307-429)

## No Frontend Changes Required
The frontend remains unchanged - the ViewStats import modal works as-is because:
- It sends batch_year and program if selected (optional now)
- Backend intelligently uses Excel columns if available


