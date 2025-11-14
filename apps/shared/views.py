from django.shortcuts import render
import pandas as pd
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.http import JsonResponse
import os
from .models import User, TrackerResponse, Question
from io import BytesIO
import logging

# Create your views here.

# Export alumni data to Excel

def export_alumni_excel(request):
    batch_year = request.GET.get('batch_year')
    alumni = User.objects.filter(account_type__user=True)
    if batch_year:
        alumni = alumni.filter(year_graduated=batch_year)

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

# Import alumni data from Excel, updating only missing fields
@csrf_exempt
def import_alumni_excel(request):
    if request.method == 'POST' and request.FILES.get('file'):
        batch_year = request.POST.get('batch_year')
        if not batch_year:
            return JsonResponse({'success': False, 'message': 'Batch year is required'}, status=400)
        df = pd.read_excel(request.FILES['file'])
        for _, row in df.iterrows():
            ctu_id = row.get('CTU_ID')
            if not ctu_id:
                continue
            # Try to find user by CTU ID and batch year
            user = User.objects.filter(acc_username=ctu_id, year_graduated=batch_year).first()
            field_map = {
                'First_Name': 'f_name',
                'Middle_Name': 'm_name',
                'Last_Name': 'l_name',
                'Gender': 'gender',
                'Phone_Number': 'phone_num',
                'Address': 'address',
                'Social Media Acc Link': 'social_media',
                'Civil Status': 'civil_status',
                'Company name current': 'company_name_current',
                'salary current': 'salary_current',
                'Post Graduate Degree': 'post_graduate_degree',
                # Add more mappings as needed
            }
            if user:
                # Only update fields that are empty in DB and present in Excel
                for excel_col, model_field in field_map.items():
                    excel_value = row.get(excel_col)
                    if excel_value and (not hasattr(user, model_field) or not getattr(user, model_field) or getattr(user, model_field) == ''):
                        setattr(user, model_field, excel_value)
                user.save()
            else:
                # Create new user for this batch
                user_data = {
                    'acc_username': ctu_id,
                    'year_graduated': batch_year,
                    # Set all fields from Excel if present
                }
                for excel_col, model_field in field_map.items():
                    excel_value = row.get(excel_col)
                    if excel_value:
                        user_data[model_field] = excel_value
                user_data['account_type_id'] = 1  # Default to alumni account type
                User.objects.create(**user_data)
        return JsonResponse({'success': True, 'message': 'Import complete'})
    return JsonResponse({'success': False, 'message': 'No file uploaded'}, status=400)

@csrf_exempt
def import_exported_alumni_excel(request):
    logger = logging.getLogger(__name__)
    debug_info = []
    if request.method == 'POST' and request.FILES.get('file'):
        batch_year = request.POST.get('batch_year')
        if not batch_year:
            return JsonResponse({'success': False, 'message': 'Batch year is required'}, status=400)
        df = pd.read_excel(request.FILES['file'])
        for idx, row in df.iterrows():
            ctu_id = row.get('CTU_ID')
            if not ctu_id:
                debug_info.append(f'Row {idx+2}: Missing CTU_ID, skipped.')
                continue
            user = User.objects.filter(acc_username=ctu_id, year_graduated=batch_year).first()
            field_map = {
                'First_Name': 'f_name',
                'Middle_Name': 'm_name',
                'Last_Name': 'l_name',
                'Gender': 'gender',
                'Phone_Number': 'phone_num',
                'Address': 'address',
                'Social_Media': 'social_media',
                'Civil_Status': 'civil_status',
                'Age': 'age',
                'Email': 'email',
                'Program_Name': 'program',
                'Status': 'status',
                'Company name current': 'company_name_current',
                'Position current': 'position_current',
                'Sector current': 'sector_current',
                'Employment duration current': 'employment_duration_current',
                'Salary current': 'salary_current',
                'Supporting document current': 'supporting_document_current',
                'Awards recognition current': 'awards_recognition_current',
                'Supporting document awards recognition': 'supporting_document_awards_recognition',
                'Unemployment reason': 'unemployment_reason',
                'Pursue further study': 'pursue_further_study',
                'Date started': 'date_started',
                'School name': 'school_name',
                'Birthdate': 'birthdate',
            }
            updated_fields = []
            try:
                if user:
                    for excel_col, model_field in field_map.items():
                        excel_value = row.get(excel_col)
                        if excel_value and (not hasattr(user, model_field) or not getattr(user, model_field) or getattr(user, model_field) == ''):
                            setattr(user, model_field, excel_value)
                            updated_fields.append(model_field)
                    user.save()
                    debug_info.append(f'Row {idx+2}: Updated user {ctu_id} (fields: {", ".join(updated_fields) if updated_fields else "none"})')
                else:
                    user_data = {'acc_username': ctu_id, 'year_graduated': batch_year}
                    for excel_col, model_field in field_map.items():
                        excel_value = row.get(excel_col)
                        if excel_value:
                            user_data[model_field] = excel_value
                    user_data['account_type_id'] = 1
                    User.objects.create(**user_data)
                    debug_info.append(f'Row {idx+2}: Created new user {ctu_id}')
            except Exception as e:
                debug_info.append(f'Row {idx+2}: Error for CTU_ID {ctu_id}: {str(e)}')
        return JsonResponse({'success': True, 'message': 'Import complete', 'debug': debug_info})
    return JsonResponse({'success': False, 'message': 'No file uploaded'}, status=400)
