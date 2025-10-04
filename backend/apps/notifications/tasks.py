from celery import shared_task
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.conf import settings
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from datetime import timedelta
import logging
from .models import FormSubmission
from apps.notifications.models import Notification

User = get_user_model()
logger = logging.getLogger(__name__)

@shared_task
def send_form_submission_notification(submission_id):
    """
    Send notification when a form is submitted
    """
    try:

        submission = FormSubmission.objects.select_related(
            'form_template', 'submitted_by'
        ).get(id=submission_id)
        
        # Get all admin users
        admin_users = User.objects.filter(role='admin')
        
        for admin in admin_users:
            # Create in-app notification
            notification = Notification.objects.create(
                recipient=admin,
                notification_type='form_submitted',
                title=f'New Form Submission: {submission.form_template.name}',
                message=f'A new submission has been received for "{submission.form_template.name}" from {submission.submitted_by.get_full_name() or submission.submitted_by.username}.',
                related_object_id=submission.id,
                related_object_type='form_submission'
            )
            
            # Send email notification
            try:
                send_email_notification.delay(notification.id)
            except Exception as e:
                logger.error(f"Failed to queue email notification: {str(e)}")
        
        logger.info(f"Form submission notification sent for submission {submission_id}")
        return f"Notification sent for submission {submission_id}"
        
    except Exception as e:
        logger.error(f"Failed to send form submission notification: {str(e)}")
        raise

@shared_task
def send_email_notification(notification_id):
    """
    Send email notification using SendGrid
    """
    try:
        from apps.notifications.models import Notification
        
        notification = Notification.objects.select_related('recipient').get(id=notification_id)
        
        if notification.is_emailed:
            logger.info(f"Email already sent for notification {notification_id}")
            return "Email already sent"
        
        # Prepare email content
        subject = notification.title
        recipient_email = notification.recipient.email
        
        if not recipient_email:
            logger.warning(f"No email address for user {notification.recipient.id}")
            return "No email address"
        
        # Create HTML content
        html_content = render_to_string('emails/notification.html', {
            'notification': notification,
            'recipient': notification.recipient,
        })
        
        # Create plain text content
        text_content = f"""
        {notification.title}
        
        {notification.message}
        
        ---
        This is an automated notification from Dynamic Forms System.
        """
        
        # Send email using SendGrid
        message = Mail(
            from_email=settings.DEFAULT_FROM_EMAIL,
            to_emails=recipient_email,
            subject=subject,
            html_content=html_content,
            plain_text_content=text_content
        )
        
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        response = sg.send(message)
        
        # Update notification
        notification.is_emailed = True
        notification.email_sent_at = timezone.now()
        notification.save(update_fields=['is_emailed', 'email_sent_at'])
        
        logger.info(f"Email sent successfully for notification {notification_id}")
        return f"Email sent to {recipient_email}"
        
    except Exception as e:
        logger.error(f"Failed to send email notification: {str(e)}")
        raise

@shared_task
def cleanup_old_drafts():
    """
    Clean up draft submissions older than 30 days
    """
    try:
        from .models import FormSubmission
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        old_drafts = FormSubmission.objects.filter(
            status='draft',
            updated_at__lt=thirty_days_ago
        )
        
        count = old_drafts.count()
        old_drafts.delete()
        
        logger.info(f"Cleaned up {count} old draft submissions")
        return f"Cleaned up {count} old drafts"
        
    except Exception as e:
        logger.error(f"Failed to cleanup old drafts: {str(e)}")
        raise

@shared_task
def send_form_review_notification(submission_id, status, review_notes=""):
    """
    Send notification when form is reviewed
    """
    try:
        from .models import FormSubmission
        from apps.notifications.models import Notification
        
        submission = FormSubmission.objects.select_related(
            'form_template', 'submitted_by', 'reviewed_by'
        ).get(id=submission_id)
        
        if not submission.submitted_by:
            return "No submitted_by user"
        
        # Create in-app notification
        status_text = {
            'approved': 'approved',
            'rejected': 'rejected',
            'reviewed': 'reviewed'
        }.get(status, 'updated')
        
        notification = Notification.objects.create(
            recipient=submission.submitted_by,
            notification_type=f'form_{status}',
            title=f'Form {status_text.title()}: {submission.form_template.name}',
            message=f'Your submission for "{submission.form_template.name}" has been {status_text}.' + 
                   (f'\n\nReview notes: {review_notes}' if review_notes else ''),
            related_object_id=submission.id,
            related_object_type='form_submission'
        )
        
        # Send email notification
        try:
            send_email_notification.delay(notification.id)
        except Exception as e:
            logger.error(f"Failed to queue email notification: {str(e)}")
        
        logger.info(f"Form review notification sent for submission {submission_id}")
        return f"Review notification sent for submission {submission_id}"
        
    except Exception as e:
        logger.error(f"Failed to send form review notification: {str(e)}")
        raise

@shared_task
def send_pending_notifications():
    """
    This task sends out any pending notifications.
    Define your actual logic here.
    """
    logger.info("Running send_pending_notifications...")
    # TODO: Add logic to check for pending notifications and send them
    return "Pending notifications sent"