from rest_framework import serializers
from .models import User
  
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        exclude = ['id', 'secret', 'type', 'parent', 'password']


class UserAccessKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        exclude = [
            'id', 
            'secret', 
            'type', 
            'parent', 
            'password',
            'first_name',
            'last_name',
            'is_staff',
            'email',
            'is_superuser',
            'date_joined',
            'groups',
            'user_permissions',
        ]
