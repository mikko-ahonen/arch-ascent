"""
Vision Creation System page views.
"""
import json
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from .models import Vision, Layer, Statement, Reference, VisionVersion, Group, GroupMembership
from dependencies.services.reference_parser import analyze_reference_definition
import re


def _analyze_statement(natural_language: str, tags: list) -> tuple:
    """
    Analyze a statement to deduce type and build formal expression.

    Returns:
        (statement_type, formal_expression, status)
    """
    text_lower = natural_language.lower()

    # Extract unique reference names from tags
    ref_names = []
    for tag in tags:
        if isinstance(tag, dict) and 'tag' in tag:
            ref_name = tag['tag']
            if ref_name not in ref_names:
                ref_names.append(ref_name)

    # Deduce statement type from keywords
    statement_type = 'existence'  # default

    # Containment patterns
    containment_patterns = [
        r'must be in', r'should be in', r'contained in', r'belongs to',
        r'part of', r'within', r'inside', r'member of'
    ]
    # Exclusion patterns
    exclusion_patterns = [
        r'must not depend', r'should not depend', r'cannot depend',
        r'must not access', r'should not access', r'cannot access',
        r'must not call', r'should not call', r'cannot call',
        r'must not use', r'should not use', r'cannot use',
        r'no dependency', r'no dependencies'
    ]
    # Cardinality patterns
    cardinality_patterns = [
        r'at least \d+', r'at most \d+', r'exactly \d+',
        r'no more than \d+', r'no fewer than \d+',
        r'maximum of \d+', r'minimum of \d+'
    ]

    # Check patterns in order of specificity
    for pattern in exclusion_patterns:
        if re.search(pattern, text_lower):
            statement_type = 'exclusion'
            break
    else:
        for pattern in containment_patterns:
            if re.search(pattern, text_lower):
                statement_type = 'containment'
                break
        else:
            for pattern in cardinality_patterns:
                if re.search(pattern, text_lower):
                    statement_type = 'cardinality'
                    break

    # Build formal expression based on type and tagged references
    formal_expression = {
        'tags': tags,
        'type': statement_type,
    }
    status = 'informal'

    if len(ref_names) == 0:
        # No references tagged - informal only
        status = 'informal'
    elif statement_type == 'existence':
        # Existence needs at least 1 reference
        if len(ref_names) >= 1:
            formal_expression['reference'] = ref_names[0]
            status = 'formal'
    elif statement_type == 'containment':
        # Containment needs 2 references: subject and container
        if len(ref_names) >= 2:
            formal_expression['subject'] = ref_names[0]
            formal_expression['container'] = ref_names[1]
            status = 'formal'
        elif len(ref_names) == 1:
            formal_expression['subject'] = ref_names[0]
            status = 'semi_formal'
    elif statement_type == 'exclusion':
        # Exclusion needs 2 references: subject and excluded
        if len(ref_names) >= 2:
            formal_expression['subject'] = ref_names[0]
            formal_expression['excluded'] = ref_names[1]
            status = 'formal'
        elif len(ref_names) == 1:
            formal_expression['subject'] = ref_names[0]
            status = 'semi_formal'
    elif statement_type == 'cardinality':
        # Cardinality needs 1 reference + number
        if len(ref_names) >= 1:
            formal_expression['reference'] = ref_names[0]
            # Try to extract number and operator
            match = re.search(r'(at least|at most|exactly|no more than|maximum of|minimum of)\s+(\d+)', text_lower)
            if match:
                operator_text = match.group(1)
                value = int(match.group(2))
                operator_map = {
                    'at least': '>=',
                    'minimum of': '>=',
                    'no fewer than': '>=',
                    'at most': '<=',
                    'maximum of': '<=',
                    'no more than': '<=',
                    'exactly': '==',
                }
                formal_expression['operator'] = operator_map.get(operator_text, '>=')
                formal_expression['value'] = value
                status = 'formal'
            else:
                status = 'semi_formal'

    return statement_type, formal_expression, status


def vision_home(request):
    """Vision Creation home page."""
    visions = Vision.objects.all().order_by('-updated_at')
    return render(request, 'vision/home.html', {'visions': visions})


def test_editor(request):
    """Test page for tagged editor component."""
    return render(request, 'vision/test_editor.html')


