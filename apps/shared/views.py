"""
Views for shared app: handles alumni data import/export and related utilities.
Consider splitting large functions into helpers if this file grows further.
"""

from django.shortcuts import render
import pandas as pd
from django.http import HttpResponse, JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.conf import settings
from django.http import JsonResponse
import os
from .models import User, TrackerResponse, Question, UserProfile, AcademicInfo, EmploymentHistory, TrackerData, OJTInfo, AccountType, UserInitialPassword, Notification
from .services import UserService
from .serializers import AlumniListSerializer
from io import BytesIO
import logging
from django.utils import timezone
import secrets
import string

logger = logging.getLogger(__name__)

# Create your views here.

# Export alumni data to Excel

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_alumni_excel(request):
    """
    Export alumni data to Excel, including tracker answers and user model fields.
    """
    try:
        batch_year = request.GET.get('batch_year')
        alumni = User.objects.select_related('profile', 'academic_info', 'employment', 'tracker_data').filter(account_type__user=True)
        if batch_year:
            alumni = alumni.filter(academic_info__year_graduated=batch_year)

        # Basic User model fields to always include
        basic_fields = [
            ("CTU_ID", "acc_username"),
            ("First Name", "f_name"),
            ("Middle Name", "m_name"),
            ("Last Name", "l_name"),
            ("Gender", "gender"),
            ("Birthdate", "birthdate"),
            ("Phone Number", "phone_num"),
            ("Address", "address"),
            ("Social Media", "social_media"),
            ("Civil Status", "civil_status"),
            ("Age", "age"),
            ("Email", "email"),
            ("Program Name", "program"),
            
        ]

        # Collect all tracker question texts that have been answered by any alumni
        all_tracker_qids = set()
        for alum in alumni:
            tracker_responses = TrackerResponse.objects.filter(user=alum).order_by('-submitted_at')
            latest_tracker = tracker_responses.first() if tracker_responses.exists() else None
            tracker_answers = latest_tracker.answers if latest_tracker and latest_tracker.answers else {}
            all_tracker_qids.update([int(qid) for qid in tracker_answers.keys() if str(qid).isdigit()])
        # Get question text for all qids
        tracker_questions = {q.id: q.text for q in Question.objects.filter(id__in=all_tracker_qids)}
        tracker_columns = [tracker_questions[qid] for qid in sorted(tracker_questions.keys())]

        # Build a unique set of export columns: basic fields + tracker question texts (no duplicates)
        export_columns = []
        seen = set()
        for col, _ in basic_fields:
            if col not in seen:
                export_columns.append(col)
                seen.add(col)
        for qtext in tracker_columns:
            if qtext not in seen:
                export_columns.append(qtext)
                seen.add(qtext)

        data = []
        for alum in alumni:
            row = {}
            # Fill basic fields
            for col, field in basic_fields:
                value = getattr(alum, field, "")
                row[col] = value if value is not None else ""
            # Fill tracker answers, but only if not already filled by user model
            tracker_responses = TrackerResponse.objects.filter(user=alum).order_by('-submitted_at')
            latest_tracker = tracker_responses.first() if tracker_responses.exists() else None
            tracker_answers = latest_tracker.answers if latest_tracker and latest_tracker.answers else {}
            for qid, qtext in tracker_questions.items():
                if qtext in row and row[qtext]:
                    continue  # Already filled by user model
                answer = tracker_answers.get(str(qid)) or tracker_answers.get(qid)
                if isinstance(answer, list):
                    answer = ', '.join(str(a) for a in answer)
                row[qtext] = answer if answer is not None else ""
            data.append(row)
        df = pd.DataFrame(data, columns=export_columns)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        output.seek(0)
        response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=alumni_export.xlsx'
        return response
    except Exception as e:
        logger.error(f"Error exporting alumni Excel: {e}")
        return JsonResponse({'success': False, 'message': 'Export failed'}, status=500)

