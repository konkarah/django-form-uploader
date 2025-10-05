from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock
from datetime import timedelta
import uuid

from .models import FormTemplate, FormSubmission, FileUpload
from .serializers import FormTemplateSerializer, FormSubmissionSerializer

User = get_user_model()


class FormTemplateModelTest(TestCase):
    """Test FormTemplate model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            role='admin'
        )
        
        self.schema = {
            'fields': [
                {
                    'id': 'field_1',
                    'name': 'full_name',
                    'label': 'Full Name',
                    'type': 'text',
                    'required': True
                },
                {
                    'id': 'field_2',
                    'name': 'email',
                    'label': 'Email',
                    'type': 'email',
                    'required': True
                }
            ]
        }
    
    def test_create_form_template(self):
        """Test creating a form template"""
        form = FormTemplate.objects.create(
            name='Test Form',
            description='A test form',
            created_by=self.user,
            schema=self.schema,
            status='active'
        )
        
        self.assertEqual(form.name, 'Test Form')
        self.assertEqual(form.status, 'active')
        self.assertEqual(form.version, 1)
        self.assertIsNotNone(form.id)
    
    def test_form_template_str(self):
        """Test string representation"""
        form = FormTemplate.objects.create(
            name='Test Form',
            created_by=self.user,
            version=2
        )
        self.assertEqual(str(form), 'Test Form (v2)')
    
    def test_get_field_by_name(self):
        """Test getting field by name"""
        form = FormTemplate.objects.create(
            name='Test Form',
            created_by=self.user,
            schema=self.schema
        )
        
        field = form.get_field_by_name('full_name')
        self.assertIsNotNone(field)
        self.assertEqual(field['label'], 'Full Name')
        
        # Non-existent field
        field = form.get_field_by_name('non_existent')
        self.assertIsNone(field)
    
    def test_increment_version(self):
        """Test version increment"""
        form = FormTemplate.objects.create(
            name='Test Form',
            created_by=self.user,
            version=1
        )
        
        form.increment_version()
        form.refresh_from_db()
        self.assertEqual(form.version, 2)
    
    def test_created_by_nullable(self):
        """Test that created_by can be null"""
        form = FormTemplate.objects.create(
            name='Anonymous Form',
            created_by=None,
            schema=self.schema
        )
        self.assertIsNone(form.created_by)


class FormSubmissionModelTest(TestCase):
    """Test FormSubmission model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            role='client'
        )
        
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            role='admin'
        )
        
        self.form_template = FormTemplate.objects.create(
            name='Test Form',
            created_by=self.admin,
            schema={
                'fields': [
                    {
                        'id': 'field_1',
                        'name': 'full_name',
                        'label': 'Full Name',
                        'type': 'text',
                        'required': True
                    },
                    {
                        'id': 'field_2',
                        'name': 'age',
                        'label': 'Age',
                        'type': 'number',
                        'required': False
                    }
                ]
            }
        )
    
    def test_create_submission(self):
        """Test creating a submission"""
        submission = FormSubmission.objects.create(
            form_template=self.form_template,
            submitted_by=self.user,
            data={'full_name': 'John Doe', 'age': 30},
            status='draft'
        )
        
        self.assertEqual(submission.status, 'draft')
        self.assertEqual(submission.data['full_name'], 'John Doe')
        self.assertIsNotNone(submission.id)
    
    def test_get_field_value(self):
        """Test getting field value"""
        submission = FormSubmission.objects.create(
            form_template=self.form_template,
            submitted_by=self.user,
            data={'full_name': 'John Doe'}
        )
        
        self.assertEqual(submission.get_field_value('full_name'), 'John Doe')
        self.assertIsNone(submission.get_field_value('non_existent'))
    
    def test_set_field_value(self):
        """Test setting field value"""
        submission = FormSubmission.objects.create(
            form_template=self.form_template,
            submitted_by=self.user,
            data={}
        )
        
        submission.set_field_value('full_name', 'Jane Doe')
        self.assertEqual(submission.data['full_name'], 'Jane Doe')
    
    def test_is_complete(self):
        """Test checking if submission is complete"""
        # Complete submission
        complete_submission = FormSubmission.objects.create(
            form_template=self.form_template,
            submitted_by=self.user,
            data={'full_name': 'John Doe'}
        )
        self.assertTrue(complete_submission.is_complete())
        
        # Incomplete submission
        incomplete_submission = FormSubmission.objects.create(
            form_template=self.form_template,
            submitted_by=self.user,
            data={}
        )
        self.assertFalse(incomplete_submission.is_complete())


