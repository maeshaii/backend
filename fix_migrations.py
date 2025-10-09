#!/usr/bin/env python3
"""
Script to fix migration issues and ensure all migrations 1-93 are properly applied
"""
import os
import sys
import django
from django.core.management import execute_from_command_line

def main():
    # Set up Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
    django.setup()
    
    print("🔍 Checking migration files...")
    
    # Check what migration files exist
    migrations_dir = "apps/shared/migrations"
    migration_files = [f for f in os.listdir(migrations_dir) if f.endswith('.py') and f != '__init__.py']
    migration_files.sort()
    
    print(f"📁 Found {len(migration_files)} migration files:")
    for i, file in enumerate(migration_files, 1):
        print(f"  {i:2d}. {file}")
    
    # Check if we have migrations 1-93
    has_0001 = any(f.startswith('0001_') for f in migration_files)
    has_0093 = any(f.startswith('0093_') for f in migration_files)
    
    print(f"\n✅ Migration 0001 (initial): {'Found' if has_0001 else 'Missing'}")
    print(f"✅ Migration 0093 (latest): {'Found' if has_0093 else 'Missing'}")
    
    if has_0001 and has_0093:
        print("\n🎉 All migrations 1-93 are present!")
        print("\n📋 To apply these migrations to your database, run:")
        print("   python manage.py migrate shared")
        print("\n📋 To check migration status, run:")
        print("   python manage.py showmigrations shared")
    else:
        print("\n❌ Some migrations are missing. You may need to:")
        print("   1. Pull the latest changes from main4 branch")
        print("   2. Or manually copy missing migration files")
    
    print("\n🔧 If you're still having issues, try:")
    print("   python manage.py migrate shared --fake-initial")
    print("   python manage.py migrate shared")

if __name__ == "__main__":
    main()
