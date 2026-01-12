"""
REST API views for Vision Creation System.

Endpoints:
    # Vision
    GET/POST /api/v1/visions/                    - List/create visions
    GET/PUT/DELETE /api/v1/visions/{id}/         - Vision detail
    POST /api/v1/visions/{id}/duplicate/         - Clone vision
    POST /api/v1/visions/{id}/snapshot/          - Create snapshot

    # Layers
    GET/POST /api/v1/visions/{id}/layers/        - List/create layers
    GET/PUT/DELETE /api/v1/visions/{id}/layers/{lid}/ - Layer detail

    # Groups
    GET/POST /api/v1/visions/{id}/layers/{lid}/groups/     - List/create groups
    PUT/DELETE /api/v1/visions/{id}/layers/{lid}/groups/{gid}/ - Group detail
    POST /api/v1/visions/{id}/layers/{lid}/groups/{gid}/members/ - Add members
    DELETE /api/v1/visions/{id}/layers/{lid}/groups/{gid}/members/ - Remove members

    # Tags
    GET/POST /api/v1/tags/                       - List/create tags
    DELETE /api/v1/tags/{id}/                    - Delete tag
    POST /api/v1/tags/assign/                    - Assign tag
    DELETE /api/v1/tags/assign/                  - Remove tag assignment

    # References
    GET/POST /api/v1/visions/{id}/references/    - List/create references
    GET/PUT/DELETE /api/v1/visions/{id}/references/{rid}/ - Reference detail
    GET /api/v1/visions/{id}/references/{rid}/resolve/ - Resolve members

    # Statements
    GET/POST /api/v1/visions/{id}/statements/    - List/create statements
    PUT/DELETE /api/v1/visions/{id}/statements/{sid}/ - Statement detail
    GET /api/v1/visions/{id}/statements/evaluate/ - Evaluate all statements
"""
import json
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone

from taggit.models import Tag
from vision.models import (
    Vision, Layer, Group, GroupMembership, LayerNodePosition,
    Reference, Statement
)
from dependencies.models import Project
from vision.services.tag_resolver import (
    resolve_reference, get_all_tags, assign_tag_to_project, remove_tag_from_project
)
from vision.services.statement_evaluator import (
    evaluate_statement, evaluate_all_statements, get_statement_violations
)


# =============================================================================
# Vision Views
# =============================================================================

@method_decorator(csrf_exempt, name='dispatch')
class VisionListView(View):
    """GET/POST /api/v1/visions/"""

    def get(self, request):
        """List all visions."""
        status_filter = request.GET.get('status')
        visions = Vision.objects.all()

        if status_filter:
            visions = visions.filter(status=status_filter)

        return JsonResponse({
            'visions': [
                {
                    'id': v.id,
                    'name': v.name,
                    'description': v.description,
                    'status': v.status,
                    'parent_id': v.parent_id,
                    'created_at': v.created_at.isoformat(),
                    'updated_at': v.updated_at.isoformat(),
                    'layer_count': v.layers.count(),
                    'statement_count': v.statements.count(),
                }
                for v in visions
            ]
        })

    def post(self, request):
        """Create a new vision."""
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        name = data.get('name')
        if not name:
            return JsonResponse({'error': 'name is required'}, status=400)

        vision = Vision.objects.create(
            name=name,
            description=data.get('description', ''),
            status=data.get('status', 'draft'),
            parent_id=data.get('parent_id'),
        )

        return JsonResponse({
            'id': vision.id,
            'name': vision.name,
            'status': vision.status,
            'created_at': vision.created_at.isoformat(),
        }, status=201)


