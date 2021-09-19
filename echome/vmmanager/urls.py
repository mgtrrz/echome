from django.urls import path
from .views import *

app_name = 'vmmanager'
urlpatterns = [
    path('create', CreateVM.as_view()),
    path('describe/<str:vm_id>', DescribeVM.as_view()),
    path('terminate/<str:vm_id>', TerminateVM.as_view()),
    path('modify/<str:vm_id>', ModifyVM.as_view()),
]
