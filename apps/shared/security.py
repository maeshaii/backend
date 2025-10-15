"""
Security utilities for content sanitization and validation.
"""

import re
import os
import bleach
from django.utils.html import strip_tags
from django.core.exceptions import ValidationError


class ContentSanitizer:
    """Handles content sanitization for user-generated content."""
    
    # Allowed HTML tags for rich text (if needed in future)
    ALLOWED_TAGS = [
        'p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li',
        'blockquote', 'code', 'pre'
    ]
    
    # Allowed HTML attributes
    ALLOWED_ATTRIBUTES = {
        'a': ['href', 'title'],
        'img': ['src', 'alt', 'title'],
    }
    
    # Maximum content length
    MAX_CONTENT_LENGTH = 10000
    
    @classmethod
    def sanitize_message_content(cls, content: str) -> str:
        """
        Sanitize message content to prevent XSS attacks.
        
        Args:
            content: Raw message content from user
            
        Returns:
            Sanitized content safe for display
            
        Raises:
            ValidationError: If content is invalid or too long
        """
        if not isinstance(content, str):
            raise ValidationError("Content must be a string")
        
        # Remove null bytes and other dangerous characters
        content = content.replace('\x00', '')
        
        # Check length
        if len(content) > cls.MAX_CONTENT_LENGTH:
            raise ValidationError(f"Content too long. Maximum {cls.MAX_CONTENT_LENGTH} characters allowed.")
        
        # Strip HTML tags completely for now (can be made configurable later)
        sanitized = strip_tags(content)
        
        # Remove any remaining HTML entities that might be dangerous
        sanitized = bleach.clean(sanitized, tags=[], strip=True)
        
        # Remove excessive whitespace
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        # Check for empty content after sanitization
        if not sanitized:
            raise ValidationError("Content cannot be empty after sanitization")
        
        return sanitized
    
    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """
        Sanitize filename to prevent path traversal and other attacks.
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename safe for storage
        """
        if not isinstance(filename, str):
            raise ValidationError("Filename must be a string")
        
        # Remove null bytes and other dangerous characters first
        filename = filename.replace('\x00', '').replace('\r', '').replace('\n', '')
        
        # Remove path traversal attempts (multiple variations)
        path_traversal_patterns = [
            '../', '..\\', './', '.\\',  # Basic path traversal
            '..%2F', '..%5C', '.%2F', '.%5C',  # URL encoded
            '..%252F', '..%255C', '.%252F', '.%255C',  # Double URL encoded
            '%2E%2E%2F', '%2E%2E%5C', '%2E%2F', '%2E%5C',  # Hex encoded
        ]
        
        for pattern in path_traversal_patterns:
            filename = filename.replace(pattern, '')
        
        # Remove dangerous characters (Windows and Unix)
        dangerous_chars = [
            '<', '>', ':', '"', '|', '?', '*',  # Windows forbidden
            '/', '\\',  # Path separators
            '\x00', '\x01', '\x02', '\x03', '\x04', '\x05', '\x06', '\x07',  # Control chars
            '\x08', '\x09', '\x0A', '\x0B', '\x0C', '\x0D', '\x0E', '\x0F',
            '\x10', '\x11', '\x12', '\x13', '\x14', '\x15', '\x16', '\x17',
            '\x18', '\x19', '\x1A', '\x1B', '\x1C', '\x1D', '\x1E', '\x1F',
            '\x7F',  # DEL character
        ]
        
        for char in dangerous_chars:
            filename = filename.replace(char, '_')
        
        # Remove any HTML/script tags
        filename = strip_tags(filename)
        
        # Remove leading/trailing dots, spaces, and hyphens
        filename = filename.strip('. -')
        
        # Remove multiple consecutive underscores/spaces
        filename = re.sub(r'[_\s]+', '_', filename)
        
        # Ensure filename is not empty
        if not filename:
            filename = 'unnamed_file'
        
        # Check for reserved names (Windows)
        reserved_names = [
            'CON', 'PRN', 'AUX', 'NUL',
            'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
            'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        ]
        
        name_without_ext = os.path.splitext(filename)[0].upper()
        if name_without_ext in reserved_names:
            filename = f'file_{filename}'
        
        # Limit length (255 chars total, but be more conservative)
        if len(filename) > 200:
            name, ext = os.path.splitext(filename)
            max_name_length = 200 - len(ext)
            filename = name[:max_name_length] + ext
        
        # Ensure filename doesn't start with a dot (hidden files)
        if filename.startswith('.'):
            filename = f'file_{filename}'
        
        # Final validation - ensure only safe characters remain
        safe_pattern = re.compile(r'^[a-zA-Z0-9._\-\s]+$')
        if not safe_pattern.match(filename):
            # If filename contains unsafe characters, create a safe one
            safe_name = re.sub(r'[^a-zA-Z0-9._\-\s]', '_', filename)
            if not safe_name.strip():
                return 'unnamed_file'
            filename = safe_name
        
        return filename
    
    @classmethod
    def validate_message_type(cls, message_type: str) -> str:
        """
        Validate and sanitize message type.
        
        Args:
            message_type: Message type string
            
        Returns:
            Validated message type
        """
        if not isinstance(message_type, str):
            raise ValidationError("Message type must be a string")
        
        # Only allow predefined message types
        allowed_types = ['text', 'image', 'file', 'system']
        message_type = message_type.lower().strip()
        
        if message_type not in allowed_types:
            raise ValidationError(f"Invalid message type. Must be one of: {', '.join(allowed_types)}")
        
        return message_type
    
    @classmethod
    def sanitize_user_input(cls, user_input: str, max_length: int = 1000) -> str:
        """
        General purpose user input sanitization.
        
        Args:
            user_input: Raw user input
            max_length: Maximum allowed length
            
        Returns:
            Sanitized input
        """
        if not isinstance(user_input, str):
            raise ValidationError("Input must be a string")
        
        # Remove null bytes
        user_input = user_input.replace('\x00', '')
        
        # Check length
        if len(user_input) > max_length:
            raise ValidationError(f"Input too long. Maximum {max_length} characters allowed.")
        
        # Strip HTML tags
        sanitized = strip_tags(user_input)
        
        # Remove excessive whitespace
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        return sanitized


class SecurityValidator:
    """Additional security validations."""
    
    @staticmethod
    def validate_file_extension(filename: str, allowed_extensions: list) -> bool:
        """
        Validate file extension against allowed list.
        
        Args:
            filename: File name to validate
            allowed_extensions: List of allowed extensions (e.g., ['.jpg', '.png'])
            
        Returns:
            True if extension is allowed
        """
        if not filename:
            return False
        
        # Get file extension
        extension = '.' + filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        
        return extension in allowed_extensions
    
    @staticmethod
    def validate_file_content(file_content: bytes, expected_mime_type: str) -> bool:
        """
        Validate file content matches expected MIME type.
        
        Args:
            file_content: Raw file content
            expected_mime_type: Expected MIME type
            
        Returns:
            True if content matches expected type
        """
        if not file_content or len(file_content) < 4:
            return False
        
        # Check file signatures (magic numbers)
        signatures = {
            'image/jpeg': [b'\xff\xd8\xff'],
            'image/png': [b'\x89PNG\r\n\x1a\n'],
            'image/gif': [b'GIF87a', b'GIF89a'],
            'image/webp': [b'RIFF', b'WEBP'],
            'application/pdf': [b'%PDF'],
            'application/zip': [b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08'],
        }
        
        if expected_mime_type in signatures:
            for signature in signatures[expected_mime_type]:
                if file_content.startswith(signature):
                    return True
            return False
        
        # For other types, assume valid if we got this far
        return True
    
    @staticmethod
    def validate_file_size(file_size: int, max_size_mb: int) -> bool:
        """
        Validate file size.
        
        Args:
            file_size: File size in bytes
            max_size_mb: Maximum size in MB
            
        Returns:
            True if size is within limits
        """
        max_size_bytes = max_size_mb * 1024 * 1024
        return 0 < file_size <= max_size_bytes
    
    @staticmethod
    def is_safe_url(url: str) -> bool:
        """
        Check if URL is safe (no javascript:, data:, etc.).
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL is safe
        """
        if not url:
            return False
        
        # Convert to lowercase for checking
        url_lower = url.lower()
        
        # Dangerous protocols
        dangerous_protocols = [
            'javascript:', 'data:', 'vbscript:', 'file:', 'ftp:'
        ]
        
        for protocol in dangerous_protocols:
            if url_lower.startswith(protocol):
                return False
        
        return True
