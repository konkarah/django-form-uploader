from django.utils.deprecation import MiddlewareMixin
from .authentication import ClerkAuthentication
import logging

logger = logging.getLogger(__name__)

class ClerkAuthenticationMiddleware(MiddlewareMixin):
    """
    Middleware to add Clerk user to request for non-API views
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.auth = ClerkAuthentication()
    
    def __call__(self, request):
        # Skip for admin and other specific paths if needed
        if request.path.startswith('/admin/'):
            return self.get_response(request)
            
        # Only process if user is not already authenticated
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            try:
                auth_result = self.auth.authenticate(request)
                if auth_result:
                    request.user = auth_result[0]
                    logger.debug(f"Authenticated user via middleware: {request.user.username}")
            except Exception as e:
                logger.debug(f"Middleware authentication failed: {str(e)}")
                # Don't raise exception in middleware, just continue
                pass
        
        return self.get_response(request)