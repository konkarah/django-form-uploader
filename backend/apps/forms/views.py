from rest_framework import generics, permissions, status, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Count, Q
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django_filters.rest_framework import DjangoFilterBackend
from .models import FormTemplate, FormSubmission, FileUpload
from .serializers import (
    FormTemplateSerializer, FormSubmissionSerializer, 
    FormSubmissionCreateSerializer, FileUploadSerializer,
    FormAnalyticsSerializer
)
from .tasks import send_form_submission_notification
from .permissions import IsAdminOrReadOnly, IsOwnerOrAdmin
import uuid
import os
import magic

class FormTemplateListCreateView(generics.ListCreateAPIView):
    queryset = FormTemplate.objects.all()
    serializer_class = FormTemplateSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'created_by']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'updated_at', 'name']
    ordering = ['-created_at']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class FormTemplateDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = FormTemplate.objects.all()
    serializer_class = FormTemplateSerializer
    permission_classes = [IsAdminOrReadOnly]
    
    def perform_update(self, serializer):
        # Increment version if schema changed
        if 'schema' in serializer.validated_data:
            old_schema = self.get_object().schema
            new_schema = serializer.validated_data['schema']
            if old_schema != new_schema:
                form = serializer.save()
                form.increment_version()

class FormSubmissionListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['form_template', 'status', 'submitted_by']
    search_fields = ['data']
    ordering_fields = ['created_at', 'updated_at', 'submitted_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return FormSubmission.objects.all()
        else:
            return FormSubmission.objects.filter(submitted_by=user)
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return FormSubmissionCreateSerializer
        return FormSubmissionSerializer
    
    def perform_create(self, serializer):
        submission = serializer.save()
        
        # Send notification if submitted (not draft)
        if submission.status == 'submitted':
            submission.submitted_at = timezone.now()
            submission.save(update_fields=['submitted_at'])
            
            # Send async notification
            send_form_submission_notification.delay(str(submission.id))

class FormSubmissionDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = FormSubmissionSerializer
    permission_classes = [IsOwnerOrAdmin]
    
    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return FormSubmission.objects.all()
        else:
            return FormSubmission.objects.filter(submitted_by=user)
    
    def perform_update(self, serializer):
        submission = serializer.save()
        
        # Handle status changes
        if 'status' in serializer.validated_data:
            new_status = serializer.validated_data['status']
            
            if new_status == 'submitted' and not submission.submitted_at:
                submission.submitted_at = timezone.now()
                submission.save(update_fields=['submitted_at'])
                
                # Send notification
                send_form_submission_notification.delay(str(submission.id))

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def public_forms(request):
    """Get list of active forms available for submission"""
    forms = FormTemplate.objects.filter(status='active')
    
    # Check if user already submitted forms that don't allow multiple submissions
    if request.user.is_authenticated:
        user_submissions = FormSubmission.objects.filter(
            submitted_by=request.user,
            status='submitted'
        ).values_list('form_template_id', flat=True)
        
        # Filter out forms that don't allow multiple submissions and user already submitted
        forms = forms.exclude(
            Q(allow_multiple_submissions=False) & Q(id__in=user_submissions)
        )
    
    serializer = FormTemplateSerializer(forms, many=True, context={'request': request})
    return Response(serializer.data)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def upload_file(request, submission_id):
    """Upload file for a specific form submission"""
    try:
        submission = FormSubmission.objects.get(id=submission_id)
        
        # Check permissions
        if submission.submitted_by != request.user and request.user.role != 'admin':
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        if 'file' not in request.FILES:
            return Response(
                {'error': 'No file provided'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        uploaded_file = request.FILES['file']
        field_name = request.data.get('field_name')
        
        if not field_name:
            return Response(
                {'error': 'field_name is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate file type
        file_content = uploaded_file.read()
        uploaded_file.seek(0)  # Reset file pointer
        
        mime_type = magic.from_buffer(file_content, mime=True)
        file_extension = uploaded_file.name.split('.')[-1].lower()
        
        from django.conf import settings
        if file_extension not in settings.ALLOWED_FILE_TYPES:
            return Response(
                {'error': f'File type {file_extension} is not allowed'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check file size
        if uploaded_file.size > settings.MAX_FILE_SIZE:
            return Response(
                {'error': 'File size exceeds maximum allowed size'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate unique filename
        file_id = str(uuid.uuid4())
        filename = f"{file_id}_{uploaded_file.name}"
        file_path = os.path.join('uploads', str(submission.id), filename)
        
        # Save file
        saved_path = default_storage.save(file_path, ContentFile(file_content))
        
        # Create FileUpload record
        file_upload = FileUpload.objects.create(
            submission=submission,
            field_name=field_name,
            original_filename=uploaded_file.name,
            file_path=saved_path,
            file_size=uploaded_file.size,
            content_type=mime_type
        )
        
        serializer = FileUploadSerializer(file_upload, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)
        
    except FormSubmission.DoesNotExist:
        return Response(
            {'error': 'Submission not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def form_analytics(request, form_id):
    """Get analytics for a specific form"""
    if request.user.role != 'admin':
        return Response(
            {'error': 'Admin access required'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        form = FormTemplate.objects.get(id=form_id)
        
        # Basic metrics
        total_submissions = form.submissions.count()
        completed_submissions = form.submissions.filter(status='submitted').count()
        draft_submissions = form.submissions.filter(status='draft').count()
        completion_rate = (completed_submissions / total_submissions * 100) if total_submissions > 0 else 0
        
        # Submissions by day (last 30 days)
        from datetime import datetime, timedelta
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        daily_submissions = (
            form.submissions.filter(created_at__gte=thirty_days_ago)
            .extra({'date': "date(created_at)"})
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )
        
        # Field analytics
        field_analytics = {}
        if form.schema and 'fields' in form.schema:
            for field in form.schema['fields']:
                field_name = field['name']
                field_type = field['type']
                
                # Count submissions with this field filled
                filled_count = 0
                for submission in form.submissions.filter(status='submitted'):
                    if submission.data.get(field_name):
                        filled_count += 1
                
                field_analytics[field_name] = {
                    'label': field.get('label', field_name),
                    'type': field_type,
                    'filled_count': filled_count,
                    'fill_rate': (filled_count / completed_submissions * 100) if completed_submissions > 0 else 0
                }
        
        analytics_data = {
            'total_submissions': total_submissions,
            'completed_submissions': completed_submissions,
            'draft_submissions': draft_submissions,
            'completion_rate': completion_rate,
            'submissions_by_day': list(daily_submissions),
            'field_analytics': field_analytics
        }
        
        serializer = FormAnalyticsSerializer(analytics_data)
        return Response(serializer.data)
        
    except FormTemplate.DoesNotExist:
        return Response(
            {'error': 'Form not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )