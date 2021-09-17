from django.urls import include, path
from .views import *

app_name = 'vmmanager'
urlpatterns = [
    path('create', CreateVM.as_view()),
    path('describe/<str:vm_id>', DescribeVM.as_view()),
]
