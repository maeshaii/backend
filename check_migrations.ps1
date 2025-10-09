Write-Host "🔍 Checking migration files..." -ForegroundColor Green

# Check migration files
$migrationsDir = "apps\shared\migrations"
$migrationFiles = Get-ChildItem -Path $migrationsDir -Filter "*.py" | Where-Object { $_.Name -ne "__init__.py" } | Sort-Object Name

Write-Host "📁 Found $($migrationFiles.Count) migration files:" -ForegroundColor Yellow
$i = 1
foreach ($file in $migrationFiles) {
    Write-Host "  $($i.ToString().PadLeft(2)) $($file.Name)" -ForegroundColor White
    $i++
}

# Check for key migrations
$has0001 = $migrationFiles | Where-Object { $_.Name -like "0001_*" }
$has0093 = $migrationFiles | Where-Object { $_.Name -like "0093_*" }

Write-Host "`n✅ Migration 0001 (initial): $(if($has0001) {'Found'} else {'Missing'})" -ForegroundColor $(if($has0001) {'Green'} else {'Red'})
Write-Host "✅ Migration 0093 (latest): $(if($has0093) {'Found'} else {'Missing'})" -ForegroundColor $(if($has0093) {'Green'} else {'Red'})

if ($has0001 -and $has0093) {
    Write-Host "`n🎉 All migrations 1-93 are present!" -ForegroundColor Green
    Write-Host "`n📋 To apply these migrations to your database, run:" -ForegroundColor Yellow
    Write-Host "   python manage.py migrate shared" -ForegroundColor White
    Write-Host "`n📋 To check migration status, run:" -ForegroundColor Yellow
    Write-Host "   python manage.py showmigrations shared" -ForegroundColor White
} else {
    Write-Host "`n❌ Some migrations are missing. You may need to:" -ForegroundColor Red
    Write-Host "   1. Pull the latest changes from main4 branch" -ForegroundColor White
    Write-Host "   2. Or manually copy missing migration files" -ForegroundColor White
}

Write-Host "`n🔧 If you're still having issues, try:" -ForegroundColor Yellow
Write-Host "   python manage.py migrate shared --fake-initial" -ForegroundColor White
Write-Host "   python manage.py migrate shared" -ForegroundColor White

Write-Host "`nPress any key to continue..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
