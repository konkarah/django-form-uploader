from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.utils import timezone
from .models import Notification
from .serializers import NotificationSerializer

class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    # def get_queryset(self):
    #     return Notification.objects.filter(recipient=self.request.user)
    def get_queryset(self):
        # Temporary debugging
        print(f"=== NOTIFICATION DEBUG ===")
        print(f"User: {self.request.user.username}")
        print(f"User ID: {self.request.user.id}")
        print(f"User role: {self.request.user.role}")
        print(f"Total notifications in DB: {Notification.objects.count()}")
        print(f"Notifications for this user: {Notification.objects.filter(recipient=self.request.user).count()}")
        
        # Show all notifications with their recipients
        all_notifs = Notification.objects.all().values('recipient__username', 'recipient__role', 'title')
        print(f"All notifications: {list(all_notifs)}")
        print(f"========================")
        
        return Notification.objects.filter(recipient=self.request.user)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def mark_notification_read(request, notification_id):
    """Mark a notification as read"""
    try:
        notification = Notification.objects.get(
            id=notification_id,
            recipient=request.user
        )
        notification.mark_as_read()
        
        serializer = NotificationSerializer(notification)
        return Response(serializer.data)
        
    except Notification.DoesNotExist:
        return Response(
            {'error': 'Notification not found'},
            status=status.HTTP_404_NOT_FOUND
        )

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def mark_all_read(request):
    """Mark all notifications as read for current user"""
    notifications = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    )
    
    updated_count = 0
    for notification in notifications:
        notification.mark_as_read()
        updated_count += 1
    
    return Response({'message': f'{updated_count} notifications marked as read'})

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def unread_count(request):
    """Get count of unread notifications for current user"""
    count = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).count()
    
    return Response({'unread_count': count})

@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def delete_notification(request, notification_id):
    """Delete a notification"""
    try:
        notification = Notification.objects.get(
            id=notification_id,
            recipient=request.user
        )
        notification.delete()
        
        return Response(
            {'message': 'Notification deleted successfully'},
            status=status.HTTP_204_NO_CONTENT
        )
        
    except Notification.DoesNotExist:
        return Response(
            {'error': 'Notification not found'},
            status=status.HTTP_404_NOT_FOUND
        )
