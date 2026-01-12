from django.contrib import admin
from .models import Project, Dependency


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'key', 'visibility', 'last_analysis', 'synced_at']
    search_fields = ['name', 'key']
    list_filter = ['visibility', 'qualifier']
    readonly_fields = ['synced_at']


@admin.register(Dependency)
class DependencyAdmin(admin.ModelAdmin):
    list_display = ['source', 'target', 'scope', 'weight']
    list_filter = ['scope']
    search_fields = ['source__name', 'target__name']
