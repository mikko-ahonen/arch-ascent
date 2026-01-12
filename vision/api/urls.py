"""
URL routing for Vision Creation System REST API.
"""
from django.urls import path
from . import views

app_name = 'vision_api'

urlpatterns = [
    # Vision endpoints
    path('visions/', views.VisionListView.as_view(), name='vision_list'),
    path('visions/<int:vision_id>/', views.VisionDetailView.as_view(), name='vision_detail'),
    path('visions/<int:vision_id>/duplicate/', views.VisionDuplicateView.as_view(), name='vision_duplicate'),
    path('visions/<int:vision_id>/snapshot/', views.VisionSnapshotView.as_view(), name='vision_snapshot'),

    # Layer endpoints
    path('visions/<int:vision_id>/layers/', views.LayerListView.as_view(), name='layer_list'),
    path('visions/<int:vision_id>/layers/<int:layer_id>/', views.LayerDetailView.as_view(), name='layer_detail'),
    path('visions/<int:vision_id>/layers/<int:layer_id>/positions/', views.LayerNodePositionsView.as_view(), name='layer_positions'),

    # Group endpoints
    path('visions/<int:vision_id>/layers/<int:layer_id>/groups/', views.GroupListView.as_view(), name='group_list'),
    path('visions/<int:vision_id>/layers/<int:layer_id>/groups/<int:group_id>/', views.GroupDetailView.as_view(), name='group_detail'),
    path('visions/<int:vision_id>/layers/<int:layer_id>/groups/<int:group_id>/members/', views.GroupMembersView.as_view(), name='group_members'),

    # Tag endpoints
    path('tags/', views.TagListView.as_view(), name='tag_list'),
    path('tags/<int:tag_id>/', views.TagDetailView.as_view(), name='tag_detail'),
    path('tags/assign/', views.TagAssignmentView.as_view(), name='tag_assign'),

    # Reference endpoints
    path('visions/<int:vision_id>/references/', views.ReferenceListView.as_view(), name='reference_list'),
    path('visions/<int:vision_id>/references/<int:reference_id>/', views.ReferenceDetailView.as_view(), name='reference_detail'),
    path('visions/<int:vision_id>/references/<int:reference_id>/resolve/', views.ReferenceResolveView.as_view(), name='reference_resolve'),

    # Statement endpoints
    path('visions/<int:vision_id>/statements/', views.StatementListView.as_view(), name='statement_list'),
    path('visions/<int:vision_id>/statements/<int:statement_id>/', views.StatementDetailView.as_view(), name='statement_detail'),
    path('visions/<int:vision_id>/statements/evaluate/', views.StatementEvaluateView.as_view(), name='statement_evaluate'),
]
