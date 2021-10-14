from rest_framework import serializers
from .models import GuestImage, UserImage
  
class GuestImageSerializer(serializers.ModelSerializer):
    # specify model and fields
    class Meta:
        model = GuestImage
        exclude = ['id']


class UserImageSerializer(serializers.ModelSerializer):
    # specify model and fields
    class Meta:
        model = UserImage
        exclude = ['id', 'account']
