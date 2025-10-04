# from rest_framework import serializers
# from django.contrib.auth import get_user_model

# User = get_user_model()

# class UserSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = User
#         fields = ['id', 'clerk_id', 'username', 'email', 'first_name', 'last_name', 
#                  'role', 'email_verified', 'created_at', 'updated_at']
#         read_only_fields = ['id', 'clerk_id', 'created_at', 'updated_at']

# class UserProfileSerializer(serializers.ModelSerializer):
#     full_name = serializers.SerializerMethodField()
    
#     class Meta:
#         model = User
#         fields = ['id', 'username', 'email', 'first_name', 'last_name', 
#                  'full_name', 'role', 'email_verified']
#         read_only_fields = ['id', 'email', 'role', 'email_verified']
    
#     def get_full_name(self, obj):
#         return f"{obj.first_name} {obj.last_name}".strip()


from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'clerk_id', 'username', 'email', 'first_name', 'last_name', 
                 'full_name', 'role', 'email_verified', 'created_at', 'updated_at']
        read_only_fields = ['id', 'clerk_id', 'created_at', 'updated_at']
    
    def get_full_name(self, obj):
        full_name = f"{obj.first_name} {obj.last_name}".strip()
        return full_name if full_name else obj.username

class UserProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 
                 'full_name', 'role', 'email_verified']
        read_only_fields = ['id', 'email', 'role', 'email_verified']
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()
