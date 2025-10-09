@echo off
echo Resetting to commit c7d876a486ca959d0e31e20dfc867512f8039684
echo "finalized donation, working web latest"
echo.
echo This will discard all current changes and go back to that commit.
echo.
pause

echo Resetting...
git reset --hard c7d876a486ca959d0e31e20dfc867512f8039684

echo.
echo Checking status...
git status

echo.
echo Checking current commit...
git log --oneline -1

echo.
echo Reset complete!
pause
