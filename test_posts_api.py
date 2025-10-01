import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User
from django.test import RequestFactory
from apps.api import views

# Create a mock request
factory = RequestFactory()
request = factory.get('/api/posts/')

# Get user 9
user = User.objects.get(user_id=9)
request.user = user

# Call the view
response = views.posts_view(request)

print("Status Code:", response.status_code)
print("\nResponse Structure:")
data = json.loads(response.content)
print(f"Number of items in feed: {len(data.get('posts', []))}")

# Show each item type
for idx, item in enumerate(data.get('posts', [])[:10]):  # Show first 10
    item_type = item.get('item_type', 'unknown')
    if item_type == 'post':
        print(f"\n{idx+1}. POST (ID: {item.get('post_id')})")
        print(f"   Content: {item.get('post_content', '')[:50]}...")
        print(f"   Sort date: {item.get('sort_date')}")
    elif item_type == 'repost':
        print(f"\n{idx+1}. REPOST (ID: {item.get('repost_id')})")
        print(f"   Reposter: {item.get('user', {}).get('f_name')} {item.get('user', {}).get('l_name')}")
        print(f"   Caption: {item.get('repost_caption', 'None')}")
        print(f"   Original: {item.get('original_post', {}).get('post_content', '')[:50]}...")
        print(f"   Sort date: {item.get('sort_date')}")

