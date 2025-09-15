"""
API endpoints for authentication, alumni, OJT, notifications, posts, and related features.
Uses shared models and serializers for data representation. If this file continues to grow, consider splitting endpoints into submodules (e.g., auth_views.py, alumni_views.py, ojt_views.py, post_views.py).
"""

import logging
logger = logging.getLogger(__name__)

from django.conf import settings
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.core.files.storage import default_storage
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils.dateparse import parse_date
from apps.shared.models import User, AccountType, OJTImport, Notification, Post, PostCategory, Like, Comment, Repost, UserProfile, AcademicInfo, EmploymentHistory, TrackerData, OJTInfo, UserInitialPassword
from apps.shared.services import UserService
from apps.shared.serializers import UserSerializer, AlumniListSerializer, UserCreateSerializer
import json
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from datetime import datetime
import secrets
import string
import base64
from rest_framework_simplejwt.tokens import RefreshToken
import pandas as pd
import io
import os
from django.core.files.uploadedfile import InMemoryUploadedFile
from collections import Counter
from apps.shared.models import Question
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Value, CharField, Q
from django.db import connection
from django.db.utils import ProgrammingError
from django.db.models.functions import Concat, Coalesce
from rest_framework.decorators import api_view
import tempfile
from django.http import FileResponse
from django.db import transaction

# --- Helpers for Posts ---
def ensure_default_post_categories():
    """Ensure minimal post categories exist to avoid 400s when DB is empty.
    Returns a mapping of category names to instances and a default instance.
    """
    try:
        if PostCategory.objects.count() == 0:
            PostCategory.objects.create(events=False, announcements=False, donation=False, personal=True)
            PostCategory.objects.create(events=True, announcements=False, donation=False, personal=False)
            PostCategory.objects.create(events=False, announcements=True, donation=False, personal=False)
            PostCategory.objects.create(events=False, announcements=False, donation=True, personal=False)
        # Choose a sensible default (personal if present, else first)
        default = PostCategory.objects.filter(personal=True).first() or PostCategory.objects.first()
        return default
    except Exception:
        return None

@ensure_csrf_cookie
def get_csrf_token(request):
    return JsonResponse({'success': True, 'message': 'CSRF cookie set'})

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

# Utility: build profile_pic URL with cache-busting when possible
def build_profile_pic_url(user):
    try:
        # Use refactored profile model
        profile = getattr(user, 'profile', None)
        pic = getattr(profile, 'profile_pic', None) if profile else None
        if pic:
            url = pic.url
            try:
                modified = default_storage.get_modified_time(pic.name)
                if modified:
                    return f"{url}?t={int(modified.timestamp())}"
            except Exception:
                pass
            return url
    except Exception:
        pass
    return None

# Utility: extract current user from Authorization header (Bearer/JWT) robustly
def get_current_user_from_request(request):
    auth_header = request.headers.get('Authorization') or request.META.get('HTTP_AUTHORIZATION')
    if not auth_header:
        return None
    try:
        parts = auth_header.strip().split()
        token = None
        if len(parts) == 2:
            # Format: "Bearer <token>" or "JWT <token>"
            token = parts[1].strip('"')
        else:
            # Sometimes the raw token may be provided
            token = parts[0].strip('"')
        if not token:
            return None
        from rest_framework_simplejwt.tokens import AccessToken
        access_token = AccessToken(token)
        current_user_id = access_token.get('user_id') or access_token.get('id')
        if not current_user_id:
            return None
        return User.objects.get(user_id=int(current_user_id))
    except Exception:
        return None

# Note: Passwords must be provided as plaintext credentials. Legacy birthdate-based
# login has been removed. All authentication uses securely hashed passwords.

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def login_view(request):
    """
    Authenticate a user using acc_username and acc_password. Returns user info and account type on success.
    """
    if request.method == "OPTIONS":
        response = JsonResponse({'detail': 'OK'})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken"
        return response
    try:
        data = json.loads(request.body)
        acc_username = data.get('acc_username')
        acc_password = data.get('acc_password')
        if not acc_username or not acc_password:
            return JsonResponse({'success': False, 'message': 'Missing credentials'}, status=400)
        try:
            user = User.objects.get(acc_username=acc_username)
        except User.DoesNotExist:
            logger.warning(f"Login failed: user {acc_username} does not exist.")
            return JsonResponse({'success': False, 'message': 'Invalid credentials'}, status=401)
        if not user.check_password(acc_password):
            logger.warning(f"Login failed: invalid password for user {acc_username}.")
            return JsonResponse({'success': False, 'message': 'Invalid credentials'}, status=401)
        academic = getattr(user, 'academic_info', None)
        profile = getattr(user, 'profile', None)
        return JsonResponse({
            'success': True,
            'message': 'Login successful',
            'user': {
                'id': user.user_id,
                'name': f"{user.f_name} {user.l_name}",
                'year_graduated': getattr(academic, 'year_graduated', None) if academic else None,
                'profile_bio': getattr(profile, 'profile_bio', None) if profile else None,
                'profile_pic': build_profile_pic_url(user),
                'account_type': {
                    'admin': user.account_type.admin,
                    'peso': user.account_type.peso,
                    'user': user.account_type.user,
                    'coordinator': user.account_type.coordinator,
                    'ojt': user.account_type.ojt,
                }
            }
        })
    except json.JSONDecodeError:
        logger.error("Login failed: Invalid JSON in request body.")
        return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Login failed: Unexpected error: {e}")
        return JsonResponse({'success': False, 'message': 'Server error'}, status=500)

