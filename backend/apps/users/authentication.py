# backend/apps/users/authentication.py - COMPLETE FIXED VERSION

import jwt
import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import authentication, exceptions
import json
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

class ClerkAuthentication(authentication.BaseAuthentication):
    """
    Clerk JWT token authentication with support for custom domains
    """
    
    def __init__(self):
        self.jwks_cache = None
        self.jwks_cache_url = None
    
    def get_clerk_domain_from_token(self, token):
        """Extract Clerk domain from token issuer"""
        try:
            # Decode without verification to get issuer
            payload = jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": False}
            )
            issuer = payload.get('iss', '')
            # issuer will be like "https://knowing-herring-54.clerk.accounts.dev"
            return issuer.rstrip('/')
        except:
            return None
    
    def get_jwks(self, token):
        """Fetch JWKS from the correct Clerk domain"""
        try:
            # Get the domain from the token's issuer
            domain = self.get_clerk_domain_from_token(token)
            
            if not domain:
                raise exceptions.AuthenticationFailed('Could not determine Clerk domain from token')
            
            jwks_url = f"{domain}/.well-known/jwks.json"
            
            # Use cache if same URL
            if self.jwks_cache and self.jwks_cache_url == jwks_url:
                logger.debug(f"Using cached JWKS from {jwks_url}")
                return self.jwks_cache
            
            logger.debug(f"Fetching JWKS from {jwks_url}")
            response = requests.get(jwks_url, timeout=10)
            
            if response.status_code != 200:
                raise exceptions.AuthenticationFailed(
                    f'Failed to fetch JWKS: HTTP {response.status_code}'
                )
            
            jwks = response.json()
            
            if 'keys' not in jwks or len(jwks['keys']) == 0:
                raise exceptions.AuthenticationFailed('JWKS contains no keys')
            
            # Cache the JWKS
            self.jwks_cache = jwks
            self.jwks_cache_url = jwks_url
            
            logger.debug(f"Successfully fetched {len(jwks['keys'])} keys from JWKS")
            return jwks
            
        except requests.RequestException as e:
            raise exceptions.AuthenticationFailed(f'Failed to fetch JWKS: {str(e)}')
        except Exception as e:
            raise exceptions.AuthenticationFailed(f'JWKS error: {str(e)}')
    
    def authenticate(self, request):
        """Authenticate request using Clerk JWT token"""
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header.split(' ')[1]
        
        try:
            # Get token header
            unverified_header = jwt.get_unverified_header(token)
            key_id = unverified_header.get('kid')
            
            if not key_id:
                raise exceptions.AuthenticationFailed('Token missing key ID (kid)')
            
            logger.debug(f"Token key ID: {key_id}")
            
            # Get JWKS (will use the correct domain from token)
            jwks = self.get_jwks(token)
            
            # Find the matching key
            rsa_key = None
            available_kids = []
            
            for key in jwks.get('keys', []):
                kid = key.get('kid')
                available_kids.append(kid)
                
                if kid == key_id:
                    try:
                        rsa_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
                        logger.debug(f"Found matching key: {key_id}")
                    except Exception as e:
                        logger.error(f"Failed to parse key: {e}")
                        raise exceptions.AuthenticationFailed(f'Invalid key format: {str(e)}')
                    break
            
            if not rsa_key:
                logger.error(f"Key ID {key_id} not found. Available: {available_kids}")
                raise exceptions.AuthenticationFailed(
                    f'Key ID {key_id} not found in JWKS. Available keys: {available_kids}'
                )
            
            # Verify and decode the token
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=['RS256'],
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_aud": False  # Clerk doesn't always use aud
                }
            )
            
            logger.debug(f"Token verified successfully for user: {payload.get('sub')}")
            
            # Get or create user
            user = self.get_or_create_user(payload)
            return (user, token)
            
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed('Token has expired')
        except jwt.InvalidTokenError as e:
            raise exceptions.AuthenticationFailed(f'Invalid token: {str(e)}')
        except exceptions.AuthenticationFailed:
            raise
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise exceptions.AuthenticationFailed(f'Authentication failed: {str(e)}')
    
    def get_or_create_user(self, payload):
        """Get or create user from Clerk token payload"""
        clerk_user_id = payload.get('sub')
        
        if not clerk_user_id:
            raise exceptions.AuthenticationFailed('Token missing user ID (sub)')
        
        # Extract user info from Clerk token
        # Clerk stores email in different fields depending on setup
        email = None
        for email_field in ['email', 'email_address', 'primary_email_address']:
            email = payload.get(email_field)
            if email:
                break
        
        # If no email, try to get from email_addresses array
        if not email:
            email_addresses = payload.get('email_addresses', [])
            if email_addresses and len(email_addresses) > 0:
                email = email_addresses[0].get('email_address', '')
        
        if not email:
            email = ''
        
        # Generate username
        if email:
            username = email.split('@')[0]
        else:
            username = f'user_{clerk_user_id[:8]}'
        
        first_name = payload.get('given_name', payload.get('first_name', ''))
        last_name = payload.get('family_name', payload.get('last_name', ''))
        
        # Get or create user
        try:
            user = User.objects.get(clerk_id=clerk_user_id)
            
            # Update user info if changed
            updated = False
            if email and user.email != email:
                user.email = email
                updated = True
            if first_name and user.first_name != first_name:
                user.first_name = first_name
                updated = True
            if last_name and user.last_name != last_name:
                user.last_name = last_name
                updated = True
            
            if updated:
                user.save()
            
            logger.debug(f"User found: {user.username}")
                
        except User.DoesNotExist:
            # Ensure unique username
            base_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            
            # Create new user
            user = User.objects.create(
                clerk_id=clerk_user_id,
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                email_verified=payload.get('email_verified', False),
                role='client'  # Default role
            )
            
            logger.info(f"Created new user: {user.username} (clerk_id: {clerk_user_id})")
        
        return user


