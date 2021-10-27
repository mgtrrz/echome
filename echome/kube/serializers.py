from rest_framework import serializers
from .models import KubeCluster
  
class KubeClusterSerializer(serializers.ModelSerializer):
    # specify model and fields
    class Meta:
        model = KubeCluster
        exclude = ['id', 'account']
