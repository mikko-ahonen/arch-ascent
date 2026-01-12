from django.contrib import admin
from .models import (
    Vision, Layer, Group, GroupMembership, LayerNodePosition,
    Reference, Statement
)


@admin.register(Vision)
class VisionAdmin(admin.ModelAdmin):
    list_display = ['name', 'status', 'parent', 'created_at', 'updated_at']
    list_filter = ['status']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Layer)
class LayerAdmin(admin.ModelAdmin):
    list_display = ['name', 'key', 'layer_type', 'vision', 'is_visible', 'order']
    list_filter = ['layer_type', 'is_visible', 'vision']
    search_fields = ['name', 'key']


class GroupMembershipInline(admin.TabularInline):
    model = GroupMembership
    extra = 0
    autocomplete_fields = ['project']


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'key', 'layer', 'color']
    list_filter = ['layer__vision', 'layer']
    search_fields = ['name', 'key']
    inlines = [GroupMembershipInline]


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ['project', 'group', 'membership_type', 'added_at']
    list_filter = ['membership_type', 'group__layer__vision']
    search_fields = ['project__key', 'group__name']
    autocomplete_fields = ['project', 'group']


@admin.register(LayerNodePosition)
class LayerNodePositionAdmin(admin.ModelAdmin):
    list_display = ['project', 'layer', 'position_x', 'position_y']
    list_filter = ['layer__vision', 'layer']
    search_fields = ['project__key']
    autocomplete_fields = ['project', 'layer']


@admin.register(Reference)
class ReferenceAdmin(admin.ModelAdmin):
    list_display = ['name', 'vision', 'definition_type', 'created_at']
    list_filter = ['definition_type', 'vision']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Statement)
class StatementAdmin(admin.ModelAdmin):
    list_display = ['natural_language_short', 'vision', 'statement_type', 'status', 'is_satisfied']
    list_filter = ['statement_type', 'status', 'is_satisfied', 'vision']
    search_fields = ['natural_language']
    readonly_fields = ['last_evaluated_at', 'created_at']

    def natural_language_short(self, obj):
        return obj.natural_language[:50] + '...' if len(obj.natural_language) > 50 else obj.natural_language
    natural_language_short.short_description = 'Statement'
