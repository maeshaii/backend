#!/usr/bin/env python
"""
Script to update existing OJT records with start dates from Excel file
without requiring a full re-import.
"""

import os
import sys
import django
import pandas as pd

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, OJTInfo

def update_ojt_start_dates_from_excel(excel_file_path):
    """
    Update existing OJT records with start dates from Excel file.
    Matches records by CTU_ID.
    """
    try:
        # Read Excel file
        df = pd.read_excel(excel_file_path)
        print(f"Loaded Excel file with {len(df)} rows")
        print(f"Columns: {list(df.columns)}")
        
        updated_count = 0
        not_found_count = 0
        
        for index, row in df.iterrows():
            try:
                ctu_id = str(row['CTU_ID']).strip()
                
                # Parse start date
                start_date_raw = row.get('Ojt_Start_Date') or row.get('Start_Date')
                if pd.notna(start_date_raw):
                    try:
                        ojt_start_date = pd.to_datetime(start_date_raw, dayfirst=True).date()
                        print(f"Row {index+2} - CTU_ID: {ctu_id}, Start Date: {ojt_start_date}")
                    except Exception as e:
                        print(f"Row {index+2} - Failed to parse start date: {e}")
                        continue
                else:
                    print(f"Row {index+2} - No start date found")
                    continue
                
                # Find user by CTU_ID
                try:
                    user = User.objects.get(acc_username=ctu_id, account_type__ojt=True)
                    ojt_info, created = OJTInfo.objects.get_or_create(user=user)
                    
                    if ojt_info.ojt_start_date != ojt_start_date:
                        ojt_info.ojt_start_date = ojt_start_date
                        ojt_info.save()
                        updated_count += 1
                        print(f"Updated OJT start date for {ctu_id}: {ojt_start_date}")
                    else:
                        print(f"Start date already correct for {ctu_id}")
                        
                except User.DoesNotExist:
                    print(f"User with CTU_ID {ctu_id} not found")
                    not_found_count += 1
                    continue
                    
            except Exception as e:
                print(f"Error processing row {index+2}: {e}")
                continue
        
        print(f"\nUpdate completed:")
        print(f"- Updated: {updated_count} records")
        print(f"- Not found: {not_found_count} records")
        
    except Exception as e:
        print(f"Error reading Excel file: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python update_ojt_start_dates.py <path_to_excel_file>")
        print("Example: python update_ojt_start_dates.py ojt_template_with_company.xlsx")
        sys.exit(1)
    
    excel_file_path = sys.argv[1]
    if not os.path.exists(excel_file_path):
        print(f"Excel file not found: {excel_file_path}")
        sys.exit(1)
    
    update_ojt_start_dates_from_excel(excel_file_path)
