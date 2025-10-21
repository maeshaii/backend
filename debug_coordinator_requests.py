import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import OJTImport, User

print('=== Testing coordinator_requests_list_view logic step by step ===')

try:
    # Test 1: Check OJTImport records
    print('\n1. Testing OJTImport records...')
    all_imports = OJTImport.objects.all()
    print(f"Total OJTImport records: {all_imports.count()}")
    for imp in all_imports:
        print(f"  Year: {imp.batch_year}, Status: {imp.status}, Course: '{imp.course}'")

    # Test 2: Check requested imports
    print('\n2. Testing requested imports...')
    requested_imports = OJTImport.objects.filter(status='Requested')
    print(f"Found {requested_imports.count()} Requested imports")
    
    # Test 3: Test the main query logic
    print('\n3. Testing main query logic...')
    items = []
    for imp in requested_imports:
        year = imp.batch_year
        course = imp.course or 'OJT'  # Default to 'OJT' if course is empty
        
        print(f"Processing: Year {year}, Course '{course}'")
        
        # Count students who are completed but not yet alumni for this year/course
        unapproved_count = User.objects.filter(
            academic_info__year_graduated=year,
            academic_info__program=course,
            ojt_info__ojtstatus='Completed'
        ).exclude(
            account_type__user=True  # Exclude alumni (already approved)
        ).count()
        
        print(f"  Unapproved count: {unapproved_count}")
        
        # Only include if there are actually unapproved students
        if unapproved_count > 0:
            items.append({
                'batch_year': year,
                'course': course,
                'count': unapproved_count
            })
    
    print(f'\n4. Final items: {items}')
    
    # Test 4: Test the fallback query
    print('\n5. Testing fallback query...')
    completed_years_courses = (
        User.objects.filter(ojt_info__ojtstatus='Completed')
        .values('academic_info__year_graduated', 'academic_info__program')
        .annotate()
    )
    
    existing_keys = {(it['batch_year'], it.get('course', '')) for it in items if it.get('batch_year') is not None}
    approved_batches = set(OJTImport.objects.filter(status='Approved').values_list('batch_year', flat=True))
    
    print(f"Existing keys: {existing_keys}")
    print(f"Approved batches: {approved_batches}")
    
    for row in completed_years_courses:
        y = row.get('academic_info__year_graduated')
        course = row.get('academic_info__program', '') or 'OJT'
        print(f"Checking: Year {y}, Course '{course}'")
        
        if y and (y, course) not in existing_keys and y not in approved_batches:
            count = User.objects.filter(
                academic_info__year_graduated=y, 
                academic_info__program=course,
                ojt_info__ojtstatus='Completed'
            ).count()
            print(f"  Adding fallback item: count {count}")
            items.append({'batch_year': y, 'course': course, 'count': count})
        else:
            print(f"  Skipping - existing: {(y, course) in existing_keys}, approved: {y in approved_batches}")
    
    print(f'\n6. Final items after fallback: {items}')
    
    # Test 5: Test deduplication
    print('\n7. Testing deduplication...')
    dedup = {}
    for it in items:
        y = it.get('batch_year')
        course = it.get('course', '')
        if y is None:
            continue
        key = (y, course)
        dedup[key] = max(dedup.get(key, 0), int(it.get('count') or 0))
    
    final_items = [{'batch_year': y, 'course': course, 'count': c} for (y, course), c in dedup.items()]
    final_items.sort(key=lambda x: int(x['batch_year']), reverse=True)
    
    print(f'8. Final deduplicated items: {final_items}')
    
except Exception as e:
    print(f'ERROR: {e}')
    import traceback
    traceback.print_exc()