@method_decorator(csrf_exempt, name='dispatch')
class VisionDetailView(View):
    """GET/PUT/DELETE /api/v1/visions/{id}/"""

    def get(self, request, vision_id):
        """Get vision with full state."""
        try:
            vision = Vision.objects.get(pk=vision_id)
        except Vision.DoesNotExist:
            return JsonResponse({'error': 'Vision not found'}, status=404)

        layers_data = []
        for layer in vision.layers.all():
            groups_data = []
            for group in layer.groups.all():
                members = list(
                    GroupMembership.objects.filter(group=group)
                    .values_list('project__key', flat=True)
                )
                groups_data.append({
                    'id': group.id,
                    'key': group.key,
                    'name': group.name,
                    'color': group.color,
                    'position_x': group.position_x,
                    'position_y': group.position_y,
                    'members': members,
                })

            layers_data.append({
                'id': layer.id,
                'key': layer.key,
                'name': layer.name,
                'layer_type': layer.layer_type,
                'color': layer.color,
                'is_visible': layer.is_visible,
                'order': layer.order,
                'groups': groups_data,
            })

        return JsonResponse({
            'id': vision.id,
            'name': vision.name,
            'description': vision.description,
            'status': vision.status,
            'parent_id': vision.parent_id,
            'created_at': vision.created_at.isoformat(),
            'updated_at': vision.updated_at.isoformat(),
            'layers': layers_data,
            'references': [
                {
                    'id': r.id,
                    'name': r.name,
                    'definition_type': r.definition_type,
                }
                for r in vision.references.all()
            ],
            'statements': [
                {
                    'id': s.id,
                    'statement_type': s.statement_type,
                    'natural_language': s.natural_language,
                    'is_satisfied': s.is_satisfied,
                }
                for s in vision.statements.all()
            ],
        })

    def put(self, request, vision_id):
        """Update vision metadata."""
        try:
            vision = Vision.objects.get(pk=vision_id)
        except Vision.DoesNotExist:
            return JsonResponse({'error': 'Vision not found'}, status=404)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        if 'name' in data:
            vision.name = data['name']
        if 'description' in data:
            vision.description = data['description']
        if 'status' in data:
            vision.status = data['status']

        vision.save()

        return JsonResponse({
            'id': vision.id,
            'name': vision.name,
            'status': vision.status,
            'updated_at': vision.updated_at.isoformat(),
        })

    def delete(self, request, vision_id):
        """Delete vision."""
        try:
            vision = Vision.objects.get(pk=vision_id)
            vision.delete()
            return JsonResponse({'status': 'deleted'})
        except Vision.DoesNotExist:
            return JsonResponse({'error': 'Vision not found'}, status=404)


@method_decorator(csrf_exempt, name='dispatch')
class VisionDuplicateView(View):
    """POST /api/v1/visions/{id}/duplicate/"""

    def post(self, request, vision_id):
        """Clone a vision with all its layers, groups, and memberships."""
        try:
            original = Vision.objects.get(pk=vision_id)
        except Vision.DoesNotExist:
            return JsonResponse({'error': 'Vision not found'}, status=404)

        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            data = {}

        # Create new vision
        new_vision = Vision.objects.create(
            name=data.get('name', f"{original.name} (copy)"),
            description=original.description,
            status='draft',
            parent=original,
        )

        # Clone layers
        layer_map = {}
        for layer in original.layers.all():
            new_layer = Layer.objects.create(
                key=layer.key,
                name=layer.name,
                description=layer.description,
                layer_type=layer.layer_type,
                vision=new_vision,
                color=layer.color,
                is_visible=layer.is_visible,
                order=layer.order,
            )
            layer_map[layer.id] = new_layer

            # Clone groups
            for group in layer.groups.all():
                new_group = Group.objects.create(
                    key=group.key,
                    name=group.name,
                    description=group.description,
                    layer=new_layer,
                    color=group.color,
                    position_x=group.position_x,
                    position_y=group.position_y,
                    width=group.width,
                    height=group.height,
                )

                # Clone memberships
                for membership in group.memberships.all():
                    GroupMembership.objects.create(
                        group=new_group,
                        project=membership.project,
                        membership_type=membership.membership_type,
                    )

            # Clone node positions
            for pos in layer.node_positions.all():
                LayerNodePosition.objects.create(
                    layer=new_layer,
                    project=pos.project,
                    position_x=pos.position_x,
                    position_y=pos.position_y,
                )

        # Clone references
        for ref in original.references.all():
            Reference.objects.create(
                name=ref.name,
                vision=new_vision,
                description=ref.description,
                definition_type=ref.definition_type,
                tag_expression=ref.tag_expression,
                explicit_members=ref.explicit_members,
            )

        # Clone statements
        for stmt in original.statements.all():
            Statement.objects.create(
                vision=new_vision,
                statement_type=stmt.statement_type,
                natural_language=stmt.natural_language,
                formal_expression=stmt.formal_expression,
                status=stmt.status,
            )

        return JsonResponse({
            'id': new_vision.id,
            'name': new_vision.name,
            'parent_id': new_vision.parent_id,
            'created_at': new_vision.created_at.isoformat(),
        }, status=201)


