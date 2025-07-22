"""
Security utilities and middleware for the allergen filtering project
"""

import re
import logging
from django.http import HttpResponse, JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.conf import settings

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Middleware to add security headers to all responses
    """
    
    def process_response(self, request, response):
        """Add security headers to response"""
        
        # Content Security Policy
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https:; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        response['Content-Security-Policy'] = csp_policy
        
        # Other security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        # HSTS (only for HTTPS)
        if request.is_secure():
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
        
        return response


class InputValidationMiddleware(MiddlewareMixin):
    """
    Middleware to validate and sanitize input
    """
    
    def process_request(self, request):
        """Validate input before processing"""
        
        # Check for suspicious patterns in URL
        if self._contains_suspicious_patterns(request.path):
            logger.warning(f"Suspicious URL pattern detected: {request.path}")
            return JsonResponse(
                {'error': 'Invalid request'}, 
                status=400
            )
        
        # Validate query parameters
        if request.method == 'GET':
            for key, value in request.GET.items():
                if not self._is_valid_parameter(key, value):
                    logger.warning(f"Invalid query parameter: {key}={value}")
                    return JsonResponse(
                        {'error': 'Invalid parameter'}, 
                        status=400
                    )
        
        # Validate POST data
        if request.method == 'POST':
            for key, value in request.POST.items():
                if not self._is_valid_parameter(key, value):
                    logger.warning(f"Invalid POST parameter: {key}={value}")
                    return JsonResponse(
                        {'error': 'Invalid parameter'}, 
                        status=400
                    )
        
        return None
    
    def _contains_suspicious_patterns(self, path):
        """Check for suspicious patterns in URL"""
        suspicious_patterns = [
            r'\.\./',  # Directory traversal
            r'<script',  # XSS attempts
            r'javascript:',  # JavaScript injection
            r'data:text/html',  # Data URL injection
            r'vbscript:',  # VBScript injection
            r'on\w+\s*=',  # Event handler injection
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, path, re.IGNORECASE):
                return True
        
        return False
    
    def _is_valid_parameter(self, key, value):
        """Validate parameter key and value"""
        
        # Check key length
        if len(key) > 100:
            return False
        
        # Check value length
        if len(value) > 1000:
            return False
        
        # Check for suspicious patterns in value
        suspicious_patterns = [
            r'<script',
            r'javascript:',
            r'data:text/html',
            r'vbscript:',
            r'on\w+\s*=',
            r'<iframe',
            r'<object',
            r'<embed',
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return False
        
        return True


class RateLimitMiddleware(MiddlewareMixin):
    """
    Simple rate limiting middleware
    """
    
    def process_request(self, request):
        """Check rate limits"""
        
        # Skip rate limiting for certain paths
        if request.path.startswith('/admin/') or request.path.startswith('/static/'):
            return None
        
        # Get client IP
        client_ip = self._get_client_ip(request)
        
        # Check rate limit
        if self._is_rate_limited(client_ip):
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return JsonResponse(
                {'error': 'Rate limit exceeded. Please try again later.'}, 
                status=429
            )
        
        return None
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _is_rate_limited(self, client_ip):
        """Check if client is rate limited"""
        # This is a simplified implementation
        # In production, use Redis or similar for proper rate limiting
        return False


def validate_url(url):
    """
    Validate URL format
    """
    validator = URLValidator()
    try:
        validator(url)
        return True
    except ValidationError:
        return False


def sanitize_html(text):
    """
    Basic HTML sanitization
    """
    if not text:
        return text
    
    # Remove script tags and content
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
    
    # Remove other dangerous tags
    dangerous_tags = ['iframe', 'object', 'embed', 'form', 'input', 'textarea', 'select']
    for tag in dangerous_tags:
        text = re.sub(r'<' + tag + r'[^>]*>.*?</' + tag + r'>', '', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'<' + tag + r'[^>]*/?>', '', text, flags=re.IGNORECASE)
    
    # Remove event handlers
    text = re.sub(r'on\w+\s*=\s*["\'][^"\']*["\']', '', text, flags=re.IGNORECASE)
    
    # Remove javascript: URLs
    text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
    
    return text


def validate_search_query(query):
    """
    Validate search query
    """
    if not query:
        return True
    
    # Check length
    if len(query) > 200:
        return False
    
    # Check for suspicious patterns
    suspicious_patterns = [
        r'<script',
        r'javascript:',
        r'data:text/html',
        r'vbscript:',
        r'on\w+\s*=',
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, query, re.IGNORECASE):
            return False
    
    return True


def validate_allergen_list(allergens):
    """
    Validate list of allergens
    """
    if not allergens:
        return True
    
    # Check if it's a list
    if not isinstance(allergens, list):
        return False
    
    # Check each allergen
    valid_allergens = [
        'celery', 'gluten', 'crustaceans', 'eggs', 'fish', 'lupin',
        'milk', 'molluscs', 'mustard', 'nuts', 'peanuts', 'sesame',
        'soy', 'sulphites', 'tree_nuts'
    ]
    
    for allergen in allergens:
        if not isinstance(allergen, str) or allergen.lower() not in valid_allergens:
            return False
    
    return True


class SecurityUtils:
    """
    Utility class for security functions
    """
    
    @staticmethod
    def log_security_event(event_type, details, request=None):
        """Log security events"""
        client_ip = request.META.get('REMOTE_ADDR') if request else 'unknown'
        user_agent = request.META.get('HTTP_USER_AGENT') if request else 'unknown'
        
        logger.warning(
            f"Security event: {event_type} - {details} - IP: {client_ip} - UA: {user_agent}"
        )
    
    @staticmethod
    def is_suspicious_request(request):
        """Check if request is suspicious"""
        suspicious_indicators = [
            # Missing or suspicious user agent
            not request.META.get('HTTP_USER_AGENT'),
            'bot' in request.META.get('HTTP_USER_AGENT', '').lower(),
            'crawler' in request.META.get('HTTP_USER_AGENT', '').lower(),
            
            # Suspicious headers
            'HTTP_X_FORWARDED_FOR' in request.META and len(request.META['HTTP_X_FORWARDED_FOR'].split(',')) > 3,
            
            # Too many requests in short time (simplified check)
            # In production, implement proper rate limiting
        ]
        
        return any(suspicious_indicators) 