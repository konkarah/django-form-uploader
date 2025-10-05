from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock
from datetime import timedelta

from .models import Notification, EmailTemplate
from .serializers import (
    NotificationSerializer, 
    NotificationCreateSerializer,
    NotificationBulkCreateSerializer
)

User = get_user_model()


class NotificationModelTest(TestCase):
    """Test Notification model"""
    
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
    
    def test_create_notification(self):
        """Test creating a notification"""
        notification = Notification.objects.create(
            recipient=self.user,
            notification_type='form_submitted',
            title='Test Notification',
            message='This is a test message',
            related_object_id='123e4567-e89b-12d3-a456-426614174000',
            related_object_type='form_submission'
        )
        
        self.assertEqual(notification.recipient, self.user)
        self.assertEqual(notification.notification_type, 'form_submitted')
        self.assertFalse(notification.is_read)
        self.assertFalse(notification.is_emailed)
        self.assertIsNotNone(notification.id)
    
    def test_notification_str(self):
        """Test string representation"""
        notification = Notification.objects.create(
            recipient=self.user,
            notification_type='system',
            title='Test Notification',
            message='Test message'
        )
        
        self.assertEqual(str(notification), f'Test Notification - {self.user.username}')
    
    def test_mark_as_read(self):
        """Test marking notification as read"""
        notification = Notification.objects.create(
            recipient=self.user,
            notification_type='system',
            title='Test Notification',
            message='Test message'
        )
        
        self.assertFalse(notification.is_read)
        self.assertIsNone(notification.read_at)
        
        notification.mark_as_read()
        
        self.assertTrue(notification.is_read)
        self.assertIsNotNone(notification.read_at)
    
    def test_mark_as_read_idempotent(self):
        """Test marking as read multiple times doesn't change read_at"""
        notification = Notification.objects.create(
            recipient=self.user,
            notification_type='system',
            title='Test Notification',
            message='Test message'
        )
        
        notification.mark_as_read()
        first_read_at = notification.read_at
        
        # Try marking as read again
        notification.mark_as_read()
        
        self.assertEqual(notification.read_at, first_read_at)
    
    def test_notification_ordering(self):
        """Test notifications are ordered by created_at descending"""
        old_notification = Notification.objects.create(
            recipient=self.user,
            notification_type='system',
            title='Old Notification',
            message='Old message'
        )
        
        new_notification = Notification.objects.create(
            recipient=self.user,
            notification_type='system',
            title='New Notification',
            message='New message'
        )
        
        notifications = Notification.objects.all()
        self.assertEqual(notifications[0], new_notification)
        self.assertEqual(notifications[1], old_notification)


class EmailTemplateModelTest(TestCase):
    """Test EmailTemplate model"""
    
    def test_create_email_template(self):
        """Test creating an email template"""
        template = EmailTemplate.objects.create(
            name='form_submission',
            subject='New Form Submission',
            html_template='<p>Hello {{ recipient_name }}</p>',
            text_template='Hello {{ recipient_name }}',
            available_variables=['recipient_name', 'form_name']
        )
        
        self.assertEqual(template.name, 'form_submission')
        self.assertEqual(len(template.available_variables), 2)
    
    def test_email_template_str(self):
        """Test string representation"""
        template = EmailTemplate.objects.create(
            name='test_template',
            subject='Test Subject',
            html_template='<p>Test</p>',
            text_template='Test'
        )
        
        self.assertEqual(str(template), 'test_template')


