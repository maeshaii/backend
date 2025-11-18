"""
Custom middleware for API CSRF handling
Senior Developer approach: Properly handle CSRF for API endpoints
"""
from django.utils.deprecation import MiddlewareMixin


class APICSRFExemptMiddleware(MiddlewareMixin):
    """
    Middleware to exempt API endpoints from CSRF protection
    since they use JWT authentication instead
    """
    
    def process_request(self, request):
        # Exempt all /api/ endpoints from CSRF protection
        if request.path.startswith('/api/'):
            setattr(request, '_dont_enforce_csrf_checks', True)
        return None


























































