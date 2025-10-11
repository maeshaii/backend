import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.test import RequestFactory
from apps.api.views import alumni_statistics_view
from apps.shared.models import User, AcademicInfo, TrackerData
from django.contrib.auth.models import AnonymousUser
from unittest.mock import Mock

def test_api_endpoint():
    """Test the alumni statistics API endpoint"""
    print("=" * 50)
    print("TESTING ALUMNI STATISTICS API ENDPOINT")
    print("=" * 50)
    
    # Create a mock request
    factory = RequestFactory()
    request = factory.get('/api/alumni/statistics/')
    request.user = Mock()  # Mock authenticated user
    
    try:
        # Call the view function directly
        response = alumni_statistics_view(request)
        
        print(f"Response status code: {response.status_code}")
        print(f"Response content: {response.content.decode()}")
        
        # Parse the JSON response
        import json
        data = json.loads(response.content.decode())
        
        if data.get('success'):
            years = data.get('years', [])
            print(f"\nYears returned by API:")
            for year_data in years:
                print(f"  {year_data}")
        else:
            print(f"API returned error: {data.get('message', 'Unknown error')}")
            
    except Exception as e:
        print(f"Error testing API endpoint: {e}")
    
    # Also test the database query directly
    print(f"\n" + "=" * 30)
    print("DIRECT DATABASE QUERY TEST")
    print("=" * 30)
    
    from collections import Counter
    
    year_values = (
        User.objects
        .filter(account_type__user=True)
        .values_list('academic_info__year_graduated', flat=True)
    )
    year_counts = Counter([y for y in year_values if y is not None])
    
    print(f"Years found in database: {dict(year_counts)}")
    
    years_list = [
        {'year': year, 'count': count}
        for year, count in sorted(year_counts.items(), reverse=True)
    ]
    
    print("Formatted years list:")
    for year_data in years_list:
        print(f"  {year_data}")

if __name__ == "__main__":
    test_api_endpoint()




