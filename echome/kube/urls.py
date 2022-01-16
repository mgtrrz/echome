from django.urls import path
from .views import (
    CreateKubeCluster,
    DescribeKubeCluster,
    TerminateKubeCluster,
    ModifyKubeCluster,
    InitAdminKubeCluster,
    NodeAddAdminKubeCluster,
)

app_name = 'kube'
urlpatterns = [
    path('cluster/create', CreateKubeCluster.as_view(), name="cluster-create"),
    path('cluster/describe/<str:cluster_id>', DescribeKubeCluster.as_view(), name="cluster-describe"),
    path('cluster/terminate/<str:cluster_id>', TerminateKubeCluster.as_view(), name="cluster-terminate"),
    path('cluster/modify/<str:cluster_id>', ModifyKubeCluster.as_view(), name="cluster-modify"),
    path('cluster-admin/init/<str:cluster_id>', InitAdminKubeCluster.as_view(), name='cluster-admin-init'),
    path('cluster-admin/node-add/<str:cluster_id>', NodeAddAdminKubeCluster.as_view(), name='cluster-admin-node-add'),
]
