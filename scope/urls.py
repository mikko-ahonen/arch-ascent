"""URL configuration for scope app."""
from django.urls import path
from . import views
from .components.filter_panel.filter_panel import (
    filter_apply,
    filter_counts,
)

app_name = 'scope'

urlpatterns = [
    # Main views
    path('', views.scoping, name='scoping'),
    path('project/<int:project_id>/description/', views.update_project_description, name='update_description'),
    path('bulk-status/', views.bulk_update_status, name='bulk_update_status'),
    path('tags/', views.get_all_tags, name='get_all_tags'),
    path('bulk-tags/', views.bulk_update_tags, name='bulk_update_tags'),

    # HTMX endpoints (for filter panel component)
    path('htmx/apply/', filter_apply, name='filter_apply'),
    path('htmx/counts/', filter_counts, name='filter_counts'),
]
