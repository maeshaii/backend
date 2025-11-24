"""
Custom exception handler to ensure CORS headers are always present on error responses.
This fixes the issue where 500 errors don't include CORS headers, causing browser CORS errors.
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from django.http import JsonResponse
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that ensures CORS headers are always present.
    This is critical because browsers block responses without CORS headers,
    even if the error is a 500 Internal Server Error.
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    # If response is None, it means DRF couldn't handle the exception
    # This happens for non-DRF exceptions (like 500 errors from views)
    if response is None:
        # Log the exception for debugging
        logger.error(f"Unhandled exception in API: {exc}", exc_info=True)
        
        # Create a proper JSON response with error details
        if hasattr(exc, 'message'):
            error_message = str(exc.message)
        else:
            error_message = str(exc)
        
        response = Response(
            {
                'detail': error_message,
                'error': 'Internal server error',
                'status_code': 500
            },
            status=500
        )
    
    # Ensure CORS headers are present by adding them explicitly
    # The CORS middleware should handle this, but we ensure it here as a fallback
    request = context.get('request')
    if request and response:
        origin = request.META.get('HTTP_ORIGIN')
        if origin:
            # Add CORS headers manually if they're missing
            # Check if response is a Response object (has .data) or a dict-like object
            if hasattr(response, 'data'):
                # DRF Response object
                if 'Access-Control-Allow-Origin' not in response:
                    response['Access-Control-Allow-Origin'] = origin
                if 'Access-Control-Allow-Credentials' not in response:
                    response['Access-Control-Allow-Credentials'] = 'true'
                if 'Access-Control-Allow-Methods' not in response:
                    response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
                if 'Access-Control-Allow-Headers' not in response:
                    response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-CSRFToken'
    
    return response