@require_http_methods(["GET", "POST"])
def vision_form(request):
    """Handle vision form modal - GET for form, POST to save."""
    if request.method == "GET":
        vision_id = request.GET.get('vision_id')
        vision = None
        if vision_id:
            vision = get_object_or_404(Vision, pk=vision_id)
        context = {
            'vision': vision,
            'status_choices': Vision.STATUS_CHOICES,
        }
        html = render_to_string(
            'vision_form/vision_form.html',
            context,
            request=request
        )
        return HttpResponse(html)

    # POST - create or update
    vision_id = request.POST.get('vision_id')
    name = request.POST.get('name', '').strip()
    description = request.POST.get('description', '').strip()
    status = request.POST.get('status', 'draft')

    if not name:
        return HttpResponse(
            '<div class="alert alert-danger">Name is required</div>',
            status=400
        )

    # Get scope project IDs if provided (from scope app)
    scope_project_ids_raw = request.POST.get('scope_project_ids', '')
    scope_project_ids = []
    if scope_project_ids_raw:
        try:
            scope_project_ids = json.loads(scope_project_ids_raw)
        except json.JSONDecodeError:
            pass

    if vision_id:
        vision = get_object_or_404(Vision, pk=vision_id)
        vision.name = name
        vision.description = description
        vision.status = status
        vision.save()
    else:
        vision = Vision.objects.create(
            name=name,
            description=description,
            status=status
        )

        # If we have scope projects, create a default layer and group with them
        if scope_project_ids:
            from dependencies.models import Project
            # Create a default layer
            default_layer = Layer.objects.create(
                vision=vision,
                key='scope',
                name='Scope',
                layer_type='freeform',
                color='#6c757d',
                order=0
            )
            # Create a default group within the layer
            default_group = Group.objects.create(
                layer=default_layer,
                key='selected',
                name='Selected Projects',
                color='#0d6efd'
            )
            # Add all selected projects to the group
            projects = Project.objects.filter(id__in=scope_project_ids)
            for project in projects:
                GroupMembership.objects.create(
                    group=default_group,
                    project=project,
                    membership_type='explicit'
                )

    # If created from scope, redirect to vision detail page
    if scope_project_ids and not vision_id:
        response = HttpResponse('')
        response['HX-Trigger'] = 'closeModal'
        response['HX-Redirect'] = f'/vision/{vision.id}/'
        return response

    # Return updated list
    visions = Vision.objects.all().order_by('-updated_at')
    html = render_to_string(
        'vision_list/vision_list.html',
        {'visions': visions},
        request=request
    )
    response = HttpResponse(html)
    response['HX-Trigger'] = 'closeModal'
    return response


@require_http_methods(["DELETE"])
def vision_delete(request):
    """Delete a vision."""
    vision_id = request.GET.get('vision_id')
    if vision_id:
        Vision.objects.filter(pk=vision_id).delete()
    return HttpResponse('')  # Empty response to remove the card


def vision_list(request):
    """Return the vision list partial."""
    visions = Vision.objects.all().order_by('-updated_at')
    html = render_to_string(
        'vision_list/vision_list.html',
        {'visions': visions},
        request=request
    )
    return HttpResponse(html)


def vision_detail(request, vision_id, version_id=None):
    """Vision detail page with layers and statements.

    If version_id is provided, load that version's layout.
    Otherwise, show the main/current layout.
    """
    vision = get_object_or_404(Vision, pk=vision_id)

    # Get all versions for this vision
    versions = vision.versions.all()

    # Get the currently viewed version (if any)
    current_version = None
    if version_id:
        current_version = get_object_or_404(VisionVersion, pk=version_id, vision=vision)

    return render(request, 'vision/detail.html', {
        'vision': vision,
        'versions': versions,
        'current_version': current_version,
    })


LAYER_COLORS = [
    '#0d6efd',  # Blue
    '#198754',  # Green
    '#dc3545',  # Red
    '#fd7e14',  # Orange
    '#6f42c1',  # Purple
    '#20c997',  # Teal
    '#ffc107',  # Yellow
    '#e83e8c',  # Pink
    '#17a2b8',  # Cyan
    '#6c757d',  # Gray
]


