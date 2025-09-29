from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
import pandas as pd
import os
from apps.shared.models import User, OJTInfo

class Command(BaseCommand):
    help = 'Update existing OJT records with start dates from Excel file'

    def add_arguments(self, parser):
        parser.add_argument('excel_file', type=str, help='Path to Excel file with OJT data')

    def handle(self, *args, **options):
        excel_file_path = options['excel_file']
        
        if not os.path.exists(excel_file_path):
            raise CommandError(f'Excel file not found: {excel_file_path}')

        try:
            # Read Excel file
            df = pd.read_excel(excel_file_path)
            self.stdout.write(f"Loaded Excel file with {len(df)} rows")
            self.stdout.write(f"Columns: {list(df.columns)}")
            
            updated_count = 0
            not_found_count = 0
            
            with transaction.atomic():
                for index, row in df.iterrows():
                    try:
                        ctu_id = str(row['CTU_ID']).strip()
                        
                        # Parse start date
                        start_date_raw = row.get('Ojt_Start_Date') or row.get('Start_Date')
                        if pd.notna(start_date_raw):
                            try:
                                ojt_start_date = pd.to_datetime(start_date_raw, dayfirst=True).date()
                                self.stdout.write(f"Row {index+2} - CTU_ID: {ctu_id}, Start Date: {ojt_start_date}")
                            except Exception as e:
                                self.stdout.write(f"Row {index+2} - Failed to parse start date: {e}")
                                continue
                        else:
                            self.stdout.write(f"Row {index+2} - No start date found")
                            continue
                        
                        # Find user by CTU_ID
                        try:
                            user = User.objects.get(acc_username=ctu_id, account_type__ojt=True)
                            ojt_info, created = OJTInfo.objects.get_or_create(user=user)
                            
                            if ojt_info.ojt_start_date != ojt_start_date:
                                ojt_info.ojt_start_date = ojt_start_date
                                ojt_info.save()
                                updated_count += 1
                                self.stdout.write(f"Updated OJT start date for {ctu_id}: {ojt_start_date}")
                            else:
                                self.stdout.write(f"Start date already correct for {ctu_id}")
                                
                        except User.DoesNotExist:
                            self.stdout.write(f"User with CTU_ID {ctu_id} not found")
                            not_found_count += 1
                            continue
                            
                    except Exception as e:
                        self.stdout.write(f"Error processing row {index+2}: {e}")
                        continue
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nUpdate completed:\n'
                    f'- Updated: {updated_count} records\n'
                    f'- Not found: {not_found_count} records'
                )
            )
            
        except Exception as e:
            raise CommandError(f'Error processing Excel file: {e}')
