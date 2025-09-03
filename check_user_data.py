import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, CompTechJob, InfoTechJob, InfoSystemJob

def check_user_data():
    print("=== Checking User Data ===")
    
    # Check job databases
    print(f"\nJob Databases:")
    print(f"CompTechJob count: {CompTechJob.objects.count()}")
    print(f"InfoTechJob count: {InfoTechJob.objects.count()}")
    print(f"InfoSystemJob count: {InfoSystemJob.objects.count()}")
    
    # Check users with positions
    users_with_positions = User.objects.filter(position_current__isnull=False).exclude(position_current='')
    print(f"\nUsers with positions: {users_with_positions.count()}")
    
    for user in users_with_positions:
        print(f"\nUser: {user.f_name} {user.l_name}")
        print(f"  CTU ID: {user.acc_username}")
        print(f"  Position: {user.position_current}")
        print(f"  Course: {user.course}")
        print(f"  Job Alignment Status: {user.job_alignment_status}")
        print(f"  Job Alignment Category: {user.job_alignment_category}")
        print(f"  Job Alignment Title: {user.job_alignment_title}")
        print(f"  Self Employed: {user.self_employed}")
        print(f"  High Position: {user.high_position}")
        
        # Check if position contains any keywords
        position_lower = user.position_current.lower()
        if 'geological' in position_lower:
            print(f"  *** Contains 'geological' keyword ***")
        if 'technician' in position_lower:
            print(f"  *** Contains 'technician' keyword ***")

if __name__ == "__main__":
    check_user_data() 