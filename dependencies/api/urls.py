"""
URL routing for static dependency analysis REST API.
"""
from django.urls import path
from . import views

app_name = 'api'

urlpatterns = [
    # Graph traversal and analysis
    path('graph/traverse/', views.TraverseGraphView.as_view(), name='traverse'),
    path('graph/topo-sort/', views.TopologicalSortView.as_view(), name='topo_sort'),
    path('graph/scc/', views.SCCView.as_view(), name='scc'),
    path('graph/metrics/', views.MetricsView.as_view(), name='metrics'),
    path('graph/metrics/<str:node>/', views.NodeMetricsView.as_view(), name='node_metrics'),

    # Layer management
    path('layers/', views.LayerListView.as_view(), name='layers'),
    path('layers/<int:pk>/', views.LayerDetailView.as_view(), name='layer_detail'),
    path('layers/violations/', views.LayerViolationsView.as_view(), name='layer_violations'),
    path('layers/auto-assign/', views.AutoAssignLayersView.as_view(), name='auto_assign'),

    # Analysis runs
    path('analysis/run/', views.RunAnalysisView.as_view(), name='run_analysis'),
    path('analysis/runs/', views.AnalysisRunListView.as_view(), name='analysis_runs'),
    path('analysis/runs/<int:pk>/', views.AnalysisRunDetailView.as_view(), name='analysis_run_detail'),
]