class CustomTokenObtainPairSerializer(serializers.Serializer):
    acc_username = serializers.CharField()
    acc_password = serializers.CharField()

    def validate(self, attrs):
        acc_username = attrs.get('acc_username')
        acc_password = attrs.get('acc_password')
        if acc_password is None:
            raise serializers.ValidationError('Password is required')
        try:
            user = User.objects.get(acc_username=acc_username)
        except User.DoesNotExist:
            raise serializers.ValidationError('Invalid credentials')

        # Hashed password only
        if not user.check_password(acc_password):
            raise serializers.ValidationError('Invalid credentials')
        refresh = RefreshToken.for_user(user)
        academic = getattr(user, 'academic_info', None)
        profile = getattr(user, 'profile', None)
        data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': user.user_id,
                'name': f"{user.f_name} {user.l_name}",
                'year_graduated': getattr(academic, 'year_graduated', None) if academic else None,
                'profile_bio': getattr(profile, 'profile_bio', None) if profile else None,
                'profile_pic': build_profile_pic_url(user),
                'account_type': {
                    'admin': user.account_type.admin,
                    'peso': user.account_type.peso,
                    'user': user.account_type.user,
                    'coordinator': user.account_type.coordinator,
                    'ojt': user.account_type.ojt,
                }
            }
        }
        return data

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def import_alumni_view(request):
    if request.method == "OPTIONS":
        response = JsonResponse({'detail': 'OK'})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken"
        return response

    try:
        if 'file' not in request.FILES:
            return JsonResponse({'success': False, 'message': 'No file uploaded'}, status=400)
        file = request.FILES['file']
        batch_year = request.POST.get('batch_year', '')
        course = request.POST.get('course', '')
        if not file.name.endswith(('.xlsx', '.xls')):
            return JsonResponse({'success': False, 'message': 'Please upload an Excel file (.xlsx or .xls)'}, status=400)
        if not batch_year or not course:
            return JsonResponse({'success': False, 'message': 'Batch year and course are required'}, status=400)
        
        # Read Excel file
        try:
            df = pd.read_excel(file)
            print('HEADERS:', list(df.columns))
            
            # Check if Birthdate column exists before trying to access it
            if 'Birthdate' in df.columns:
                print('DEBUG: Raw birthdate column first 5 rows:')
                print(df['Birthdate'].head())
                print('DEBUG: Birthdate column data types:', df['Birthdate'].dtype)
                
                # Now try to convert birthdate column to proper dates
                try:
                    df['Birthdate'] = pd.to_datetime(df['Birthdate'], errors='coerce')
                    print('DEBUG: After pd.to_datetime conversion:')
                    print(df['Birthdate'].head())
                except Exception as e:
                    print(f"DEBUG: Error converting dates: {e}")
            else:
                print('DEBUG: No Birthdate column found in Excel file')

        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error reading Excel file: {str(e)}'}, status=400)
        
        # Expected columns: keep Birthdate for profile; use Password for login
        required_columns = ['CTU_ID', 'First_Name', 'Last_Name', 'Gender']
        optional_columns = ['Password', 'Birthdate', 'Phone_Number', 'Address', 'Civil Status', 'Social Media']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return JsonResponse({
                'success': False,
                'message': f'Missing required columns: {", ".join(missing_columns)}'
            }, status=400)
        
        # Get alumni account type (user=True) - ensure AccountType is properly imported
        # Get or create alumni account type to avoid failures when it's missing
        from apps.shared.models import AccountType
        alumni_account_type, _ = AccountType.objects.get_or_create(
            user=True,
            admin=False,
            peso=False,
            coordinator=False,
            ojt=False,
        )
        
        created_count = 0
        skipped_count = 0
        errors = []
        exported_passwords = []  # List to collect (username, password) for export
        
        # Ensure an OJT account type exists; create if missing to avoid failures on fresh DBs
        try:
            ojt_account_type, _ = AccountType.objects.get_or_create(
                ojt=True, admin=False, peso=False, user=False, coordinator=False
            )
        except Exception:
            ojt_account_type = None

        for index, row in df.iterrows():
            try:
                ctu_id = str(row['CTU_ID']).strip()
                first_name = str(row['First_Name']).strip()
                middle_name = str(row.get('Middle_Name', '')).strip() if pd.notna(row.get('Middle_Name')) else ''
                last_name = str(row['Last_Name']).strip()
                gender = str(row['Gender']).strip().upper()
                password_raw = str(row.get('Password', '')).strip()
                birthdate_val = row.get('Birthdate') if 'Birthdate' in df.columns else None

                print(f"DEBUG: Row {index + 2} - CTU_ID: {ctu_id}, Name: {first_name} {last_name}")
                phone_number = str(row.get('Phone_Number', '')).strip() if pd.notna(row.get('Phone_Number')) else ''
                address = str(row.get('Address', '')).strip() if pd.notna(row.get('Address')) else ''
                civil_status = str(row.get('Civil Status', '')).strip() if pd.notna(row.get('Civil Status', '')) else ''
                social_media = str(row.get('Social Media', '')).strip() if pd.notna(row.get('Social Media', '')) else ''
                
                # Validate required fields
                if not ctu_id or not first_name or not last_name or not gender:
                    errors.append(f"Row {index + 2}: Missing required fields (CTU_ID, First_Name, Last_Name, Gender)")
                    continue
                
                # Validate gender
                if gender not in ['M', 'F']:
                    errors.append(f"Row {index + 2}: Gender must be 'M' or 'F'")
                    continue
                
                # Determine password: use provided Password column or auto-generate
                if not password_raw:
                    alphabet = string.ascii_letters + string.digits
                    password_raw = ''.join(secrets.choice(alphabet) for _ in range(12))
                
                # Check if user already exists
                if User.objects.filter(acc_username=ctu_id).exists():
                    errors.append(f"Row {index + 2}: CTU ID {ctu_id} already exists (skipped)")
                    skipped_count += 1
                    continue
                
                # Create user and related models securely
                user = User.objects.create(
                    acc_username=ctu_id,
                    user_status='active',
                    f_name=first_name,
                    m_name=middle_name,
                    l_name=last_name,
                    gender=gender,
                    account_type=alumni_account_type,
                )
                user.set_password(password_raw)
                user.save()
                
                # Store initial password (encrypted) for export/sharing
                try:
                    up, _ = UserInitialPassword.objects.get_or_create(user=user)
                    up.set_plaintext(password_raw)
                    up.is_active = True
                    up.save()
                except Exception as e:
                    print(f"DEBUG: Error saving initial password for {ctu_id}: {e}")
                    pass
                
                # Set profile including birthdate if provided
                profile_kwargs = dict(
                    user=user,
                    phone_num=phone_number or None,
                    address=address or None,
                    civil_status=civil_status or None,
                    social_media=social_media or None,
                )
                
                # Parse birthdate if present
                if birthdate_val and pd.notna(birthdate_val):
                    try:
                        bd = pd.to_datetime(birthdate_val, errors='coerce').date()
                        if bd:
                            profile_kwargs['birthdate'] = bd
                    except Exception as e:
                        print(f"DEBUG: Error parsing birthdate for {ctu_id}: {e}")
                
                try:
                    from apps.shared.models import UserProfile, AcademicInfo
                    UserProfile.objects.create(**profile_kwargs)
                    AcademicInfo.objects.create(
                        user=user,
                        year_graduated=int(batch_year) if batch_year.isdigit() else None,
                        course=course,
                    )
                except Exception as e:
                    print(f"DEBUG: Error creating profile/academic info for {ctu_id}: {e}")
                
                exported_passwords.append({
                    'CTU_ID': ctu_id,
                    'First_Name': first_name,
                    'Last_Name': last_name,
                    'Password': password_raw
                })

                created_count += 1
            except Exception as e:
                errors.append(f"Row {index + 2}: Unexpected error: {str(e)}")
                print(f"DEBUG: Error processing row {index + 2}: {e}")
                continue
        # Export passwords to Excel after import
        if exported_passwords:
            df_export = pd.DataFrame(exported_passwords)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
                df_export.to_excel(tmp.name, index=False)
                tmp.seek(0)
                response = FileResponse(open(tmp.name, 'rb'), as_attachment=True, filename='alumni_passwords.xlsx')
                # Add a comment: Only share this file securely with the intended users.
                return response
        return JsonResponse({
            'success': True,
            'message': f'Successfully created {created_count} alumni accounts. Skipped {skipped_count} duplicates.',
            'created_count': created_count,
            'skipped_count': skipped_count,
            'errors': errors
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Server error: {str(e)}'}, status=500)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def alumni_statistics_view(request):
    # Count by year_graduated from AcademicInfo for alumni users (safe even if some lack AcademicInfo)
    year_values = (
        User.objects
        .filter(account_type__user=True)
        .values_list('academic_info__year_graduated', flat=True)
    )
    year_counts = Counter([y for y in year_values if y is not None])
    return JsonResponse({
        'success': True,
        'years': [
            {'year': year, 'count': count}
            for year, count in sorted(year_counts.items(), reverse=True)
        ]
    })

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def alumni_list_view(request):
    alumni = User.objects.filter(account_type__user=True)
    alumni_data = [
        {
            'id': a.user_id,
            'ctu_id': a.acc_username,
            'name': f"{a.f_name} {a.m_name or ''} {a.l_name}",
            'course': getattr(a.academic_info, 'course', None) if hasattr(a, 'academic_info') else None,
            'batch': getattr(a.academic_info, 'year_graduated', None) if hasattr(a, 'academic_info') else None,
            'status': a.user_status,
            'gender': a.gender,
            'birthdate': str(getattr(a.profile, 'birthdate', None)) if hasattr(a, 'profile') and getattr(a, 'profile', None) else None,
            'phone': getattr(a.profile, 'phone_num', None) if hasattr(a, 'profile') and getattr(a, 'profile', None) else None,
            'address': getattr(a.profile, 'address', None) if hasattr(a, 'profile') and getattr(a, 'profile', None) else None,
            'civilStatus': getattr(a.profile, 'civil_status', None) if hasattr(a, 'profile') and getattr(a, 'profile', None) else None,
            'socialMedia': getattr(a.profile, 'social_media', None) if hasattr(a, 'profile') and getattr(a, 'profile', None) else None,
        }
        for a in alumni
    ]
    return JsonResponse({'success': True, 'alumni': alumni_data})

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def send_reminder_view(request):
    import json
    data = json.loads(request.body)
    emails = data.get('emails', [])
    user_ids = data.get('user_ids', [])
    message = data.get('message', '')
    subject = data.get('subject', 'Tracker Form Reminder')
    # Try to get sender name from request.user if authenticated, else fallback
    sender = 'CCICT'  # Always use CCICT as sender for tracker form notifications
    if not (emails or user_ids) or not message:
        return JsonResponse({'success': False, 'message': 'Missing users or message'}, status=400)
    sent = 0
    # Send by user_ids if provided, else by emails
    users = list(User.objects.filter(user_id__in=user_ids)) if user_ids else list(User.objects.filter(email__in=emails))
    tracker_form_base_url = "https://yourdomain.com/tracker/fill"  # Change to your actual domain/path
    for user in users:
        try:
            personalized_message = message.replace('[User\'s Name]', f"{user.f_name} {user.l_name}")
            user_link = f"{tracker_form_base_url}?user={user.user_id}"
            personalized_message = personalized_message.replace('[Tracker Form Link]', user_link)
            Notification.objects.create(
                user=user,
                notif_type=sender,
                notifi_content=personalized_message,
                notif_date=timezone.now(),
                subject=subject
            )
            sent += 1
        except Exception as e:
            continue
    return JsonResponse({'success': True, 'sent': sent, 'total': len(users)})

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def notifications_view(request):
    user_id = request.GET.get('user_id')
    if not user_id:
        return JsonResponse({'success': False, 'message': 'user_id is required'}, status=400)
    try:
        user = User.objects.get(user_id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'User not found'}, status=404)
    # Alumni: show all notifications; OJT: filter out tracker notifications
    if hasattr(user.account_type, 'user') and user.account_type.user:
        notifications = Notification.objects.filter(user_id=user_id).order_by('-notif_date')
    elif hasattr(user.account_type, 'ojt') and user.account_type.ojt:
        notifications = Notification.objects.filter(user_id=user_id).exclude(notif_type__iexact='tracker').order_by('-notif_date')
    else:
        notifications = Notification.objects.filter(user_id=user_id).exclude(notif_type__iexact='tracker').order_by('-notif_date')
    notif_list = []
    import re
    for n in notifications:
        entry = {
            'id': n.notification_id,
            'type': n.notif_type,
            'subject': getattr(n, 'subject', None) or 'Tracker Form Reminder',
            'content': n.notifi_content,
            'date': n.notif_date.strftime('%Y-%m-%d %H:%M:%S'),
        }
        # Extract follower profile link if present (e.g., /alumni/profile/<id>)
        try:
            match = re.search(r"/alumni/profile/(\d+)", n.notifi_content or '')
            if match:
                follower_id = int(match.group(1))
                entry['link'] = f"/alumni/profile/{follower_id}"
                entry['link_user_id'] = follower_id
        except Exception:
            pass
        notif_list.append(entry)
    return JsonResponse({'success': True, 'notifications': notif_list})

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def notifications_count_view(request):
    user_id = request.GET.get('user_id')
    if not user_id:
        return JsonResponse({'success': False, 'message': 'user_id is required'}, status=400)
    try:
        user = User.objects.get(user_id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'User not found'}, status=404)

    # Count notifications based on user type
    if hasattr(user.account_type, 'user') and user.account_type.user:
        count = Notification.objects.filter(user_id=user_id).count()
    elif hasattr(user.account_type, 'ojt') and user.account_type.ojt:
        count = Notification.objects.filter(user_id=user_id).exclude(notif_type__iexact='tracker').count()
    else:
        count = Notification.objects.filter(user_id=user_id).exclude(notif_type__iexact='tracker').count()

    return JsonResponse({'success': True, 'count': count})

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def users_list_view(request):
    user = request.user
    # Allow any authenticated user to fetch suggested users
    current_user_id = request.GET.get('current_user_id')
    try:
        # Parse current_user_id to int if possible for safety
        try:
            current_user_id_int = int(current_user_id) if current_user_id is not None else None
        except (TypeError, ValueError):
            current_user_id_int = None

        # Exclude admin users and the current logged-in user, randomize and limit
        users_qs = (
            User.objects
            .filter(account_type__admin=False)
            .select_related('profile', 'academic_info')
        )
        if current_user_id_int is not None:
            users_qs = users_qs.exclude(user_id=current_user_id_int)
        users = users_qs.order_by('?')[:10]
        users_data = []
        for u in users:
            try:
                users_data.append({
                    'id': u.user_id,
                    'name': f"{u.f_name} {u.l_name}",
                    'profile_pic': build_profile_pic_url(u),
                    'batch': getattr(u.academic_info, 'year_graduated', None),
                })
            except Exception:
                continue
        return JsonResponse({'success': True, 'users': users_data})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def delete_notifications_view(request):
    import json
    try:
        data = json.loads(request.body)
        notif_ids = data.get('notification_ids', [])
        if not notif_ids:
            return JsonResponse({'success': False, 'message': 'No notification IDs provided'}, status=400)
        from apps.shared.models import Notification
        deleted, _ = Notification.objects.filter(notification_id__in=notif_ids).delete()
        return JsonResponse({'success': True, 'deleted': deleted})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

