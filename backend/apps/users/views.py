# from rest_framework import generics, permissions, status
# from rest_framework.decorators import api_view, permission_classes
# from rest_framework.response import Response
# from django.contrib.auth import get_user_model
# from .serializers import UserSerializer, UserProfileSerializer
# from django.contrib.auth import authenticate
# from rest_framework.permissions import AllowAny

# User = get_user_model()

# class UserProfileView(generics.RetrieveUpdateAPIView):
#     serializer_class = UserProfileSerializer
#     permission_classes = [permissions.IsAuthenticated]
    
#     def get_object(self):
#         return self.request.user

# @api_view(['GET'])
# @permission_classes([permissions.IsAuthenticated])
# def user_info(request):
#     """Get current user information"""
#     serializer = UserSerializer(request.user)
#     return Response(serializer.data)

# @api_view(['POST'])
# @permission_classes([permissions.IsAuthenticated])
# def promote_to_admin(request):
#     """Promote current user to admin role (for demo purposes)"""
#     if request.user.role == 'admin':
#         return Response({'message': 'User is already an admin'})
    
#     request.user.role = 'admin'
#     request.user.save(update_fields=['role'])
    
#     return Response({'message': 'User promoted to admin successfully'})

# @api_view(['POST'])
# @permission_classes([AllowAny])
# def get_test_token(request):
#     username = request.data.get('username')
#     password = request.data.get('password')
    
#     user = authenticate(username=username, password=password)
#     if user:
#         # For testing, return user info
#         return Response({
#             'user_id': str(user.id),
#             'username': user.username,
#             'role': user.role,
#             'message': 'Authentication successful'
#         })
#     return Response({'error': 'Invalid credentials'}, status=400)


from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
from .serializers import UserSerializer, UserProfileSerializer

User = get_user_model()

class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_info(request):
    """Get current user information"""
    serializer = UserSerializer(request.user)
    return Response(serializer.data)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def promote_to_admin(request):
    """Promote current user to admin role (for demo purposes)"""
    if request.user.role == 'admin':
        return Response({'message': 'User is already an admin'})
    
    request.user.role = 'admin'
    request.user.save(update_fields=['role'])
    
    return Response({'message': 'User promoted to admin successfully'})

@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    Login endpoint for testing with session authentication
    """
    username = request.data.get('username')
    password = request.data.get('password')
    
    if not username or not password:
        return Response(
            {'error': 'Username and password required'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    user = authenticate(request, username=username, password=password)
    
    if user is not None:
        login(request, user)
        serializer = UserSerializer(user)
        return Response({
            'message': 'Login successful',
            'user': serializer.data
        })
    else:
        return Response(
            {'error': 'Invalid credentials'}, 
            status=status.HTTP_401_UNAUTHORIZED
        )

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout_view(request):
    """Logout endpoint"""
    logout(request)
    return Response({'message': 'Logout successful'})

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def check_auth(request):
    """Check if user is authenticated"""
    serializer = UserSerializer(request.user)
    return Response({
        'authenticated': True,
        'user': serializer.data
    })
