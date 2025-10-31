# Clear OJT and Alumni Data Script

This script allows you to delete OJT and/or Alumni data from the database. Useful for testing, re-importing, or cleaning up data.

## Location
`backend/apps/shared/management/commands/clear_ojt_alumni_data.py`

## Usage

### ⚠️ Important: Always use `--confirm` flag
The script requires `--confirm` flag to prevent accidental deletions.

### Command Options

#### 1. Clear ALL OJT and Alumni Data
```bash
cd backend
python manage.py clear_ojt_alumni_data --confirm
```
This deletes:
- All OJT users and their data
- All Alumni users and their data
- Related records: OJTInfo, OJTCompanyProfile, AcademicInfo, UserProfile, EmploymentHistory, TrackerData, UserPoints, RewardHistory, UserInitialPassword

#### 2. Clear ONLY OJT Data (Keep Alumni)
```bash
python manage.py clear_ojt_alumni_data --confirm --ojt-only
```
This deletes:
- OJT users (account_type.ojt = True)
- OJTInfo records
- OJTCompanyProfile records
- OJTImport records
- SendDate records
- Related user data: AcademicInfo, UserProfile, etc.

#### 3. Clear ONLY Alumni Data (Keep OJT)
```bash
python manage.py clear_ojt_alumni_data --confirm --alumni-only
```
This deletes:
- Alumni users (account_type.user = True, excluding admin/coordinator/peso)
- AcademicInfo records
- UserProfile records
- TrackerData records
- EmploymentHistory records
- UserPoints records
- RewardHistory records
- UserInitialPassword records

## What Gets Deleted?

### OJT Data (`--ojt-only`):
- ✅ OJT users (complete deletion)
- ✅ OJTInfo (student OJT status, start/end dates)
- ✅ OJTCompanyProfile (company assignments)
- ✅ OJTImport (import history records)
- ✅ SendDate (batch submission deadlines)
- ✅ AcademicInfo (year graduated, program, section)
- ✅ UserProfile (personal info: birthdate, phone, address)
- ✅ UserInitialPassword (generated passwords)
- ✅ TrackerData, UserPoints, RewardHistory

### Alumni Data (`--alumni-only`):
- ✅ Alumni users (account_type.user = True)
- ✅ AcademicInfo (graduation year, program)
- ✅ UserProfile (personal information)
- ✅ TrackerData (tracker form responses)
- ✅ EmploymentHistory (current job, company)
- ✅ UserPoints (forum points)
- ✅ RewardHistory (point transaction history)
- ✅ UserInitialPassword (login credentials)

### Protected Users:
- ❌ Admin accounts (excluded)
- ❌ Coordinator accounts (excluded)
- ❌ PESO officer accounts (excluded)
- ❌ Users with system usernames: 'admin', 'coordinator', 'peso'

## Special Handling

### Forum Posts Protection
Users who have created forum posts/comments cannot be fully deleted due to database constraints.

**When this happens:**
- For OJT users: Account is kept but OJT status is cleared (`account_type.ojt = False`)
- For Alumni users: Account is kept but all related data is cleared
- A warning message will be displayed for each affected user

## Example Workflows

### Scenario 1: Re-import OJT Students
```bash
# Clear OJT data only
python manage.py clear_ojt_alumni_data --confirm --ojt-only

# Now you can re-import fresh OJT data via the coordinator dashboard
```

### Scenario 2: Reset Entire System
```bash
# Clear everything
python manage.py clear_ojt_alumni_data --confirm

# Now you can start fresh with both OJT and alumni imports
```

### Scenario 3: Clear Alumni for Fresh Tracker Data
```bash
# Clear alumni only
python manage.py clear_ojt_alumni_data --confirm --alumni-only

# Alumni tracker data is now cleared, ready for new responses
```

## Output Example

```
🗑️  Deleting OJT Data...
  Found 5 OJT users to delete
  ✓ Deleted 5 OJT Info records
  ✓ Deleted 5 OJT Company Profile records
  ✓ Deleted 2 OJT Import records
  ✓ Deleted 1 Send Date records
  ✓ Deleted 5 OJT users completely

🗑️  Deleting Alumni Data...
  ✓ Deleted 9 Alumni users
  ✓ Deleted 9 Academic Info records
  ✓ Deleted 9 User Profile records
  ✓ Deleted 3 Tracker Data records
  ✓ Deleted 5 Employment History records
  ✓ Deleted 2 User Points records
  ✓ Deleted 1 Reward History records
  ✓ Deleted 9 Initial Password records

✅ Data deletion completed successfully!
   All OJT and Alumni data has been cleared. You can now re-import fresh data.
```

## Safety Features

1. **Confirmation Required**: Script won't run without `--confirm` flag
2. **Protected Accounts**: Admin, coordinator, and PESO accounts are excluded
3. **Graceful Handling**: Forum relationship conflicts are handled gracefully
4. **Detailed Logging**: Shows exactly what was deleted
5. **Error Reporting**: Reports any issues with individual user deletions

## Troubleshooting

### "Error processing user..."
- Usually due to foreign key constraints (forum posts/comments)
- User data is cleared, but account may be kept
- This is normal behavior and safe

### "No users found"
- Database is already clean
- Check account types if users exist but aren't being detected

## Notes

- This operation cannot be undone
- Always backup your database before running in production
- For development/testing environments only (unless you're sure!)
- OJT import records are also deleted to hide batch cards in coordinator dashboard