# OJT-specific import function for coordinators
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def import_ojt_view(request):
    print("IMPORT OJT VIEW CALLED")  # Debug print
    if request.method == "OPTIONS":
        response = JsonResponse({'detail': 'OK'})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken"
        return response

    try:
        if 'file' not in request.FILES:
            return JsonResponse({'success': False, 'message': 'No file uploaded'}, status=400)

        file = request.FILES['file']
        batch_year = request.POST.get('batch_year', '')
        course = request.POST.get('course', '')
        coordinator_username = request.POST.get('coordinator_username', '')

        if not file.name.endswith(('.xlsx', '.xls')):
            return JsonResponse({'success': False, 'message': 'Please upload an Excel file (.xlsx or .xls)'}, status=400)

        if not batch_year or not course or not coordinator_username:
            return JsonResponse({'success': False, 'message': 'Batch year, course, and coordinator username are required'}, status=400)

        # Read Excel file
        try:
            df = pd.read_excel(file)
            print('OJT IMPORT - HEADERS:', list(df.columns))
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error reading Excel file: {str(e)}'}, status=400)

        # Normalize flexible header names for common variants
        try:
            df.rename(columns={
                'Company Name': 'Company',
                'company name': 'Company',
                'company': 'Company',
                'company_name': 'Company',
                'OJT_Start_Date': 'Ojt_Start_Date',
                'OJT_End_Date': 'Ojt_End_Date',
                'ojt_start_date': 'Ojt_Start_Date',
                'ojt_end_date': 'Ojt_End_Date',
                'Civil Status': 'Civil_Status',
                'Social Media': 'Social_Media',
            }, inplace=True)
        except Exception:
            pass

        # OJT-specific required columns: keep Birthdate; Password is optional and can be generated
        required_columns = ['CTU_ID', 'First_Name', 'Last_Name', 'Gender']
        optional_columns = ['Password', 'Birthdate', 'Phone_Number', 'Address', 'Civil_Status', 'Social_Media']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return JsonResponse({
                'success': False,
                'message': f'Missing required OJT columns: {", ".join(missing_columns)}'
            }, status=400)
        # OJT_Company and OJT_Position are now optional

        # Create import record
        # Normalize batch_year to a single 4-digit year if possible
        try:
            import re
            match = re.search(r"(20\d{2})", str(batch_year))
            normalized_year = int(match.group(1)) if match else int(str(batch_year).strip())
        except Exception:
            normalized_year = batch_year

        import_record = OJTImport.objects.create(
            coordinator=coordinator_username,
            batch_year=normalized_year,
            course=course,
            file_name=file.name
        )

        created_count = 0
        skipped_count = 0
        errors = []
        exported_passwords = []  # List to collect (username, password) for export
        total_rows = int(getattr(df, 'shape', [0])[0] or 0)

        # Ensure OJT account type exists for new OJT users
        try:
            ojt_account_type, _ = AccountType.objects.get_or_create(
                admin=False,
                peso=False,
                user=False,
                coordinator=False,
                ojt=True,
            )
        except Exception:
            ojt_account_type = None

        for index, row in df.iterrows():
            print(f"--- Processing Row {index+2} ---")
            try:
                # --- Field Extraction and Cleaning ---
                ctu_id = str(row.get('CTU_ID', '')).strip()
                first_name = str(row.get('First_Name', '')).strip()
                middle_name = str(row.get('Middle_Name', '')).strip() if pd.notna(row.get('Middle_Name')) else ''
                last_name = str(row.get('Last_Name', '')).strip()
                gender = str(row.get('Gender', '')).strip().upper()

                # --- Password Handling (no birthdate login) ---
                password_raw = str(row.get('Password', '')).strip()
                if not password_raw:
                    alphabet = string.ascii_letters + string.digits
                    password_raw = ''.join(secrets.choice(alphabet) for _ in range(12))

                # --- Age not derived from password; keep None unless separately provided
                age = None

                # --- Parse OJT Start/End Dates ---
                ojt_start_date = None
                ojt_end_date = None

                # Try different possible column names for start date
                start_date_raw = row.get('Ojt_Start_Date') or row.get('Start_Date')
                print(f"Row {index+2} - Raw Start Date: '{start_date_raw}', Type: {type(start_date_raw)}")
                if pd.notna(start_date_raw):
                    try:
                        ojt_start_date = pd.to_datetime(start_date_raw, dayfirst=True).date()
                        print(f"Row {index+2} - Parsed start date successfully: {ojt_start_date}")
                    except Exception as e:
                        print(f"Row {index+2} - FAILED to parse start date. Error: {e}")
                        ojt_start_date = None

                # Try different possible column names for end date
                end_date_raw = row.get('Ojt_End_Date') or row.get('End_Date')
                print(f"Row {index+2} - Raw End Date: '{end_date_raw}', Type: {type(end_date_raw)}")
                if pd.notna(end_date_raw):
                    try:
                        ojt_end_date = pd.to_datetime(end_date_raw, dayfirst=True).date()
                        print(f"Row {index+2} - Parsed end date successfully: {ojt_end_date}")
                    except Exception as e:
                        print(f"Row {index+2} - FAILED to parse end date. Error: {e}")
                        ojt_end_date = None

                # --- Validation Check ---
                required_data = {
                    "CTU_ID": ctu_id,
                    "First_Name": first_name,
                    "Last_Name": last_name,
                    "Gender": gender
                }
                missing_fields = [key for key, value in required_data.items() if not value]

                if missing_fields:
                    error_msg = f"Row {index + 2}: Missing or invalid required fields - {', '.join(missing_fields)}"
                    print(f"SKIPPING: {error_msg}")
                    errors.append(error_msg)
                    skipped_count += 1
                    continue

                # --- Gender Validation ---
                if gender not in ['M', 'F']:
                    error_msg = f"Row {index + 2}: Gender must be 'M' or 'F', but was '{gender}'"
                    print(f"SKIPPING: {error_msg}")
                    errors.append(error_msg)
                    skipped_count += 1
                    continue

                # If a user with this CTU_ID already exists, update academic year/course
                existing_user = User.objects.filter(acc_username=ctu_id).first()
                if existing_user:
                    try:
                        # Ensure related models exist
                        from apps.shared.models import UserProfile, AcademicInfo, OJTInfo, EmploymentHistory
                        profile, _ = UserProfile.objects.get_or_create(user=existing_user)
                        academic, _ = AcademicInfo.objects.get_or_create(user=existing_user)
                        ojt_info, _ = OJTInfo.objects.get_or_create(user=existing_user)
                        employment, _ = EmploymentHistory.objects.get_or_create(user=existing_user)

                        # Update names to match latest import where present
                        if first_name:
                            existing_user.f_name = first_name
                        if middle_name:
                            existing_user.m_name = middle_name
                        if last_name:
                            existing_user.l_name = last_name
                        if gender:
                            existing_user.gender = gender
                        existing_user.save()

                        # Update academic info from batch and course
                        # Save normalized batch year
                        try:
                            academic.year_graduated = int(normalized_year)
                        except Exception:
                            pass
                        if course:
                            academic.course = course
                        academic.save()

                        # Update profile birthdate if present
                        if pd.notna(row.get('Birthdate')):
                            try:
                                bd = pd.to_datetime(row.get('Birthdate'), errors='coerce').date()
                                if bd:
                                    profile.birthdate = bd
                            except Exception:
                                pass
                        profile.save()

                        # Update employment company and start date from spreadsheet
                        company_name = (
                            row.get('Company Name')
                            or row.get('Company')
                            or row.get('Company name current')
                        )
                        if pd.notna(company_name) and str(company_name).strip():
                            employment.company_name_current = str(company_name).strip()
                        if 'ojt_start_date' in locals() and ojt_start_date:
                            employment.date_started = ojt_start_date
                        employment.save()

                        # Update OJT info (status, dates if parsed)
                        ojt_info.ojtstatus = str(row.get('Status') or row.get('status') or '').strip() or ojt_info.ojtstatus
                        # Start/End already parsed above if available
                        if 'ojt_start_date' in locals() and ojt_start_date:
                            # model has only end date field; keep for future extension
                            pass
                        if 'ojt_end_date' in locals() and ojt_end_date:
                            ojt_info.ojt_end_date = ojt_end_date
                        ojt_info.save()

                        # Count as updated instead of skipped
                        skipped_count += 0
                        created_count += 0
                        continue
                    except Exception as _e:
                        # Fall through to try creating a new one if update fails
                        print(f"Row {index+2} - failed to update existing user {ctu_id}: {_e}")

                # --- Create OJT user securely ---
                ojt_user = User.objects.create(
                    acc_username=ctu_id,
                    user_status='active',
                    f_name=first_name,
                    m_name=middle_name,
                    l_name=last_name,
                    gender=gender,
                    account_type=ojt_account_type or AccountType.objects.get(ojt=True, admin=False, peso=False, user=False, coordinator=False),
                )
                ojt_user.set_password(password_raw)
                ojt_user.save()
                # Store initial password (encrypted)
                try:
                    up, _ = UserInitialPassword.objects.get_or_create(user=ojt_user)
                    up.set_plaintext(password_raw)
                    up.is_active = True
                    up.save()
                except Exception:
                    pass
                from apps.shared.models import UserProfile, AcademicInfo, EmploymentHistory, OJTInfo
                birthdate_val = row.get('Birthdate')
                profile_kwargs = dict(
                    user=ojt_user,
                    age=None,
                    phone_num=str(row.get('Phone_Number', '')).strip() if pd.notna(row.get('Phone_Number')) else None,
                    address=str(row.get('Address', '')).strip() if pd.notna(row.get('Address')) else None,
                    civil_status=str(row.get('Civil_Status', '')).strip() if pd.notna(row.get('Civil_Status')) else None,
                    social_media=str(row.get('Social_Media', '')).strip() if pd.notna(row.get('Social_Media')) else None,
                )
                if pd.notna(birthdate_val):
                    try:
                        bd = pd.to_datetime(birthdate_val, errors='coerce').date()
                    except Exception:
                        bd = None
                    if bd:
                        profile_kwargs['birthdate'] = bd
                UserProfile.objects.create(**profile_kwargs)
                # Employment: company name
                company_name_new = (
                    row.get('Company Name')
                    or row.get('Company')
                    or row.get('Company name current')
                )
                if pd.notna(company_name_new) and str(company_name_new).strip():
                    EmploymentHistory.objects.create(
                        user=ojt_user,
                        company_name_current=str(company_name_new).strip(),
                        date_started=ojt_start_date if 'ojt_start_date' in locals() else None,
                    )
                AcademicInfo.objects.create(
                    user=ojt_user,
                    year_graduated=int(normalized_year) if str(normalized_year).isdigit() else None,
                    course=course,
                )
                # Create OJT info
                try:
                    OJTInfo.objects.create(
                        user=ojt_user,
                        ojt_end_date=ojt_end_date,
                        ojtstatus=str(row.get('Status') or row.get('status') or '').strip() or None,
                    )
                except Exception:
                    pass
                exported_passwords.append({
                    'CTU_ID': ctu_id,
                    'First_Name': first_name,
                    'Last_Name': last_name,
                    'Password': password_raw
                })

                print(f"SUCCESS: Created OJT record for CTU_ID {ctu_id}")
                created_count += 1

            except Exception as e:
                error_msg = f"Row {index + 2}: An unexpected error occurred - {str(e)}"
                print(f"ERROR: {error_msg}")
                errors.append(error_msg)
                skipped_count += 1
                continue

        # Update import record
        import_record.records_imported = total_rows
        if errors:
            import_record.status = 'Partial' if created_count > 0 else 'Failed'
        import_record.save()

        # Export passwords to Excel after import
        if exported_passwords:
            # Ensure the import record reflects counts before any early return
            import_record.records_imported = total_rows
            if errors:
                import_record.status = 'Partial' if created_count > 0 else 'Failed'
            import_record.save()

            df_export = pd.DataFrame(exported_passwords)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
                df_export.to_excel(tmp.name, index=False)
                tmp.seek(0)
                response = FileResponse(open(tmp.name, 'rb'), as_attachment=True, filename='ojt_passwords.xlsx')
                # Add a comment: Only share this file securely with the intended users.
                return response

        return JsonResponse({
            'success': True,
            'message': f'OJT import completed. Created: {created_count}, Skipped: {skipped_count}',
            'created_count': created_count,
            'skipped_count': skipped_count,
            'errors': errors[:10]  # Limit errors to first 10
        })

    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Import failed: {str(e)}'}, status=500)

