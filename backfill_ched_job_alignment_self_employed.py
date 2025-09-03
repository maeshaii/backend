import os
import django

def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
    django.setup()
    from apps.shared.models import User, TrackerResponse, Ched, InfoTechJob, InfoSystemJob, CompTechJob, Standard

    updated = 0
    for user in User.objects.filter(account_type__user=True):
        latest_response = TrackerResponse.objects.filter(user=user).order_by('-submitted_at').first()
        if not latest_response:
            continue
        answers = latest_response.answers or {}
        job_title = answers.get('26') or answers.get(26) or answers.get('Current Position') or answers.get('Position current') or answers.get('position')
        self_employed = answers.get('Self-employed') or answers.get('self employed')
        course = getattr(user, 'course', None)
        comptechjob = infotechjob = infosystemjob = None
        if job_title:
            if course and 'bit-ct' in course.lower():
                comptechjob = CompTechJob.objects.filter(job_title__icontains=job_title).first()
            if course and 'bsit' in course.lower():
                infotechjob = InfoTechJob.objects.filter(job_title__icontains=job_title).first()
            if course and 'bsis' in course.lower():
                infosystemjob = InfoSystemJob.objects.filter(job_title__icontains=job_title).first()
            if not comptechjob:
                comptechjob = CompTechJob.objects.filter(job_title__icontains=job_title).first()
            if not infotechjob:
                infotechjob = InfoTechJob.objects.filter(job_title__icontains=job_title).first()
            if not infosystemjob:
                infosystemjob = InfoSystemJob.objects.filter(job_title__icontains=job_title).first()
        # Find the latest Standard for this user
        standard = Standard.objects.filter(tracker_form__user=user).order_by('-standard_id').first()
        if not standard or not hasattr(standard, 'ched') or not standard.ched:
            continue
        ched = standard.ched
        changed = False
        # Job alignment
        if job_title and (comptechjob or infotechjob or infosystemjob):
            ched.job_alignment_count = 1
            ched.comp_tech_jobs = comptechjob
            ched.info_tech_jobs = infotechjob
            ched.info_system_jobs = infosystemjob
            changed = True
        # Self-employed
        if self_employed and str(self_employed).lower() in ['yes', 'true', '1']:
            ched.self_employed_count = 1
            changed = True
        if changed:
            ched.save()
            updated += 1
    print(f"Updated job_alignment_count and self_employed_count for {updated} alumni CHED records.")

if __name__ == '__main__':
    main() 