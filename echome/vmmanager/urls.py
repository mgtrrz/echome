from django.urls import path
from .views import (
    CreateVM,
    DescribeVM,
    TerminateVM,
    ModifyVM,
    CreateVolume,
    DescribeVolume,
    DeleteVolume,
    ModifyVolume,
    RegisterImage,
    DescribeImage,
    DeleteImage,
    ModifyImage,
)

app_name = 'vmmanager'
urlpatterns = [
    path('vm/create', CreateVM.as_view()),
    path('vm/describe/<str:vm_id>', DescribeVM.as_view()),
    path('vm/terminate/<str:vm_id>', TerminateVM.as_view()),
    path('vm/modify/<str:vm_id>', ModifyVM.as_view()),
    path('volume/create', CreateVolume.as_view()),
    path('volume/describe/<str:vol_id>', DescribeVolume.as_view()),
    path('volume/terminate/<str:vol_id>', DeleteVolume.as_view()),
    path('volume/modify/<str:vol_id>', ModifyVolume.as_view()),
    path('image/guest/register', RegisterImage.as_view()),
    path('image/<str:img_type>/describe/<str:img_id>', DescribeImage.as_view()),
    path('image/<str:img_type>/delete/<str:img_id>', DeleteImage.as_view()),
    path('image/<str:img_type>/modify/<str:img_id>', ModifyImage.as_view()),
]