@method_decorator(csrf_exempt, name='dispatch')
class VisionSnapshotView(View):
    """POST /api/v1/visions/{id}/snapshot/"""

    def post(self, request, vision_id):
        """Create a shareable snapshot of the vision."""
        try:
            vision = Vision.objects.get(pk=vision_id)
        except Vision.DoesNotExist:
            return JsonResponse({'error': 'Vision not found'}, status=404)

        # Build snapshot data
        snapshot = {
            'name': vision.name,
            'description': vision.description,
            'created_at': timezone.now().isoformat(),
            'layers': [],
            'references': [],
            'statements': [],
        }

        for layer in vision.layers.all():
            layer_data = {
                'key': layer.key,
                'name': layer.name,
                'layer_type': layer.layer_type,
                'groups': [],
                'node_positions': [],
            }

            for group in layer.groups.all():
                layer_data['groups'].append({
                    'key': group.key,
                    'name': group.name,
                    'position': [group.position_x, group.position_y],
                    'size': [group.width, group.height],
                    'members': list(
                        group.memberships.values_list('project__key', flat=True)
                    ),
                })

            for pos in layer.node_positions.all():
                layer_data['node_positions'].append({
                    'project_key': pos.project.key,
                    'position': [pos.position_x, pos.position_y],
                })

            snapshot['layers'].append(layer_data)

        for ref in vision.references.all():
            snapshot['references'].append({
                'name': ref.name,
                'definition_type': ref.definition_type,
                'tag_expression': ref.tag_expression,
                'explicit_members': ref.explicit_members,
            })

        for stmt in vision.statements.all():
            snapshot['statements'].append({
                'type': stmt.statement_type,
                'natural_language': stmt.natural_language,
                'formal_expression': stmt.formal_expression,
                'is_satisfied': stmt.is_satisfied,
            })

        # Store snapshot and update status
        vision.snapshot_data = snapshot
        vision.status = 'shared'
        vision.save()

        return JsonResponse({
            'id': vision.id,
            'status': vision.status,
            'snapshot_created_at': snapshot['created_at'],
        })


# =============================================================================
# Layer Views
# =============================================================================

@method_decorator(csrf_exempt, name='dispatch')
class LayerListView(View):
    """GET/POST /api/v1/visions/{id}/layers/"""

    def get(self, request, vision_id):
        """List layers in vision."""
        try:
            vision = Vision.objects.get(pk=vision_id)
        except Vision.DoesNotExist:
            return JsonResponse({'error': 'Vision not found'}, status=404)

        return JsonResponse({
            'layers': [
                {
                    'id': layer.id,
                    'key': layer.key,
                    'name': layer.name,
                    'layer_type': layer.layer_type,
                    'color': layer.color,
                    'is_visible': layer.is_visible,
                    'order': layer.order,
                    'group_count': layer.groups.count(),
                }
                for layer in vision.layers.all()
            ]
        })

    def post(self, request, vision_id):
        """Create layer."""
        try:
            vision = Vision.objects.get(pk=vision_id)
        except Vision.DoesNotExist:
            return JsonResponse({'error': 'Vision not found'}, status=404)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        key = data.get('key')
        name = data.get('name')
        if not key or not name:
            return JsonResponse({'error': 'key and name are required'}, status=400)

        if Layer.objects.filter(vision=vision, key=key).exists():
            return JsonResponse({'error': f'Layer {key} already exists in this vision'}, status=400)

        layer = Layer.objects.create(
            key=key,
            name=name,
            description=data.get('description', ''),
            layer_type=data.get('layer_type', 'freeform'),
            vision=vision,
            color=data.get('color', ''),
            order=data.get('order', 0),
        )

        return JsonResponse({
            'id': layer.id,
            'key': layer.key,
            'name': layer.name,
        }, status=201)


