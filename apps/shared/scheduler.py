"""
Automatic Scheduler for OJT Send Dates Processing
This runs automatically when Django server starts
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def process_send_dates_job():
    """
    Job to process scheduled send dates automatically
    Runs daily to check if any OJT batches should be sent to admin
    """
    try:
        # Close old database connections to prevent stale connection errors
        # This is critical for background threads that may hold stale connections
        from django.db import close_old_connections
        close_old_connections()
        
        from django.core.management import call_command
        logger.info("🔄 Running scheduled send dates processing...")
        call_command('process_send_dates')
        logger.info("✅ Scheduled send dates processing completed")
    except Exception as e:
        logger.error(f"❌ Error in scheduled send dates processing: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Always close connections after the job completes
        # This ensures no stale connections are left open
        try:
            from django.db import close_old_connections
            close_old_connections()
        except Exception:
            pass


def start_scheduler():
    """
    Start the background scheduler
    Runs process_send_dates_job every day at 12:01 AM
    """
    import pytz
    from datetime import datetime
    
    # Use Asia/Manila timezone for Philippines
    timezone = pytz.timezone('Asia/Manila')
    scheduler = BackgroundScheduler(timezone=timezone)
    
    logger.info(f"🌍 Scheduler timezone: {timezone}")
    logger.info(f"⏰ Current time: {datetime.now(timezone)}")
    
    # Add job: Run every day at 12:01 AM (Daily production schedule)
    scheduler.add_job(
        process_send_dates_job,
        trigger=CronTrigger(hour=0, minute=1),  # 12:01 AM daily
        id='process_send_dates_daily',
        name='Process OJT Send Dates (Daily)',
        replace_existing=True,
        max_instances=1  # Only one instance at a time
    )
    
    # Add job: Run every 3 minutes (for testing)
    scheduler.add_job(
        process_send_dates_job,
        trigger=CronTrigger(minute='*/3'),  # Every 3 minutes
        id='process_send_dates_frequent',
        name='Process OJT Send Dates (Every 3 min)',
        replace_existing=True,
        max_instances=1
    )
    
    scheduler.start()
    logger.info("🚀 APScheduler started - OJT processing schedules:")
    logger.info("   ⚡ FREQUENT: Every 3 minutes (for testing)")
    logger.info("   📅 DAILY: Every day at 12:01 AM")
    
    # Print scheduled jobs
    jobs = scheduler.get_jobs()
    logger.info(f"📋 Scheduled jobs: {len(jobs)}")
    for job in jobs:
        logger.info(f"   - {job.name} (Next run: {job.next_run_time})")
    
    return scheduler

