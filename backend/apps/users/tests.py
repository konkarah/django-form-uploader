from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock
import jwt
import json

from .authentication import ClerkAuthentication

User = get_user_model()


class UserModelTest(TestCase):
    """Test User model"""
    
    def test_create_user(self):
        """Test creating a basic user"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.email, 'test@example.com')
        self.assertTrue(user.check_password('testpass123'))
    
    def test_user_default_role(self):
        """Test user has default role of client"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )
        
        self.assertEqual(user.role, 'client')
    
    def test_create_admin_user(self):
        """Test creating an admin user"""
        user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            role='admin'
        )
        
        self.assertEqual(user.role, 'admin')


class ClerkAuthenticationTest(TestCase):
    """Test Clerk authentication"""
    
    def setUp(self):
        self.auth = ClerkAuthentication()
    
    def test_no_authorization_header(self):
        """Test authentication returns None without auth header"""
        from django.http import HttpRequest
        
        request = HttpRequest()
        request.META = {}
        
        result = self.auth.authenticate(request)
        self.assertIsNone(result)
    
    def test_invalid_authorization_header(self):
        """Test authentication returns None with invalid header"""
        from django.http import HttpRequest
        
        request = HttpRequest()
        request.META = {'HTTP_AUTHORIZATION': 'InvalidToken'}
        
        result = self.auth.authenticate(request)
        self.assertIsNone(result)
    
    @patch('requests.get')
    def test_get_or_create_user_creates_new_user(self, mock_get):
        """Test get_or_create_user creates new user"""
        payload = {
            'sub': 'clerk_12345',
            'email': 'newuser@example.com',
            'given_name': 'John',
            'family_name': 'Doe',
            'email_verified': True
        }
        
        user = self.auth.get_or_create_user(payload)
        
        self.assertEqual(user.clerk_id, 'clerk_12345')
        self.assertEqual(user.email, 'newuser@example.com')
        self.assertEqual(user.first_name, 'John')
        self.assertEqual(user.last_name, 'Doe')
        self.assertEqual(user.role, 'client')
    
    def test_get_or_create_user_updates_existing_user(self):
        """Test get_or_create_user updates existing user info"""
        # Create existing user
        existing_user = User.objects.create_user(
            username='olduser',
            email='old@example.com',
            clerk_id='clerk_12345'
        )
        
        payload = {
            'sub': 'clerk_12345',
            'email': 'newemail@example.com',
            'given_name': 'Updated',
            'family_name': 'Name'
        }
        
        user = self.auth.get_or_create_user(payload)
        
        self.assertEqual(user.id, existing_user.id)
        self.assertEqual(user.email, 'newemail@example.com')
        self.assertEqual(user.first_name, 'Updated')
        self.assertEqual(user.last_name, 'Name')
    
    def test_get_or_create_user_generates_username_from_email(self):
        """Test username generation from email"""
        payload = {
            'sub': 'clerk_12345',
            'email': 'testuser@example.com'
        }
        
        user = self.auth.get_or_create_user(payload)
        
        self.assertEqual(user.username, 'testuser')
    
    def test_get_or_create_user_handles_duplicate_username(self):
        """Test username uniqueness handling"""
        # Create existing user with same username
        User.objects.create_user(
            username='testuser',
            email='existing@example.com',
            clerk_id='clerk_existing'
        )
        
        payload = {
            'sub': 'clerk_new',
            'email': 'testuser@example.com'
        }
        
        user = self.auth.get_or_create_user(payload)
        
        # Should have incremented username
        self.assertIn('testuser', user.username)
        self.assertNotEqual(user.username, 'testuser')
    
    def test_get_or_create_user_without_email(self):
        """Test user creation without email"""
        payload = {
            'sub': 'clerk_12345'
        }
        
        user = self.auth.get_or_create_user(payload)
        
        self.assertEqual(user.email, '')
        self.assertTrue(user.username.startswith('user_'))


class UserAPITest(APITestCase):
    """Test User API endpoints"""
    
    def setUp(self):
        self.client = APIClient()
        
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            first_name='John',
            last_name='Doe',
            role='client',
            clerk_id='clerk_test'
        )
        
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            role='admin',
            clerk_id='clerk_admin'
        )
    
    def test_get_current_user_info_requires_auth(self):
        """Test getting user info requires authentication"""
        response = self.client.get('/api/users/me/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_get_current_user_info(self):
        """Test getting current user info"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/users/me/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'testuser')
        self.assertEqual(response.data['email'], 'test@example.com')
        self.assertEqual(response.data['role'], 'client')
    
    def test_update_user_profile(self):
        """Test updating user profile"""
        self.client.force_authenticate(user=self.user)
        
        data = {
            'first_name': 'Jane',
            'last_name': 'Smith'
        }
        
        response = self.client.patch('/api/users/me/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Jane')
        self.assertEqual(self.user.last_name, 'Smith')
    
    def test_user_cannot_change_role(self):
        """Test users cannot change their own role"""
        self.client.force_authenticate(user=self.user)
        
        original_role = self.user.role
        response = self.client.patch(
            '/api/users/me/',
            {'role': 'admin'},
            format='json'
        )
        
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, original_role)


class ClerkTokenDecodingTest(TestCase):
    """Test Clerk token decoding helpers"""
    
    def test_get_clerk_domain_from_token(self):
        """Test extracting Clerk domain from token"""
        auth = ClerkAuthentication()
        
        # Create a fake token with issuer
        payload = {
            'iss': 'https://test-domain.clerk.accounts.dev',
            'sub': 'user_123'
        }
        
        token = jwt.encode(payload, 'secret', algorithm='HS256')
        
        domain = auth.get_clerk_domain_from_token(token)
        
        self.assertEqual(domain, 'https://test-domain.clerk.accounts.dev')
    
    def test_get_clerk_domain_invalid_token(self):
        """Test handling invalid token"""
        auth = ClerkAuthentication()
        
        domain = auth.get_clerk_domain_from_token('invalid_token')
        
        self.assertIsNone(domain)


# Run tests with: python manage.py test apps.users