from django.urls import path
from .views import *

app_name = 'keys'
urlpatterns = [
    path('create', CreateKeys.as_view()),
    path('describe/<str:key_name>', DescribeKeys.as_view()),
    path('delete/<str:key_name>', DeleteKeys.as_view()),
    path('modify/<str:key_name>', ModifyKeys.as_view()),
]
