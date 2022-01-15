from django.urls import path
from .views import (
    CreateKubeCluster,
    DescribeKubeCluster,
    TerminateKubeCluster,
    ModifyKubeCluster,
    InitAdminKubeCluster,
)

app_name = 'kube'
urlpatterns = [
    path('cluster/create', CreateKubeCluster.as_view()),
    path('cluster/describe/<str:cluster_id>', DescribeKubeCluster.as_view()),
    path('cluster/terminate/<str:cluster_id>', TerminateKubeCluster.as_view()),
    path('cluster/modify/<str:cluster_id>', ModifyKubeCluster.as_view()),
    path('cluster-admin/init/<str:cluster_id>', InitAdminKubeCluster.as_view()),
]