@method_decorator(csrf_exempt, name='dispatch')
class LayerDetailView(View):
    """GET/PUT/DELETE /api/v1/visions/{id}/layers/{lid}/"""

    def get(self, request, vision_id, layer_id):
        """Get layer detail with groups and positions."""
        try:
            layer = Layer.objects.get(pk=layer_id, vision_id=vision_id)
        except Layer.DoesNotExist:
            return JsonResponse({'error': 'Layer not found'}, status=404)

        groups_data = []
        for group in layer.groups.all():
            members = list(
                GroupMembership.objects.filter(group=group)
                .values_list('project__key', flat=True)
            )
            groups_data.append({
                'id': group.id,
                'key': group.key,
                'name': group.name,
                'color': group.color,
                'position_x': group.position_x,
                'position_y': group.position_y,
                'width': group.width,
                'height': group.height,
                'members': members,
            })

        node_positions = {
            pos.project.key: {'x': pos.position_x, 'y': pos.position_y}
            for pos in layer.node_positions.select_related('project').all()
        }

        return JsonResponse({
            'id': layer.id,
            'key': layer.key,
            'name': layer.name,
            'description': layer.description,
            'layer_type': layer.layer_type,
            'color': layer.color,
            'is_visible': layer.is_visible,
            'order': layer.order,
            'groups': groups_data,
            'node_positions': node_positions,
        })

    def put(self, request, vision_id, layer_id):
        """Update layer."""
        try:
            layer = Layer.objects.get(pk=layer_id, vision_id=vision_id)
        except Layer.DoesNotExist:
            return JsonResponse({'error': 'Layer not found'}, status=404)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        if 'name' in data:
            layer.name = data['name']
        if 'description' in data:
            layer.description = data['description']
        if 'layer_type' in data:
            layer.layer_type = data['layer_type']
        if 'color' in data:
            layer.color = data['color']
        if 'is_visible' in data:
            layer.is_visible = data['is_visible']
        if 'order' in data:
            layer.order = data['order']

        layer.save()

        return JsonResponse({
            'id': layer.id,
            'key': layer.key,
            'name': layer.name,
        })

    def delete(self, request, vision_id, layer_id):
        """Delete layer."""
        try:
            layer = Layer.objects.get(pk=layer_id, vision_id=vision_id)
            layer.delete()
            return JsonResponse({'status': 'deleted'})
        except Layer.DoesNotExist:
            return JsonResponse({'error': 'Layer not found'}, status=404)


# =============================================================================
# Group Views
# =============================================================================

@method_decorator(csrf_exempt, name='dispatch')
class GroupListView(View):
    """GET/POST /api/v1/visions/{id}/layers/{lid}/groups/"""

    def get(self, request, vision_id, layer_id):
        """List groups in layer."""
        try:
            layer = Layer.objects.get(pk=layer_id, vision_id=vision_id)
        except Layer.DoesNotExist:
            return JsonResponse({'error': 'Layer not found'}, status=404)

        return JsonResponse({
            'groups': [
                {
                    'id': group.id,
                    'key': group.key,
                    'name': group.name,
                    'color': group.color,
                    'member_count': group.memberships.count(),
                }
                for group in layer.groups.all()
            ]
        })

    def post(self, request, vision_id, layer_id):
        """Create group."""
        try:
            layer = Layer.objects.get(pk=layer_id, vision_id=vision_id)
        except Layer.DoesNotExist:
            return JsonResponse({'error': 'Layer not found'}, status=404)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        key = data.get('key')
        name = data.get('name')
        if not key or not name:
            return JsonResponse({'error': 'key and name are required'}, status=400)

        if Group.objects.filter(layer=layer, key=key).exists():
            return JsonResponse({'error': f'Group {key} already exists in this layer'}, status=400)

        group = Group.objects.create(
            key=key,
            name=name,
            description=data.get('description', ''),
            layer=layer,
            color=data.get('color', ''),
            position_x=data.get('position_x'),
            position_y=data.get('position_y'),
            width=data.get('width'),
            height=data.get('height'),
        )

        return JsonResponse({
            'id': group.id,
            'key': group.key,
            'name': group.name,
        }, status=201)


@method_decorator(csrf_exempt, name='dispatch')
class GroupDetailView(View):
    """PUT/DELETE /api/v1/visions/{id}/layers/{lid}/groups/{gid}/"""

    def put(self, request, vision_id, layer_id, group_id):
        """Update group."""
        try:
            group = Group.objects.get(pk=group_id, layer_id=layer_id, layer__vision_id=vision_id)
        except Group.DoesNotExist:
            return JsonResponse({'error': 'Group not found'}, status=404)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        if 'name' in data:
            group.name = data['name']
        if 'description' in data:
            group.description = data['description']
        if 'color' in data:
            group.color = data['color']
        if 'position_x' in data:
            group.position_x = data['position_x']
        if 'position_y' in data:
            group.position_y = data['position_y']
        if 'width' in data:
            group.width = data['width']
        if 'height' in data:
            group.height = data['height']

        group.save()

        return JsonResponse({
            'id': group.id,
            'key': group.key,
            'name': group.name,
        })

    def delete(self, request, vision_id, layer_id, group_id):
        """Delete group."""
        try:
            group = Group.objects.get(pk=group_id, layer_id=layer_id, layer__vision_id=vision_id)
            group.delete()
            return JsonResponse({'status': 'deleted'})
        except Group.DoesNotExist:
            return JsonResponse({'error': 'Group not found'}, status=404)


