# backend/apps/forms/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import FormTemplate, FormSubmission, FormField, FileUpload
import json

User = get_user_model()

class FormFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormField
        fields = '__all__'


class FileUploadSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    
    class Meta:
        model = FileUpload
        fields = ['id', 'field_name', 'original_filename', 'file_size', 
                 'content_type', 'uploaded_at', 'url']
    
    def get_url(self, obj):
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(f'/media/uploads/{obj.file_path}')
        return f'/media/uploads/{obj.file_path}'


class FormTemplateSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    submission_count = serializers.SerializerMethodField()
    
    class Meta:
        model = FormTemplate
        fields = ['id', 'name', 'description', 'created_by', 'created_by_name', 
                 'status', 'schema', 'allow_multiple_submissions', 
                 'require_authentication', 'auto_save_drafts', 'version',
                 'created_at', 'updated_at', 'submission_count']
        read_only_fields = ['id', 'created_by', 'version', 'created_at', 'updated_at']
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            full_name = f"{obj.created_by.first_name} {obj.created_by.last_name}".strip()
            return full_name if full_name else obj.created_by.username
        return "Unknown"
    
    def get_submission_count(self, obj):
        return obj.submissions.filter(status='submitted').count()
    
    def validate_schema(self, value):
        """Validate form schema structure"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Schema must be a JSON object")
        
        fields = value.get('fields', [])
        if not isinstance(fields, list):
            raise serializers.ValidationError("Schema must contain a 'fields' array")
        
        if len(fields) == 0:
            raise serializers.ValidationError("Schema must contain at least one field")
        
        field_names = set()
        valid_types = [choice[0] for choice in FormField.FIELD_TYPES]
        
        for idx, field in enumerate(fields):
            if not isinstance(field, dict):
                raise serializers.ValidationError(f"Field at index {idx} must be an object")
            
            # Check required field properties
            required_props = ['id', 'name', 'type', 'label']
            missing_props = [prop for prop in required_props if prop not in field]
            if missing_props:
                raise serializers.ValidationError(
                    f"Field at index {idx} is missing required properties: {', '.join(missing_props)}"
                )
            
            # Check for duplicate field names
            field_name = field['name']
            if field_name in field_names:
                raise serializers.ValidationError(f"Duplicate field name: {field_name}")
            field_names.add(field_name)
            
            # Validate field type
            if field['type'] not in valid_types:
                raise serializers.ValidationError(
                    f"Invalid field type '{field['type']}' at index {idx}. "
                    f"Valid types: {', '.join(valid_types)}"
                )
            
            # Validate options for select/radio fields
            if field['type'] in ['select', 'multiselect', 'radio']:
                options = field.get('options', [])
                if not options or not isinstance(options, list):
                    raise serializers.ValidationError(
                        f"Field '{field_name}' of type '{field['type']}' requires a non-empty 'options' array"
                    )
                
                for opt_idx, option in enumerate(options):
                    if not isinstance(option, dict) or 'label' not in option or 'value' not in option:
                        raise serializers.ValidationError(
                            f"Option at index {opt_idx} in field '{field_name}' must have 'label' and 'value'"
                        )
        
        return value


class FormSubmissionSerializer(serializers.ModelSerializer):
    submitted_by_name = serializers.SerializerMethodField()
    files = FileUploadSerializer(many=True, read_only=True)
    form_name = serializers.SerializerMethodField()
    is_complete = serializers.SerializerMethodField()
    
    class Meta:
        model = FormSubmission
        fields = ['id', 'form_template', 'form_name', 'submitted_by', 
                 'submitted_by_name', 'data', 'schema_version', 'status', 
                 'created_at', 'updated_at', 'submitted_at', 'files', 
                 'reviewed_by', 'reviewed_at', 'review_notes', 'is_complete']
        read_only_fields = ['id', 'submitted_by', 'schema_version', 'created_at', 
                           'updated_at', 'submitted_at']
    
    def get_submitted_by_name(self, obj):
        if obj.submitted_by:
            full_name = f"{obj.submitted_by.first_name} {obj.submitted_by.last_name}".strip()
            return full_name if full_name else obj.submitted_by.username
        return "Anonymous"
    
    def get_form_name(self, obj):
        return obj.form_template.name
    
    def get_is_complete(self, obj):
        return obj.is_complete()


class FormSubmissionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormSubmission
        fields = ['form_template', 'data', 'status']
    
    def create(self, validated_data):
        # Set schema version from current form template
        form_template = validated_data['form_template']
        validated_data['schema_version'] = form_template.version
        validated_data['submitted_by'] = self.context['request'].user
        
        return super().create(validated_data)
    
    def validate(self, attrs):
        form_template = attrs.get('form_template')
        data = attrs.get('data', {})
        status = attrs.get('status', 'draft')
        
        # Only validate if status is 'submitted'
        if status == 'submitted':
            self.validate_form_data(form_template, data)
        
        return attrs
    
    def validate_form_data(self, form_template, data):
        """Validate form data against schema"""
        if not form_template.schema or 'fields' not in form_template.schema:
            return
        
        schema = form_template.schema
        fields = schema.get('fields', [])
        
        # Validate required fields
        for field in fields:
            if field.get('required', False):
                field_name = field['name']
                field_value = data.get(field_name)
                
                # Check if field is filled
                if field_value is None or field_value == '' or (isinstance(field_value, list) and len(field_value) == 0):
                    raise serializers.ValidationError({
                        field_name: f"Field '{field.get('label', field_name)}' is required"
                    })
        
        # Validate field types and values
        errors = {}
        for field_name, field_value in data.items():
            field_config = self.get_field_config(fields, field_name)
            
            if field_config:
                try:
                    self.validate_field_value(field_config, field_value)
                except serializers.ValidationError as e:
                    errors[field_name] = e.detail
        
        if errors:
            raise serializers.ValidationError(errors)
    
    def get_field_config(self, fields, field_name):
        """Get field configuration by name"""
        for field in fields:
            if field['name'] == field_name:
                return field
        return None
    
    def validate_field_value(self, field_config, value):
        """Validate individual field value"""
        if value is None or value == '':
            return  # Skip validation for empty values
        
        field_type = field_config['type']
        field_label = field_config.get('label', field_config['name'])
        
        # Type-specific validations
        if field_type == 'number':
            try:
                num_value = float(value)
                
                # Check min/max
                if 'config' in field_config:
                    config = field_config['config']
                    if 'min' in config and num_value < config['min']:
                        raise serializers.ValidationError(
                            f"'{field_label}' must be at least {config['min']}"
                        )
                    if 'max' in config and num_value > config['max']:
                        raise serializers.ValidationError(
                            f"'{field_label}' must be at most {config['max']}"
                        )
            except (ValueError, TypeError):
                raise serializers.ValidationError(f"'{field_label}' must be a number")
        
        elif field_type == 'email':
            from django.core.validators import validate_email
            from django.core.exceptions import ValidationError
            try:
                validate_email(value)
            except ValidationError:
                raise serializers.ValidationError(f"'{field_label}' must be a valid email")
        
        elif field_type == 'phone':
            import re
            phone_pattern = re.compile(r'^[\+]?[1-9][\d]{0,15}$')
            if not phone_pattern.match(str(value)):
                raise serializers.ValidationError(f"'{field_label}' must be a valid phone number")
        
        elif field_type in ['select', 'radio']:
            options = field_config.get('options', [])
            valid_values = [opt.get('value') for opt in options if isinstance(opt, dict)]
            if value not in valid_values:
                raise serializers.ValidationError(
                    f"'{field_label}' contains invalid selection"
                )
        
        elif field_type == 'multiselect':
            if not isinstance(value, list):
                raise serializers.ValidationError(
                    f"'{field_label}' must be a list of values"
                )
            
            options = field_config.get('options', [])
            valid_values = [opt.get('value') for opt in options if isinstance(opt, dict)]
            for v in value:
                if v not in valid_values:
                    raise serializers.ValidationError(
                        f"'{field_label}' contains invalid selection: {v}"
                    )
        
        elif field_type == 'date':
            from datetime import datetime
            try:
                datetime.strptime(str(value), '%Y-%m-%d')
            except ValueError:
                raise serializers.ValidationError(f"'{field_label}' must be a valid date (YYYY-MM-DD)")
        
        elif field_type == 'datetime':
            from datetime import datetime
            try:
                datetime.fromisoformat(str(value).replace('Z', '+00:00'))
            except ValueError:
                raise serializers.ValidationError(f"'{field_label}' must be a valid datetime")


class FormAnalyticsSerializer(serializers.Serializer):
    total_submissions = serializers.IntegerField()
    completed_submissions = serializers.IntegerField()
    draft_submissions = serializers.IntegerField()
    completion_rate = serializers.FloatField()
    submissions_by_day = serializers.ListField()
    field_analytics = serializers.DictField()