class NotificationSerializerTest(TestCase):
    """Test Notification serializers"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            first_name='John',
            last_name='Doe',
            role='client'
        )
    
    def test_notification_serializer(self):
        """Test NotificationSerializer output"""
        notification = Notification.objects.create(
            recipient=self.user,
            notification_type='form_submitted',
            title='Test Notification',
            message='Test message'
        )
        
        serializer = NotificationSerializer(notification)
        data = serializer.data
        
        self.assertEqual(data['title'], 'Test Notification')
        self.assertEqual(data['recipient_name'], 'John Doe')
        self.assertEqual(data['notification_type_display'], 'Form Submitted')
        self.assertIn('time_since', data)
    
    def test_time_since_calculation(self):
        """Test time_since field calculation"""
        notification = Notification.objects.create(
            recipient=self.user,
            notification_type='system',
            title='Test',
            message='Test'
        )
        
        serializer = NotificationSerializer(notification)
        self.assertEqual(serializer.data['time_since'], 'just now')
    
    def test_notification_create_serializer(self):
        """Test NotificationCreateSerializer validation"""
        data = {
            'recipient': self.user.id,
            'notification_type': 'system',
            'title': 'Test Notification',
            'message': 'Test message'
        }
        
        serializer = NotificationCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
    
    def test_invalid_notification_type(self):
        """Test validation fails for invalid notification type"""
        data = {
            'recipient': self.user.id,
            'notification_type': 'invalid_type',
            'title': 'Test',
            'message': 'Test'
        }
        
        serializer = NotificationCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('notification_type', serializer.errors)
    
    def test_bulk_create_serializer(self):
        """Test NotificationBulkCreateSerializer"""
        user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com'
        )
        
        data = {
            'recipient_ids': [str(self.user.id), str(user2.id)],
            'notification_type': 'system',
            'title': 'Bulk Notification',
            'message': 'Sent to multiple users'
        }
        
        serializer = NotificationBulkCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        notifications = serializer.save()
        self.assertEqual(len(notifications), 2)
        self.assertEqual(Notification.objects.count(), 2)


class NotificationAPITest(APITestCase):
    """Test Notification API endpoints"""
    
    def setUp(self):
        self.client = APIClient()
        
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            role='client',
            clerk_id='clerk_test'
        )
        
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            role='client',
            clerk_id='clerk_other'
        )
    
    def test_list_notifications_requires_auth(self):
        """Test listing notifications requires authentication"""
        response = self.client.get('/api/notifications/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_list_user_notifications(self):
        """Test user can only see their own notifications"""
        # Create notifications for both users
        Notification.objects.create(
            recipient=self.user,
            notification_type='system',
            title='User Notification',
            message='For user'
        )
        Notification.objects.create(
            recipient=self.other_user,
            notification_type='system',
            title='Other Notification',
            message='For other user'
        )
        
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/notifications/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['title'], 'User Notification')
    
    def test_mark_notification_read(self):
        """Test marking a notification as read"""
        notification = Notification.objects.create(
            recipient=self.user,
            notification_type='system',
            title='Test',
            message='Test'
        )
        
        self.client.force_authenticate(user=self.user)
        response = self.client.post(f'/api/notifications/{notification.id}/mark-read/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
        self.assertIsNotNone(notification.read_at)
    
    def test_cannot_mark_other_user_notification_read(self):
        """Test user cannot mark another user's notification as read"""
        notification = Notification.objects.create(
            recipient=self.other_user,
            notification_type='system',
            title='Test',
            message='Test'
        )
        
        self.client.force_authenticate(user=self.user)
        response = self.client.post(f'/api/notifications/{notification.id}/mark-read/')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_mark_all_read(self):
        """Test marking all notifications as read"""
        # Create multiple notifications
        for i in range(3):
            Notification.objects.create(
                recipient=self.user,
                notification_type='system',
                title=f'Notification {i}',
                message='Test'
            )
        
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/notifications/mark-all-read/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('3 notifications marked as read', response.data['message'])
        
        # Verify all are read
        unread_count = Notification.objects.filter(
            recipient=self.user,
            is_read=False
        ).count()
        self.assertEqual(unread_count, 0)
    
    def test_unread_count(self):
        """Test getting unread notification count"""
        # Create read and unread notifications
        Notification.objects.create(
            recipient=self.user,
            notification_type='system',
            title='Read',
            message='Test',
            is_read=True
        )
        Notification.objects.create(
            recipient=self.user,
            notification_type='system',
            title='Unread 1',
            message='Test'
        )
        Notification.objects.create(
            recipient=self.user,
            notification_type='system',
            title='Unread 2',
            message='Test'
        )
        
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/notifications/unread-count/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['unread_count'], 2)
    
    def test_delete_notification(self):
        """Test deleting a notification"""
        notification = Notification.objects.create(
            recipient=self.user,
            notification_type='system',
            title='Test',
            message='Test'
        )
        
        self.client.force_authenticate(user=self.user)
        response = self.client.delete(f'/api/notifications/{notification.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Notification.objects.count(), 0)
    
    def test_cannot_delete_other_user_notification(self):
        """Test user cannot delete another user's notification"""
        notification = Notification.objects.create(
            recipient=self.other_user,
            notification_type='system',
            title='Test',
            message='Test'
        )
        
        self.client.force_authenticate(user=self.user)
        response = self.client.delete(f'/api/notifications/{notification.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Notification.objects.count(), 1)


class NotificationTaskTest(TestCase):
    """Test notification Celery tasks"""
    
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            role='admin'
        )
        
        self.user = User.objects.create_user(
            username='user',
            email='user@example.com',
            role='client'
        )
    
    @patch('apps.forms.tasks.send_email_notification.delay')
    def test_send_form_submission_notification(self, mock_email_task):
        """Test form submission notification task"""
        from apps.forms.models import FormTemplate, FormSubmission
        from apps.forms.tasks import send_form_submission_notification
        
        # Create form and submission
        form = FormTemplate.objects.create(
            name='Test Form',
            created_by=self.admin
        )
        
        submission = FormSubmission.objects.create(
            form_template=form,
            submitted_by=self.user,
            data={'test': 'data'},
            status='submitted'
        )
        
        # Run task
        result = send_form_submission_notification(str(submission.id))
        
        # Verify notification was created
        self.assertEqual(Notification.objects.count(), 1)
        notification = Notification.objects.first()
        self.assertEqual(notification.recipient, self.admin)
        self.assertEqual(notification.notification_type, 'form_submitted')
        self.assertIn(form.name, notification.title)
        
        # Verify email task was queued
        mock_email_task.assert_called_once()
    
    @patch('sendgrid.SendGridAPIClient.send')
    def test_send_email_notification(self, mock_sendgrid):
        """Test email notification task"""
        from apps.forms.tasks import send_email_notification
        
        # Create notification
        notification = Notification.objects.create(
            recipient=self.user,
            notification_type='system',
            title='Test Notification',
            message='Test message'
        )
        
        # Mock SendGrid response
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_sendgrid.return_value = mock_response
        
        # Run task
        result = send_email_notification(notification.id)
        
        # Verify notification was marked as emailed
        notification.refresh_from_db()
        self.assertTrue(notification.is_emailed)
        self.assertIsNotNone(notification.email_sent_at)
        
        # Verify SendGrid was called
        mock_sendgrid.assert_called_once()
    
    def test_send_email_notification_no_email(self):
        """Test email task handles user without email"""
        from apps.forms.tasks import send_email_notification
        
        # Create user without email
        user_no_email = User.objects.create_user(
            username='noemail',
            email=''
        )
        
        notification = Notification.objects.create(
            recipient=user_no_email,
            notification_type='system',
            title='Test',
            message='Test'
        )
        
        result = send_email_notification(notification.id)
        
        self.assertEqual(result, 'No email address')
        notification.refresh_from_db()
        self.assertFalse(notification.is_emailed)
    
    def test_send_email_notification_already_sent(self):
        """Test email task skips already sent notifications"""
        from apps.forms.tasks import send_email_notification
        
        notification = Notification.objects.create(
            recipient=self.user,
            notification_type='system',
            title='Test',
            message='Test',
            is_emailed=True,
            email_sent_at=timezone.now()
        )
        
        result = send_email_notification(notification.id)
        
        self.assertEqual(result, 'Email already sent')
    
    def test_cleanup_old_drafts(self):
        """Test cleanup old drafts task"""
        from apps.forms.models import FormTemplate, FormSubmission
        from apps.forms.tasks import cleanup_old_drafts
        
        form = FormTemplate.objects.create(
            name='Test Form',
            created_by=self.admin
        )
        
        # Create old draft
        old_draft = FormSubmission.objects.create(
            form_template=form,
            submitted_by=self.user,
            status='draft',
            data={}
        )
        old_draft.updated_at = timezone.now() - timedelta(days=31)
        old_draft.save()
        
        # Create recent draft
        recent_draft = FormSubmission.objects.create(
            form_template=form,
            submitted_by=self.user,
            status='draft',
            data={}
        )
        
        # Run task
        result = cleanup_old_drafts()
        
        # Verify old draft was deleted
        self.assertEqual(FormSubmission.objects.count(), 1)
        self.assertTrue(FormSubmission.objects.filter(id=recent_draft.id).exists())
        self.assertFalse(FormSubmission.objects.filter(id=old_draft.id).exists())
    
    @patch('apps.forms.tasks.send_email_notification.delay')
    def test_send_form_review_notification(self, mock_email_task):
        """Test form review notification task"""
        from apps.forms.models import FormTemplate, FormSubmission
        from apps.forms.tasks import send_form_review_notification
        
        form = FormTemplate.objects.create(
            name='Test Form',
            created_by=self.admin
        )
        
        submission = FormSubmission.objects.create(
            form_template=form,
            submitted_by=self.user,
            status='submitted',
            data={}
        )
        
        # Run task
        result = send_form_review_notification(
            str(submission.id),
            'approved',
            'Looks good!'
        )
        
        # Verify notification was created for submitter
        self.assertEqual(Notification.objects.count(), 1)
        notification = Notification.objects.first()
        self.assertEqual(notification.recipient, self.user)
        self.assertIn('approved', notification.message.lower())
        self.assertIn('Looks good!', notification.message)


# Run tests with: python manage.py test apps.notifications