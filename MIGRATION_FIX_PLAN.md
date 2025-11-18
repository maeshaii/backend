# Migration Fix Plan

## Problem Summary
- **Total migrations**: 117
- **Duplicate migration numbers**: 16 (0005, 0007, 0010, 0011, 0012, 0016, 0023, 0028, 0029, 0031, 0033, 0036, 0041, 0044, 0045, 0048)
- **Issue**: When someone clones the system fresh, Django can't determine which migration to apply when there are multiple with the same number

## Solution
We'll create a clean migration history by:
1. Backing up old migrations
2. Creating a single squashed migration from current models
3. Providing scripts for both fresh installs and existing databases

## Implementation Steps

### For Fresh Installs (New Clones)
- Single clean `0001_initial.py` migration
- No conflicts, smooth migration

### For Existing Databases
- Fake-apply the initial migration (since tables already exist)
- Continue with new migrations going forward

## Files to Create
1. `backup_migrations/` - Archive of old migrations
2. `0001_squashed_initial.py` - New clean initial migration
3. `migrate_fresh.bat` - Script for fresh databases
4. `migrate_existing.bat` - Script for existing databases with data
5. `MIGRATION_GUIDE.md` - Team documentation




















