@require_http_methods(["GET", "POST"])
def layer_form(request):
    """Handle layer form modal - GET for form, POST to save."""
    if request.method == "GET":
        vision_id = request.GET.get('vision_id')
        layer_id = request.GET.get('layer_id')

        vision = get_object_or_404(Vision, pk=vision_id) if vision_id else None
        layer = get_object_or_404(Layer, pk=layer_id) if layer_id else None

        # Determine default color for new layers (round-robin)
        default_color = '#6c757d'
        if vision and not layer:
            layer_count = vision.layers.count()
            default_color = LAYER_COLORS[layer_count % len(LAYER_COLORS)]

        context = {
            'vision': vision or (layer.vision if layer else None),
            'layer': layer,
            'layer_types': Layer.LAYER_TYPES,
            'default_color': default_color,
        }
        html = render_to_string(
            'vision/components/layer_form/layer_form.html',
            context,
            request=request
        )
        return HttpResponse(html)

    # POST - create or update layer
    vision_id = request.POST.get('vision_id')
    layer_id = request.POST.get('layer_id')
    key = request.POST.get('key', '').strip()
    name = request.POST.get('name', '').strip()
    layer_type = request.POST.get('layer_type', 'freeform')
    color = request.POST.get('color', '#6c757d')

    if not name:
        return HttpResponse(
            '<div class="alert alert-danger">Name is required</div>',
            status=400
        )

    if not key:
        key = name.lower().replace(' ', '-')

    if layer_id:
        # Update existing
        layer = get_object_or_404(Layer, pk=layer_id)
        layer.key = key
        layer.name = name
        layer.layer_type = layer_type
        layer.color = color
        layer.save()
    else:
        # Create new
        vision = get_object_or_404(Vision, pk=vision_id)
        order = vision.layers.count()
        layer = Layer.objects.create(
            vision=vision,
            key=key,
            name=name,
            layer_type=layer_type,
            color=color,
            order=order
        )

    # Return updated layers list
    response = HttpResponse('')
    response['HX-Trigger'] = 'closeModal, layersUpdated'
    response['HX-Redirect'] = f'/vision/{layer.vision.id}/'
    return response


@require_http_methods(["DELETE"])
def layer_delete(request):
    """Delete a layer."""
    layer_id = request.GET.get('layer_id')
    if layer_id:
        layer = Layer.objects.filter(pk=layer_id).first()
        if layer:
            vision = layer.vision
            layer.delete()
            # Return updated list
            html = render_to_string(
                'vision/components/layers_list.html',
                {'vision': vision},
                request=request
            )
            return HttpResponse(html)
    return HttpResponse('')


