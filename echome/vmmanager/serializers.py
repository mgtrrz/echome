from rest_framework import serializers
from .models import VirtualMachine, Volume
  
class VirtualMachineSerializer(serializers.ModelSerializer):
    # specify model and fields
    class Meta:
        model = VirtualMachine
        exclude = ['id', 'firewall_rules', 'account']


class VolumeSerializer(serializers.ModelSerializer):
    # specify model and fields
    class Meta:
        model = Volume
        exclude = ['id', 'account']
