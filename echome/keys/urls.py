from django.urls import path
from .views import *

app_name = 'keys'
urlpatterns = [
    path('sshkey/create', CreateKeys.as_view()),
    path('sshkey/describe/<str:key_name>', DescribeKeys.as_view()),
    path('sshkey/delete/<str:key_name>', DeleteKeys.as_view()),
    path('sshkey/modify/<str:key_name>', ModifyKeys.as_view()),
]
