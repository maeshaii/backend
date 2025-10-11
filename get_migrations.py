#!/usr/bin/env python3
import subprocess
import os
import sys

def run_command(cmd):
    """Run a command and return the output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout, result.stderr, result.returncode
    except Exception as e:
        return "", str(e), 1

def main():
    print("Getting migrations from main4 branch...")
    
    # First, let's check what migrations we currently have
    print("\nCurrent migrations:")
    stdout, stderr, code = run_command("dir apps\\shared\\migrations\\*.py")
    print(stdout)
    
    # Get migrations from main4 branch
    print("\nGetting migrations from origin/main4...")
    stdout, stderr, code = run_command("git checkout origin/main4 -- apps/shared/migrations/")
    if code == 0:
        print("✅ Successfully got migrations from main4!")
    else:
        print(f"❌ Error: {stderr}")
        return
    
    # Check what migrations we have now
    print("\nMigrations after getting from main4:")
    stdout, stderr, code = run_command("dir apps\\shared\\migrations\\*.py")
    print(stdout)
    
    # Show migration status
    print("\nDjango migration status:")
    stdout, stderr, code = run_command("python manage.py showmigrations shared")
    print(stdout)
    if stderr:
        print(f"Errors: {stderr}")

if __name__ == "__main__":
    main()
