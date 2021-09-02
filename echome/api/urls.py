from django.urls import include, path

app_name = 'api'
urlpatterns = [
    path('identity/', include('identity.urls')),
    path('vm/', include('vmmanager.urls')),
]
