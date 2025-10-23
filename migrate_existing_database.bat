@echo off
REM ===================================================================
REM EXISTING DATABASE MIGRATION SCRIPT
REM Use this script when you have an EXISTING database with data
REM ===================================================================

echo.
echo ===================================================================
echo EXISTING DATABASE MIGRATION - CTU Alumni Tracker System
echo ===================================================================
echo.
echo WARNING: This script is for EXISTING databases with data!
echo          For fresh/new databases, use migrate_fresh_database.bat
echo.
echo This script will:
echo   1. Fake-apply the new 0001_initial migration (tables already exist)
echo   2. Apply any future migrations
echo   3. Verify migration status
echo.

set /p CONFIRM="Do you have an EXISTING database with data? (yes/no): "
if /i not "%CONFIRM%"=="yes" (
    echo.
    echo Migration cancelled. Use migrate_fresh_database.bat for new databases.
    pause
    exit /b 0
)

REM Activate virtual environment
echo.
echo [1/3] Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    echo Please ensure venv exists by running: python -m venv venv
    pause
    exit /b 1
)

REM Fake-apply initial migration
echo.
echo [2/3] Fake-applying initial migration (tables already exist)...
python manage.py migrate shared 0001 --fake
if errorlevel 1 (
    echo ERROR: Failed to fake-apply migration!
    pause
    exit /b 1
)

REM Apply any remaining migrations
echo.
echo [3/3] Applying any new migrations...
python manage.py migrate
if errorlevel 1 (
    echo ERROR: Migration failed!
    pause
    exit /b 1
)

REM Show migration status
echo.
echo Verifying migration status...
python manage.py showmigrations shared
if errorlevel 1 (
    echo WARNING: Could not show migration status
)

echo.
echo ===================================================================
echo SUCCESS! Existing database has been updated successfully.
echo ===================================================================
echo.
echo Your data has been preserved and migrations are now clean.
echo.
pause
























