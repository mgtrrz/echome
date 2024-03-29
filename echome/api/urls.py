from django.urls import include, path

app_name = 'api'
urlpatterns = [
    path('identity/', include('identity.urls')),
    path('keys/', include('keys.urls')),
    path('vm/', include('vmmanager.urls')),
    path('network/', include('network.urls')),
    path('kube/', include('kube.urls')),
]
