from django.urls import path
from . import views

urlpatterns = [
    # Form Templates
    path('templates/', views.FormTemplateListCreateView.as_view(), name='form-template-list'),
    path('templates/<uuid:pk>/', views.FormTemplateDetailView.as_view(), name='form-template-detail'),
    path('templates/<uuid:form_id>/analytics/', views.form_analytics, name='form-analytics'),
    
    # Form Submissions
    path('submissions/', views.FormSubmissionListCreateView.as_view(), name='form-submission-list'),
    path('submissions/<uuid:pk>/', views.FormSubmissionDetailView.as_view(), name='form-submission-detail'),
    path('submissions/<uuid:submission_id>/upload/', views.upload_file, name='file-upload'),
    
    # Public endpoints
    path('public/', views.public_forms, name='public-forms'),
]
