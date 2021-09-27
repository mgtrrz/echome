from rest_framework import serializers
from .models import UserKey
  
class UserKeySerializer(serializers.ModelSerializer):
    # specify model and fields
    class Meta:
        model = UserKey
        exclude = ['id', 'account', 'service_key', 'service_owner']
