@echo off
REM Batch script to process send dates automatically
REM This runs the Django management command to send completed OJT students to admin

cd /d "E:\wny latest\backend"
python manage.py process_send_dates >> "E:\wny latest\backend\process_send_dates.log" 2>&1

REM Append timestamp to log
echo Processed on %date% at %time% >> "E:\wny latest\backend\process_send_dates.log"
echo ---------------------------------------- >> "E:\wny latest\backend\process_send_dates.log"

