import os
import django
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from apps.shared.models import User, TrackerResponse, Question

def migrate_tracker_data_to_user_fields():
    """
    Migrate existing TrackerResponse JSON data to User model fields
    Note: Basic info fields (name, age, birthdate, phone, address, civil_status, social_media) 
    already exist in User model from import, so we only migrate employment/study data
    """
    print("Starting migration of tracker data to user fields...")
    
    # Question ID to field mapping (only new fields, not duplicates)
    question_field_mapping = {
        # Employment Information (new fields)
        21: 'q_employment_status',       # "Are you employed?"
        22: 'q_employment_type',         # "Employed by company/self-employed"
        23: 'q_employment_permanent',    # "Permanent/Temporary"
        24: 'q_company_name',           # "Current Company Name"
        25: 'q_current_position',       # "Current Position"
        26: 'q_job_sector',             # "Private/Government"
        27: 'q_employment_duration',    # "How long employed"
        28: 'q_salary_range',           # "Salary range"
        29: 'q_awards_received',        # "Yes/No"
        30: 'q_awards_document',        # File upload
        31: 'q_employment_document',    # File upload
        
        # Unemployment (new field)
        32: 'q_unemployment_reason',    # Checkbox options
        
        # Further Study (new fields)
        33: 'q_pursue_study',           # "Yes/No"
        34: 'q_study_start_date',       # "Date Started"
        35: 'q_post_graduate_degree',   # "Specify degree"
        36: 'q_institution_name',       # "Institution name"
        37: 'q_units_obtained',         # "Units obtained"
    }
    
    # Get all tracker responses
    tracker_responses = TrackerResponse.objects.all()
    print(f"Found {tracker_responses.count()} tracker responses to migrate")
    
    migrated_count = 0
    skipped_count = 0
    error_count = 0
    
    for response in tracker_responses:
        try:
            user = response.user
            answers = response.answers
            
            # Track if any fields were updated
            fields_updated = False
            
            # Migrate each answer to the corresponding User field
            for question_id_str, answer in answers.items():
                try:
                    # Handle both string and integer question IDs
                    if isinstance(question_id_str, str):
                        # Try to convert to int, skip if it's not a valid number
                        try:
                            question_id = int(question_id_str)
                        except ValueError:
                            print(f"Warning: Skipping invalid question ID '{question_id_str}' for user {user.user_id}")
                            continue
                    else:
                        question_id = question_id_str
                    
                    if question_id in question_field_mapping:
                        field_name = question_field_mapping[question_id]
                        
                        # Handle different field types
                        if field_name in ['q_study_start_date']:
                            # Convert date strings to DateField
                            try:
                                if answer and answer != '' and answer != 'last':
                                    # Handle different date formats
                                    if '/' in str(answer):
                                        # Format: MM/DD/YYYY
                                        date_obj = datetime.strptime(str(answer), '%m/%d/%Y').date()
                                    else:
                                        # Format: YYYY-MM-DD
                                        date_obj = datetime.strptime(str(answer), '%Y-%m-%d').date()
                                    setattr(user, field_name, date_obj)
                                    fields_updated = True
                            except (ValueError, TypeError) as e:
                                print(f"Warning: Could not parse date '{answer}' for user {user.user_id}: {e}")
                        
                        elif field_name in ['q_awards_document', 'q_employment_document']:
                            # Handle file uploads (skip for now, files need special handling)
                            print(f"Note: File upload field {field_name} skipped for user {user.user_id}")
                        
                        elif field_name == 'q_unemployment_reason':
                            # Handle JSON field for checkbox options
                            if isinstance(answer, list):
                                setattr(user, field_name, answer)
                                fields_updated = True
                            else:
                                setattr(user, field_name, [answer] if answer else [])
                                fields_updated = True
                        
                        else:
                            # Handle regular CharField/TextField
                            setattr(user, field_name, str(answer) if answer else None)
                            fields_updated = True
                            
                except Exception as e:
                    print(f"Warning: Error processing question {question_id_str} for user {user.user_id}: {e}")
                    continue
            
            # Update metadata if any fields were changed
            if fields_updated:
                user.tracker_submitted_at = response.submitted_at
                user.save()
                migrated_count += 1
                print(f"✓ Migrated user {user.user_id} ({user.f_name} {user.l_name})")
            else:
                skipped_count += 1
                print(f"- Skipped user {user.user_id} (no new data to migrate)")
                
        except Exception as e:
            error_count += 1
            print(f"Error migrating user {response.user.user_id}: {str(e)}")
            continue
    
    print(f"\nMigration completed!")
    print(f"✓ Successfully migrated: {migrated_count} users")
    print(f"- Skipped: {skipped_count} users")
    print(f"❌ Errors: {error_count} users")
    print(f"Total processed: {migrated_count + skipped_count + error_count} users")

if __name__ == "__main__":
    migrate_tracker_data_to_user_fields() 