class FormTemplateAPITest(APITestCase):
    """Test FormTemplate API endpoints"""
    
    def setUp(self):
        self.client = APIClient()
        
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            role='admin',
            clerk_id='clerk_admin'
        )
        
        self.client_user = User.objects.create_user(
            username='client',
            email='client@example.com',
            role='client',
            clerk_id='clerk_client'
        )
        
        self.schema = {
            'fields': [
                {
                    'id': 'field_1',
                    'name': 'full_name',
                    'label': 'Full Name',
                    'type': 'text',
                    'required': True
                }
            ]
        }
    
    def test_list_form_templates(self):
        """Test listing all form templates"""
        FormTemplate.objects.create(
            name='Form 1',
            created_by=self.admin,
            schema=self.schema
        )
        FormTemplate.objects.create(
            name='Form 2',
            created_by=self.admin,
            schema=self.schema
        )
        
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/forms/templates/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_create_form_template(self):
        """Test creating a form template"""
        self.client.force_authenticate(user=self.admin)
        
        data = {
            'name': 'New Form',
            'description': 'A new form',
            'schema': self.schema,
            'status': 'active'
        }
        
        response = self.client.post('/api/forms/templates/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New Form')
        self.assertEqual(FormTemplate.objects.count(), 1)
    
    def test_retrieve_form_template(self):
        """Test retrieving a specific form template"""
        form = FormTemplate.objects.create(
            name='Test Form',
            created_by=self.admin,
            schema=self.schema
        )
        
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(f'/api/forms/templates/{form.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Form')
    
    def test_update_form_template(self):
        """Test updating a form template"""
        form = FormTemplate.objects.create(
            name='Test Form',
            created_by=self.admin,
            schema=self.schema,
            version=1
        )
        
        self.client.force_authenticate(user=self.admin)
        
        new_schema = {
            'fields': [
                {
                    'id': 'field_1',
                    'name': 'email',
                    'label': 'Email',
                    'type': 'email',
                    'required': True
                }
            ]
        }
        
        response = self.client.patch(
            f'/api/forms/templates/{form.id}/',
            {'schema': new_schema},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        form.refresh_from_db()
        self.assertEqual(form.version, 2)
    
    def test_delete_form_template(self):
        """Test deleting a form template"""
        form = FormTemplate.objects.create(
            name='Test Form',
            created_by=self.admin,
            schema=self.schema
        )
        
        self.client.force_authenticate(user=self.admin)
        response = self.client.delete(f'/api/forms/templates/{form.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(FormTemplate.objects.count(), 0)
    
    def test_filter_by_status(self):
        """Test filtering form templates by status"""
        FormTemplate.objects.create(
            name='Active Form',
            created_by=self.admin,
            schema=self.schema,
            status='active'
        )
        FormTemplate.objects.create(
            name='Draft Form',
            created_by=self.admin,
            schema=self.schema,
            status='draft'
        )
        
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/forms/templates/?status=active')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['status'], 'active')
    
    def test_search_form_templates(self):
        """Test searching form templates"""
        FormTemplate.objects.create(
            name='KYC Form',
            description='Customer verification',
            created_by=self.admin,
            schema=self.schema
        )
        FormTemplate.objects.create(
            name='Loan Application',
            description='Apply for loan',
            created_by=self.admin,
            schema=self.schema
        )
        
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/forms/templates/?search=KYC')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'KYC Form')


class FormSubmissionAPITest(APITestCase):
    """Test FormSubmission API endpoints"""
    
    def setUp(self):
        self.client = APIClient()
        
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            role='admin',
            clerk_id='clerk_admin'
        )
        
        self.client_user = User.objects.create_user(
            username='client',
            email='client@example.com',
            role='client',
            clerk_id='clerk_client'
        )
        
        self.form_template = FormTemplate.objects.create(
            name='Test Form',
            created_by=self.admin,
            schema={
                'fields': [
                    {
                        'id': 'field_1',
                        'name': 'full_name',
                        'label': 'Full Name',
                        'type': 'text',
                        'required': True
                    }
                ]
            },
            status='active'
        )
    
    def test_create_submission_as_draft(self):
        """Test creating a draft submission"""
        self.client.force_authenticate(user=self.client_user)
        
        data = {
            'form_template': str(self.form_template.id),
            'data': {'full_name': 'John Doe'},
            'status': 'draft'
        }
        
        response = self.client.post('/api/forms/submissions/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'draft')
        self.assertIsNone(response.data['submitted_at'])
    
    @patch('apps.forms.tasks.send_form_submission_notification.delay')
    def test_create_submission_as_submitted(self, mock_task):
        """Test creating a submitted submission triggers notification"""
        self.client.force_authenticate(user=self.client_user)
        
        data = {
            'form_template': str(self.form_template.id),
            'data': {'full_name': 'John Doe'},
            'status': 'submitted'
        }
        
        response = self.client.post('/api/forms/submissions/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'submitted')
        self.assertIsNotNone(response.data['submitted_at'])
        
        # Verify notification task was called
        mock_task.assert_called_once()
    
    def test_list_submissions_as_admin(self):
        """Test admin can see all submissions"""
        FormSubmission.objects.create(
            form_template=self.form_template,
            submitted_by=self.client_user,
            data={'full_name': 'John Doe'},
            status='submitted'
        )
        FormSubmission.objects.create(
            form_template=self.form_template,
            submitted_by=self.admin,
            data={'full_name': 'Admin User'},
            status='submitted'
        )
        
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/forms/submissions/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_list_submissions_as_client(self):
        """Test client can only see their own submissions"""
        FormSubmission.objects.create(
            form_template=self.form_template,
            submitted_by=self.client_user,
            data={'full_name': 'John Doe'},
            status='submitted'
        )
        FormSubmission.objects.create(
            form_template=self.form_template,
            submitted_by=self.admin,
            data={'full_name': 'Admin User'},
            status='submitted'
        )
        
        self.client.force_authenticate(user=self.client_user)
        response = self.client.get('/api/forms/submissions/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['submitted_by'], self.client_user.id)
    
    def test_update_submission(self):
        """Test updating a submission"""
        submission = FormSubmission.objects.create(
            form_template=self.form_template,
            submitted_by=self.client_user,
            data={'full_name': 'John Doe'},
            status='draft'
        )
        
        self.client.force_authenticate(user=self.client_user)
        response = self.client.patch(
            f'/api/forms/submissions/{submission.id}/',
            {'data': {'full_name': 'Jane Doe'}},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        submission.refresh_from_db()
        self.assertEqual(submission.data['full_name'], 'Jane Doe')
    
    @patch('apps.forms.tasks.send_form_submission_notification.delay')
    def test_submit_draft(self, mock_task):
        """Test submitting a draft triggers notification"""
        submission = FormSubmission.objects.create(
            form_template=self.form_template,
            submitted_by=self.client_user,
            data={'full_name': 'John Doe'},
            status='draft'
        )
        
        self.client.force_authenticate(user=self.client_user)
        response = self.client.patch(
            f'/api/forms/submissions/{submission.id}/',
            {'status': 'submitted'},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        submission.refresh_from_db()
        self.assertEqual(submission.status, 'submitted')
        self.assertIsNotNone(submission.submitted_at)
        mock_task.assert_called_once()
    
    def test_filter_submissions_by_status(self):
        """Test filtering submissions by status"""
        FormSubmission.objects.create(
            form_template=self.form_template,
            submitted_by=self.client_user,
            data={'full_name': 'John Doe'},
            status='draft'
        )
        FormSubmission.objects.create(
            form_template=self.form_template,
            submitted_by=self.client_user,
            data={'full_name': 'Jane Doe'},
            status='submitted'
        )
        
        self.client.force_authenticate(user=self.client_user)
        response = self.client.get('/api/forms/submissions/?status=submitted')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['status'], 'submitted')


class PublicFormsAPITest(APITestCase):
    """Test public forms endpoint"""
    
    def setUp(self):
        self.client = APIClient()
        
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            role='client',
            clerk_id='clerk_test'
        )
        
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            role='admin',
            clerk_id='clerk_admin'
        )
    
    def test_public_forms_returns_active_forms(self):
        """Test public endpoint returns only active forms"""
        FormTemplate.objects.create(
            name='Active Form',
            created_by=self.admin,
            status='active'
        )
        FormTemplate.objects.create(
            name='Draft Form',
            created_by=self.admin,
            status='draft'
        )
        FormTemplate.objects.create(
            name='Inactive Form',
            created_by=self.admin,
            status='inactive'
        )
        
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/forms/public/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Active Form')
    
    def test_public_forms_excludes_already_submitted(self):
        """Test forms user already submitted are excluded if multiple submissions not allowed"""
        form = FormTemplate.objects.create(
            name='Single Submission Form',
            created_by=self.admin,
            status='active',
            allow_multiple_submissions=False
        )
        
        # User already submitted this form
        FormSubmission.objects.create(
            form_template=form,
            submitted_by=self.user,
            status='submitted',
            data={}
        )
        
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/forms/public/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)
    
    def test_public_forms_includes_multiple_submission_forms(self):
        """Test forms that allow multiple submissions are always shown"""
        form = FormTemplate.objects.create(
            name='Multiple Submission Form',
            created_by=self.admin,
            status='active',
            allow_multiple_submissions=True
        )
        
        # User already submitted this form
        FormSubmission.objects.create(
            form_template=form,
            submitted_by=self.user,
            status='submitted',
            data={}
        )
        
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/forms/public/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


class FormAnalyticsAPITest(APITestCase):
    """Test form analytics endpoint"""
    
    def setUp(self):
        self.client = APIClient()
        
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            role='admin',
            clerk_id='clerk_admin'
        )
        
        self.client_user = User.objects.create_user(
            username='client',
            email='client@example.com',
            role='client',
            clerk_id='clerk_client'
        )
        
        self.form_template = FormTemplate.objects.create(
            name='Test Form',
            created_by=self.admin,
            schema={
                'fields': [
                    {
                        'id': 'field_1',
                        'name': 'full_name',
                        'label': 'Full Name',
                        'type': 'text',
                        'required': True
                    },
                    {
                        'id': 'field_2',
                        'name': 'email',
                        'label': 'Email',
                        'type': 'email',
                        'required': False
                    }
                ]
            },
            status='active'
        )
    
    def test_analytics_requires_admin(self):
        """Test non-admin cannot access analytics"""
        self.client.force_authenticate(user=self.client_user)
        response = self.client.get(f'/api/forms/templates/{self.form_template.id}/analytics/')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_analytics_basic_metrics(self):
        """Test analytics returns basic metrics"""
        # Create submissions
        FormSubmission.objects.create(
            form_template=self.form_template,
            submitted_by=self.client_user,
            data={'full_name': 'John Doe'},
            status='submitted'
        )
        FormSubmission.objects.create(
            form_template=self.form_template,
            submitted_by=self.client_user,
            data={'full_name': 'Jane Doe'},
            status='draft'
        )
        
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(f'/api/forms/templates/{self.form_template.id}/analytics/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_submissions'], 2)
        self.assertEqual(response.data['completed_submissions'], 1)
        self.assertEqual(response.data['draft_submissions'], 1)
        self.assertEqual(response.data['completion_rate'], 50.0)
    
    def test_analytics_field_analytics(self):
        """Test analytics includes field-level data"""
        FormSubmission.objects.create(
            form_template=self.form_template,
            submitted_by=self.client_user,
            data={'full_name': 'John Doe', 'email': 'john@example.com'},
            status='submitted'
        )
        FormSubmission.objects.create(
            form_template=self.form_template,
            submitted_by=self.admin,
            data={'full_name': 'Jane Doe'},
            status='submitted'
        )
        
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(f'/api/forms/templates/{self.form_template.id}/analytics/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        field_analytics = response.data['field_analytics']
        self.assertIn('full_name', field_analytics)
        self.assertIn('email', field_analytics)
        
        self.assertEqual(field_analytics['full_name']['filled_count'], 2)
        self.assertEqual(field_analytics['full_name']['fill_rate'], 100.0)
        
        self.assertEqual(field_analytics['email']['filled_count'], 1)
        self.assertEqual(field_analytics['email']['fill_rate'], 50.0)


class FileUploadAPITest(APITestCase):
    """Test file upload functionality"""
    
    def setUp(self):
        self.client = APIClient()
        
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            role='client',
            clerk_id='clerk_test'
        )
        
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            role='admin',
            clerk_id='clerk_admin'
        )
        
        self.form_template = FormTemplate.objects.create(
            name='Test Form',
            created_by=self.admin,
            status='active'
        )
        
        self.submission = FormSubmission.objects.create(
            form_template=self.form_template,
            submitted_by=self.user,
            data={},
            status='draft'
        )
    
    def test_upload_requires_authentication(self):
        """Test file upload requires authentication"""
        response = self.client.post(
            f'/api/forms/submissions/{self.submission.id}/upload/'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_upload_requires_file(self):
        """Test file upload requires a file"""
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f'/api/forms/submissions/{self.submission.id}/upload/',
            {'field_name': 'document'}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('No file provided', response.data['error'])
    
    def test_upload_requires_field_name(self):
        """Test file upload requires field_name"""
        self.client.force_authenticate(user=self.user)
        
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        file = SimpleUploadedFile("test.txt", b"file content", content_type="text/plain")
        
        response = self.client.post(
            f'/api/forms/submissions/{self.submission.id}/upload/',
            {'file': file}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('field_name is required', response.data['error'])
    
    def test_upload_permission_denied_for_other_users(self):
        """Test users cannot upload to other users' submissions"""
        other_user = User.objects.create_user(
            username='other',
            email='other@example.com',
            role='client',
            clerk_id='clerk_other'
        )
        
        self.client.force_authenticate(user=other_user)
        
        from django.core.files.uploadedfile import SimpleUploadedFile
        file = SimpleUploadedFile("test.txt", b"file content", content_type="text/plain")
        
        response = self.client.post(
            f'/api/forms/submissions/{self.submission.id}/upload/',
            {'file': file, 'field_name': 'document'}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# Run tests with: python manage.py test apps.forms