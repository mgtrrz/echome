from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from .views import DescribeUsers, CreateUser, ModifyUser

app_name = 'identity'
urlpatterns = [
    path('user/describe/<str:user_id>', DescribeUsers.as_view()),
    path('user/create', CreateUser.as_view()),
    path('user/modify', ModifyUser.as_view()),
    path('token', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify', TokenVerifyView.as_view(), name='token_verify'),
]