@method_decorator(csrf_exempt, name='dispatch')
class GroupMembersView(View):
    """POST/DELETE /api/v1/visions/{id}/layers/{lid}/groups/{gid}/members/"""

    def post(self, request, vision_id, layer_id, group_id):
        """Add members to group."""
        try:
            group = Group.objects.get(pk=group_id, layer_id=layer_id, layer__vision_id=vision_id)
        except Group.DoesNotExist:
            return JsonResponse({'error': 'Group not found'}, status=404)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        project_keys = data.get('project_keys', [])
        if not project_keys:
            return JsonResponse({'error': 'project_keys is required'}, status=400)

        added = []
        for key in project_keys:
            try:
                project = Project.objects.get(key=key)
                _, created = GroupMembership.objects.get_or_create(
                    group=group,
                    project=project,
                    defaults={'membership_type': data.get('membership_type', 'explicit')}
                )
                if created:
                    added.append(key)
            except Project.DoesNotExist:
                pass

        return JsonResponse({
            'added': added,
            'total_members': group.memberships.count(),
        })

    def delete(self, request, vision_id, layer_id, group_id):
        """Remove members from group."""
        try:
            group = Group.objects.get(pk=group_id, layer_id=layer_id, layer__vision_id=vision_id)
        except Group.DoesNotExist:
            return JsonResponse({'error': 'Group not found'}, status=404)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        project_keys = data.get('project_keys', [])
        if not project_keys:
            return JsonResponse({'error': 'project_keys is required'}, status=400)

        deleted, _ = GroupMembership.objects.filter(
            group=group,
            project__key__in=project_keys
        ).delete()

        return JsonResponse({
            'removed': deleted,
            'total_members': group.memberships.count(),
        })


@method_decorator(csrf_exempt, name='dispatch')
class LayerNodePositionsView(View):
    """POST /api/v1/visions/{id}/layers/{lid}/positions/"""

    def post(self, request, vision_id, layer_id):
        """Update node positions in a layer."""
        try:
            layer = Layer.objects.get(pk=layer_id, vision_id=vision_id)
        except Layer.DoesNotExist:
            return JsonResponse({'error': 'Layer not found'}, status=404)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        positions = data.get('positions', {})
        updated = 0

        for project_key, pos in positions.items():
            try:
                project = Project.objects.get(key=project_key)
                LayerNodePosition.objects.update_or_create(
                    layer=layer,
                    project=project,
                    defaults={
                        'position_x': pos.get('x', 0),
                        'position_y': pos.get('y', 0),
                    }
                )
                updated += 1
            except Project.DoesNotExist:
                pass

        return JsonResponse({
            'updated': updated,
        })


# =============================================================================
# Tag Views (using django-taggit)
# =============================================================================

@method_decorator(csrf_exempt, name='dispatch')
class TagListView(View):
    """GET/POST /api/v1/tags/"""

    def get(self, request):
        """List all tags using taggit."""
        tags = get_all_tags()
        return JsonResponse({'tags': tags})

    def post(self, request):
        """Create a tag (or get existing)."""
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        name = data.get('name')
        if not name:
            return JsonResponse({'error': 'name is required'}, status=400)

        # taggit creates tags on-demand, but we can also create them explicitly
        tag, created = Tag.objects.get_or_create(name=name)

        return JsonResponse({
            'id': tag.id,
            'name': tag.name,
            'slug': tag.slug,
            'created': created,
        }, status=201 if created else 200)


@method_decorator(csrf_exempt, name='dispatch')
class TagDetailView(View):
    """DELETE /api/v1/tags/{id}/"""

    def delete(self, request, tag_id):
        """Delete tag."""
        try:
            tag = Tag.objects.get(pk=tag_id)
            tag.delete()
            return JsonResponse({'status': 'deleted'})
        except Tag.DoesNotExist:
            return JsonResponse({'error': 'Tag not found'}, status=404)


