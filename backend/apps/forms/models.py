from django.db import models
from django.contrib.auth import get_user_model
import json
import uuid

User = get_user_model()

class FormTemplate(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_forms')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    
    # JSON schema for form fields
    schema = models.JSONField(default=dict)
    
    # Settings
    allow_multiple_submissions = models.BooleanField(default=False)
    require_authentication = models.BooleanField(default=True)
    auto_save_drafts = models.BooleanField(default=True)
    
    # Metadata
    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} (v{self.version})"
    
    def get_field_by_name(self, field_name):
        """Get field configuration by name from schema"""
        for field in self.schema.get('fields', []):
            if field.get('name') == field_name:
                return field
        return None
    
    def increment_version(self):
        """Increment version when schema changes"""
        self.version += 1
        self.save(update_fields=['version', 'updated_at'])


class FormSubmission(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('reviewed', 'Reviewed'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    form_template = models.ForeignKey(FormTemplate, on_delete=models.CASCADE, related_name='submissions')
    submitted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submissions', null=True, blank=True)
    
    # Store form data as JSON
    data = models.JSONField(default=dict)
    
    # Track which schema version was used
    schema_version = models.IntegerField(default=1)
    
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='draft')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    
    # Admin review
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_submissions')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = [['form_template', 'submitted_by']]  # Prevent duplicate submissions unless allowed
    
    def __str__(self):
        return f"{self.form_template.name} - {self.submitted_by or 'Anonymous'}"
    
    def get_field_value(self, field_name):
        """Get value for a specific field"""
        return self.data.get(field_name)
    
    def set_field_value(self, field_name, value):
        """Set value for a specific field"""
        self.data[field_name] = value
    
    def is_complete(self):
        """Check if all required fields are filled"""
        schema = self.form_template.schema
        required_fields = [
            field['name'] for field in schema.get('fields', [])
            if field.get('required', False)
        ]
        
        for field_name in required_fields:
            if not self.data.get(field_name):
                return False
        return True


class FormField(models.Model):
    """Template for common field configurations"""
    FIELD_TYPES = [
        ('text', 'Text Input'),
        ('textarea', 'Textarea'),
        ('number', 'Number'),
        ('email', 'Email'),
        ('phone', 'Phone'),
        ('date', 'Date'),
        ('datetime', 'Date & Time'),
        ('select', 'Dropdown'),
        ('multiselect', 'Multiple Select'),
        ('checkbox', 'Checkbox'),
        ('radio', 'Radio Buttons'),
        ('file', 'File Upload'),
        ('files', 'Multiple File Upload'),
        ('richtext', 'Rich Text Editor'),
        ('rating', 'Rating Scale'),
        ('slider', 'Slider'),
        ('address', 'Address'),
        ('signature', 'Digital Signature'),
    ]
    
    name = models.CharField(max_length=100)
    label = models.CharField(max_length=255)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES)
    description = models.TextField(blank=True)
    
    # Configuration JSON
    config = models.JSONField(default=dict)
    
    # Common properties
    required = models.BooleanField(default=False)
    placeholder = models.CharField(max_length=255, blank=True)
    default_value = models.TextField(blank=True)
    
    # Validation rules
    validation_rules = models.JSONField(default=dict)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.label} ({self.field_type})"


class FileUpload(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.ForeignKey(FormSubmission, on_delete=models.CASCADE, related_name='files')
    field_name = models.CharField(max_length=100)
    
    # File details
    original_filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    file_size = models.PositiveIntegerField()
    content_type = models.CharField(max_length=100)
    
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.original_filename} - {self.submission}"