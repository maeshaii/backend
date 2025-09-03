import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User

def update_all_job_alignments():
    print("=== UPDATING ALL USER JOB ALIGNMENTS ===")
    
    # Get all alumni users
    alumni_users = User.objects.filter(account_type__user=True)
    print(f"Found {alumni_users.count()} alumni users")
    
    updated_count = 0
    aligned_count = 0
    not_aligned_count = 0
    self_employed_count = 0
    
    for user in alumni_users:
        try:
            # Store original values for comparison
            original_alignment = user.job_alignment_status
            original_category = user.job_alignment_category
            original_self_employed = user.self_employed
            
            # Update job alignment
            user.update_job_alignment()
            
            # Check if anything changed
            if (original_alignment != user.job_alignment_status or 
                original_category != user.job_alignment_category or
                original_self_employed != user.self_employed):
                
                # Save the user
                user.save()
                updated_count += 1
                
                print(f"Updated {user.f_name} {user.l_name}:")
                print(f"  Course: {user.course}")
                print(f"  Position: {user.position_current}")
                print(f"  Employment Type: {user.q_employment_type}")
                print(f"  Alignment: {original_alignment} -> {user.job_alignment_status}")
                print(f"  Category: {original_category} -> {user.job_alignment_category}")
                print(f"  Self-employed: {original_self_employed} -> {user.self_employed}")
                print()
            
            # Count statistics
            if user.job_alignment_status == 'aligned':
                aligned_count += 1
            else:
                not_aligned_count += 1
                
            if user.self_employed:
                self_employed_count += 1
                
        except Exception as e:
            print(f"Error updating user {user.f_name} {user.l_name}: {e}")
            continue
    
    print(f"\n=== SUMMARY ===")
    print(f"Total users processed: {alumni_users.count()}")
    print(f"Users updated: {updated_count}")
    print(f"Aligned jobs: {aligned_count}")
    print(f"Not aligned jobs: {not_aligned_count}")
    print(f"Self-employed: {self_employed_count}")
    
    # Calculate percentages
    if alumni_users.count() > 0:
        alignment_rate = (aligned_count / alumni_users.count()) * 100
        self_employed_rate = (self_employed_count / alumni_users.count()) * 100
        print(f"Job alignment rate: {alignment_rate:.1f}%")
        print(f"Self-employed rate: {self_employed_rate:.1f}%")

if __name__ == '__main__':
    update_all_job_alignments() 