# OJT statistics for coordinators
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ojt_statistics_view(request):
    try:
        coordinator_username = request.GET.get('coordinator', '')

        # Build cards from OJT users' academic years and also any years from OJTImport
        users_qs = User.objects.filter(account_type__ojt=True).select_related('academic_info')
        years_to_counts = {}
        for u in users_qs:
            try:
                year = getattr(u.academic_info, 'year_graduated', None)
                if year is None:
                    continue
                years_to_counts[year] = years_to_counts.get(year, 0) + 1
            except Exception:
                continue

        # Also include any batch years that were imported, so a card appears immediately after import
        try:
            from apps.shared.models import OJTImport
            for imp in OJTImport.objects.all():
                y = getattr(imp, 'batch_year', None)
                if y is None:
                    continue
                if y not in years_to_counts:
                    # Show at least 1 so a card appears; clicking will query users by year
                    years_to_counts[y] = max(int(getattr(imp, 'records_imported', 0) or 1), 1)
        except Exception:
            pass

        years_list = [{'year': y, 'count': c} for y, c in years_to_counts.items()]
        years_list.sort(key=lambda x: (x['year'] is None, x['year'] or 0), reverse=True)

        return JsonResponse({'success': True, 'years': years_list, 'total_records': sum(years_to_counts.values())})

    except Exception as e:
        return JsonResponse({'success': True, 'years': [], 'total_records': 0, 'note': str(e)})

