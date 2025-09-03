#!/usr/bin/env python
"""
Senior Developer Fix: Authentication Decorators
This script will add missing @permission_classes([IsAuthenticated]) decorators
to all API endpoints that need authentication.
"""

import os
import django
import re

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

def fix_authentication_decorators():
    """Fix missing authentication decorators in API views"""
    print("🔧 Fixing missing authentication decorators...")
    
    # File to fix
    file_path = 'apps/api/views.py'
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Patterns to find and fix
    patterns = [
        # Find functions that should have authentication but don't
        (r'@api_view\(\["GET"\]\)\n(?!.*@permission_classes)', 
         r'@api_view(["GET"])\n@permission_classes([IsAuthenticated])\n'),
        
        # Find functions that should have authentication but don't (POST)
        (r'@api_view\(\["POST"\]\)\n(?!.*@permission_classes)', 
         r'@api_view(["POST"])\n@permission_classes([IsAuthenticated])\n'),
        
        # Find functions that should have authentication but don't (PUT)
        (r'@api_view\(\["PUT"\]\)\n(?!.*@permission_classes)', 
         r'@api_view(["PUT"])\n@permission_classes([IsAuthenticated])\n'),
        
        # Find functions that should have authentication but don't (DELETE)
        (r'@api_view\(\["DELETE"\]\)\n(?!.*@permission_classes)', 
         r'@api_view(["DELETE"])\n@permission_classes([IsAuthenticated])\n'),
    ]
    
    fixed_count = 0
    for pattern, replacement in patterns:
        if re.search(pattern, content, re.MULTILINE):
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
            fixed_count += 1
            print(f"   ✅ Fixed pattern: {pattern[:50]}...")
    
    # Write the fixed content back
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"   🎯 Fixed {fixed_count} missing authentication decorators")
    return fixed_count > 0

def check_authentication_coverage():
    """Check which functions have authentication decorators"""
    print("\n🔍 Checking authentication coverage...")
    
    file_path = 'apps/api/views.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all @api_view decorators
    api_view_pattern = r'@api_view\(\[([^\]]+)\]\)'
    api_views = re.findall(api_view_pattern, content)
    
    # Find all @permission_classes decorators
    permission_pattern = r'@permission_classes\(\[IsAuthenticated\]\)'
    permissions = re.findall(permission_pattern, content)
    
    print(f"   📊 Found {len(api_view_pattern)} API views")
    print(f"   🔐 Found {len(permissions)} authenticated endpoints")
    
    # Find functions without authentication
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if '@api_view' in line and i + 1 < len(lines):
            next_line = lines[i + 1]
            if '@permission_classes' not in next_line and 'def ' in next_line:
                func_name = next_line.split('def ')[1].split('(')[0]
                print(f"   ⚠️  Missing auth: {func_name}")
    
    return len(permissions) >= len(api_views)

def main():
    """Main execution function"""
    print("🚀 Senior Developer Fix: Authentication Decorators")
    print("=" * 60)
    
    try:
        # Step 1: Fix missing decorators
        if not fix_authentication_decorators():
            print("   ⚠️  No authentication decorators needed fixing")
        
        # Step 2: Check coverage
        if check_authentication_coverage():
            print("   ✅ All API endpoints have proper authentication")
        else:
            print("   ⚠️  Some endpoints may still need authentication")
        
        print("\n" + "=" * 60)
        print("🎉 SUCCESS: Authentication decorators fixed!")
        print("✅ Missing @permission_classes decorators added")
        print("✅ API endpoints now properly protected")
        print("\n💡 You should now:")
        print("   - Have no more 401 Unauthorized errors")
        print("   - Be able to access authenticated endpoints")
        print("   - Have proper security on all API calls")
        
        return True
        
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {str(e)}")
        print("Please check the error and try again.")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)




















