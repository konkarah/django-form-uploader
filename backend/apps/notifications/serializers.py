from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Notification, EmailTemplate

User = get_user_model()

class NotificationSerializer(serializers.ModelSerializer):
    recipient_name = serializers.SerializerMethodField()
    notification_type_display = serializers.CharField(
        source='get_notification_type_display', 
        read_only=True
    )
    time_since = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = ['id', 'recipient', 'recipient_name', 'notification_type', 
                 'notification_type_display', 'title', 'message', 
                 'related_object_id', 'related_object_type', 'is_read', 
                 'is_emailed', 'created_at', 'read_at', 'email_sent_at', 
                 'time_since']
        read_only_fields = ['id', 'created_at', 'read_at', 'email_sent_at']
    
    def get_recipient_name(self, obj):
        if obj.recipient:
            full_name = f"{obj.recipient.first_name} {obj.recipient.last_name}".strip()
            return full_name if full_name else obj.recipient.username
        return "Unknown"
    
    def get_time_since(self, obj):
        """Get human-readable time since notification was created"""
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        diff = now - obj.created_at
        
        if diff < timedelta(minutes=1):
            return "just now"
        elif diff < timedelta(hours=1):
            minutes = int(diff.total_seconds() / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif diff < timedelta(days=1):
            hours = int(diff.total_seconds() / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif diff < timedelta(days=7):
            days = diff.days
            return f"{days} day{'s' if days != 1 else ''} ago"
        elif diff < timedelta(days=30):
            weeks = int(diff.days / 7)
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"
        else:
            months = int(diff.days / 30)
            return f"{months} month{'s' if months != 1 else ''} ago"


class NotificationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['recipient', 'notification_type', 'title', 'message', 
                 'related_object_id', 'related_object_type']
    
    def validate_recipient(self, value):
        """Ensure recipient exists"""
        if not User.objects.filter(id=value.id).exists():
            raise serializers.ValidationError("Recipient user does not exist")
        return value
    
    def validate_notification_type(self, value):
        """Ensure notification type is valid"""
        valid_types = [choice[0] for choice in Notification.TYPE_CHOICES]
        if value not in valid_types:
            raise serializers.ValidationError(
                f"Invalid notification type. Valid types: {', '.join(valid_types)}"
            )
        return value


class EmailTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailTemplate
        fields = '__all__'
    
    def validate_available_variables(self, value):
        """Ensure available_variables is a list"""
        if not isinstance(value, list):
            raise serializers.ValidationError("available_variables must be a list")
        return value
    
    def validate(self, attrs):
        """Validate that template uses only available variables"""
        html_template = attrs.get('html_template', '')
        text_template = attrs.get('text_template', '')
        available_vars = attrs.get('available_variables', [])
        
        # Simple check for variable usage ({{ variable_name }})
        import re
        html_vars = set(re.findall(r'\{\{\s*(\w+)\s*\}\}', html_template))
        text_vars = set(re.findall(r'\{\{\s*(\w+)\s*\}\}', text_template))
        
        all_used_vars = html_vars.union(text_vars)
        invalid_vars = all_used_vars - set(available_vars)
        
        if invalid_vars:
            raise serializers.ValidationError({
                'available_variables': f"Template uses undefined variables: {', '.join(invalid_vars)}"
            })
        
        return attrs


class NotificationBulkCreateSerializer(serializers.Serializer):
    """Serializer for creating multiple notifications at once"""
    recipient_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1
    )
    notification_type = serializers.ChoiceField(choices=Notification.TYPE_CHOICES)
    title = serializers.CharField(max_length=255)
    message = serializers.CharField()
    related_object_id = serializers.UUIDField(required=False, allow_null=True)
    related_object_type = serializers.CharField(max_length=50, required=False, allow_blank=True)
    
    def validate_recipient_ids(self, value):
        """Ensure all recipient IDs exist"""
        existing_ids = set(User.objects.filter(id__in=value).values_list('id', flat=True))
        invalid_ids = set(value) - existing_ids
        
        if invalid_ids:
            raise serializers.ValidationError(
                f"Invalid recipient IDs: {', '.join(map(str, invalid_ids))}"
            )
        
        return value
    
    def create(self, validated_data):
        """Create notifications for all recipients"""
        recipient_ids = validated_data.pop('recipient_ids')
        notifications = []
        
        for recipient_id in recipient_ids:
            notification = Notification.objects.create(
                recipient_id=recipient_id,
                **validated_data
            )
            notifications.append(notification)
        
        return notifications


class NotificationStatsSerializer(serializers.Serializer):
    """Serializer for notification statistics"""
    total_notifications = serializers.IntegerField()
    unread_notifications = serializers.IntegerField()
    read_notifications = serializers.IntegerField()
    emailed_notifications = serializers.IntegerField()
    notifications_by_type = serializers.DictField()
    recent_notifications = NotificationSerializer(many=True)