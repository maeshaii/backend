import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.db import connection

def test_cross_course_alignment():
    print("=== CROSS-COURSE JOB ALIGNMENT TEST ===")
    
    # Test a cross-course job
    test_job = "Network and Computer Systems Administrators"
    
    with connection.cursor() as cursor:
        # Check BSIT database
        cursor.execute("SELECT job_title FROM shared_simpleinfotechjob WHERE job_title = %s", [test_job])
        bsit_match = cursor.fetchone()
        
        # Check BSIS database
        cursor.execute("SELECT job_title FROM shared_simpleinfosystemjob WHERE job_title = %s", [test_job])
        bsis_match = cursor.fetchone()
        
        # Check BIT-CT database
        cursor.execute("SELECT job_title FROM shared_simplecomptechjob WHERE job_title = %s", [test_job])
        bit_ct_match = cursor.fetchone()
    
    print(f"Job: '{test_job}'")
    print(f"BSIT database: {'✓ Found' if bsit_match else '❌ Not found'}")
    print(f"BSIS database: {'✓ Found' if bsis_match else '❌ Not found'}")
    print(f"BIT-CT database: {'✓ Found' if bit_ct_match else '❌ Not found'}")
    
    print("\nThis means:")
    if bsit_match:
        print("- BSIT graduates with this job → ALIGNED")
    if bsis_match:
        print("- BSIS graduates with this job → ALIGNED")
    if bit_ct_match:
        print("- BIT-CT graduates with this job → ALIGNED")
    
    # Test with a real user
    from apps.shared.models import User
    user = User.objects.filter(f_name='Carlo', l_name='Lopez').first()
    if user:
        print(f"\nReal user test:")
        print(f"User: {user.f_name} {user.l_name}")
        print(f"Course: {user.course}")
        print(f"Position: {user.position_current}")
        print(f"Alignment: {user.job_alignment_status}")
        print(f"Category: {user.job_alignment_category}")
    
    # Show cross-course statistics
    print("\n=== CROSS-COURSE STATISTICS ===")
    with connection.cursor() as cursor:
        cursor.execute("SELECT job_title FROM shared_simpleinfotechjob")
        bsit_jobs = [r[0] for r in cursor.fetchall()]
        
        cursor.execute("SELECT job_title FROM shared_simpleinfosystemjob")
        bsis_jobs = [r[0] for r in cursor.fetchall()]
        
        cursor.execute("SELECT job_title FROM shared_simplecomptechjob")
        bit_ct_jobs = [r[0] for r in cursor.fetchall()]
    
    # Find cross-course jobs
    bsit_bsis_cross = [job for job in bsit_jobs if job in bsis_jobs]
    bsit_bit_ct_cross = [job for job in bsit_jobs if job in bit_ct_jobs]
    bsis_bit_ct_cross = [job for job in bsis_jobs if job in bit_ct_jobs]
    all_three_cross = [job for job in bsit_jobs if job in bsis_jobs and job in bit_ct_jobs]
    
    print(f"BSIT-BSIS cross: {len(bsit_bsis_cross)} jobs")
    print(f"BSIT-BIT-CT cross: {len(bsit_bit_ct_cross)} jobs")
    print(f"BSIS-BIT-CT cross: {len(bsis_bit_ct_cross)} jobs")
    print(f"All three courses cross: {len(all_three_cross)} jobs")
    
    print("\nExamples of cross-course jobs:")
    print("BSIT-BSIS cross jobs:")
    for job in bsit_bsis_cross[:3]:
        print(f"  - {job}")
    
    print("\nBSIT-BIT-CT cross jobs:")
    for job in bsit_bit_ct_cross[:3]:
        print(f"  - {job}")

if __name__ == "__main__":
    test_cross_course_alignment() 