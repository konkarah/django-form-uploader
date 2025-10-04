# backend/apps/forms/permissions.py
from rest_framework import permissions

class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow admins to create/edit forms.
    Regular users can only view active forms.
    """
    
    def has_permission(self, request, view):
        # Read permissions for all authenticated users
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        
        # Write permissions only for admins
        return request.user and request.user.is_authenticated and request.user.role == 'admin'
    
    def has_object_permission(self, request, view, obj):
        # Read permissions for authenticated users
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        
        # Write permissions only for admins
        return request.user and request.user.is_authenticated and request.user.role == 'admin'


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow owners of submissions or admins to access them.
    """
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Admin can access all submissions
        if request.user.role == 'admin':
            return True
        
        # Users can only access their own submissions
        return obj.submitted_by == request.user


class IsAdmin(permissions.BasePermission):
    """
    Permission class that only allows admin users.
    """
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'admin'


class CanSubmitForm(permissions.BasePermission):
    """
    Permission to check if user can submit a specific form.
    Checks if multiple submissions are allowed.
    """
    
    def has_object_permission(self, request, view, obj):
        # Admin can always submit
        if request.user.role == 'admin':
            return True
        
        # Check if form requires authentication
        if obj.require_authentication and not request.user.is_authenticated:
            return False
        
        # Check if form allows multiple submissions
        if not obj.allow_multiple_submissions:
            # Check if user has already submitted this form
            from .models import FormSubmission
            existing_submission = FormSubmission.objects.filter(
                form_template=obj,
                submitted_by=request.user,
                status='submitted'
            ).exists()
            
            if existing_submission:
                return False
        
        return True


class CanReviewSubmission(permissions.BasePermission):
    """
    Permission to check if user can review/approve/reject submissions.
    Only admins can review.
    """
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'admin'
    
    def has_object_permission(self, request, view, obj):
        # Only admins can review
        return request.user.role == 'admin'


class CanEditDraft(permissions.BasePermission):
    """
    Permission to check if user can edit a draft submission.
    """
    
    def has_object_permission(self, request, view, obj):
        # Admin can edit any draft
        if request.user.role == 'admin':
            return True
        
        # Owner can edit their own draft
        if obj.submitted_by == request.user and obj.status == 'draft':
            return True
        
        # Cannot edit submitted forms
        return False


class CanViewSubmission(permissions.BasePermission):
    """
    Permission to check if user can view a submission.
    """
    
    def has_object_permission(self, request, view, obj):
        # Admin can view all submissions
        if request.user.role == 'admin':
            return True
        
        # Owner can view their own submissions
        if obj.submitted_by == request.user:
            return True
        
        return False


# backend/apps/notifications/permissions.py
from rest_framework import permissions

class IsRecipient(permissions.BasePermission):
    """
    Permission to check if user is the notification recipient.
    """
    
    def has_object_permission(self, request, view, obj):
        return obj.recipient == request.user


class IsRecipientOrAdmin(permissions.BasePermission):
    """
    Permission to allow notification recipient or admin to access.
    """
    
    def has_object_permission(self, request, view, obj):
        # Admin can access all notifications
        if request.user.role == 'admin':
            return True
        
        # Recipient can access their own notifications
        return obj.recipient == request.user


class CanCreateNotification(permissions.BasePermission):
    """
    Permission to check if user can create notifications.
    Only admins and system can create notifications.
    """
    
    def has_permission(self, request, view):
        # Only admins can manually create notifications
        return request.user and request.user.is_authenticated and request.user.role == 'admin'


# backend/apps/users/permissions.py
from rest_framework import permissions

class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Permission to allow users to edit their own profile or admins to edit any profile.
    """
    
    def has_object_permission(self, request, view, obj):
        # Admin can access any user
        if request.user.role == 'admin':
            return True
        
        # Users can only access their own profile
        return obj == request.user


class IsAdmin(permissions.BasePermission):
    """
    Permission class that only allows admin users.
    """
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'admin'


class CanPromoteUser(permissions.BasePermission):
    """
    Permission to check if user can promote other users to admin.
    Only existing admins can promote.
    """
    
    def has_permission(self, request, view):
        # Only admins can promote users
        return request.user and request.user.is_authenticated and request.user.role == 'admin'
    
    def has_object_permission(self, request, view, obj):
        # Admin can promote any non-admin user
        if request.user.role == 'admin':
            return obj.role != 'admin'
        
        return False


class CanViewUserList(permissions.BasePermission):
    """
    Permission to check if user can view list of users.
    Only admins can view user lists.
    """
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'admin'


# Helper function to check permissions programmatically
def user_can_access_form(user, form_template):
    """
    Check if user has permission to access a form template.
    
    Args:
        user: User instance
        form_template: FormTemplate instance
    
    Returns:
        bool: True if user can access, False otherwise
    """
    # Admin can access everything
    if user.role == 'admin':
        return True
    
    # Check if form is active
    if form_template.status != 'active':
        return False
    
    # Check if form requires authentication
    if form_template.require_authentication and not user.is_authenticated:
        return False
    
    return True


def user_can_submit_form(user, form_template):
    """
    Check if user can submit a specific form.
    
    Args:
        user: User instance
        form_template: FormTemplate instance
    
    Returns:
        tuple: (bool, str) - (can_submit, reason_if_not)
    """
    from apps.forms.models import FormSubmission
    
    # Admin can always submit
    if user.role == 'admin':
        return True, None
    
    # Check if form is active
    if form_template.status != 'active':
        return False, "Form is not active"
    
    # Check if form requires authentication
    if form_template.require_authentication and not user.is_authenticated:
        return False, "Authentication required"
    
    # Check if form allows multiple submissions
    if not form_template.allow_multiple_submissions:
        existing_submission = FormSubmission.objects.filter(
            form_template=form_template,
            submitted_by=user,
            status='submitted'
        ).exists()
        
        if existing_submission:
            return False, "You have already submitted this form"
    
    return True, None


def user_can_review_submission(user, submission):
    """
    Check if user can review a submission.
    
    Args:
        user: User instance
        submission: FormSubmission instance
    
    Returns:
        bool: True if user can review, False otherwise
    """
    # Only admins can review
    if user.role != 'admin':
        return False
    
    # Cannot review drafts
    if submission.status == 'draft':
        return False
    
    return True