@require_http_methods(["GET", "POST"])
def statement_form(request):
    """Handle statement form modal - GET for form, POST to save."""
    if request.method == "GET":
        vision_id = request.GET.get('vision_id')
        statement_id = request.GET.get('statement_id')

        vision = get_object_or_404(Vision, pk=vision_id) if vision_id else None
        statement = get_object_or_404(Statement, pk=statement_id) if statement_id else None

        if statement and not vision:
            vision = statement.vision

        # Get references for this vision (available as tags)
        references = vision.references.all() if vision else []

        # Parse existing tags from formal_expression if editing
        tags = []
        seen_tags = set()  # Track (start, end, tag) to deduplicate
        if statement and statement.formal_expression:
            raw_tags = statement.formal_expression.get('tags', [])
            # Ensure each tag has required fields and deduplicate
            for tag in raw_tags:
                if isinstance(tag, dict) and 'start' in tag and 'end' in tag and 'tag' in tag:
                    # Create dedup key from position and tag name
                    tag_key = (tag['start'], tag['end'], tag['tag'])
                    if tag_key in seen_tags:
                        continue  # Skip duplicate
                    seen_tags.add(tag_key)
                    tags.append({
                        'id': tag.get('id', f"tag-{len(tags)}"),
                        'start': tag['start'],
                        'end': tag['end'],
                        'tag': tag['tag'],
                        'color': tag.get('color', '#3498db'),
                    })

        context = {
            'vision': vision,
            'statement': statement,
            'statement_types': Statement.STATEMENT_TYPES,
            'status_choices': Statement.FORMALIZATION_STATUS,
            'references': references,
            'tags': json.dumps(tags),
        }
        html = render_to_string(
            'vision/components/statement_form/statement_form.html',
            context,
            request=request
        )
        return HttpResponse(html)

    # POST - create or update statement
    statement_id = request.POST.get('statement_id')
    vision_id = request.POST.get('vision_id')

    # Get the tagged editor data
    editor_data = request.POST.get('statement-editor', '{}')
    try:
        editor_state = json.loads(editor_data)
        natural_language = editor_state.get('text', '')
        raw_tags = editor_state.get('tags', [])
        # Deduplicate tags before saving
        seen_tags = set()
        tags = []
        for tag in raw_tags:
            if isinstance(tag, dict) and 'start' in tag and 'end' in tag and 'tag' in tag:
                tag_key = (tag['start'], tag['end'], tag['tag'])
                if tag_key not in seen_tags:
                    seen_tags.add(tag_key)
                    tags.append(tag)
    except json.JSONDecodeError:
        natural_language = editor_data
        tags = []

    if not natural_language.strip():
        return HttpResponse(
            '<div class="alert alert-danger">Statement text is required</div>',
            status=400
        )

    # Auto-deduce statement type and build formal expression
    statement_type, formal_expression, status = _analyze_statement(natural_language, tags)

    if statement_id:
        # Update existing
        statement = get_object_or_404(Statement, pk=statement_id)
        statement.statement_type = statement_type
        statement.natural_language = natural_language
        statement.formal_expression = formal_expression
        statement.status = status
        statement.save()
        vision = statement.vision
    else:
        # Create new
        vision = get_object_or_404(Vision, pk=vision_id)
        statement = Statement.objects.create(
            vision=vision,
            statement_type=statement_type,
            natural_language=natural_language,
            formal_expression=formal_expression,
            status=status
        )

    # Return empty response with trigger to close modal and refresh statements list
    response = HttpResponse('')
    response['HX-Trigger'] = 'closeModal, statementsUpdated'
    return response


@require_http_methods(["GET"])
def statements_list(request):
    """Return the statements list HTML fragment."""
    vision_id = request.GET.get('vision_id')
    vision = get_object_or_404(Vision, pk=vision_id)

    html = render_to_string(
        'vision/components/statements_list.html',
        {'vision': vision},
        request=request
    )
    return HttpResponse(html)


@require_http_methods(["GET"])
def references_list(request):
    """Return the references list HTML fragment."""
    vision_id = request.GET.get('vision_id')
    vision = get_object_or_404(Vision, pk=vision_id)

    html = render_to_string(
        'vision/components/references_list.html',
        {'vision': vision},
        request=request
    )
    return HttpResponse(html)


@require_http_methods(["DELETE"])
def statement_delete(request):
    """Delete a statement."""
    statement_id = request.GET.get('statement_id')
    if statement_id:
        statement = Statement.objects.filter(pk=statement_id).first()
        if statement:
            vision = statement.vision
            statement.delete()
            # Return updated list
            html = render_to_string(
                'vision/components/statements_list.html',
                {'vision': vision},
                request=request
            )
            return HttpResponse(html)
    return HttpResponse('')


@require_http_methods(["POST"])
@csrf_exempt
def reference_create(request):
    """Create a new reference via HTMX (from tagged editor popup)."""
    vision_id = request.POST.get('vision_id')
    name = request.POST.get('name', '').strip()
    color = request.POST.get('color', '#3498db')

    if not vision_id or not name:
        return HttpResponse(
            '<div class="alert alert-danger">Vision ID and name are required</div>',
            status=400
        )

    vision = get_object_or_404(Vision, pk=vision_id)

    # Create or get the reference
    reference, created = Reference.objects.get_or_create(
        vision=vision,
        name=name,
        defaults={
            'definition_type': 'informal',
            'description': f'Reference created from statement editor',
        }
    )

    return HttpResponse(json.dumps({
        'id': reference.id,
        'name': reference.name,
        'color': color,
        'created': created,
    }), content_type='application/json')


