# 🤖 Scheduler Configuration Guide

## Current Setup: DUAL SCHEDULE

Both schedules are active for flexible testing and production use.

### ⏰ Schedule 1: Hourly (For Testing)
- **Trigger:** Every hour at :00 minutes
- **Purpose:** Quick testing without waiting until midnight
- **File:** `apps/shared/scheduler.py` (lines 45-53)

### 📅 Schedule 2: Daily (Production)
- **Trigger:** Every day at 12:01 AM
- **Purpose:** Normal daily processing
- **File:** `apps/shared/scheduler.py` (lines 35-43)

---

## 🔧 How to Disable Hourly Schedule (After Testing)

1. Open: `backend/apps/shared/scheduler.py`
2. Comment out lines 45-53:

```python
# Add job: Run every hour (for testing)
# scheduler.add_job(
#     process_send_dates_job,
#     trigger=CronTrigger(minute=0),
#     id='process_send_dates_hourly',
#     name='Process OJT Send Dates (Hourly Test)',
#     replace_existing=True,
#     max_instances=1
# )
```

3. Restart Django server
4. Only daily schedule will run

---

## ⚙️ How to Change Schedule Times

### Daily Schedule - Change Time
```python
# Run at 2:00 AM
trigger=CronTrigger(hour=2, minute=0)

# Run at 11:30 PM
trigger=CronTrigger(hour=23, minute=30)
```

### Hourly Schedule - Change Frequency
```python
# Every 2 hours
trigger=CronTrigger(minute=0, hour='*/2')

# Every 30 minutes
trigger=CronTrigger(minute='*/30')

# Every 15 minutes
trigger=CronTrigger(minute='*/15')
```

---

## 📊 Check Schedule Status

When server starts, check the logs:
```
🚀 APScheduler started - OJT processing schedules:
   ⏰ HOURLY: Every hour at :00 (for testing)
   📅 DAILY: Every day at 12:01 AM
📋 Scheduled jobs: 2
   - Process OJT Send Dates (Hourly Test) (Next run: ...)
   - Process OJT Send Dates (Daily) (Next run: ...)
```

---

## 🎯 Recommended Configuration

### During Development/Testing
- ✅ Keep both hourly + daily
- Quick feedback for testing

### Production Deployment
- ✅ Keep only daily schedule
- Less resource usage
- Predictable processing time

---

## 🚀 Current Status

**BOTH SCHEDULES ACTIVE**
- Hourly processing for quick testing
- Daily processing for normal operation
- Can disable hourly after testing complete

