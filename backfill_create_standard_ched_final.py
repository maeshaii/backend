import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, TrackerForm, Standard, Ched, Qpro, Aacup
from django.db import connection

def create_standard_ched_final():
    """Create Standard and Ched records with proper ordering"""
    with connection.cursor() as cursor:
        # Get the tracker form
        cursor.execute("SELECT tracker_form_id FROM shared_trackerform LIMIT 1")
        result = cursor.fetchone()
        if not result:
            print("No tracker form found")
            return
        tracker_form_id = result[0]
        
        # Check if Standard already exists
        cursor.execute("SELECT standard_id FROM shared_standard WHERE tracker_form_id = %s", [tracker_form_id])
        if cursor.fetchone():
            print("Standard already exists for this tracker form")
            return
        
        # Create Standard first with temporary values
        cursor.execute("""
            INSERT INTO shared_standard (standard_id, tracker_form_id, qpro_id, suc_id, aacup_id, ched_id) 
            VALUES (1, %s, 1, NULL, 1, 1)
        """, [tracker_form_id])
        
        # Create Qpro with standard_id=1
        cursor.execute("""
            INSERT INTO shared_qpro (qpro_id, standard_id) 
            VALUES (1, 1)
            ON CONFLICT (qpro_id) DO UPDATE SET standard_id = 1
        """)
        
        # Create Aacup with standard_id=1
        cursor.execute("""
            INSERT INTO shared_aacup (aacup_id, standard_id) 
            VALUES (1, 1)
            ON CONFLICT (aacup_id) DO UPDATE SET standard_id = 1
        """)
        
        # Create Ched with standard_id=1
        cursor.execute("""
            INSERT INTO shared_ched (ched_id, standard_id) 
            VALUES (1, 1)
            ON CONFLICT (ched_id) DO UPDATE SET standard_id = 1
        """)
        
        print(f"Created Standard and Ched records for tracker_form_id {tracker_form_id}")

def main():
    print("=== CREATING STANDARD AND CHED RECORDS (FINAL APPROACH) ===")
    create_standard_ched_final()
    print("Done!")

if __name__ == '__main__':
    main() 