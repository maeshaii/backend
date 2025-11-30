# ===================================================================
# EXISTING DATABASE MIGRATION SCRIPT (PowerShell)
# Use this script when you have an EXISTING database with data
# ===================================================================

Write-Host ""
Write-Host "===================================================================" -ForegroundColor Cyan
Write-Host "EXISTING DATABASE MIGRATION - CTU Alumni Tracker System" -ForegroundColor Cyan
Write-Host "===================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "WARNING: This script is for EXISTING databases with data!" -ForegroundColor Red
Write-Host "         For fresh/new databases, use migrate_fresh_database.ps1" -ForegroundColor Red
Write-Host ""
Write-Host "This script will:" -ForegroundColor Yellow
Write-Host "  1. Fake-apply the new 0001_initial migration (tables already exist)" -ForegroundColor Yellow
Write-Host "  2. Apply any future migrations" -ForegroundColor Yellow
Write-Host "  3. Verify migration status" -ForegroundColor Yellow
Write-Host ""

$confirm = Read-Host "Do you have an EXISTING database with data? (yes/no)"
if ($confirm -ne "yes") {
    Write-Host ""
    Write-Host "Migration cancelled. Use migrate_fresh_database.ps1 for new databases." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 0
}

# Activate virtual environment
Write-Host ""
Write-Host "[1/3] Activating virtual environment..." -ForegroundColor Green
& .\venv\Scripts\Activate.ps1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to activate virtual environment" -ForegroundColor Red
    Write-Host "Please ensure venv exists by running: python -m venv venv" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Fake-apply initial migration
Write-Host ""
Write-Host "[2/3] Fake-applying initial migration (tables already exist)..." -ForegroundColor Green
python manage.py migrate shared 0001 --fake
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to fake-apply migration!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Apply any remaining migrations
Write-Host ""
Write-Host "[3/3] Applying any new migrations..." -ForegroundColor Green
python manage.py migrate
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Migration failed!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Show migration status
Write-Host ""
Write-Host "Verifying migration status..." -ForegroundColor Green
python manage.py showmigrations shared
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: Could not show migration status" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "===================================================================" -ForegroundColor Green
Write-Host "SUCCESS! Existing database has been updated successfully." -ForegroundColor Green
Write-Host "===================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Your data has been preserved and migrations are now clean." -ForegroundColor Green
Write-Host ""
Read-Host "Press Enter to exit"






































































