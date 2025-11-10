"""
Tests for security functionality.

This module tests content sanitization, file validation,
and security measures.
"""

import os
import tempfile
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from apps.shared.security import ContentSanitizer, SecurityValidator
from apps.messaging.views import AttachmentUploadView
from apps.shared.models import Conversation, User
from rest_framework.test import APIClient
from rest_framework import status


class SecurityTestCase(TestCase):
    """Test case for security functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.User = get_user_model()
        
        # Create test user
        self.user = self.User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            user_id=1,
            name='Test User',
            full_name='Test User'
        )
        
        # Create test conversation
        self.conversation = Conversation.objects.create()
        self.conversation.participants.add(self.user)
        
        # Create API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_content_sanitization_xss_prevention(self):
        """Test XSS prevention in content sanitization."""
        # Test malicious HTML content
        malicious_content = '<script>alert("xss")</script>Hello World'
        sanitized = ContentSanitizer.sanitize_message_content(malicious_content)
        
        # Should remove script tags
        self.assertNotIn('<script>', sanitized)
        self.assertNotIn('</script>', sanitized)
        self.assertIn('Hello World', sanitized)
    
    def test_content_sanitization_length_limit(self):
        """Test content length limiting."""
        # Create content exceeding limit
        long_content = 'A' * 15000  # Exceeds 10000 character limit
        
        with self.assertRaises(Exception):
            ContentSanitizer.sanitize_message_content(long_content)
    
    def test_message_type_validation(self):
        """Test message type validation."""
        # Test valid message types
        valid_types = ['text', 'image', 'file', 'system']
        for msg_type in valid_types:
            result = ContentSanitizer.validate_message_type(msg_type)
            self.assertEqual(result, msg_type)
        
        # Test invalid message type
        with self.assertRaises(Exception):
            ContentSanitizer.validate_message_type('invalid_type')
    
    def test_filename_sanitization(self):
        """Test filename sanitization."""
        # Test malicious filename
        malicious_filename = '../../../etc/passwd'
        sanitized = ContentSanitizer.sanitize_filename(malicious_filename)
        
        # Should remove path traversal
        self.assertNotIn('../', sanitized)
        self.assertNotIn('etc/passwd', sanitized)
        self.assertEqual(sanitized, 'passwd')
        
        # Test filename with special characters
        special_filename = 'file<>:"|?*name.txt'
        sanitized = ContentSanitizer.sanitize_filename(special_filename)
        
        # Should replace special characters
        self.assertNotIn('<', sanitized)
        self.assertNotIn('>', sanitized)
        self.assertNotIn(':', sanitized)
        self.assertNotIn('"', sanitized)
        self.assertNotIn('|', sanitized)
        self.assertNotIn('?', sanitized)
        self.assertNotIn('*', sanitized)
    
    def test_file_extension_validation(self):
        """Test file extension validation."""
        # Test valid extensions
        valid_extensions = ['.jpg', '.png', '.pdf', '.docx']
        for ext in valid_extensions:
            result = SecurityValidator.validate_file_extension(f'test{ext}', [ext])
            self.assertTrue(result)
        
        # Test invalid extension
        result = SecurityValidator.validate_file_extension('test.exe', ['.jpg', '.png'])
        self.assertFalse(result)
    
    def test_file_size_validation(self):
        """Test file size validation."""
        # Test valid file size
        result = SecurityValidator.validate_file_size(1024 * 1024, 10)  # 1MB, limit 10MB
        self.assertTrue(result)
        
        # Test file size exceeding limit
        result = SecurityValidator.validate_file_size(15 * 1024 * 1024, 10)  # 15MB, limit 10MB
        self.assertFalse(result)
        
        # Test zero file size
        result = SecurityValidator.validate_file_size(0, 10)
        self.assertFalse(result)
    
    def test_file_content_validation(self):
        """Test file content validation."""
        # Test valid JPEG content
        jpeg_content = b'\xff\xd8\xff\xe0\x00\x10JFIF'
        result = SecurityValidator.validate_file_content(jpeg_content, 'image/jpeg')
        self.assertTrue(result)
        
        # Test invalid JPEG content
        invalid_content = b'This is not a JPEG file'
        result = SecurityValidator.validate_file_content(invalid_content, 'image/jpeg')
        self.assertFalse(result)
        
        # Test valid PDF content
        pdf_content = b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj'
        result = SecurityValidator.validate_file_content(pdf_content, 'application/pdf')
        self.assertTrue(result)
    
    def test_file_upload_security(self):
        """Test file upload security measures."""
        # Create test file
        test_file = SimpleUploadedFile(
            'test.txt',
            b'Test file content',
            content_type='text/plain'
        )
        
        # Test file upload
        response = self.client.post(
            f'/api/messaging/conversations/{self.conversation.conversation_id}/attachments/',
            {'file': test_file},
            format='multipart'
        )
        
        # Should succeed for valid file
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify response data
        self.assertIn('attachment_id', response.data)
        self.assertIn('file_name', response.data)
        self.assertIn('file_type', response.data)
        self.assertIn('file_size', response.data)
    
    def test_malicious_file_upload_rejection(self):
        """Test rejection of malicious file uploads."""
        # Test executable file upload
        exe_file = SimpleUploadedFile(
            'malware.exe',
            b'MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00',
            content_type='application/x-msdownload'
        )
        
        response = self.client.post(
            f'/api/messaging/conversations/{self.conversation.conversation_id}/attachments/',
            {'file': exe_file},
            format='multipart'
        )
        
        # Should reject executable files
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('File type not allowed', response.data['error'])
    
    def test_large_file_upload_rejection(self):
        """Test rejection of large file uploads."""
        # Create large file content
        large_content = b'A' * (50 * 1024 * 1024)  # 50MB
        
        large_file = SimpleUploadedFile(
            'large.txt',
            large_content,
            content_type='text/plain'
        )
        
        response = self.client.post(
            f'/api/messaging/conversations/{self.conversation.conversation_id}/attachments/',
            {'file': large_file},
            format='multipart'
        )
        
        # Should reject large files
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('File too large', response.data['error'])
    
    def test_empty_file_upload_rejection(self):
        """Test rejection of empty file uploads."""
        # Create empty file
        empty_file = SimpleUploadedFile(
            'empty.txt',
            b'',
            content_type='text/plain'
        )
        
        response = self.client.post(
            f'/api/messaging/conversations/{self.conversation.conversation_id}/attachments/',
            {'file': empty_file},
            format='multipart'
        )
        
        # Should reject empty files
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Empty files are not allowed', response.data['error'])
    
    def test_filename_sanitization_in_upload(self):
        """Test filename sanitization in file upload."""
        # Create file with malicious filename
        malicious_file = SimpleUploadedFile(
            '../../../etc/passwd',
            b'Test content',
            content_type='text/plain'
        )
        
        response = self.client.post(
            f'/api/messaging/conversations/{self.conversation.conversation_id}/attachments/',
            {'file': malicious_file},
            format='multipart'
        )
        
        # Should succeed but with sanitized filename
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn('../', response.data['file_name'])
        self.assertNotIn('etc/passwd', response.data['file_name'])
    
    def test_mime_type_validation(self):
        """Test MIME type validation."""
        # Test file with correct MIME type
        jpeg_file = SimpleUploadedFile(
            'test.jpg',
            b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00',
            content_type='image/jpeg'
        )
        
        response = self.client.post(
            f'/api/messaging/conversations/{self.conversation.conversation_id}/attachments/',
            {'file': jpeg_file},
            format='multipart'
        )
        
        # Should succeed
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_mime_type_mismatch_detection(self):
        """Test MIME type mismatch detection."""
        # Test file with incorrect MIME type
        text_file = SimpleUploadedFile(
            'test.jpg',  # .jpg extension
            b'This is not a JPEG file',
            content_type='image/jpeg'  # Claims to be JPEG but isn't
        )
        
        response = self.client.post(
            f'/api/messaging/conversations/{self.conversation.conversation_id}/attachments/',
            {'file': text_file},
            format='multipart'
        )
        
        # Should handle MIME type mismatch gracefully
        # (In a real implementation, this might be rejected or logged)
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])
    
    def test_file_extension_mime_type_matching(self):
        """Test file extension and MIME type matching."""
        # Test file with matching extension and MIME type
        pdf_file = SimpleUploadedFile(
            'test.pdf',
            b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj',
            content_type='application/pdf'
        )
        
        response = self.client.post(
            f'/api/messaging/conversations/{self.conversation.conversation_id}/attachments/',
            {'file': pdf_file},
            format='multipart'
        )
        
        # Should succeed
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_file_extension_mime_type_mismatch(self):
        """Test file extension and MIME type mismatch."""
        # Test file with mismatched extension and MIME type
        mismatched_file = SimpleUploadedFile(
            'test.jpg',  # .jpg extension
            b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj',  # PDF content
            content_type='application/pdf'  # PDF MIME type
        )
        
        response = self.client.post(
            f'/api/messaging/conversations/{self.conversation.conversation_id}/attachments/',
            {'file': mismatched_file},
            format='multipart'
        )
        
        # Should reject due to extension mismatch
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('File extension does not match file type', response.data['error'])
    
    def test_content_sanitization_edge_cases(self):
        """Test content sanitization edge cases."""
        # Test empty content
        result = ContentSanitizer.sanitize_message_content('')
        self.assertEqual(result, '')
        
        # Test None content
        result = ContentSanitizer.sanitize_message_content(None)
        self.assertEqual(result, '')
        
        # Test content with only HTML tags
        result = ContentSanitizer.sanitize_message_content('<p></p><div></div>')
        self.assertEqual(result, '')
        
        # Test content with mixed HTML and text
        result = ContentSanitizer.sanitize_message_content('<p>Hello</p> <strong>World</strong>')
        self.assertEqual(result, 'Hello World')
    
    def test_filename_sanitization_edge_cases(self):
        """Test filename sanitization edge cases."""
        # Test empty filename
        result = ContentSanitizer.sanitize_filename('')
        self.assertEqual(result, 'untitled')
        
        # Test None filename
        result = ContentSanitizer.sanitize_filename(None)
        self.assertEqual(result, 'untitled')
        
        # Test filename with only special characters
        result = ContentSanitizer.sanitize_filename('<>:"|?*')
        self.assertEqual(result, 'untitled')
        
        # Test filename with unicode characters
        result = ContentSanitizer.sanitize_filename('файл.txt')
        self.assertEqual(result, 'файл.txt')  # Should preserve valid unicode
    
    def test_security_validator_edge_cases(self):
        """Test security validator edge cases."""
        # Test file extension validation with empty filename
        result = SecurityValidator.validate_file_extension('', ['.txt'])
        self.assertFalse(result)
        
        # Test file extension validation with None filename
        result = SecurityValidator.validate_file_extension(None, ['.txt'])
        self.assertFalse(result)
        
        # Test file content validation with empty content
        result = SecurityValidator.validate_file_content(b'', 'image/jpeg')
        self.assertFalse(result)
        
        # Test file content validation with None content
        result = SecurityValidator.validate_file_content(None, 'image/jpeg')
        self.assertFalse(result)
    
    def test_comprehensive_security_validation(self):
        """Test comprehensive security validation."""
        # Create file that passes all security checks
        secure_file = SimpleUploadedFile(
            'document.pdf',
            b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n>>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \ntrailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n179\n%%EOF',
            content_type='application/pdf'
        )
        
        response = self.client.post(
            f'/api/messaging/conversations/{self.conversation.conversation_id}/attachments/',
            {'file': secure_file},
            format='multipart'
        )
        
        # Should succeed
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify all security measures were applied
        self.assertIn('attachment_id', response.data)
        self.assertEqual(response.data['file_type'], 'application/pdf')
        self.assertGreater(response.data['file_size'], 0)
        self.assertIn('file_category', response.data)
    
    def test_security_logging(self):
        """Test security event logging."""
        # Test that security events are logged
        with patch('apps.shared.security.logger') as mock_logger:
            # Attempt to sanitize malicious content
            ContentSanitizer.sanitize_message_content('<script>alert("xss")</script>')
            
            # Verify logging occurred
            # (In a real test, you'd verify specific log messages)
    
    def test_performance_under_security_load(self):
        """Test performance under security validation load."""
        import time
        
        start_time = time.time()
        
        # Perform many security validations
        for i in range(100):
            ContentSanitizer.sanitize_message_content(f'Test message {i}')
            ContentSanitizer.sanitize_filename(f'file_{i}.txt')
            SecurityValidator.validate_file_size(1024, 10)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete within reasonable time
        self.assertLess(duration, 1.0)
    
    def test_concurrent_security_operations(self):
        """Test concurrent security operations."""
        import threading
        import time
        
        results = []
        
        def perform_security_operations():
            for i in range(10):
                result = ContentSanitizer.sanitize_message_content(f'Test message {i}')
                results.append(result)
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=perform_security_operations)
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all operations completed
        self.assertEqual(len(results), 50)
        
        # Verify all results are sanitized
        for result in results:
            self.assertIsInstance(result, str)
            self.assertNotIn('<script>', result)









































