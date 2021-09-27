from django.urls import path
from .views import *

app_name = 'keys'
urlpatterns = [
    path('create', CreateKeys.as_view()),
    path('describe/<str:key_id>', DescribeKeys.as_view()),
    path('delete/<str:key_id>', DeleteKeys.as_view()),
    path('modify/<str:key_id>', ModifyKeys.as_view()),
]
