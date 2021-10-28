from django.urls import path
from .views import *

app_name = 'network'
urlpatterns = [
    path('vnet/create', CreateNetwork.as_view()),
    path('vnet/describe/<str:net_id>', DescribeNetwork.as_view()),
    path('vnet/terminate/<str:net_id>', TerminateNetwork.as_view()),
    path('vnet/modify/<str:net_id>', ModifyNetwork.as_view()),
]
