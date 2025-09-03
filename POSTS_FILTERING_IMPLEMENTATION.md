# Posts Filtering Implementation

## Overview
This implementation adds the ability to filter posts by user account type, allowing:
- **CCICT page** to show only posts from admin users
- **PESO page** to show only posts from PESO users (alumni/OJT users)

## Backend Changes

### 1. New API Endpoint
- **URL**: `/api/posts/by-user-type/`
- **Method**: GET
- **Parameters**: `user_type` (either "peso" or "admin")
- **Response**: Filtered posts based on user account type

### 2. New View Function
- **File**: `backend-wny/apps/api/views.py`
- **Function**: `posts_by_user_type_view()`
- **Features**:
  - Filters posts by `user__account_type__peso=True` for PESO users
  - Filters posts by `user__account_type__admin=True` for admin users
  - Includes all post data (title, content, image, likes, comments, etc.)
  - Handles authentication and sets `is_liked` field for current user
  - Proper error handling and validation

### 3. URL Configuration
- **File**: `backend-wny/apps/api/urls.py`
- **Added**: `path('posts/by-user-type/', views.posts_by_user_type_view, name='posts_by_user_type')`

## Frontend Changes

### 1. PESO Page (`mobile-wny/app/peso/pesopage.tsx`)
- **Updated**: Now uses `getPostsByUserType('peso')` instead of `getPosts()`
- **Result**: Only shows posts from PESO users (alumni/OJT users)
- **Enhanced**: Better error messages and user feedback

### 2. CCICT Page (`mobile-wny/app/ccict/ccictpage.tsx`)
- **Updated**: Now uses `getPostsByUserType('admin')` instead of `getPosts()`
- **Result**: Only shows posts from admin users
- **Enhanced**: Better error messages and user feedback

### 3. API Service (`mobile-wny/services/api.ts`)
- **Added**: `getPostsByUserType(userType: 'peso' | 'admin')` function
- **Purpose**: Calls the new backend endpoint with appropriate user type filter

## User Account Types

### PESO Users (alumni/OJT)
- **Account Type Field**: `account_type.peso = True`
- **Who**: Alumni and OJT students
- **Posts**: Will appear on PESO page

### Admin Users
- **Account Type Field**: `account_type.admin = True`
- **Who**: CCICT administrators
- **Posts**: Will appear on CCICT page

## Features Maintained

Both pages still support:
- ✅ **Profile View**: Organization profile display
- ✅ **Messaging**: Direct message buttons
- ✅ **Like System**: Full like/unlike functionality
- ✅ **Comment System**: Complete commenting with modal
- ✅ **Real-time Updates**: Immediate UI updates
- ✅ **Pull-to-Refresh**: Refresh functionality
- ✅ **Error Handling**: Proper error messages
- ✅ **Loading States**: Loading indicators

## API Response Format

```json
{
  "posts": [
    {
      "post_id": 123,
      "post_title": "Post Title",
      "post_content": "Post content...",
      "post_image": "image_url_or_null",
      "type": "personal",
      "created_at": "2024-01-01T00:00:00Z",
      "likes_count": 5,
      "comments_count": 3,
      "reposts_count": 1,
      "is_liked": false,
      "user": {
        "user_id": 456,
        "f_name": "John",
        "l_name": "Doe",
        "profile_pic": "profile_pic_url"
      },
      "category": {
        "post_cat_id": 1,
        "events": false,
        "announcements": true,
        "donation": false,
        "personal": false
      }
    }
  ]
}
```

## Testing

### Test Script
- **File**: `test_posts_filter.py`
- **Purpose**: Verify the new API endpoint works correctly
- **Tests**:
  1. PESO posts filtering
  2. Admin posts filtering
  3. Invalid user type handling
  4. Missing parameter handling

### Manual Testing
1. **PESO Page**: Should only show posts from alumni/OJT users
2. **CCICT Page**: Should only show posts from admin users
3. **Cross-check**: Posts should not appear on the wrong page

## Benefits

1. **Content Separation**: Clear distinction between admin announcements and user posts
2. **User Experience**: Users see relevant content for their context
3. **Performance**: Reduced data transfer by filtering at the database level
4. **Maintainability**: Clean separation of concerns
5. **Scalability**: Easy to add more user type filters in the future

## Future Enhancements

1. **Additional User Types**: Support for coordinator, regular user types
2. **Hybrid Posts**: Posts that appear on multiple pages
3. **User Preferences**: Allow users to customize what they see
4. **Analytics**: Track engagement by user type
5. **Moderation**: Admin controls for user-generated content
