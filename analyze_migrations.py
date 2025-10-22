#!/usr/bin/env python3
"""
Analyze migration files for duplicates and conflicts.
"""
import os
import re
from collections import defaultdict

migrations_dir = 'apps/shared/migrations'
files = sorted([f for f in os.listdir(migrations_dir) if f.endswith('.py') and f != '__init__.py'])

# Group by migration number
by_number = defaultdict(list)
for f in files:
    match = re.match(r'(\d{4})_', f)
    if match:
        num = match.group(1)
        by_number[num].append(f)

# Find duplicates
print("=" * 80)
print("DUPLICATE MIGRATION NUMBERS")
print("=" * 80)
duplicates = {k: v for k, v in by_number.items() if len(v) > 1}
for num in sorted(duplicates.keys()):
    print(f"\n{num}:")
    for f in duplicates[num]:
        print(f"  - {f}")

# Analyze dependencies
print("\n" + "=" * 80)
print("MIGRATION DEPENDENCY ANALYSIS")
print("=" * 80)

for f in files:
    filepath = os.path.join(migrations_dir, f)
    with open(filepath, 'r', encoding='utf-8') as file:
        content = file.read()
        
        # Extract dependencies
        deps_match = re.search(r'dependencies\s*=\s*\[(.*?)\]', content, re.DOTALL)
        if deps_match:
            deps_str = deps_match.group(1)
            deps = re.findall(r"\('shared',\s*'(\d{4}_[^']+)'\)", deps_str)
            
            # Check if dependencies exist
            for dep in deps:
                dep_file = f"{dep}.py"
                if dep_file not in files:
                    print(f"\n⚠️  {f}")
                    print(f"   Missing dependency: {dep}")

print("\n" + "=" * 80)
print(f"Total migrations: {len(files)}")
print(f"Duplicate numbers: {len(duplicates)}")
print("=" * 80)
























