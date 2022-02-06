from django.urls import path
from .views import (
    CreateKubeCluster,
    DescribeKubeCluster,
    ConfigKubeCluster,
    TerminateKubeCluster,
    ModifyKubeCluster,
    PrepareAdminKubeCluster,
    InitAdminKubeCluster,
    NodeAddAdminKubeCluster,
    CreateKubeImage
)

app_name = 'kube'
urlpatterns = [
    path('cluster/create', CreateKubeCluster.as_view(), name="cluster-create"),
    path('cluster/describe/<str:cluster_name>', DescribeKubeCluster.as_view(), name="cluster-describe"),
    path('cluster/config/<str:cluster_name>', ConfigKubeCluster.as_view(), name="cluster-config"),
    path('cluster/terminate/<str:cluster_name>', TerminateKubeCluster.as_view(), name="cluster-terminate"),
    path('cluster/modify/<str:cluster_name>', ModifyKubeCluster.as_view(), name="cluster-modify"),
    path('cluster-admin/prepare/', PrepareAdminKubeCluster.as_view(), name='cluster-admin-prepare'),
    path('cluster-admin/init/<str:cluster_id>', InitAdminKubeCluster.as_view(), name='cluster-admin-init'),
    path('cluster-admin/node-add/<str:cluster_id>', NodeAddAdminKubeCluster.as_view(), name='cluster-admin-node-add'),
    path('image/create', CreateKubeImage.as_view(), name="image-create"),
]