def _format_definition_for_display(reference):
    """Format a reference's definition back to natural language for editing."""
    if not reference:
        return ''

    if reference.definition_type == 'tag_expression' and reference.tag_expression:
        return _format_tag_expression(reference.tag_expression)
    elif reference.definition_type == 'explicit_list' and reference.explicit_members:
        return 'components: ' + ', '.join(reference.explicit_members)
    elif reference.definition_type == 'layer' and reference.layer_id:
        # Try to get layer name
        from .models import Layer
        layer = Layer.objects.filter(pk=reference.layer_id).first()
        if layer:
            return f'groups on $$${layer.key}$$$'
        return ''

    return ''


def _format_tag_expression(expr):
    """Format a tag expression dict back to natural language."""
    if isinstance(expr, str):
        return f"components tagged with '{expr}'"

    if 'tag' in expr:
        return f"components tagged with '{expr['tag']}'"

    if 'and' in expr:
        parts = []
        for item in expr['and']:
            if isinstance(item, str):
                parts.append(f"'{item}'")
            elif isinstance(item, dict) and 'tag' in item:
                parts.append(f"'{item['tag']}'")
            elif isinstance(item, dict) and 'not' in item:
                inner = item['not']
                if isinstance(inner, str):
                    parts.append(f"not '{inner}'")
                elif isinstance(inner, dict) and 'tag' in inner:
                    parts.append(f"not '{inner['tag']}'")
            elif isinstance(item, dict):
                parts.append('(' + _format_tag_expression_inner(item) + ')')
        return 'components tagged with ' + ' and '.join(parts)

    if 'or' in expr:
        parts = []
        for item in expr['or']:
            if isinstance(item, str):
                parts.append(f"'{item}'")
            elif isinstance(item, dict) and 'tag' in item:
                parts.append(f"'{item['tag']}'")
            elif isinstance(item, dict):
                parts.append('(' + _format_tag_expression_inner(item) + ')')
        return 'components tagged with ' + ' or '.join(parts)

    if 'not' in expr:
        inner = expr['not']
        if isinstance(inner, str):
            return f"components tagged with not '{inner}'"
        elif isinstance(inner, dict) and 'tag' in inner:
            return f"components tagged with not '{inner['tag']}'"

    return ''


def _format_tag_expression_inner(expr):
    """Format inner tag expression (without 'components tagged with' prefix)."""
    if isinstance(expr, str):
        return f"'{expr}'"

    if 'tag' in expr:
        return f"'{expr['tag']}'"

    if 'and' in expr:
        parts = []
        for item in expr['and']:
            if isinstance(item, str):
                parts.append(f"'{item}'")
            elif isinstance(item, dict) and 'tag' in item:
                parts.append(f"'{item['tag']}'")
            elif isinstance(item, dict):
                parts.append('(' + _format_tag_expression_inner(item) + ')')
        return ' and '.join(parts)

    if 'or' in expr:
        parts = []
        for item in expr['or']:
            if isinstance(item, str):
                parts.append(f"'{item}'")
            elif isinstance(item, dict) and 'tag' in item:
                parts.append(f"'{item['tag']}'")
            elif isinstance(item, dict):
                parts.append('(' + _format_tag_expression_inner(item) + ')')
        return ' or '.join(parts)

    if 'not' in expr:
        inner = expr['not']
        if isinstance(inner, str):
            return f"not '{inner}'"
        elif isinstance(inner, dict) and 'tag' in inner:
            return f"not '{inner['tag']}'"
        elif isinstance(inner, dict):
            return 'not (' + _format_tag_expression_inner(inner) + ')'

    return ''