@method_decorator(csrf_exempt, name='dispatch')
class TagAssignmentView(View):
    """POST/DELETE /api/v1/tags/assign/

    With django-taggit, tags are assigned directly to Project models.
    Tags are created on-demand when assigning.
    """

    def post(self, request):
        """Assign tag to a project."""
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        tag_name = data.get('tag_name') or data.get('tag_key')  # Support both
        project_key = data.get('project_key') or data.get('target_key')  # Support both

        if not tag_name or not project_key:
            return JsonResponse(
                {'error': 'tag_name and project_key are required'},
                status=400
            )

        result = assign_tag_to_project(tag_name, project_key)
        if not result:
            return JsonResponse({'error': f'Project {project_key} not found'}, status=404)

        return JsonResponse({
            'created': True,
            'tag_name': tag_name,
            'project_key': project_key,
        }, status=201)

    def delete(self, request):
        """Remove tag from a project."""
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        tag_name = data.get('tag_name') or data.get('tag_key')  # Support both
        project_key = data.get('project_key') or data.get('target_key')  # Support both

        if not tag_name or not project_key:
            return JsonResponse(
                {'error': 'tag_name and project_key are required'},
                status=400
            )

        result = remove_tag_from_project(tag_name, project_key)

        return JsonResponse({'deleted': result})


# =============================================================================
# Reference Views
# =============================================================================

@method_decorator(csrf_exempt, name='dispatch')
class ReferenceListView(View):
    """GET/POST /api/v1/visions/{id}/references/"""

    def get(self, request, vision_id):
        """List references in vision."""
        try:
            vision = Vision.objects.get(pk=vision_id)
        except Vision.DoesNotExist:
            return JsonResponse({'error': 'Vision not found'}, status=404)

        return JsonResponse({
            'references': [
                {
                    'id': ref.id,
                    'name': ref.name,
                    'description': ref.description,
                    'definition_type': ref.definition_type,
                    'tag_expression': ref.tag_expression,
                }
                for ref in vision.references.all()
            ]
        })

    def post(self, request, vision_id):
        """Create reference."""
        try:
            vision = Vision.objects.get(pk=vision_id)
        except Vision.DoesNotExist:
            return JsonResponse({'error': 'Vision not found'}, status=404)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        name = data.get('name')
        if not name:
            return JsonResponse({'error': 'name is required'}, status=400)

        if Reference.objects.filter(name=name, vision=vision).exists():
            return JsonResponse({'error': f'Reference {name} already exists'}, status=400)

        ref = Reference.objects.create(
            name=name,
            vision=vision,
            description=data.get('description', ''),
            definition_type=data.get('definition_type', 'informal'),
            tag_expression=data.get('tag_expression'),
            explicit_members=data.get('explicit_members', []),
        )

        return JsonResponse({
            'id': ref.id,
            'name': ref.name,
            'definition_type': ref.definition_type,
        }, status=201)


@method_decorator(csrf_exempt, name='dispatch')
class ReferenceDetailView(View):
    """GET/PUT/DELETE /api/v1/visions/{id}/references/{rid}/"""

    def get(self, request, vision_id, reference_id):
        """Get reference with resolved members."""
        try:
            ref = Reference.objects.get(pk=reference_id, vision_id=vision_id)
        except Reference.DoesNotExist:
            return JsonResponse({'error': 'Reference not found'}, status=404)

        members = list(resolve_reference(ref))

        return JsonResponse({
            'id': ref.id,
            'name': ref.name,
            'description': ref.description,
            'definition_type': ref.definition_type,
            'tag_expression': ref.tag_expression,
            'explicit_members': ref.explicit_members,
            'resolved_members': members,
            'member_count': len(members),
        })

    def put(self, request, vision_id, reference_id):
        """Update reference."""
        try:
            ref = Reference.objects.get(pk=reference_id, vision_id=vision_id)
        except Reference.DoesNotExist:
            return JsonResponse({'error': 'Reference not found'}, status=404)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        if 'description' in data:
            ref.description = data['description']
        if 'definition_type' in data:
            ref.definition_type = data['definition_type']
        if 'tag_expression' in data:
            ref.tag_expression = data['tag_expression']
        if 'explicit_members' in data:
            ref.explicit_members = data['explicit_members']

        ref.save()

        return JsonResponse({
            'id': ref.id,
            'name': ref.name,
            'definition_type': ref.definition_type,
        })

    def delete(self, request, vision_id, reference_id):
        """Delete reference."""
        try:
            ref = Reference.objects.get(pk=reference_id, vision_id=vision_id)
            ref.delete()
            return JsonResponse({'status': 'deleted'})
        except Reference.DoesNotExist:
            return JsonResponse({'error': 'Reference not found'}, status=404)


