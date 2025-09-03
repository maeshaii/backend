import os
import django
import pandas as pd
import difflib
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, Ched, Standard

def normalize_title(title):
    return str(title).strip().lower()

def smart_job_match(user_job, mapping_jobs):
    user_job_normalized = normalize_title(user_job)
    # Exact match
    if user_job_normalized in mapping_jobs:
        return True, user_job_normalized
    # Substring match
    for mapping_job in mapping_jobs:
        if user_job_normalized in mapping_job or mapping_job in user_job_normalized:
            return True, mapping_job
    # Fuzzy match (difflib)
    close_matches = difflib.get_close_matches(user_job_normalized, mapping_jobs, n=1, cutoff=0.8)
    if close_matches:
        return True, close_matches[0]
    return False, None

def main():
    print("=== BACKFILLING JOB ALIGNMENT FROM EXCEL (SMART MATCHING) ===")
    # Load mapping from Excel
    df = pd.read_excel('job_alignment_mapping.xlsx')
    print(f"Loaded {len(df)} mapping rows.")
    # Build mapping: course -> set of normalized job titles
    mapping = {}
    for _, row in df.iterrows():
        course = str(row.get('Course', '')).strip().upper()
        job_title = normalize_title(row.get('Job Title', ''))
        if not job_title or job_title == 'nan':
            continue
        mapping.setdefault(course, set()).add(job_title)
    print(f"Built mapping for {len(mapping)} courses.")
    print(f"Mapping keys (courses): {list(mapping.keys())}")
    # For each user, check alignment
    updated = 0
    for user in User.objects.filter(account_type__user=True):
        user_course = str(getattr(user, 'course', '')).strip().upper()
        user_job = normalize_title(getattr(user, 'position_current', ''))
        print(f"User: {user.f_name} {user.l_name} | course: '{user_course}' | job: '{user_job}'")
        aligned = False
        matched_job = None
        if user_course in mapping and user_job:
            aligned, matched_job = smart_job_match(user_job, mapping[user_course])
            if not aligned:
                print(f"  -> No match for '{user_job}' in mapping for course '{user_course}'.")
                print(f"     Sample jobs: {list(mapping[user_course])[:5]}")
            else:
                print(f"  -> Matched with '{matched_job}' in mapping for course '{user_course}'.")
        else:
            if user_course not in mapping:
                print(f"  -> Course '{user_course}' not in mapping keys!")
        # Find the latest Standard for this user
        standard = Standard.objects.filter(tracker_form__user=user).order_by('-standard_id').first()
        if not standard:
            print(f"  -> No Standard record found for user {user.f_name} {user.l_name} (user_id: {user.user_id})")
            continue
        ched = Ched.objects.filter(standard=standard).first()
        if not ched:
            print(f"  -> No Ched record found for user {user.f_name} {user.l_name} (user_id: {user.user_id}, standard_id: {standard.standard_id})")
            continue
        ched.job_alignment_count = 1 if aligned else 0
        ched.save()
        updated += 1
        print(f"  -> {'ALIGNED' if aligned else 'NOT ALIGNED'}")
    print(f"Updated job_alignment_count for {updated} alumni CHED records.")

if __name__ == '__main__':
    main() 