@require_http_methods(["GET", "POST"])
def reference_form(request):
    """Handle reference form modal - GET for form, POST to save."""
    if request.method == "GET":
        vision_id = request.GET.get('vision_id')
        reference_id = request.GET.get('reference_id')

        vision = get_object_or_404(Vision, pk=vision_id) if vision_id else None
        reference = get_object_or_404(Reference, pk=reference_id) if reference_id else None

        if reference and not vision:
            vision = reference.vision

        # Format definition for display
        if reference:
            reference.definition_display = _format_definition_for_display(reference)

        context = {
            'vision': vision,
            'reference': reference,
        }

        html = render_to_string(
            'vision/components/reference_form/reference_form.html',
            context,
            request=request
        )
        return HttpResponse(html)

    # POST - create or update reference
    reference_id = request.POST.get('reference_id')
    vision_id = request.POST.get('vision_id')
    name = request.POST.get('name', '').strip()
    description = request.POST.get('description', '').strip()
    definition = request.POST.get('definition', '').strip()

    if not name:
        return HttpResponse(
            '<div class="alert alert-danger">Name is required</div>',
            status=400
        )

    # Infer definition type from the definition text
    definition_type = 'informal'
    tag_expression = None
    explicit_members = []
    layer_id = None

    if definition:
        analysis = analyze_reference_definition(definition)
        if analysis['parsed']:
            parsed = analysis['parsed']
            definition_type = parsed['type']

            if definition_type == 'tag_expression':
                tag_expression = parsed['expression']
            elif definition_type == 'explicit_list':
                explicit_members = parsed['members']
            elif definition_type == 'layer':
                # Try to resolve layer by key
                from .models import Layer
                layer_key = parsed['layer']
                vision_obj = get_object_or_404(Vision, pk=vision_id) if vision_id else None
                if reference_id:
                    reference_obj = get_object_or_404(Reference, pk=reference_id)
                    vision_obj = reference_obj.vision
                if vision_obj:
                    layer = Layer.objects.filter(vision=vision_obj, key=layer_key).first()
                    if layer:
                        layer_id = layer.id

    if reference_id:
        # Update existing
        reference = get_object_or_404(Reference, pk=reference_id)
        reference.name = name
        reference.description = description
        reference.definition_type = definition_type
        reference.tag_expression = tag_expression
        reference.explicit_members = explicit_members
        reference.layer_id = layer_id
        reference.save()
        vision = reference.vision
    else:
        # Create new
        vision = get_object_or_404(Vision, pk=vision_id)
        reference = Reference.objects.create(
            vision=vision,
            name=name,
            description=description,
            definition_type=definition_type,
            tag_expression=tag_expression,
            explicit_members=explicit_members,
            layer_id=layer_id
        )

    response = HttpResponse('')
    response['HX-Trigger'] = 'closeModal, referencesUpdated'
    response['HX-Redirect'] = f'/vision/{vision.id}/'
    return response


@require_http_methods(["DELETE"])
def reference_delete(request):
    """Delete a reference."""
    reference_id = request.GET.get('reference_id')
    if reference_id:
        reference = Reference.objects.filter(pk=reference_id).first()
        if reference:
            vision = reference.vision
            reference.delete()
            # Return updated list
            html = render_to_string(
                'vision/components/references_list.html',
                {'vision': vision},
                request=request
            )
            return HttpResponse(html)
    return HttpResponse('')


@require_http_methods(["POST"])
def layer_from_reference(request):
    """Create a layer from a reference's members."""
    from dependencies.models import Project
    from vision.services.tag_resolver import resolve_reference

    reference_id = request.GET.get('reference_id')
    if not reference_id:
        return HttpResponse('Reference ID required', status=400)

    reference = get_object_or_404(Reference, pk=reference_id)
    vision = reference.vision

    # Create a new layer with the reference name
    base_key = reference.name.lower().replace(' ', '-')
    layer_key = base_key
    layer_count = vision.layers.count()

    # Ensure unique key
    counter = 1
    while vision.layers.filter(key=layer_key).exists():
        counter += 1
        layer_key = f"{base_key}-{counter}"

    # Get a color for the new layer (round-robin)
    layer = Layer.objects.create(
        vision=vision,
        key=layer_key,
        name=reference.name,
        layer_type='freeform',
        color=LAYER_COLORS[layer_count % len(LAYER_COLORS)],
        order=layer_count,
    )

    # Create a group in the layer with the same name
    group = Group.objects.create(
        layer=layer,
        key=layer_key,
        name=reference.name,
        color=layer.color,
    )

    # Resolve the reference to get member project keys
    project_keys = resolve_reference(reference)
    if project_keys:
        projects = Project.objects.filter(key__in=project_keys)
        for project in projects:
            GroupMembership.objects.create(
                group=group,
                project=project,
                membership_type='explicit',
            )

    # Return updated layers list
    html = render_to_string(
        'vision/components/layers_list.html',
        {'vision': vision},
        request=request
    )
    return HttpResponse(html)


# =============================================================================
# Vision Version endpoints
# =============================================================================

