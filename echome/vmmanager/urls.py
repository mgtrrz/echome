from django.urls import include, path
from .views import CreateVM

app_name = 'api'
urlpatterns = [
    path('create', CreateVM.as_view()),
]
