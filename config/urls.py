from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('main.urls')),
    path('scope/', include('scope.urls')),
    path('vision/', include('vision.urls')),
    path('htmx/', include('config.component_urls')),
    path('api/v1/', include('dependencies.api.urls')),
    path('api/v1/', include('vision.api.urls')),
]
