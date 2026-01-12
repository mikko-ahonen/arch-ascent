"""
URL routing for Vision page views.
"""
from django.urls import path
from . import views
from .components.vision_canvas.vision_canvas import VisionCanvas

app_name = 'vision'

urlpatterns = [
    # Page routes
    path('', views.vision_home, name='home'),
    path('<int:vision_id>/', views.vision_detail, name='detail'),
    path('<int:vision_id>/version/<int:version_id>/', views.vision_detail, name='detail-version'),
    path('test-editor/', views.test_editor, name='test-editor'),

    # HTMX component routes
    path('htmx/vision-form/', views.vision_form, name='vision-form'),
    path('htmx/vision-delete/', views.vision_delete, name='vision-delete'),
    path('htmx/vision-list/', views.vision_list, name='vision-list'),

    # Layer routes
    path('htmx/layer-form/', views.layer_form, name='layer-form'),
    path('htmx/layer-delete/', views.layer_delete, name='layer-delete'),

    # Statement routes
    path('htmx/statement-form/', views.statement_form, name='statement-form'),
    path('htmx/statement-delete/', views.statement_delete, name='statement-delete'),
    path('htmx/statements-list/', views.statements_list, name='statements-list'),

    # Reference routes
    path('htmx/reference-create/', views.reference_create, name='reference-create'),
    path('htmx/reference-form/', views.reference_form, name='reference-form'),
    path('htmx/reference-delete/', views.reference_delete, name='reference-delete'),
    path('htmx/reference-validate/', views.reference_validate, name='reference-validate'),

    # Version routes
    path('htmx/version-form/', views.version_form, name='version-form'),
    path('htmx/version-delete/', views.version_delete, name='version-delete'),
    path('htmx/version-snapshot/', views.version_snapshot, name='version-snapshot'),
    path('htmx/versions-tabs/', views.versions_tabs, name='versions-tabs'),

    # Canvas routes
    path('htmx/canvas/<int:vision_id>/data/', VisionCanvas.htmx_get_data, name='canvas-data'),
    path('htmx/canvas/<int:vision_id>/save/', VisionCanvas.htmx_save_layout, name='canvas-save'),
    path('htmx/canvas/<int:vision_id>/cluster/', VisionCanvas.htmx_cluster, name='canvas-cluster'),
]
