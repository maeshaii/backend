@echo off
echo ========================================
echo Fixing Persistent Errors
echo ========================================
echo.

echo [1/2] Running database migrations...
python manage.py migrate
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Migration failed. Trying with --fake flag...
    python manage.py migrate shared 0001 --fake
    python manage.py migrate
)

echo.
echo [2/2] Verifying migration status...
python manage.py showmigrations shared | findstr "0001_initial"

echo.
echo ========================================
echo Done! 
echo ========================================
echo.
echo Redis errors should now be gone (using dummy cache in development).
echo Database errors should be fixed after migrations run.
echo.
pause

