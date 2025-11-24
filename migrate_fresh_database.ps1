# ===================================================================
# FRESH DATABASE MIGRATION SCRIPT (PowerShell)
# Use this script when setting up a NEW/EMPTY database (fresh clone)
# ===================================================================

Write-Host ""
Write-Host "===================================================================" -ForegroundColor Cyan
Write-Host "FRESH DATABASE MIGRATION - CTU Alumni Tracker System" -ForegroundColor Cyan
Write-Host "===================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "This script will:" -ForegroundColor Yellow
Write-Host "  1. Apply all migrations to create database tables from scratch" -ForegroundColor Yellow
Write-Host "  2. Create a default tracker form" -ForegroundColor Yellow
Write-Host "  3. Verify migration status" -ForegroundColor Yellow
Write-Host ""

# Activate virtual environment
Write-Host "[1/3] Activating virtual environment..." -ForegroundColor Green
& .\venv\Scripts\Activate.ps1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to activate virtual environment" -ForegroundColor Red
    Write-Host "Please ensure venv exists by running: python -m venv venv" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Run migrations
Write-Host ""
Write-Host "[2/3] Running database migrations..." -ForegroundColor Green
python manage.py migrate
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Migration failed!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Show migration status
Write-Host ""
Write-Host "[3/3] Verifying migration status..." -ForegroundColor Green
python manage.py showmigrations shared
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: Could not show migration status" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "===================================================================" -ForegroundColor Green
Write-Host "SUCCESS! Database has been set up successfully." -ForegroundColor Green
Write-Host "===================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Create account types: python create_alumni_account_type.py" -ForegroundColor Yellow
Write-Host "  2. Create super user: python create_admin_user.py" -ForegroundColor Yellow
Write-Host "  3. Create tracker questions: python create_tracker_form.py" -ForegroundColor Yellow
Write-Host ""
Read-Host "Press Enter to exit"

























































