from django.urls import include, path
from .views import *

app_name = 'vmmanager'
urlpatterns = [
    path('create', CreateVM.as_view()),
    path(r'^describe/(?P<vm_id>)/$', DescribeVM.as_view()),
]