class ClerkAuthenticationMiddleware:
    """
    Middleware to add Clerk authenticated user to request
    """
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Skip for admin
        if request.path.startswith('/admin/'):
            return self.get_response(request)
        
        # Only try Clerk auth if user is not already authenticated
        if not hasattr(request, 'user') or request.user.is_anonymous:
            auth = ClerkAuthentication()
            try:
                user_auth = auth.authenticate(request)
                if user_auth:
                    request.user = user_auth[0]
                    logger.debug(f"User authenticated via middleware: {request.user.username}")
            except exceptions.AuthenticationFailed as e:
                logger.debug(f"Middleware auth failed: {e}")
                pass
            except Exception as e:
                logger.debug(f"Middleware error: {e}")
                pass
        
        response = self.get_response(request)
        return response


# ============================================
# DEBUGGING HELPER
# ============================================

def debug_clerk_token(token):
    """
    Debug helper to inspect Clerk token
    Usage: python manage.py shell
    >>> from apps.users.authentication import debug_clerk_token
    >>> debug_clerk_token("your_token")
    """
    try:
        # Decode header
        header = jwt.get_unverified_header(token)
        print("\n" + "="*60)
        print("TOKEN HEADER:")
        print(json.dumps(header, indent=2))
        
        # Decode payload (without verification)
        payload = jwt.decode(token, options={"verify_signature": False, "verify_exp": False})
        print("\nTOKEN PAYLOAD:")
        print(json.dumps(payload, indent=2))
        
        # Extract important info
        print("\n" + "="*60)
        print("KEY INFORMATION:")
        print(f"Key ID (kid): {header.get('kid')}")
        print(f"Algorithm: {header.get('alg')}")
        print(f"Issuer: {payload.get('iss')}")
        print(f"Subject (User ID): {payload.get('sub')}")
        print(f"Expires: {payload.get('exp')}")
        
        # Try to fetch JWKS
        issuer = payload.get('iss')
        if issuer:
            jwks_url = f"{issuer.rstrip('/')}/.well-known/jwks.json"
            print(f"\nJWKS URL: {jwks_url}")
            
            try:
                response = requests.get(jwks_url, timeout=5)
                if response.status_code == 200:
                    jwks = response.json()
                    print(f"✓ JWKS fetched successfully")
                    print(f"  Available keys: {[k.get('kid') for k in jwks.get('keys', [])]}")
                    
                    # Check if our key is there
                    if header.get('kid') in [k.get('kid') for k in jwks.get('keys', [])]:
                        print(f"  ✓ Your token's key ({header.get('kid')}) is in JWKS!")
                    else:
                        print(f"  ✗ Your token's key ({header.get('kid')}) NOT found in JWKS")
                else:
                    print(f"✗ Failed to fetch JWKS: HTTP {response.status_code}")
            except Exception as e:
                print(f"✗ Error fetching JWKS: {e}")
        
        print("="*60 + "\n")
        return {'header': header, 'payload': payload}
        
    except Exception as e:
        print(f"Error: {e}")
        return None