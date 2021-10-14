from django.urls import path
from .views import CreateImage, DeleteImage, DescribeImage, ModifyImage

app_name = 'images'
urlpatterns = [
    path('create', CreateImage.as_view()),
    path('<str:type>/describe/<str:image_id>', DescribeImage.as_view()),
    path('<str:type>/delete/<str:image_id>', DeleteImage.as_view()),
    path('<str:type>/modify/<str:image_id>', ModifyImage.as_view()),
]
