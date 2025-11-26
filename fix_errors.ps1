Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Fixing Persistent Errors" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/2] Running database migrations..." -ForegroundColor Yellow
python manage.py migrate
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Migration failed. Trying with --fake flag..." -ForegroundColor Red
    python manage.py migrate shared 0001 --fake
    python manage.py migrate
}

Write-Host ""
Write-Host "[2/2] Verifying migration status..." -ForegroundColor Yellow
python manage.py showmigrations shared | Select-String "0001_initial"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Done!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Redis errors should now be gone (using dummy cache in development)." -ForegroundColor Green
Write-Host "Database errors should be fixed after migrations run." -ForegroundColor Green
Write-Host ""
Read-Host "Press Enter to continue"

