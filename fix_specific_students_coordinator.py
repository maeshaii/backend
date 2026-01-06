"""
Script to manually fix coordinator assignments for specific students.

Use this to correct students that were incorrectly assigned to the wrong coordinator.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, OJTCompanyProfile

def fix_specific_students():
    """Fix coordinator for specific students by CTU ID"""
    print("=" * 70)
    print("Fixing Coordinator for Specific Students")
    print("=" * 70)
    
    # List of students that should belong to CTCOORDINATOR
    # Format: {'CTU_ID': 'CORRECT_COORDINATOR'}
    students_to_fix = {
        '1334315': 'CTCOORDINATOR',  # Maria Gonzaga (first one)
        '1334319': 'CTCOORDINATOR',  # Maria Gonzaga (second one)
    }
    
    fixed_count = 0
    
    for ctu_id, correct_coordinator in students_to_fix.items():
        try:
            student = User.objects.get(acc_username=ctu_id, account_type__ojt=True)
            profile, created = OJTCompanyProfile.objects.get_or_create(user=student)
            
            old_coord = profile.coordinator
            profile.coordinator = correct_coordinator
            profile.save()
            
            fixed_count += 1
            print(f"✓ Fixed {student.f_name} {student.l_name} ({ctu_id})")
            print(f"   Changed from '{old_coord}' to '{correct_coordinator}'")
        except User.DoesNotExist:
            print(f"✗ Student with CTU_ID {ctu_id} not found")
        except Exception as e:
            print(f"✗ Error fixing {ctu_id}: {e}")
    
    print("\n" + "=" * 70)
    print(f"Fixed {fixed_count} student(s)")
    print("=" * 70)

if __name__ == "__main__":
    fix_specific_students()


