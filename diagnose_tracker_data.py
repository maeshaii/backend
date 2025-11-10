#!/usr/bin/env python
"""
Diagnostic script to investigate why statistics show 0 values
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.shared.models import User, TrackerData, TrackerResponse, Question

print("=" * 80)
print("DIAGNOSTIC REPORT: Statistics Zero Values Issue")
print("=" * 80)

# Check alumni users
alumni_users = User.objects.filter(account_type__user=True)
print(f"\n1. Total Alumni Users: {alumni_users.count()}")

# Check TrackerData
tracker_data_records = TrackerData.objects.all()
print(f"\n2. Total TrackerData Records: {tracker_data_records.count()}")

# Check TrackerResponse
tracker_responses = TrackerResponse.objects.all()
print(f"\n3. Total TrackerResponse Records: {tracker_responses.count()}")

# Detailed TrackerData analysis
print("\n4. TrackerData Details:")
print("-" * 80)
for idx, td in enumerate(tracker_data_records[:5], 1):  # First 5 records
    print(f"\n   Record #{idx}:")
    print(f"   - User: {td.user.full_name} (ID: {td.user.user_id})")
    print(f"   - q_employment_status: {repr(td.q_employment_status)}")
    print(f"   - q_employment_type: {repr(td.q_employment_type)}")
    print(f"   - q_company_name: {repr(td.q_company_name)}")
    print(f"   - q_current_position: {repr(td.q_current_position)}")
    print(f"   - q_sector_current: {repr(td.q_sector_current)}")
    print(f"   - q_scope_current: {repr(td.q_scope_current)}")
    print(f"   - tracker_submitted_at: {td.tracker_submitted_at}")
    print(f"   - created_at: {td.created_at}")

# Detailed TrackerResponse analysis
print("\n5. TrackerResponse Details:")
print("-" * 80)
for idx, tr in enumerate(tracker_responses[:5], 1):  # First 5 records
    print(f"\n   Response #{idx}:")
    print(f"   - User: {tr.user.full_name} (ID: {tr.user.user_id})")
    print(f"   - Submitted at: {tr.submitted_at}")
    print(f"   - Number of answers: {len(tr.answers) if tr.answers else 0}")
    if tr.answers:
        print(f"   - Answer keys: {list(tr.answers.keys())[:10]}...")  # First 10 keys
        # Check for employment status question (usually question 21)
        for qid in [21, 22, 23, 24, 25]:
            if str(qid) in tr.answers:
                print(f"   - Question {qid}: {tr.answers[str(qid)]}")

# Check question mapping
print("\n6. Key Questions (for employment status):")
print("-" * 80)
key_questions = Question.objects.filter(id__in=[21, 22, 23, 24, 25, 26, 27])
for q in key_questions:
    print(f"   - Q{q.id}: {q.text}")

# Check if TrackerData has any employment status values
print("\n7. Employment Status Distribution in TrackerData:")
print("-" * 80)
statuses = TrackerData.objects.values_list('q_employment_status', flat=True)
status_counts = {}
for status in statuses:
    key = repr(status) if status is not None else 'None'
    status_counts[key] = status_counts.get(key, 0) + 1
for status, count in status_counts.items():
    print(f"   - {status}: {count}")

# Root cause analysis
print("\n" + "=" * 80)
print("ROOT CAUSE ANALYSIS:")
print("=" * 80)

if tracker_responses.count() > 0 and tracker_data_records.count() > 0:
    # Check if data is in TrackerResponse but not in TrackerData
    has_answers = any(tr.answers for tr in tracker_responses)
    has_employment_status = any(td.q_employment_status for td in tracker_data_records)
    
    if has_answers and not has_employment_status:
        print("\n❌ ISSUE FOUND: TrackerResponse has data, but TrackerData is empty!")
        print("   This means the TrackerResponse.update_user_fields() method is NOT")
        print("   properly copying data to TrackerData model.")
        print("\n   SOLUTION: Re-run update_user_fields() for all TrackerResponses")
    elif not has_answers:
        print("\n❌ ISSUE FOUND: TrackerResponse.answers field is empty!")
        print("   Alumni submitted tracker but answers were not saved.")
    else:
        print("\n✅ Data appears to be present in both models")
else:
    print("\n❌ ISSUE FOUND: No tracker data exists!")
    print("   Alumni have not submitted the tracker form yet.")

print("\n" + "=" * 80)