class ReferenceResolveView(View):
    """GET /api/v1/visions/{id}/references/{rid}/resolve/"""

    def get(self, request, vision_id, reference_id):
        """Resolve reference to current members."""
        try:
            ref = Reference.objects.get(pk=reference_id, vision_id=vision_id)
        except Reference.DoesNotExist:
            return JsonResponse({'error': 'Reference not found'}, status=404)

        members = list(resolve_reference(ref))

        return JsonResponse({
            'reference': ref.name,
            'members': members,
            'count': len(members),
        })


# =============================================================================
# Statement Views
# =============================================================================

@method_decorator(csrf_exempt, name='dispatch')
class StatementListView(View):
    """GET/POST /api/v1/visions/{id}/statements/"""

    def get(self, request, vision_id):
        """List statements with satisfaction status."""
        try:
            vision = Vision.objects.get(pk=vision_id)
        except Vision.DoesNotExist:
            return JsonResponse({'error': 'Vision not found'}, status=404)

        return JsonResponse({
            'statements': [
                {
                    'id': stmt.id,
                    'statement_type': stmt.statement_type,
                    'natural_language': stmt.natural_language,
                    'formal_expression': stmt.formal_expression,
                    'status': stmt.status,
                    'is_satisfied': stmt.is_satisfied,
                    'last_evaluated_at': stmt.last_evaluated_at.isoformat() if stmt.last_evaluated_at else None,
                }
                for stmt in vision.statements.all()
            ]
        })

    def post(self, request, vision_id):
        """Create statement."""
        try:
            vision = Vision.objects.get(pk=vision_id)
        except Vision.DoesNotExist:
            return JsonResponse({'error': 'Vision not found'}, status=404)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        statement_type = data.get('statement_type')
        natural_language = data.get('natural_language')

        if not statement_type or not natural_language:
            return JsonResponse(
                {'error': 'statement_type and natural_language are required'},
                status=400
            )

        stmt = Statement.objects.create(
            vision=vision,
            statement_type=statement_type,
            natural_language=natural_language,
            formal_expression=data.get('formal_expression'),
            status=data.get('status', 'informal'),
        )

        return JsonResponse({
            'id': stmt.id,
            'statement_type': stmt.statement_type,
            'status': stmt.status,
        }, status=201)


@method_decorator(csrf_exempt, name='dispatch')
class StatementDetailView(View):
    """PUT/DELETE /api/v1/visions/{id}/statements/{sid}/"""

    def put(self, request, vision_id, statement_id):
        """Update statement."""
        try:
            stmt = Statement.objects.get(pk=statement_id, vision_id=vision_id)
        except Statement.DoesNotExist:
            return JsonResponse({'error': 'Statement not found'}, status=404)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        if 'natural_language' in data:
            stmt.natural_language = data['natural_language']
        if 'formal_expression' in data:
            stmt.formal_expression = data['formal_expression']
        if 'status' in data:
            stmt.status = data['status']
        if 'statement_type' in data:
            stmt.statement_type = data['statement_type']

        stmt.save()

        # Re-evaluate if formal
        if stmt.status in ('semi_formal', 'formal') and stmt.formal_expression:
            evaluate_statement(stmt)

        return JsonResponse({
            'id': stmt.id,
            'statement_type': stmt.statement_type,
            'is_satisfied': stmt.is_satisfied,
        })

    def delete(self, request, vision_id, statement_id):
        """Delete statement."""
        try:
            stmt = Statement.objects.get(pk=statement_id, vision_id=vision_id)
            stmt.delete()
            return JsonResponse({'status': 'deleted'})
        except Statement.DoesNotExist:
            return JsonResponse({'error': 'Statement not found'}, status=404)


class StatementEvaluateView(View):
    """GET /api/v1/visions/{id}/statements/evaluate/"""

    def get(self, request, vision_id):
        """Evaluate all statements in vision."""
        try:
            Vision.objects.get(pk=vision_id)
        except Vision.DoesNotExist:
            return JsonResponse({'error': 'Vision not found'}, status=404)

        results = evaluate_all_statements(vision_id)

        return JsonResponse(results)
