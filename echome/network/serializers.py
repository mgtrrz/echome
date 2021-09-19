from rest_framework import serializers
from .models import VirtualNetwork
  
class NetworkSerializer(serializers.ModelSerializer):
    # specify model and fields
    class Meta:
        model = VirtualNetwork
        exclude = ['id', 'firewall_rules', 'deactivated']