@require_http_methods(["GET", "POST"])
def version_form(request):
    """Handle version form modal - GET for form, POST to create."""
    if request.method == "GET":
        vision_id = request.GET.get('vision_id')
        version_id = request.GET.get('version_id')

        vision = get_object_or_404(Vision, pk=vision_id) if vision_id else None
        version = get_object_or_404(VisionVersion, pk=version_id) if version_id else None

        if version and not vision:
            vision = version.vision

        context = {
            'vision': vision,
            'version': version,
        }
        html = render_to_string(
            'vision/components/version_form/version_form.html',
            context,
            request=request
        )
        return HttpResponse(html)

    # POST - create or update version
    vision_id = request.POST.get('vision_id')
    version_id = request.POST.get('version_id')
    name = request.POST.get('name', '').strip()
    description = request.POST.get('description', '').strip()
    snapshot_current = request.POST.get('snapshot_current', 'on') == 'on'

    if not name:
        return HttpResponse(
            '<div class="alert alert-danger">Name is required</div>',
            status=400
        )

    if version_id:
        # Update existing version
        version = get_object_or_404(VisionVersion, pk=version_id)
        version.name = name
        version.description = description
        version.save()
        vision = version.vision
    else:
        # Create new version
        vision = get_object_or_404(Vision, pk=vision_id)
        order = vision.versions.count()
        version = VisionVersion.objects.create(
            vision=vision,
            name=name,
            description=description,
            order=order
        )
        # Snapshot current layout if requested
        if snapshot_current:
            version.snapshot_current_layout()

    response = HttpResponse('')
    response['HX-Trigger'] = 'closeModal'
    response['HX-Redirect'] = f'/vision/{vision.id}/'
    return response


@require_http_methods(["POST"])
@csrf_exempt
def version_snapshot(request):
    """Snapshot the current layout into a version."""
    version_id = request.POST.get('version_id')
    if version_id:
        version = get_object_or_404(VisionVersion, pk=version_id)
        version.snapshot_current_layout()
        return HttpResponse(
            '<div class="alert alert-success alert-dismissible fade show">'
            '<i class="bi bi-check-circle me-2"></i>'
            f'Layout saved to "{version.name}"'
            '<button type="button" class="btn-close" data-bs-dismiss="alert"></button>'
            '</div>'
        )
    return HttpResponse(
        '<div class="alert alert-danger">Version ID required</div>',
        status=400
    )


@require_http_methods(["DELETE"])
def version_delete(request):
    """Delete a version."""
    version_id = request.GET.get('version_id')
    if version_id:
        version = VisionVersion.objects.filter(pk=version_id).first()
        if version:
            vision_id = version.vision.id
            version.delete()
            response = HttpResponse('')
            response['HX-Redirect'] = f'/vision/{vision_id}/'
            return response
    return HttpResponse('')


def versions_tabs(request):
    """Return the version tabs partial for HTMX updates."""
    vision_id = request.GET.get('vision_id')
    current_version_id = request.GET.get('current_version_id')

    vision = get_object_or_404(Vision, pk=vision_id)
    versions = vision.versions.all()

    current_version = None
    if current_version_id:
        current_version = VisionVersion.objects.filter(pk=current_version_id).first()

    html = render_to_string(
        'vision/components/version_tabs.html',
        {
            'vision': vision,
            'versions': versions,
            'current_version': current_version,
        },
        request=request
    )
    return HttpResponse(html)


@require_http_methods(["POST"])
def reference_validate(request):
    """Validate a reference definition and return the parsed type."""
    definition = request.POST.get('definition', '').strip()

    if not definition:
        return JsonResponse({
            'valid': False,
            'type': None,
            'type_display': None,
        })

    analysis = analyze_reference_definition(definition)

    if analysis['parsed']:
        # Map parsed type to display name
        type_display_map = {
            'tag_expression': 'Tag Expression',
            'layer': 'Layer',
            'explicit_list': 'Explicit List',
        }
        return JsonResponse({
            'valid': True,
            'type': analysis['definition_type'],
            'type_display': type_display_map.get(analysis['definition_type'], 'Formal'),
            'parsed': analysis['parsed'],
        })
    else:
        return JsonResponse({
            'valid': False,
            'type': None,
            'type_display': None,
            'error': analysis.get('error'),
        })
