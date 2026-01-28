from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/scope/', permanent=False), name='home'),
    path('main/', include('main.urls')),
    path('scope/', include('scope.urls')),
    path('vision/', include('vision.urls')),
    path('htmx/', include('config.component_urls')),
    path('api/v1/', include('dependencies.api.urls')),
    path('api/v1/', include('vision.api.urls')),
]