# OJT data by year for coordinators
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ojt_by_year_view(request):
    try:
        year = request.GET.get('year', '')
        coordinator_username = request.GET.get('coordinator', '')

        if not year:
            return JsonResponse({'success': False, 'message': 'Year parameter is required'}, status=400)

        # Be lenient: extract a 4-digit year from the string (e.g., "2025 ", "2025-2026")
        try:
            import re
            match = re.search(r"(20\d{2})", str(year))
            year_int = int(match.group(1)) if match else int(str(year).strip())
        except Exception:
            return JsonResponse({'success': False, 'message': 'Invalid year parameter'}, status=400)

        # Include all users for the batch year so data shows even if they were not created as OJT type
        ojt_data = (
            User.objects
            .filter(academic_info__year_graduated=year_int)
            .select_related('profile', 'academic_info', 'ojt_info')
            .order_by('l_name', 'f_name')
        )

        # Fallbacks to avoid empty UI and help coordinators verify recent imports
        if not ojt_data.exists():
            # 1) Prefer recently created/updated users (likely the ones just imported)
            try:
                recent_since = timezone.now() - timezone.timedelta(days=1)
                recent_users = (
                    User.objects
                    .filter(updated_at__gte=recent_since)
                    .select_related('profile', 'academic_info', 'ojt_info')
                    .order_by('-updated_at', 'l_name', 'f_name')
                )
            except Exception:
                recent_users = User.objects.none()

            if recent_users.exists():
                ojt_data = recent_users
            else:
                # 2) As a last resort, show all OJT-type users
                ojt_data = (
                    User.objects
                    .filter(account_type__ojt=True)
                    .select_related('profile', 'academic_info', 'ojt_info')
                    .order_by('l_name', 'f_name')
                )

        ojt_list = []
        for ojt in ojt_data:
            ojt_list.append({
                'id': ojt.user_id,
                'ctu_id': ojt.acc_username,
                'name': f"{ojt.f_name} {ojt.l_name}",
                'first_name': ojt.f_name,
                'middle_name': ojt.m_name,
                'last_name': ojt.l_name,
                'gender': ojt.gender,
                'birthdate': getattr(ojt.profile, 'birthdate', None),
                'age': getattr(ojt.profile, 'calculated_age', None),
                'phone_number': getattr(ojt.profile, 'phone_num', None),
                'address': getattr(ojt.profile, 'address', None),
                'civil_status': getattr(ojt.profile, 'civil_status', None),
                'social_media': getattr(ojt.profile, 'social_media', None),
                'course': getattr(ojt.academic_info, 'course', None),
                'company': getattr(ojt.employment, 'company_name_current', None),
                'ojt_start_date': None,
                'ojt_end_date': getattr(getattr(ojt, 'ojt_info', None), 'ojt_end_date', None),
                'ojt_status': getattr(getattr(ojt, 'ojt_info', None), 'ojtstatus', None) or 'Pending',
                'batch_year': getattr(ojt.academic_info, 'year_graduated', None),
            })

        return JsonResponse({
            'success': True,
            'ojt_data': ojt_list
        })

    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# Clear OJT data for a specific batch year
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ojt_clear_view(request):
    try:
        data = json.loads(request.body or '{}')
        year = data.get('batch_year')
        if not year:
            return JsonResponse({'success': False, 'message': 'batch_year is required'}, status=400)

        try:
            import re
            match = re.search(r"(20\d{2})", str(year))
            year_int = int(match.group(1)) if match else int(str(year).strip())
        except Exception:
            return JsonResponse({'success': False, 'message': 'Invalid batch_year'}, status=400)

        # Delete AcademicInfo with that year and any OJTInfo for those users
        from apps.shared.models import AcademicInfo, OJTInfo, OJTImport
        with transaction.atomic():
            users_qs = User.objects.filter(academic_info__year_graduated=year_int)
            OJTInfo.objects.filter(user__in=users_qs).delete()
            AcademicInfo.objects.filter(user__in=users_qs, year_graduated=year_int).delete()
            # Remove import records for this batch so the card disappears
            OJTImport.objects.filter(batch_year=year_int).delete()

        return JsonResponse({'success': True, 'message': f'Cleared OJT data for batch {year_int}'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# Update OJT status for a specific user
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ojt_status_update_view(request):
    try:
        data = json.loads(request.body or '{}')
        user_id = data.get('user_id')
        status_val = (data.get('status') or '').strip()
        if not user_id or not status_val:
            return JsonResponse({'success': False, 'message': 'user_id and status are required'}, status=400)
        try:
            user = User.objects.get(user_id=int(user_id))
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'User not found'}, status=404)
        from apps.shared.models import OJTInfo
        ojt_info, _ = OJTInfo.objects.get_or_create(user=user)
        ojt_info.ojtstatus = status_val
        ojt_info.save()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# Clear ALL OJT-related data imported (OJT users, OJTInfo, OJTImport, and AcademicInfo for OJT users)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ojt_clear_all_view(request):
    try:
        from apps.shared.models import OJTImport, OJTInfo, AcademicInfo
        with transaction.atomic():
            # Identify OJT users
            ojt_users = User.objects.filter(account_type__ojt=True)
            # Delete OJTInfo for those users
            OJTInfo.objects.filter(user__in=ojt_users).delete()
            # Delete AcademicInfo for those users
            AcademicInfo.objects.filter(user__in=ojt_users).delete()
            # Optionally delete the users themselves or convert their account type
            # Here, we delete OJT users completely for a clean re-import
            ojt_users.delete()
            # Remove import history to hide cards
            OJTImport.objects.all().delete()
        return JsonResponse({'success': True, 'message': 'All OJT data cleared successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@api_view(["GET","PUT"])
@permission_classes([IsAuthenticated])
def profile_bio_view(request, user_id):
    try:
        user = User.objects.get(user_id=user_id)
        profile = getattr(user, 'profile', None)
        if profile is None:
            from apps.shared.models import UserProfile
            profile, _ = UserProfile.objects.get_or_create(user=user)
        if request.method == "GET":
            return JsonResponse({'profile_bio': profile.profile_bio or ''})
        elif request.method == "PUT":
            data = json.loads(request.body)
            profile.profile_bio = data.get('profile_bio', '')
            profile.save()
            return JsonResponse({'profile_bio': profile.profile_bio})
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)



@api_view(["POST","PUT","DELETE"])
@permission_classes([IsAuthenticated])
def update_resume(request):
    user_id = request.GET.get('user_id')

    if not user_id:
        return JsonResponse({"error": "Missing user_id"}, status=400)

    try:
        user = User.objects.get(user_id=user_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)

    if request.method in ['POST', 'PUT']:
        resume_file = request.FILES.get('resume')
        if not resume_file:
            return JsonResponse({"error": "No resume file uploaded"}, status=400)

        # Optional: File size limit check
        if resume_file.size > 10 * 1024 * 1024:
            return JsonResponse({"error": "Resume file exceeds 10MB limit"}, status=400)

        filename = default_storage.save(f"resumes/{user_id}_{resume_file.name}", resume_file)
        from apps.shared.models import UserProfile
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.profile_resume = filename
        profile.save()
        return JsonResponse({
            "message": "Resume uploaded",
            "resume": profile.profile_resume.url if profile.profile_resume else ""
        })


    elif request.method == 'DELETE':
        from apps.shared.models import UserProfile
        profile, _ = UserProfile.objects.get_or_create(user=user)
        if profile.profile_resume:
            file_path = os.path.join(settings.MEDIA_ROOT, profile.profile_resume.name)
            if os.path.exists(file_path):
                os.remove(file_path)
            profile.profile_resume = None
            profile.save()
            return JsonResponse({"message": "Resume deleted"})
        return JsonResponse({"error": "No resume found"}, status=400)

    return JsonResponse({"error": "Invalid request method"}, status=405)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_resume(request):
    # Delegate to update_resume with DELETE semantics
    return update_resume(request)

@api_view(['PUT'])
@parser_classes([MultiPartParser])
def update_alumni_profile(request):
    user_id = request.GET.get('user_id')
    if not user_id:
        return Response({'message': 'Missing user_id'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(user_id=user_id)
        from apps.shared.models import UserProfile
        profile, _ = UserProfile.objects.get_or_create(user=user)

        bio = request.data.get('bio')
        if bio is not None:
            profile.profile_bio = bio

        if 'profile_pic' in request.FILES:
            profile.profile_pic = request.FILES['profile_pic']

        profile.save()

        return Response({
            'user': {
                'id': user.user_id,
                'name': f"{user.f_name} {user.l_name}",
                'profile_pic': profile.profile_pic.url if profile.profile_pic else None,
                'bio': profile.profile_bio,
            }
        })

    except User.DoesNotExist:
        return Response({'message': 'User not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
def search_alumni(request):
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'results': []})
    # Search by first, middle, or last name (case-insensitive)
    alumni = User.objects.filter(
        Q(f_name__icontains=query) |
        Q(m_name__icontains=query) |
        Q(l_name__icontains=query),
        account_type__user=True
    )[:10]
    results = [
        {
            'id': a.user_id,
            'name': f"{a.f_name} {a.l_name}",
            'profile_pic': a.profile.profile_pic.url if hasattr(a, 'profile') and a.profile and a.profile.profile_pic else None
        }
        for a in alumni
    ]
    return JsonResponse({'results': results})


@api_view(['DELETE'])
def delete_alumni_profile_pic(request):
    user_id = request.GET.get('user_id')
    if not user_id:
        return Response({'message': 'Missing user_id'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(user_id=user_id)
        from apps.shared.models import UserProfile
        profile, _ = UserProfile.objects.get_or_create(user=user)
        if profile.profile_pic:
            # Delete the file from storage
            try:
                file_path = profile.profile_pic.path
            except Exception:
                file_path = None
            profile.profile_pic.delete(save=False)
            profile.profile_pic = None
            profile.save()
            # Also remove local file if path is available
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass
        return Response({'success': True})
    except User.DoesNotExist:
        return Response({'message': 'User not found'}, status=status.HTTP_404_NOT_FOUND)



# mobile side

@api_view(["GET", "PUT", "DELETE"])
@permission_classes([IsAuthenticatedOrReadOnly])
def post_detail_view(request, post_id):
    try:
        post = Post.objects.get(post_id=post_id)
    except Post.DoesNotExist:
        return JsonResponse({'error': 'Post not found'}, status=404)

    if request.method == "GET":
        try:
            # Get repost information for THIS specific post
            reposts = Repost.objects.filter(post=post).select_related('user')
            repost_data = []
            for repost in reposts:
                repost_data.append({
                    'repost_id': repost.repost_id,
                    'repost_date': repost.repost_date.isoformat(),
                    'user': {
                        'user_id': repost.user.user_id,
                        'f_name': repost.user.f_name,
                        'l_name': repost.user.l_name,
                        'profile_pic': build_profile_pic_url(repost.user),
                    }
                })

            # Get comments for THIS specific post
            comments = Comment.objects.filter(post=post).select_related('user').order_by('-date_created')
            comments_data = []
            for comment in comments:
                comments_data.append({
                    'comment_id': comment.comment_id,
                    'comment_content': comment.comment_content,
                    'date_created': comment.date_created.isoformat() if comment.date_created else None,
                    'user': {
                        'user_id': comment.user.user_id,
                        'f_name': comment.user.f_name,
                        'l_name': comment.user.l_name,
                        'profile_pic': build_profile_pic_url(comment.user),
                    }
                })

            # Get likes for THIS specific post with user information
            likes = Like.objects.filter(post=post).select_related('user')
            likes_data = []
            for like in likes:
                likes_data.append({
                    'like_id': like.like_id,
                    'user_id': like.user.user_id,
                    'f_name': like.user.f_name,
                    'l_name': like.user.l_name,
                    'profile_pic': build_profile_pic_url(like.user),
                })

            post_data = {
                'post_id': post.post_id,
                'post_title': post.post_title,
                'post_content': post.post_content,
                'post_image': (post.post_image.url if getattr(post, 'post_image', None) else None),
                'type': post.type,
                'created_at': post.created_at.isoformat() if hasattr(post, 'created_at') else None,
                'likes_count': len(likes_data),
                'comments_count': post.comments.count() if hasattr(post, 'comments') else 0,
                'reposts_count': post.reposts.count() if hasattr(post, 'reposts') else 0,
                'likes': likes_data,
                'reposts': repost_data,
                'comments': comments_data,
                'user': {
                    'user_id': post.user.user_id,
                    'f_name': post.user.f_name,
                    'l_name': post.user.l_name,
                    'profile_pic': build_profile_pic_url(post.user),
                },
                'category': {
                    'post_cat_id': post.post_cat.post_cat_id if getattr(post, 'post_cat', None) else None,
                    'events': post.post_cat.events if getattr(post, 'post_cat', None) else False,
                    'announcements': post.post_cat.announcements if getattr(post, 'post_cat', None) else False,
                    'donation': post.post_cat.donation if getattr(post, 'post_cat', None) else False,
                    'personal': post.post_cat.personal if getattr(post, 'post_cat', None) else False,
                }
            }
            return JsonResponse(post_data)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
def post_like_view(request, post_id):
    try:
        post = Post.objects.get(post_id=post_id)
        user = request.user

        if request.method == "POST":
            # Like the post
            like, created = Like.objects.get_or_create(user=user, post=post)
            if created:
                # Create notification for post owner (only if the liker is not the post owner)
                if user.user_id != post.user.user_id:
                    Notification.objects.create(
                        user=post.user,
                        notif_type='like',
                        subject='Post Liked',
                        notifi_content=f"{user.f_name} {user.l_name} liked your post",
                        notif_date=timezone.now()
                    )
                return JsonResponse({'success': True, 'message': 'Post liked'})
            else:
                return JsonResponse({'success': False, 'message': 'Post already liked'})
        elif request.method == "DELETE":
            # Unlike the post
            try:
                like = Like.objects.get(user=user, post=post)
                like.delete()
                return JsonResponse({'success': True, 'message': 'Post unliked'})
            except Like.DoesNotExist:
                return JsonResponse({'success': False, 'message': 'Post not liked'})
    except Post.DoesNotExist:
        return JsonResponse({'error': 'Post not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def post_edit_view(request, post_id):
    try:
        post = Post.objects.get(post_id=post_id)
        user = request.user

        # Check if user owns the post
        if post.user.user_id != user.user_id:
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        if request.method == "PUT":
            data = json.loads(request.body)
            post_title = data.get('post_title')
            post_content = data.get('post_content')

            if post_title is not None:
                post.post_title = post_title
            if post_content is not None:
                post.post_content = post_content

            post.save()
            return JsonResponse({'success': True, 'message': 'Post updated'})

        elif request.method == "DELETE":
            post.delete()
            return JsonResponse({'success': True, 'message': 'Post deleted'})

    except Post.DoesNotExist:
        return JsonResponse({'error': 'Post not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def comment_edit_view(request, post_id, comment_id):
    try:
        comment = Comment.objects.get(comment_id=comment_id)
        user = request.user

        # Check if user owns the comment
        if comment.user.user_id != user.user_id:
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        if request.method == "PUT":
            data = json.loads(request.body)
            comment_content = data.get('comment_content')

            if comment_content is not None:
                comment.comment_content = comment_content
                comment.save()
                return JsonResponse({'success': True, 'message': 'Comment updated'})
            else:
                return JsonResponse({'error': 'No content provided'}, status=400)

        elif request.method == "DELETE":
            comment.delete()
            return JsonResponse({'success': True, 'message': 'Comment deleted'})

    except Comment.DoesNotExist:
        return JsonResponse({'error': 'Comment not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def post_comments_view(request, post_id):
    try:
        post = Post.objects.get(post_id=post_id)

        if request.method == "GET":
            # Get comments for the post
            comments = Comment.objects.filter(post=post).select_related('user').order_by('-date_created')
            comments_data = []

            for comment in comments:
                comments_data.append({
                    'comment_id': comment.comment_id,
                    'comment_content': comment.comment_content,
                    'date_created': comment.date_created.isoformat(),
                    'user': {
                        'user_id': comment.user.user_id,
                        'f_name': comment.user.f_name,
                        'l_name': comment.user.l_name,
                        'profile_pic': build_profile_pic_url(comment.user),
                    }
                })

            return JsonResponse({'comments': comments_data})
        elif request.method == "POST":
            data = json.loads(request.body)
            user = request.user

            # Create comment
            comment = Comment.objects.create(
                user=user,
                post=post,
                comment_content=data.get('comment_content', ''),
                date_created=timezone.now()
            )

            # Create notification for post owner
            if user.user_id != post.user.user_id:
                Notification.objects.create(
                    user=post.user,
                    notif_type='comment',
                    subject='Post Commented',
                    notifi_content=f"{user.f_name} {user.l_name} commented on your post",
                    notif_date=timezone.now()
                )

            return JsonResponse({
                'success': True,
                'message': 'Comment added',
                'comment_id': comment.comment_id
            })
    except Post.DoesNotExist:
        return JsonResponse({'error': 'Post not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def post_delete_view(request, post_id):
    try:
        post = Post.objects.get(post_id=post_id)
        user = request.user

        # Check if user owns the post
        if post.user.user_id != user.user_id:
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        post.delete()
        return JsonResponse({'success': True, 'message': 'Post deleted'})
    except Post.DoesNotExist:
        return JsonResponse({'error': 'Post not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def post_categories_view(request):
    if request.method == "OPTIONS":
        response = JsonResponse({'detail': 'OK'})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken"
        return response

    try:
        categories = PostCategory.objects.all()
        categories_data = []

        for category in categories:
            categories_data.append({
                'post_cat_id': category.post_cat_id,
                'events': category.events,
                'announcements': category.announcements,
                'donation': category.donation,
                'personal': category.personal,
            })

        return JsonResponse({'categories': categories_data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def post_repost_view(request, post_id):
    if request.method == "OPTIONS":
        response = JsonResponse({'detail': 'OK'})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken, Authorization"
        return response

    try:
        post = Post.objects.get(post_id=post_id)

        # Get user from token
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return JsonResponse({'error': 'Authentication required'}, status=401)

        token = auth_header.split(' ')[1]
        try:
            from rest_framework_simplejwt.tokens import AccessToken
            access_token = AccessToken(token)
            user_id = access_token['user_id']
            user = User.objects.get(user_id=user_id)
        except Exception as e:
            return JsonResponse({'error': 'Invalid token'}, status=401)

        # Check if user already reposted this post
        existing_repost = Repost.objects.filter(user=user, post=post).first()
        if existing_repost:
            return JsonResponse({'error': 'You have already reposted this'}, status=400)

        # Create repost
        repost = Repost.objects.create(
            user=user,
            post=post,
            repost_date=timezone.now()
        )

        # Create notification for post owner (only if the reposter is not the post owner)
        if user.user_id != post.user.user_id:
            Notification.objects.create(
                user=post.user,
                notif_type='repost',
                subject='Post Reposted',
                notifi_content=f"{user.f_name} {user.l_name} reposted your post",
                notif_date=timezone.now()
            )

        return JsonResponse({
            'success': True,
            'repost_id': repost.repost_id,
            'message': 'Post reposted successfully'
        })
    except Post.DoesNotExist:
        return JsonResponse({'error': 'Post not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def repost_delete_view(request, repost_id):
    if request.method == "OPTIONS":
        response = JsonResponse({'detail': 'OK'})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "DELETE, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken, Authorization"
        return response

    try:
        repost = Repost.objects.get(repost_id=repost_id)

        # Get user from token
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return JsonResponse({'error': 'Authentication required'}, status=401)

        token = auth_header.split(' ')[1]
        try:
            from rest_framework_simplejwt.tokens import AccessToken
            access_token = AccessToken(token)
            user_id = access_token['user_id']
            user = User.objects.get(user_id=user_id)
        except Exception as e:
            return JsonResponse({'error': 'Invalid token'}, status=401)

        # Check if user owns the repost
        if repost.user.user_id != user.user_id:
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        repost.delete()
        return JsonResponse({'success': True, 'message': 'Repost deleted'})
    except Repost.DoesNotExist:
        return JsonResponse({'error': 'Repost not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def alumni_followers_view(request, user_id):
    if request.method == "OPTIONS":
        response = JsonResponse({'detail': 'OK'})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken, Authorization"
        return response

    try:
        user = User.objects.get(user_id=user_id)
        from apps.shared.models import Follow
        followers = Follow.objects.filter(following=user).select_related('follower')
        if not followers.exists():
            return JsonResponse({
                'success': True,
                'followers': [],
                'message': 'no followers',
                'count': 0
            })
        followers_data = []
        for follow_obj in followers:
            follower = follow_obj.follower
            followers_data.append({
                'user_id': follower.user_id,
                'ctu_id': follower.acc_username,
                'name': f"{follower.f_name} {follower.l_name}",
                'profile_pic': build_profile_pic_url(follower),
                'followed_at': follow_obj.followed_at.isoformat()
            })
        return JsonResponse({
            'success': True,
            'followers': followers_data,
            'count': len(followers_data)
        })
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def alumni_following_view(request, user_id):
    if request.method == "OPTIONS":
        response = JsonResponse({'detail': 'OK'})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken, Authorization"
        return response

    try:
        user = User.objects.get(user_id=user_id)
        from apps.shared.models import Follow
        following = Follow.objects.filter(follower=user).select_related('following')
        if not following.exists():
            return JsonResponse({
                'success': True,
                'following': [],
                'message': 'no following',
                'count': 0
            })
        following_data = []
        for follow_obj in following:
            followed_user = follow_obj.following
            following_data.append({
                'user_id': followed_user.user_id,
                'ctu_id': followed_user.acc_username,
                'name': f"{followed_user.f_name} {followed_user.l_name}",
                'profile_pic': build_profile_pic_url(followed_user),
                'followed_at': follow_obj.followed_at.isoformat()
            })
        return JsonResponse({
            'success': True,
            'following': following_data,
            'count': len(following_data)
        })
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from apps.shared.models import Follow

@api_view(["POST","DELETE"])
@permission_classes([IsAuthenticated])
def follow_user_view(request, user_id):
    if request.method == "OPTIONS":
        response = JsonResponse({'detail': 'OK'})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "POST, DELETE, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken, Authorization"
        return response

    try:
        # Authenticate via JWT manually to avoid issues with custom user
        current_user = get_current_user_from_request(request)
        if not current_user:
            return JsonResponse({'error': 'Authentication required'}, status=401)

        user_to_follow = User.objects.get(user_id=user_id)

        if current_user.user_id == user_to_follow.user_id:
            return JsonResponse({'error': 'Cannot follow yourself'}, status=400)

        if request.method == 'POST':
            follow_obj, created = Follow.objects.get_or_create(
                follower=current_user,
                following=user_to_follow
            )
            if created:
                # Notify the followed user
                try:
                    Notification.objects.create(
                        user=user_to_follow,
                        notif_type='follow',
                        subject='New Follower',
                        notifi_content=f"{current_user.f_name} {current_user.l_name} started following you. View profile: /alumni/profile/{current_user.user_id}",
                        notif_date=timezone.now()
                    )
                except Exception:
                    pass
                return JsonResponse({
                    'success': True,
                    'message': f'Successfully followed {user_to_follow.f_name} {user_to_follow.l_name}'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Already following this user'
                }, status=400)

        elif request.method == 'DELETE':
            try:
                follow_obj = Follow.objects.get(
                    follower=current_user,
                    following=user_to_follow
                )
                follow_obj.delete()
                return JsonResponse({
                    'success': True,
                    'message': f'Successfully unfollowed {user_to_follow.f_name} {user_to_follow.l_name}'
                })
            except Follow.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Not following this user'
                }, status=400)

    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def check_follow_status_view(request, user_id):
    if request.method == "OPTIONS":
        response = JsonResponse({'detail': 'OK'})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken, Authorization"
        return response

    try:
        # Get the user to check
        user_to_check = User.objects.get(user_id=user_id)

        # Get the current user from token
        auth_header = request.headers.get('Authorization') or request.META.get('HTTP_AUTHORIZATION')
        if not auth_header or not auth_header.startswith('Bearer '):
            # If no authentication, return not following
            return JsonResponse({
                'success': True,
                'is_following': False
            })

        token = auth_header.split(' ')[1]
        try:
            from rest_framework_simplejwt.tokens import AccessToken
            access_token = AccessToken(token)
            current_user_id = access_token.get('user_id') or access_token.get('id')
            current_user = User.objects.get(user_id=int(current_user_id))
        except Exception as e:
            # If token is invalid, return not following
            return JsonResponse({
                'success': True,
                'is_following': False
            })

        # Check if current user is following the target user
        from apps.shared.models import Follow
        is_following = Follow.objects.filter(
            follower=current_user,
            following=user_to_check
        ).exists()

        return JsonResponse({
            'success': True,
            'is_following': is_following
        })

    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def posts_view(request):
    """Get all posts or create a new post"""
    try:
        if request.method == "POST":
            data = json.loads(request.body or "{}")
            post_title = data.get('post_title') or ''
            post_content = data.get('post_content') or ''
            post_cat_id = data.get('post_cat_id')
            post_type = data.get('type') or 'personal'

            if not post_content.strip() and not post_title.strip():
                return JsonResponse({'success': False, 'message': 'post_content or post_title is required'}, status=400)

            # Resolve category if provided
            post_cat = None
            if post_cat_id is not None:
                try:
                    post_cat = PostCategory.objects.get(post_cat_id=int(post_cat_id))
                except Exception:
                    post_cat = None

            new_post = Post.objects.create(
                user=request.user,
                post_title=post_title,
                post_content=post_content,
                post_cat=post_cat,
                type=post_type,
            )

            return JsonResponse({
                'success': True,
                'post': {
                    'post_id': new_post.post_id,
                    'post_title': new_post.post_title,
                    'post_content': new_post.post_content,
                    'post_image': (new_post.post_image.url if getattr(new_post, 'post_image', None) else None),
                    'type': new_post.type,
                    'created_at': new_post.created_at.isoformat() if hasattr(new_post, 'created_at') else None,
                    'user': {
                        'user_id': request.user.user_id,
                        'f_name': request.user.f_name,
                        'l_name': request.user.l_name,
                        'profile_pic': build_profile_pic_url(request.user),
                    },
                    'category': {
                        'post_cat_id': post_cat.post_cat_id if post_cat else None,
                        'events': getattr(post_cat, 'events', False) if post_cat else False,
                        'announcements': getattr(post_cat, 'announcements', False) if post_cat else False,
                        'donation': getattr(post_cat, 'donation', False) if post_cat else False,
                        'personal': getattr(post_cat, 'personal', False) if post_cat else False,
                    }
                }
            }, status=201)

        # Existing GET behavior
        # Get all posts ordered by most recent
        posts = Post.objects.all().select_related('user', 'post_cat').order_by('-post_id')
        posts_data = []

        for post in posts:
            try:
                # Get likes count
                likes_count = Like.objects.filter(post=post).count()
                # Get comments count
                comments_count = Comment.objects.filter(post=post).count()
                # Get reposts count
                reposts_count = Repost.objects.filter(post=post).count()

                # Get reposts data for the feed
                reposts = Repost.objects.filter(post=post).select_related('user')
                reposts_data = []
                for repost in reposts:
                    reposts_data.append({
                        'repost_id': repost.repost_id,
                        'repost_date': repost.repost_date.isoformat(),
                        'user': {
                            'user_id': repost.user.user_id,
                            'f_name': repost.user.f_name,
                            'l_name': repost.user.l_name,
                            'profile_pic': build_profile_pic_url(repost.user),
                        }
                    })

                # Get likes data
                likes = Like.objects.filter(post=post).select_related('user')
                likes_data = []
                for like in likes:
                    likes_data.append({
                        'user_id': like.user.user_id,
                        'f_name': like.user.f_name,
                        'l_name': like.user.l_name,
                        'profile_pic': build_profile_pic_url(like.user),
                    })

                # Get comments for the post
                comments = Comment.objects.filter(post=post).select_related('user').order_by('-date_created')
                comments_data = []
                for comment in comments:
                    comments_data.append({
                        'comment_id': comment.comment_id,
                        'comment_content': comment.comment_content,
                        'date_created': comment.date_created.isoformat(),
                        'user': {
                            'user_id': comment.user.user_id,
                            'f_name': comment.user.f_name,
                            'l_name': comment.user.l_name,
                            'profile_pic': build_profile_pic_url(comment.user),
                        }
                    })

                posts_data.append({
                    'post_id': post.post_id,
                    'post_title': post.post_title,
                    'post_content': post.post_content,
                    'post_image': (post.post_image.url if getattr(post, 'post_image', None) else None),
                    'type': post.type,
                    'created_at': post.created_at.isoformat() if hasattr(post, 'created_at') else None,
                    'likes_count': likes_count,
                    'comments_count': comments_count,
                    'reposts_count': reposts_count,
                    'likes': likes_data,
                    'reposts': reposts_data,
                    'comments': comments_data,
                    'user': {
                        'user_id': post.user.user_id,
                        'f_name': post.user.f_name,
                        'l_name': post.user.l_name,
                        'profile_pic': build_profile_pic_url(post.user),
                    },
                    'category': {
                        'post_cat_id': post.post_cat.post_cat_id if getattr(post, 'post_cat', None) else None,
                        'events': post.post_cat.events if getattr(post, 'post_cat', None) else False,
                        'announcements': post.post_cat.announcements if getattr(post, 'post_cat', None) else False,
                        'donation': post.post_cat.donation if getattr(post, 'post_cat', None) else False,
                        'personal': post.post_cat.personal if getattr(post, 'post_cat', None) else False,
                    }
                })
            except Exception:
                continue

        return JsonResponse({'posts': posts_data})
    except Exception as e:
        logger.error(f"posts_view failed: {e}")
        return JsonResponse({'posts': []}, status=200)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def posts_by_user_type_view(request):
    """Get posts filtered by user type (alumni, OJT, etc.)"""
    try:
        user_type = request.GET.get('user_type', 'all')

        if user_type == 'alumni':
            users = User.objects.filter(account_type__user=True)
        elif user_type == 'ojt':
            users = User.objects.filter(account_type__ojt=True)
        elif user_type == 'coordinator':
            users = User.objects.filter(account_type__coordinator=True)
        else:
            users = User.objects.all()

        posts = Post.objects.filter(user__in=users).select_related('user', 'post_cat').order_by('-post_id')
        posts_data = []

        for post in posts:
            try:
                # Get likes count
                likes_count = Like.objects.filter(post=post).count()
                # Get comments count
                comments_count = Comment.objects.filter(post=post).count()
                # Get reposts count
                reposts_count = Repost.objects.filter(post=post).count()

                posts_data.append({
                    'post_id': post.post_id,
                    'post_title': post.post_title,
                    'post_content': post.post_content,
                    'post_image': (post.post_image.url if getattr(post, 'post_image', None) else None),
                    'type': post.type,
                    'created_at': post.created_at.isoformat() if hasattr(post, 'created_at') else None,
                    'likes_count': likes_count,
                    'comments_count': comments_count,
                    'reposts_count': reposts_count,
                    'user': {
                        'user_id': post.user.user_id,
                        'f_name': post.user.f_name,
                        'l_name': post.user.l_name,
                        'profile_pic': build_profile_pic_url(post.user),
                    },
                    'category': {
                        'post_cat_id': post.post_cat.post_cat_id if getattr(post, 'post_cat', None) else None,
                        'events': post.post_cat.events if getattr(post, 'post_cat', None) else False,
                        'announcements': post.post_cat.announcements if getattr(post, 'post_cat', None) else False,
                        'donation': post.post_cat.donation if getattr(post, 'post_cat', None) else False,
                        'personal': post.post_cat.personal if getattr(post, 'post_cat', None) else False,
                    }
                })
            except Exception:
                continue

        return JsonResponse({'posts': posts_data})
    except Exception as e:
        logger.error(f"posts_by_user_type_view failed: {e}")
        return JsonResponse({'posts': []}, status=200)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_all_alumni(request):
    """Get all alumni with pagination and search capabilities"""
    try:
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 20))
        search = request.GET.get('search', '').strip()
        
        # Base queryset
        alumni = User.objects.filter(account_type__user=True).select_related('profile', 'academic_info')
        
        # Apply search if provided
        if search:
            alumni = alumni.filter(
                Q(f_name__icontains=search) |
                Q(m_name__icontains=search) |
                Q(l_name__icontains=search) |
                Q(acc_username__icontains=search)
            )
        
        # Calculate pagination
        total_count = alumni.count()
        start = (page - 1) * limit
        end = start + limit
        
        # Get paginated results
        alumni_page = alumni[start:end]
        
        alumni_data = []
        for a in alumni_page:
            try:
                alumni_data.append({
                    'id': a.user_id,
                    'ctu_id': a.acc_username,
                    'name': f"{a.f_name} {a.m_name or ''} {a.l_name}".strip(),
                    'course': getattr(a.academic_info, 'course', None) if hasattr(a, 'academic_info') else None,
                    'batch': getattr(a.academic_info, 'year_graduated', None) if hasattr(a, 'academic_info') else None,
                    'status': a.user_status,
                    'gender': a.gender,
                    'birthdate': str(getattr(a.profile, 'birthdate', None)) if hasattr(a, 'profile') and getattr(a, 'profile', None) else None,
                    'phone': getattr(a.profile, 'phone_num', None) if hasattr(a, 'profile') and getattr(a, 'profile', None) else None,
                    'address': getattr(a.profile, 'address', None) if hasattr(a, 'profile') and getattr(a, 'profile', None) else None,
                    'civilStatus': getattr(a.profile, 'civil_status', None) if hasattr(a, 'profile') and getattr(a, 'profile', None) else None,
                    'socialMedia': getattr(a.profile, 'social_media', None) if hasattr(a, 'profile') and getattr(a, 'profile', None) else None,
                    'profile_pic': build_profile_pic_url(a),
                })
            except Exception:
                continue
        
        return JsonResponse({
            'success': True,
            'alumni': alumni_data,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total_count,
                'pages': (total_count + limit - 1) // limit
            }
        })
    except Exception as e:
        logger.error(f"get_all_alumni failed: {e}")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)
