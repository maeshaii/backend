"""
Cloud storage integration for file attachments.

This module provides AWS S3 integration for storing and managing file attachments
with proper security, CDN integration, and performance optimization.
"""

import logging
import os
import uuid
from typing import Optional, Dict, Any, Tuple
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.utils import timezone
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from botocore.config import Config

logger = logging.getLogger(__name__)


class S3StorageManager:
    """
    AWS S3 storage manager for file attachments.
    
    Features:
    - Secure file upload with presigned URLs
    - CDN integration for fast delivery
    - File lifecycle management
    - Access control and permissions
    - Performance optimization
    """
    
    def __init__(self):
        self.s3_client = None
        self.bucket_name = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None)
        self.region = getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1')
        self.cdn_domain = getattr(settings, 'AWS_S3_CUSTOM_DOMAIN', None)
        
        # Initialize S3 client if credentials are available
        if self._has_aws_credentials():
            self._initialize_s3_client()
    
    def _has_aws_credentials(self) -> bool:
        """Check if AWS credentials are available."""
        return bool(
            getattr(settings, 'AWS_ACCESS_KEY_ID', None) and
            getattr(settings, 'AWS_SECRET_ACCESS_KEY', None) and
            self.bucket_name
        )
    
    def _initialize_s3_client(self):
        """Initialize S3 client with proper configuration."""
        try:
            config = Config(
                region_name=self.region,
                retries={'max_attempts': 3, 'mode': 'adaptive'},
                max_pool_connections=50,
            )
            
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=getattr(settings, 'AWS_ACCESS_KEY_ID', None),
                aws_secret_access_key=getattr(settings, 'AWS_SECRET_ACCESS_KEY', None),
                region_name=self.region,
                config=config,
            )
            
            logger.info("S3 client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            self.s3_client = None
    
    def upload_file(self, file_content: bytes, file_name: str, content_type: str, 
                   user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Upload a file to S3.
        
        Args:
            file_content: File content as bytes
            file_name: Original file name
            content_type: MIME type of the file
            user_id: Optional user ID for organization
            
        Returns:
            Dictionary with upload result and file information
        """
        try:
            if not self.s3_client:
                return self._fallback_upload(file_content, file_name, content_type)
            
            # Generate unique file key
            file_key = self._generate_file_key(file_name, user_id)
            
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_key,
                Body=file_content,
                ContentType=content_type,
                Metadata={
                    'original_filename': file_name,
                    'user_id': str(user_id) if user_id else '',
                    'uploaded_at': timezone.now().isoformat(),
                }
            )
            
            # Generate public URL
            file_url = self._generate_file_url(file_key)
            
            logger.info(f"File uploaded to S3: {file_key}")
            
            return {
                'success': True,
                'file_key': file_key,
                'file_url': file_url,
                'file_name': file_name,
                'content_type': content_type,
                'size': len(file_content),
                'storage_type': 's3',
            }
            
        except ClientError as e:
            logger.error(f"S3 upload failed: {e}")
            return self._fallback_upload(file_content, file_name, content_type)
        except Exception as e:
            logger.error(f"File upload failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'storage_type': 'error',
            }
    
    def delete_file(self, file_key: str) -> bool:
        """
        Delete a file from S3.
        
        Args:
            file_key: S3 object key
            
        Returns:
            bool: True if deletion was successful
        """
        try:
            if not self.s3_client:
                return False
            
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=file_key
            )
            
            logger.info(f"File deleted from S3: {file_key}")
            return True
            
        except ClientError as e:
            logger.error(f"S3 deletion failed: {e}")
            return False
        except Exception as e:
            logger.error(f"File deletion failed: {e}")
            return False
    
    def generate_presigned_url(self, file_key: str, expiration: int = 3600) -> Optional[str]:
        """
        Generate a presigned URL for secure file access.
        
        Args:
            file_key: S3 object key
            expiration: URL expiration time in seconds
            
        Returns:
            Presigned URL or None if generation failed
        """
        try:
            if not self.s3_client:
                return None
            
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': file_key},
                ExpiresIn=expiration
            )
            
            return url
            
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            return None
        except Exception as e:
            logger.error(f"Presigned URL generation failed: {e}")
            return None
    
    def get_file_info(self, file_key: str) -> Optional[Dict[str, Any]]:
        """
        Get file information from S3.
        
        Args:
            file_key: S3 object key
            
        Returns:
            File information dictionary or None if not found
        """
        try:
            if not self.s3_client:
                return None
            
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=file_key
            )
            
            return {
                'size': response.get('ContentLength', 0),
                'content_type': response.get('ContentType', ''),
                'last_modified': response.get('LastModified'),
                'metadata': response.get('Metadata', {}),
            }
            
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.warning(f"File not found in S3: {file_key}")
            else:
                logger.error(f"Failed to get file info: {e}")
            return None
        except Exception as e:
            logger.error(f"File info retrieval failed: {e}")
            return None
    
    def _generate_file_key(self, file_name: str, user_id: Optional[int] = None) -> str:
        """Generate a unique file key for S3 storage."""
        # Create organized folder structure
        timestamp = timezone.now().strftime('%Y/%m/%d')
        unique_id = str(uuid.uuid4())
        file_extension = os.path.splitext(file_name)[1].lower()
        
        if user_id:
            return f"attachments/{timestamp}/user_{user_id}/{unique_id}{file_extension}"
        else:
            return f"attachments/{timestamp}/{unique_id}{file_extension}"
    
    def _generate_file_url(self, file_key: str) -> str:
        """Generate public URL for the file."""
        if self.cdn_domain:
            return f"https://{self.cdn_domain}/{file_key}"
        else:
            return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{file_key}"
    
    def _fallback_upload(self, file_content: bytes, file_name: str, content_type: str) -> Dict[str, Any]:
        """Fallback to local storage if S3 is not available."""
        try:
            # Generate unique filename
            unique_filename = f"{uuid.uuid4()}_{file_name}"
            
            # Save to local storage
            file_obj = ContentFile(file_content, name=unique_filename)
            saved_path = default_storage.save(unique_filename, file_obj)
            
            # Generate URL
            file_url = default_storage.url(saved_path)
            
            logger.info(f"File uploaded to local storage: {saved_path}")
            
            return {
                'success': True,
                'file_key': saved_path,
                'file_url': file_url,
                'file_name': file_name,
                'content_type': content_type,
                'size': len(file_content),
                'storage_type': 'local',
            }
            
        except Exception as e:
            logger.error(f"Fallback upload failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'storage_type': 'error',
            }
    
    def is_available(self) -> bool:
        """Check if S3 storage is available."""
        return self.s3_client is not None
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get storage statistics.
        
        Returns:
            Dictionary with storage statistics
        """
        try:
            if not self.s3_client:
                return {
                    'available': False,
                    'storage_type': 'local',
                    'message': 'S3 not configured, using local storage'
                }
            
            # Get bucket size (this is expensive, so we'll skip it for now)
            return {
                'available': True,
                'storage_type': 's3',
                'bucket_name': self.bucket_name,
                'region': self.region,
                'cdn_enabled': bool(self.cdn_domain),
                'cdn_domain': self.cdn_domain,
            }
            
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {
                'available': False,
                'storage_type': 'error',
                'error': str(e)
            }


class CloudStorageManager:
    """
    High-level cloud storage manager that handles different storage backends.
    
    Features:
    - Multiple storage backend support
    - Automatic fallback mechanisms
    - File lifecycle management
    - Performance optimization
    """
    
    def __init__(self):
        self.s3_manager = S3StorageManager()
        self.storage_type = 's3' if self.s3_manager.is_available() else 'local'
    
    def upload_file(self, file_content: bytes, file_name: str, content_type: str, 
                   user_id: Optional[int] = None) -> Dict[str, Any]:
        """Upload file using the best available storage backend."""
        if self.storage_type == 's3':
            return self.s3_manager.upload_file(file_content, file_name, content_type, user_id)
        else:
            return self.s3_manager._fallback_upload(file_content, file_name, content_type)
    
    def delete_file(self, file_key: str) -> bool:
        """Delete file from storage."""
        if self.storage_type == 's3':
            return self.s3_manager.delete_file(file_key)
        else:
            try:
                return default_storage.delete(file_key)
            except Exception as e:
                logger.error(f"Local file deletion failed: {e}")
                return False
    
    def get_file_url(self, file_key: str, presigned: bool = False) -> Optional[str]:
        """Get file URL with optional presigned access."""
        if self.storage_type == 's3' and presigned:
            return self.s3_manager.generate_presigned_url(file_key)
        elif self.storage_type == 's3':
            return self.s3_manager._generate_file_url(file_key)
        else:
            try:
                return default_storage.url(file_key)
            except Exception as e:
                logger.error(f"Failed to get local file URL: {e}")
                return None
    
    def get_storage_info(self) -> Dict[str, Any]:
        """Get storage backend information."""
        return {
            'storage_type': self.storage_type,
            's3_available': self.s3_manager.is_available(),
            's3_stats': self.s3_manager.get_storage_stats(),
        }


# Global instance
cloud_storage = CloudStorageManager()


