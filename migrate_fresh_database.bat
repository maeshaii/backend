@echo off
REM ===================================================================
REM FRESH DATABASE MIGRATION SCRIPT
REM Use this script when setting up a NEW/EMPTY database (fresh clone)
REM ===================================================================

echo.
echo ===================================================================
echo FRESH DATABASE MIGRATION - CTU Alumni Tracker System
echo ===================================================================
echo.
echo This script will:
echo   1. Apply all migrations to create database tables from scratch
echo   2. Create a default tracker form
echo   3. Verify migration status
echo.

REM Activate virtual environment
echo [1/3] Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    echo Please ensure venv exists by running: python -m venv venv
    pause
    exit /b 1
)

REM Run migrations
echo.
echo [2/3] Running database migrations...
python manage.py migrate
if errorlevel 1 (
    echo ERROR: Migration failed!
    pause
    exit /b 1
)

REM Show migration status
echo.
echo [3/3] Verifying migration status...
python manage.py showmigrations shared
if errorlevel 1 (
    echo WARNING: Could not show migration status
)

echo.
echo ===================================================================
echo SUCCESS! Database has been set up successfully.
echo ===================================================================
echo.
echo Next steps:
echo   1. Create account types: python create_alumni_account_type.py
echo   2. Create super user: python create_admin_user.py
echo   3. Create tracker questions: python create_tracker_form.py
echo.
pause























































