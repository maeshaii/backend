<<<<<<< HEAD
from django.test import TestCase, Client
from django.urls import reverse
from apps.shared.models import User, AccountType, UserProfile
import json

class ForgotPasswordTestCase(TestCase):
    def setUp(self):
        """Set up test data"""
        # Create account types
        self.alumni_account_type = AccountType.objects.create(
            admin=False,
            peso=False,
            user=True,
            coordinator=False,
            ojt=False
        )
        
        self.ojt_account_type = AccountType.objects.create(
            admin=False,
            peso=False,
            user=False,
            coordinator=False,
            ojt=True
        )
        
        self.admin_account_type = AccountType.objects.create(
            admin=True,
            peso=False,
            user=False,
            coordinator=False,
            ojt=False
        )
        
        # Create test users
        self.alumni_user = User.objects.create(
            acc_username='ALUMNI001',
            f_name='John',
            l_name='Doe',
            gender='M',
            account_type=self.alumni_account_type,
            user_status='active'
        )
        self.alumni_user.set_password('oldpassword123')
        self.alumni_user.save()
        
        # Create profile for alumni user
        UserProfile.objects.create(
            user=self.alumni_user,
            email='john.doe@example.com'
        )
        
        self.ojt_user = User.objects.create(
            acc_username='OJT001',
            f_name='Jane',
            l_name='Smith',
            gender='F',
            account_type=self.ojt_account_type,
            user_status='active'
        )
        self.ojt_user.set_password('oldpassword123')
        self.ojt_user.save()
        
        # Create profile for OJT user
        UserProfile.objects.create(
            user=self.ojt_user,
            email='jane.smith@example.com'
        )
        
        self.admin_user = User.objects.create(
            acc_username='ADMIN001',
            f_name='Admin',
            l_name='User',
            gender='M',
            account_type=self.admin_account_type,
            user_status='active'
        )
        self.admin_user.set_password('adminpassword123')
        self.admin_user.save()
        
        self.client = Client()

    def test_forgot_password_success_alumni(self):
        """Test successful password reset for alumni user"""
        data = {
            'ctu_id': 'ALUMNI001',
            'email': 'john.doe@example.com',
            'last_name': 'Doe',
            'first_name': 'John',
            'middle_name': ''
        }
        
        response = self.client.post(
            '/api/forgot-password/',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertIn('temp_password', response_data)
        self.assertEqual(len(response_data['temp_password']), 12)
        
        # Verify password was actually changed
        self.alumni_user.refresh_from_db()
        self.assertFalse(self.alumni_user.check_password('oldpassword123'))
        self.assertTrue(self.alumni_user.check_password(response_data['temp_password']))

    def test_forgot_password_success_ojt(self):
        """Test successful password reset for OJT user"""
        data = {
            'ctu_id': 'OJT001',
            'email': 'jane.smith@example.com',
            'last_name': 'Smith',
            'first_name': 'Jane',
            'middle_name': ''
        }
        
        response = self.client.post(
            '/api/forgot-password/',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertIn('temp_password', response_data)

    def test_forgot_password_invalid_credentials(self):
        """Test password reset with invalid credentials"""
        data = {
            'ctu_id': 'ALUMNI001',
            'email': 'wrong.email@example.com',
            'last_name': 'Doe',
            'first_name': 'John'
        }
        
        response = self.client.post(
            '/api/forgot-password/',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])

    def test_forgot_password_user_not_found(self):
        """Test password reset for non-existent user"""
        data = {
            'ctu_id': 'NONEXISTENT',
            'email': 'test@example.com',
            'last_name': 'Test',
            'first_name': 'User'
        }
        
        response = self.client.post(
            '/api/forgot-password/',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 404)
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])

    def test_forgot_password_admin_denied(self):
        """Test that admin users cannot use forgot password"""
        data = {
            'ctu_id': 'ADMIN001',
            'email': 'admin@example.com',
            'last_name': 'User',
            'first_name': 'Admin'
        }
        
        response = self.client.post(
            '/api/forgot-password/',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 403)
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
        self.assertIn('only available for alumni and OJT', response_data['message'])

    def test_forgot_password_missing_fields(self):
        """Test password reset with missing required fields"""
        data = {
            'ctu_id': 'ALUMNI001',
            'email': 'john.doe@example.com',
            # Missing last_name and first_name
        }
        
        response = self.client.post(
            '/api/forgot-password/',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
        self.assertIn('All fields are required', response_data['message'])

    def test_forgot_password_middle_name_validation(self):
        """Test password reset with middle name validation"""
        # Test with correct middle name
        data = {
            'ctu_id': 'ALUMNI001',
            'email': 'john.doe@example.com',
            'last_name': 'Doe',
            'first_name': 'John',
            'middle_name': ''  # Empty middle name should work
        }
        
        response = self.client.post(
            '/api/forgot-password/',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
=======
from django.test import TestCase

# Create your tests here.
>>>>>>> 746e601016fd6b6113a8116f65f35a08788c789a
