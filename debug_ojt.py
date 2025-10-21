import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import OJTImport, User, AcademicInfo

print('=== Debugging OJTImport and User Data ===')

# Check OJTImport records
imports = OJTImport.objects.all()
print(f'OJTImport records: {imports.count()}')
for imp in imports:
    print(f'  Year: {imp.batch_year}, Status: {imp.status}, Course: "{imp.course}"')

# Check completed users
completed_users = User.objects.filter(ojt_info__ojtstatus='Completed')
print(f'\nCompleted OJT users: {completed_users.count()}')
for user in completed_users[:3]:
    academic_info = getattr(user, 'academic_info', None)
    if academic_info:
        print(f'  User: {user.f_name} {user.l_name}')
        print(f'    Year: {academic_info.year_graduated}')
        print(f'    Program: "{academic_info.program}"')
        print(f'    Section: "{academic_info.section}"')
    else:
        print(f'  User: {user.f_name} {user.l_name} - No academic info')

# Test the query that's failing
print('\n=== Testing the failing query ===')
try:
    year = 2020
    course = 'OJT'
    unapproved_count = User.objects.filter(
        academic_info__year_graduated=year,
        academic_info__program=course,
        ojt_info__ojtstatus='Completed'
    ).exclude(
        account_type__user=True
    ).count()
    print(f'Query result for year {year}, program {course}: {unapproved_count}')
except Exception as e:
    print(f'Query failed: {e}')
    import traceback
    traceback.print_exc()

# Test the coordinator_requests_list_view function directly
print('\n=== Testing coordinator_requests_list_view function ===')
try:
    from apps.api.views import coordinator_requests_list_view
    from django.test import RequestFactory
    
    factory = RequestFactory()
    request = factory.get('/api/ojt/coordinator-requests/list/')
    
    # Mock authentication
    class MockUser:
        is_authenticated = True
    request.user = MockUser()
    
    response = coordinator_requests_list_view(request)
    print(f'Response status: {response.status_code}')
    if hasattr(response, 'content'):
        print(f'Response content: {response.content.decode()}')
except Exception as e:
    print(f'Function test failed: {e}')
    import traceback
    traceback.print_exc()