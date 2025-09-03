import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, TrackerForm, Standard, Ched, Qpro, Aacup
from django.db import connection

def create_standard_ched_with_raw_sql():
    """Create Standard and Ched records using raw SQL to bypass ORM constraints"""
    with connection.cursor() as cursor:
        # Get the tracker form
        cursor.execute("SELECT tracker_form_id FROM shared_trackerform LIMIT 1")
        result = cursor.fetchone()
        if not result:
            print("No tracker form found")
            return
        tracker_form_id = result[0]
        
        # Create Qpro record
        cursor.execute("""
            INSERT INTO shared_qpro (qpro_id, standard_id) 
            VALUES (1, NULL)
            ON CONFLICT (qpro_id) DO NOTHING
        """)
        
        # Create Aacup record
        cursor.execute("""
            INSERT INTO shared_aacup (aacup_id, standard_id) 
            VALUES (1, NULL)
            ON CONFLICT (aacup_id) DO NOTHING
        """)
        
        # Create Ched record
        cursor.execute("""
            INSERT INTO shared_ched (ched_id, standard_id) 
            VALUES (1, NULL)
            ON CONFLICT (ched_id) DO NOTHING
        """)
        
        # Create Standard record
        cursor.execute("""
            INSERT INTO shared_standard (standard_id, tracker_form_id, qpro_id, suc_id, aacup_id, ched_id) 
            VALUES (1, %s, 1, NULL, 1, 1)
            ON CONFLICT (standard_id) DO NOTHING
        """, [tracker_form_id])
        
        # Update related records to point to Standard
        cursor.execute("UPDATE shared_qpro SET standard_id = 1 WHERE qpro_id = 1")
        cursor.execute("UPDATE shared_aacup SET standard_id = 1 WHERE aacup_id = 1")
        cursor.execute("UPDATE shared_ched SET standard_id = 1 WHERE ched_id = 1")
        
        print(f"Created Standard and Ched records for tracker_form_id {tracker_form_id}")

def main():
    print("=== CREATING STANDARD AND CHED RECORDS (SIMPLE APPROACH) ===")
    create_standard_ched_with_raw_sql()
    print("Done!")

if __name__ == '__main__':
    main() 