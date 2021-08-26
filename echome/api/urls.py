from django.urls import path
from . import views

app_name = 'api'
urlpatterns = [
    path('', views.index, name='index'),
    path('test2', views.indextwo, name='indextwo'),
]
