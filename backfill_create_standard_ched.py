import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, TrackerForm, Standard, Ched, Qpro, Suc, Aacup, CompTechJob, InfoTechJob, InfoSystemJob

def create_placeholder_jobs():
    """Create placeholder job records if they don't exist"""
    if not CompTechJob.objects.exists():
        comp_tech = CompTechJob.objects.create(
            comp_tech_jobs_id=1,
            suc_id=1,  # Will be updated later
            info_system_jobs_id=1,  # Will be updated later
            info_tech_jobs_id=1,  # Will be updated later
            job_title="Placeholder"
        )
        print("Created placeholder CompTechJob")
    else:
        comp_tech = CompTechJob.objects.first()
    
    if not InfoTechJob.objects.exists():
        info_tech = InfoTechJob.objects.create(
            info_tech_jobs_id=1,
            suc_id=1,  # Will be updated later
            info_systems_jobs_id=1,  # Will be updated later
            comp_tech_jobs_id=comp_tech.comp_tech_jobs_id,
            job_title="Placeholder"
        )
        print("Created placeholder InfoTechJob")
    else:
        info_tech = InfoTechJob.objects.first()
    
    if not InfoSystemJob.objects.exists():
        info_system = InfoSystemJob.objects.create(
            info_system_jobs_id=1,
            suc_id=1,  # Will be updated later
            info_tech_jobs_id=info_tech.info_tech_jobs_id,
            comp_tech_jobs_id=comp_tech.comp_tech_jobs_id,
            job_title="Placeholder"
        )
        print("Created placeholder InfoSystemJob")
    else:
        info_system = InfoSystemJob.objects.first()
    
    return comp_tech, info_tech, info_system

def main():
    print("=== BACKFILLING MISSING STANDARD AND CHED RECORDS (TWO-PHASE) ===")
    
    # Create placeholder job records first
    comp_tech, info_tech, info_system = create_placeholder_jobs()
    
    created_standard = 0
    created_ched = 0
    for user in User.objects.filter(account_type__user=True):
        tracker_forms = TrackerForm.objects.filter(user=user)
        if not tracker_forms.exists():
            print(f"User {user.f_name} {user.l_name} (user_id: {user.user_id}) has no TrackerForm.")
            continue
        for tracker_form in tracker_forms:
            # Check if a Standard exists for this TrackerForm
            standard = Standard.objects.filter(tracker_form=tracker_form).first()
            if not standard:
                # Phase 1: Create Standard with null related fields
                standard = Standard.objects.create(
                    tracker_form=tracker_form,
                    qpro=None,
                    suc=None,
                    aacup=None,
                    ched=None
                )
                # Phase 2: Create related records with standard set
                qpro = Qpro.objects.create(standard=standard)
                aacup = Aacup.objects.create(standard=standard)
                ched = Ched.objects.create(standard=standard)
                
                # Create Suc with proper job references
                suc = Suc.objects.create(
                    standard=standard,
                    info_tech_jobs=info_tech,
                    info_system_jobs=info_system,
                    comp_tech_jobs=comp_tech
                )
                
                # Update Standard to point to related records
                standard.qpro = qpro
                standard.suc = suc
                standard.aacup = aacup
                standard.ched = ched
                standard.save()
                created_standard += 1
                created_ched += 1
                print(f"  -> Created Standard and Ched for user {user.f_name} {user.l_name} (user_id: {user.user_id}, tracker_form_id: {tracker_form.tracker_form_id})")
            else:
                # Ensure Ched exists and is linked
                ched = Ched.objects.filter(standard=standard).first()
                if not ched:
                    ched = Ched.objects.create(standard=standard)
                    standard.ched = ched
                    standard.save()
                    created_ched += 1
                    print(f"  -> Created missing Ched for user {user.f_name} {user.l_name} (user_id: {user.user_id}, standard_id: {standard.standard_id})")
    print(f"Created {created_standard} Standard records and {created_ched} Ched records.")

if __name__ == '__main__':
    main() 