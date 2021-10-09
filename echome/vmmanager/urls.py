from django.urls import path
from .views import (
    CreateVM,
    DescribeVM,
    TerminateVM,
    ModifyVM
)

app_name = 'vmmanager'
urlpatterns = [
    path('vm/create', CreateVM.as_view()),
    path('vm/describe/<str:vm_id>', DescribeVM.as_view()),
    path('vm/terminate/<str:vm_id>', TerminateVM.as_view()),
    path('vm/modify/<str:vm_id>', ModifyVM.as_view()),
]
