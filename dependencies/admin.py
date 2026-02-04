from django.contrib import admin
from .models import Component, Dependency, GitProject, SonarProject, CheckmarxProject


@admin.register(Component)
class ComponentAdmin(admin.ModelAdmin):
    list_display = ['name', 'component_type', 'group_id', 'artifact_id', 'internal', 'synced_at']
    search_fields = ['name', 'group_id', 'artifact_id']
    list_filter = ['component_type', 'internal', 'status']
    readonly_fields = ['id', 'synced_at']


@admin.register(Dependency)
class DependencyAdmin(admin.ModelAdmin):
    list_display = ['source', 'target', 'scope', 'weight']
    list_filter = ['scope']
    search_fields = ['source__name', 'target__name']


@admin.register(GitProject)
class GitProjectAdmin(admin.ModelAdmin):
    list_display = ['path_with_namespace', 'name', 'component', 'synced_at']
    search_fields = ['path_with_namespace', 'name']
    list_filter = ['default_branch']
    readonly_fields = ['gitlab_id', 'synced_at']


@admin.register(SonarProject)
class SonarProjectAdmin(admin.ModelAdmin):
    list_display = ['sonar_key', 'name', 'component', 'last_analysis', 'synced_at']
    search_fields = ['sonar_key', 'name']
    list_filter = ['visibility', 'qualifier']
    readonly_fields = ['synced_at']


@admin.register(CheckmarxProject)
class CheckmarxProjectAdmin(admin.ModelAdmin):
    list_display = ['checkmarx_id', 'name', 'component', 'created_at', 'synced_at']
    search_fields = ['checkmarx_id', 'name']
    readonly_fields = ['synced_at']