# Import alumni data from Excel, updating only missing fields
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def import_alumni_excel(request):
    """
    Import alumni data from Excel, updating only missing fields.
    """
    try:
        if request.FILES.get('file'):
            batch_year = request.POST.get('batch_year')
            
            # Get or create alumni account type dynamically to avoid 500s on fresh DBs
            alumni_account_type, _ = AccountType.objects.get_or_create(
                user=True,
                admin=False,
                coordinator=False,
                peso=False,
                ojt=False,
            )
            
            df = pd.read_excel(request.FILES['file'])
            created_count = 0
            updated_count = 0
            
            for _, row in df.iterrows():
                ctu_id = row.get('CTU_ID')
                if not ctu_id:
                    continue
                
                # Try to find user by CTU ID
                user = User.objects.filter(acc_username=ctu_id).first()
                
                # Fields that go directly to User model
                user_field_map = {
                    'First_Name': 'f_name',
                    'Middle_Name': 'm_name',
                    'Last_Name': 'l_name',
                    'Last_Nam': 'l_name',  # Handle truncated column name
                    'Gender': 'gender',
                }
                
                # Fields that go to UserProfile model
                profile_field_map = {
                    'Phone_Number': 'phone_num',
                    'Address': 'address',
                    'Birthdate': 'birthdate',
                    'Social Media Acc Link': 'social_media',
                    'Civil Status': 'civil_status',
                }
                
                # Fields that go to EmploymentHistory model
                employment_field_map = {
                    'Company name current': 'company_name_current',
                    'salary current': 'salary_current',
                    # Aliases from your spreadsheet
                    'Current Company Name': 'company_name_current',
                    'Current Position': 'position_current',
                    'Current Salary Range': 'salary_current',
                    'Current Sector of your Job': 'sector_current',
                }
                
                # Fields that go to AcademicInfo model
                academic_field_map = {
                    'Post Graduate Degree': 'post_graduate_degree',
                    'Year_Graduated': 'year_graduated',
                    'Batch Year': 'year_graduated',
                    'Batch_Year': 'year_graduated',
                    'Batch Graduated': 'year_graduated',
                    'Course': 'program',  # Map Course to Program instead
                    'Please specify post graduate/degree.': 'q_post_graduate_degree',
                }
                
                # Fields that go to TrackerData model (used by graphs)
                tracker_field_map = {
                    'Are you PRESENTLY employed?': 'q_employment_status',  # expects Yes/No
                    'Current Company Name': 'q_company_name',
                    'Current Position': 'q_current_position',
                    'Current Salary Range': 'q_salary_range',
                    'Current Sector of your Job': 'q_sector_current',
                }
                
                if user:
                    # Update existing user
                    updated = False
                    
                    # Update User model fields
                    for excel_col, model_field in user_field_map.items():
                        excel_value = row.get(excel_col)
                        if excel_value and (not hasattr(user, model_field) or not getattr(user, model_field) or getattr(user, model_field) == ''):
                            setattr(user, model_field, excel_value)
                            updated = True
                    
                    if updated:
                        user.save()
                        updated_count += 1
                    
                    # Update or create UserProfile
                    profile, profile_created = UserProfile.objects.get_or_create(user=user)
                    profile_updated = False
                    for excel_col, model_field in profile_field_map.items():
                        excel_value = row.get(excel_col)
                        if excel_value and (not hasattr(profile, model_field) or not getattr(profile, model_field) or getattr(profile, model_field) == ''):
                            # Special handling for birthdate - convert string to date
                            if model_field == 'birthdate' and excel_value:
                                try:
                                    bd = pd.to_datetime(excel_value, errors='coerce').date()
                                    if bd:
                                        setattr(profile, model_field, bd)
                                        profile_updated = True
                                except Exception as e:
                                    print(f"DEBUG: Error parsing birthdate for {ctu_id}: {e}")
                            else:
                                setattr(profile, model_field, excel_value)
                                profile_updated = True
                    if profile_updated:
                        profile.save()
                    
                    # Update or create EmploymentHistory
                    employment, employment_created = EmploymentHistory.objects.get_or_create(user=user)
                    employment_updated = False
                    for excel_col, model_field in employment_field_map.items():
                        excel_value = row.get(excel_col)
                        if excel_value and (not hasattr(employment, model_field) or not getattr(employment, model_field) or getattr(employment, model_field) == ''):
                            setattr(employment, model_field, excel_value)
                            employment_updated = True
                    if employment_updated:
                        employment.save()
                    
                    # Update or create AcademicInfo
                    academic_values = {}
                    for excel_col, model_field in academic_field_map.items():
                        excel_value = row.get(excel_col)
                        if excel_value and (not hasattr(user, 'academic_info') or not getattr(user.academic_info, model_field, None)):
                            if model_field == 'year_graduated':
                                try:
                                    academic_values[model_field] = int(str(excel_value).strip())
                                except Exception:
                                    academic_values[model_field] = excel_value
                            else:
                                academic_values[model_field] = excel_value
                    if academic_values:
                        AcademicInfo.objects.update_or_create(
                            user=user,
                            defaults=academic_values,
                        )

                    # Update or create TrackerData (employment status for graphs)
                    tracker_values = {}
                    for excel_col, model_field in tracker_field_map.items():
                        excel_value = row.get(excel_col)
                        if excel_value is not None and excel_value != '':
                            if model_field == 'q_employment_status':
                                val = str(excel_value).strip().lower()
                                if val in ['yes', 'y', 'true', '1']:
                                    tracker_values[model_field] = 'yes'
                                elif val in ['no', 'n', 'false', '0']:
                                    tracker_values[model_field] = 'no'
                                else:
                                    tracker_values[model_field] = str(excel_value)
                            else:
                                tracker_values[model_field] = excel_value
                    if tracker_values:
                        TrackerData.objects.update_or_create(
                            user=user,
                            defaults=tracker_values,
                        )
                        
                else:
                    # Create new user
                    user_data = {
                        'acc_username': ctu_id,
                        'account_type': alumni_account_type,
                        'user_status': 'active'
                    }
                    
                    # Add User model fields from Excel
                    for excel_col, model_field in user_field_map.items():
                        excel_value = row.get(excel_col)
                        if excel_value:
                            user_data[model_field] = excel_value
                    
                    # Create the user
                    user = User.objects.create(**user_data)
                    
                    # Generate and set password for new user
                    alphabet = string.ascii_letters + string.digits
                    password_raw = ''.join(secrets.choice(alphabet) for _ in range(12))
                    user.set_password(password_raw)
                    user.save()
                    
                    # Store initial password for export
                    try:
                        up, _ = UserInitialPassword.objects.get_or_create(user=user)
                        up.set_plaintext(password_raw)
                        up.is_active = True
                        up.save()
                    except Exception as e:
                        logger.error(f"Error saving initial password for {ctu_id}: {e}")
                    
                    # Create UserProfile
                    profile_data = {}
                    for excel_col, model_field in profile_field_map.items():
                        excel_value = row.get(excel_col)
                        if excel_value:
                            # Special handling for birthdate - convert string to date
                            if model_field == 'birthdate':
                                try:
                                    bd = pd.to_datetime(excel_value, errors='coerce').date()
                                    if bd:
                                        profile_data[model_field] = bd
                                except Exception as e:
                                    print(f"DEBUG: Error parsing birthdate for {ctu_id}: {e}")
                            else:
                                profile_data[model_field] = excel_value
                    if profile_data:
                        UserProfile.objects.create(user=user, **profile_data)
                    
                    # Create/Upsert EmploymentHistory
                    employment_data = {}
                    for excel_col, model_field in employment_field_map.items():
                        excel_value = row.get(excel_col)
                        if excel_value:
                            employment_data[model_field] = excel_value
                    if employment_data:
                        EmploymentHistory.objects.update_or_create(
                            user=user,
                            defaults=employment_data,
                        )
                    
                    # Create AcademicInfo
                    academic_data = {}
                    for excel_col, model_field in academic_field_map.items():
                        excel_value = row.get(excel_col)
                        if excel_value is not None and excel_value != '':
                            # Normalize year to int when possible
                            if model_field == 'year_graduated':
                                try:
                                    academic_data[model_field] = int(str(excel_value).strip())
                                except Exception:
                                    academic_data[model_field] = excel_value
                            else:
                                 academic_data[model_field] = excel_value
                    
                    # Ensure year_graduated is set at least from request if missing
                    if 'year_graduated' not in academic_data:
                        academic_data['year_graduated'] = int(batch_year) if str(batch_year).isdigit() else None
                    
                    if academic_data:
                        AcademicInfo.objects.update_or_create(
                            user=user,
                            defaults=academic_data,
                        )

                    # Upsert TrackerData (employment status)
                    tracker_values_new = {}
                    for excel_col, model_field in tracker_field_map.items():
                        excel_value = row.get(excel_col)
                        if excel_value is not None and excel_value != '':
                            if model_field == 'q_employment_status':
                                val = str(excel_value).strip().lower()
                                if val in ['yes', 'y', 'true', '1']:
                                    tracker_values_new[model_field] = 'yes'
                                elif val in ['no', 'n', 'false', '0']:
                                    tracker_values_new[model_field] = 'no'
                                else:
                                    tracker_values_new[model_field] = str(excel_value)
                            else:
                                tracker_values_new[model_field] = excel_value
                    if tracker_values_new:
                        TrackerData.objects.update_or_create(
                            user=user,
                            defaults=tracker_values_new,
                        )
                    
                    created_count += 1
            
            # Export passwords if any users were created
            if created_count > 0:
                try:
                    # Get all newly created users for this import
                    new_users = User.objects.filter(
                        account_type=alumni_account_type,
                        created_at__gte=timezone.now() - timezone.timedelta(minutes=5)  # Users created in last 5 minutes
                    )
                    
                    # Create password export data
                    password_data = []
                    for user in new_users:
                        try:
                            initial_password = UserInitialPassword.objects.get(user=user)
                            password_data.append({
                                'CTU_ID': user.acc_username,
                                'First_Name': user.f_name,
                                'Last_Name': user.l_name,
                                'Password': initial_password.get_plaintext() if hasattr(initial_password, 'get_plaintext') else 'Generated'
                            })
                        except UserInitialPassword.DoesNotExist:
                            password_data.append({
                                'CTU_ID': user.acc_username,
                                'First_Name': user.f_name,
                                'Last_Name': user.l_name,
                                'Password': 'Not Generated'
                            })
                    
                    # Create Excel file with passwords
                    if password_data:
                        df_passwords = pd.DataFrame(password_data)
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            df_passwords.to_excel(writer, sheet_name='Passwords', index=False)
                        output.seek(0)
                        
                        # Return the Excel file for download
                        response = HttpResponse(
                            output.getvalue(),
                            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                        )
                        response['Content-Disposition'] = f'attachment; filename="alumni_passwords_{batch_year}.xlsx"'
                        return response
                        
                except Exception as e:
                    logger.error(f"Error exporting passwords: {e}")
                    # Continue with normal response if password export fails
            
            return JsonResponse({
                'success': True, 
                'message': f'Import complete. Created: {created_count}, Updated: {updated_count}'
            })
        
        return JsonResponse({'success': False, 'message': 'No file uploaded'}, status=400)
        
    except Exception as e:
        logger.error(f"Error importing alumni Excel: {e}")
        return JsonResponse({'success': False, 'message': f'Import failed: {str(e)}'}, status=500)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def import_exported_alumni_excel(request):
    """
    Import alumni data from an exported Excel file, updating or creating users as needed.
    """
    logger = logging.getLogger(__name__)
    debug_info = []
    try:
        if request.method == 'POST' and request.FILES.get('file'):
            batch_year = request.POST.get('batch_year')  # Optional; Excel may contain per-row year
            df = pd.read_excel(request.FILES['file'])
            created_users = []
            updated_users = []
            for idx, row in df.iterrows():
                ctu_id = row.get('CTU_ID')
                if not ctu_id:
                    debug_info.append(f'Row {idx+2}: Missing CTU_ID, skipped.')
                    continue
                user = User.objects.filter(acc_username=ctu_id).first()
                # Split mappings by model to avoid writing unrelated fields to User directly
                user_fields = {
                    'First_Name': 'f_name',
                    'Middle_Name': 'm_name',
                    'Last_Name': 'l_name',
                    'Last_Nam': 'l_name',
                    'Gender': 'gender',
                }
                profile_fields = {
                    'Phone_Number': 'phone_num',
                    'Address': 'address',
                    'Social_Media': 'social_media',
                    'Civil_Status': 'civil_status',
                    'Age': 'age',
                    'Email': 'email',
                    'Birthdate': 'birthdate',
                }
                academic_fields = {
                    'Program_Name': 'program',
                    'Program': 'program',  # Alternative field name
                    'Course': 'program',  # Map Course to Program instead
                    'course': 'program',  # Case-insensitive mapping
                    'COURSE': 'program',  # Case-insensitive mapping
                    'Section': 'section',
                    'Year_Graduated': 'year_graduated',
                    'Pursue further study': 'pursue_further_study',
                    'School name': 'school_name',
                }
                employment_fields = {
                    'Company name current': 'company_name_current',
                    'Company_Name_Current': 'company_name_current',  # Alternative field name
                    'Position current': 'position_current',
                    'Position_Current': 'position_current',  # Alternative field name
                    'Sector current': 'sector_current',
                    'Sector_Current': 'sector_current',  # Alternative field name
                    'Employment duration current': 'employment_duration_current',
                    'Salary current': 'salary_current',
                    'Salary_Current': 'salary_current',  # Alternative field name
                    'Supporting document current': 'supporting_document_current',
                    'Awards recognition current': 'awards_recognition_current',
                    'Supporting document awards recognition': 'supporting_document_awards_recognition',
                    'Unemployment reason': 'unemployment_reason',
                    'Date started': 'date_started',
                }
                updated_fields = []
                try:
                    if user:
                        # Update User core fields
                        for excel_col, model_field in user_fields.items():
                            excel_value = row.get(excel_col)
                            if excel_value and (getattr(user, model_field, None) in (None, '')):
                                setattr(user, model_field, excel_value)
                                updated_fields.append(f'user.{model_field}')
                        user.save()
                        # Update/create Profile
                        profile, _ = UserProfile.objects.get_or_create(user=user)
                        for excel_col, model_field in profile_fields.items():
                            excel_value = row.get(excel_col)
                            if excel_value and (getattr(profile, model_field, None) in (None, '')):
                                if model_field == 'birthdate':
                                    try:
                                        bd = pd.to_datetime(excel_value, errors='coerce').date()
                                        if bd:
                                            setattr(profile, model_field, bd)
                                            updated_fields.append(f'profile.{model_field}')
                                    except Exception:
                                        pass
                                else:
                                    setattr(profile, model_field, excel_value)
                                    updated_fields.append(f'profile.{model_field}')
                        profile.save()
                        # Update/create AcademicInfo
                        academic, _ = AcademicInfo.objects.get_or_create(user=user)
                        for excel_col, model_field in academic_fields.items():
                            excel_value = row.get(excel_col)
                            if excel_value and (getattr(academic, model_field, None) in (None, '')):
                                setattr(academic, model_field, excel_value)
                                updated_fields.append(f'academic.{model_field}')
                        academic.save()
                        # Update/create Employment
                        employment, _ = EmploymentHistory.objects.get_or_create(user=user)
                        for excel_col, model_field in employment_fields.items():
                            excel_value = row.get(excel_col)
                            if excel_value and (getattr(employment, model_field, None) in (None, '')):
                                if model_field == 'date_started':
                                    try:
                                        ds = pd.to_datetime(excel_value, errors='coerce').date()
                                        if ds:
                                            setattr(employment, model_field, ds)
                                            updated_fields.append(f'employment.{model_field}')
                                    except Exception:
                                        pass
                                else:
                                    setattr(employment, model_field, excel_value)
                                    updated_fields.append(f'employment.{model_field}')
                        employment.update_job_alignment()
                        employment.save()
                        debug_info.append(f'Row {idx+2}: Updated user {ctu_id} (fields: {", ".join(updated_fields) if updated_fields else "none"})')
                        updated_users.append(ctu_id)
                    else:
                        # Create new user with mappings
                        user_data = {'acc_username': ctu_id}
                        for excel_col, model_field in user_fields.items():
                            excel_value = row.get(excel_col)
                            if excel_value:
                                user_data[model_field] = excel_value
                        # Get alumni account type dynamically
                        try:
                            alumni_account_type = AccountType.objects.get(user=True, admin=False, coordinator=False, peso=False, ojt=False)
                            user_data['account_type'] = alumni_account_type
                            user_data['user_status'] = 'active'
                        except AccountType.DoesNotExist:
                            debug_info.append(f'Row {idx+2}: Alumni account type not found for {ctu_id}')
                            continue
                        user = User.objects.create(**user_data)
                        # Generate and store initial password
                        alphabet = string.ascii_letters + string.digits
                        password_raw = ''.join(secrets.choice(alphabet) for _ in range(12))
                        user.set_password(password_raw)
                        user.save()
                        try:
                            up, _ = UserInitialPassword.objects.get_or_create(user=user)
                            up.set_plaintext(password_raw)
                            up.is_active = True
                            up.save()
                        except Exception:
                            pass
                        # Create related models
                        profile_kwargs = {}
                        for excel_col, model_field in profile_fields.items():
                            excel_value = row.get(excel_col)
                            if excel_value:
                                if model_field == 'birthdate':
                                    try:
                                        bd = pd.to_datetime(excel_value, errors='coerce').date()
                                        if bd:
                                            profile_kwargs[model_field] = bd
                                    except Exception:
                                        pass
                                else:
                                    profile_kwargs[model_field] = excel_value
                        if profile_kwargs:
                            UserProfile.objects.create(user=user, **profile_kwargs)
                        academic_kwargs = {}
                        for excel_col, model_field in academic_fields.items():
                            excel_value = row.get(excel_col)
                            if excel_value:
                                if excel_col == 'Course' or excel_col == 'course' or excel_col == 'COURSE':
                                    print(f"DEBUG: Found Course column '{excel_col}' with value '{excel_value}' for user {user.acc_username}")
                                academic_kwargs[model_field] = excel_value
                        # Always set at least batch year if convertible
                        if batch_year and str(batch_year).isdigit():
                            academic_kwargs.setdefault('year_graduated', int(batch_year))
                        if academic_kwargs:
                            AcademicInfo.objects.create(user=user, **academic_kwargs)
                        employment_kwargs = {}
                        for excel_col, model_field in employment_fields.items():
                            excel_value = row.get(excel_col)
                            if excel_value:
                                if model_field == 'date_started':
                                    try:
                                        ds = pd.to_datetime(excel_value, errors='coerce').date()
                                        if ds:
                                            employment_kwargs[model_field] = ds
                                    except Exception:
                                        pass
                                else:
                                    employment_kwargs[model_field] = excel_value
                        if employment_kwargs:
                            EmploymentHistory.objects.create(user=user, **employment_kwargs)
                        created_users.append({'CTU_ID': ctu_id, 'Password': password_raw})
                except Exception as e:
                    debug_info.append(f'Row {idx+2}: Error for CTU_ID {ctu_id}: {str(e)}')
            # If we created users, return an Excel file of their passwords
            if created_users:
                df_pw = pd.DataFrame(created_users)
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_pw.to_excel(writer, sheet_name='Passwords', index=False)
                output.seek(0)
                response = HttpResponse(
                    output.getvalue(),
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                response['Content-Disposition'] = 'attachment; filename="imported_alumni_passwords.xlsx"'
                return response
            return JsonResponse({'success': True, 'message': 'Import complete', 'debug': debug_info, 'created': len(created_users), 'updated': len(updated_users)})
        return JsonResponse({'success': False, 'message': 'No file uploaded'}, status=400)
    except Exception as e:
        logger.error(f"Error importing exported alumni Excel: {e}")
        return JsonResponse({'success': False, 'message': 'Import failed'}, status=500)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_initial_passwords(request):
    """
    Export initial passwords for alumni accounts to Excel.
    This function exports usernames and their corresponding initial passwords.
    """
    try:
        # Get all alumni users with their stored initial passwords
        alumni = User.objects.filter(account_type__user=True).select_related('initial_password')
        
        # Prepare data for export
        password_data = []
        for alum in alumni:
            # Get the actual stored password or use default
            initial_password = 'wherenayou2025'  # Default fallback
            if hasattr(alum, 'initial_password') and alum.initial_password:
                initial_password = alum.initial_password.password_encrypted
            
            password_data.append({
                'CTU_ID': alum.acc_username,
                'First_Name': alum.f_name,
                'Last_Name': alum.l_name,
                'Email': getattr(alum, 'email', ''),
                'Initial_Password': initial_password
            })
        
        if not password_data:
            return JsonResponse({'success': False, 'message': 'No alumni found'}, status=404)
        
        # Create DataFrame and export to Excel
        df = pd.DataFrame(password_data)
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Initial_Passwords', index=False)
        
        output.seek(0)
        
        # Create response with Excel file
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="alumni_initial_passwords.xlsx"'
        
        return response
        
    except Exception as e:
        logger.error(f"Error exporting initial passwords: {e}")
        return JsonResponse({'success': False, 'message': f'Export failed: {str(e)}'}, status=500)
