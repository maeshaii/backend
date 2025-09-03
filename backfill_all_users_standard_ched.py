import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, TrackerForm, Standard, Ched, Qpro, Aacup
from django.db import connection

def create_standard_ched_for_all_users():
    """Create Standard and Ched records for all alumni users"""
    with connection.cursor() as cursor:
        # Get the tracker form
        cursor.execute("SELECT tracker_form_id FROM shared_trackerform LIMIT 1")
        result = cursor.fetchone()
        if not result:
            print("No tracker form found")
            return
        tracker_form_id = result[0]
        
        # Get all alumni users using Django ORM
        users = User.objects.filter(account_type__user=True)
        
        created_count = 0
        for user in users:
            # Check if Standard already exists for this tracker form
            cursor.execute("SELECT standard_id FROM shared_standard WHERE tracker_form_id = %s", [tracker_form_id])
            existing_standard = cursor.fetchone()
            
            if existing_standard:
                standard_id = existing_standard[0]
                # Check if Ched exists for this Standard
                cursor.execute("SELECT ched_id FROM shared_ched WHERE standard_id = %s", [standard_id])
                if not cursor.fetchone():
                    # Create Ched for existing Standard
                    cursor.execute("""
                        INSERT INTO shared_ched (ched_id, standard_id) 
                        VALUES (%s, %s)
                        ON CONFLICT (ched_id) DO NOTHING
                    """, [created_count + 1, standard_id])
                    print(f"Created Ched for existing Standard {standard_id}")
            else:
                # Create new Standard and related records
                standard_id = created_count + 1
                
                # Create Standard
                cursor.execute("""
                    INSERT INTO shared_standard (standard_id, tracker_form_id, qpro_id, suc_id, aacup_id, ched_id) 
                    VALUES (%s, %s, %s, NULL, %s, %s)
                    ON CONFLICT (standard_id) DO NOTHING
                """, [standard_id, tracker_form_id, standard_id, standard_id, standard_id])
                
                # Create Qpro
                cursor.execute("""
                    INSERT INTO shared_qpro (qpro_id, standard_id) 
                    VALUES (%s, %s)
                    ON CONFLICT (qpro_id) DO UPDATE SET standard_id = %s
                """, [standard_id, standard_id, standard_id])
                
                # Create Aacup
                cursor.execute("""
                    INSERT INTO shared_aacup (aacup_id, standard_id) 
                    VALUES (%s, %s)
                    ON CONFLICT (aacup_id) DO UPDATE SET standard_id = %s
                """, [standard_id, standard_id, standard_id])
                
                # Create Ched
                cursor.execute("""
                    INSERT INTO shared_ched (ched_id, standard_id) 
                    VALUES (%s, %s)
                    ON CONFLICT (ched_id) DO UPDATE SET standard_id = %s
                """, [standard_id, standard_id, standard_id])
                
                print(f"Created Standard {standard_id} and Ched for user {user.user_id} ({user.f_name} {user.l_name})")
                created_count += 1
        
        print(f"Created {created_count} new Standard/Ched record sets")

def main():
    print("=== CREATING STANDARD AND CHED RECORDS FOR ALL USERS ===")
    create_standard_ched_for_all_users()
    print("Done!")

if __name__ == '__main__':
    main() 