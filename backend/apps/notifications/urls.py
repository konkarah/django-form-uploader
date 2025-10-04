from django.urls import path
from . import views

urlpatterns = [
    path('', views.NotificationListView.as_view(), name='notification-list'),
    path('<uuid:notification_id>/read/', views.mark_notification_read, name='mark-notification-read'),
    path('mark-all-read/', views.mark_all_read, name='mark-all-read'),
    path('unread-count/', views.unread_count, name='unread-count'),
    path('<uuid:notification_id>/delete/', views.delete_notification, name='delete-notification'),
]