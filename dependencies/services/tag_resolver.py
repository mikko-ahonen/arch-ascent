"""
Tag Expression Resolver Service.

Resolves tag expressions to sets of project keys based on taggit tags.
Uses django-taggit for tag management.
"""
from typing import Optional
from taggit.models import Tag
from dependencies.models import Component


def resolve_tag_expression(
    expression: dict | str,
    vision_id: Optional[int] = None
) -> set[str]:
    """
    Resolve a tag expression to a set of project keys.

    Expression format:
    - "tag_name" - projects with this tag (string shorthand)
    - {"and": ["tag1", "tag2"]} - projects with ALL tags
    - {"or": ["tag1", "tag2"]} - projects with ANY tag
    - {"not": "tag1"} - projects WITHOUT this tag
    - {"and": [{"or": ["a", "b"]}, "c"]} - nested expressions

    Args:
        expression: Tag expression (dict or string)
        vision_id: Optional vision scope (currently unused with taggit, reserved for future)

    Returns:
        Set of project keys matching the expression
    """
    if isinstance(expression, str):
        return _get_projects_with_tag(expression)

    if not isinstance(expression, dict):
        return set()

    if "and" in expression:
        return _resolve_and(expression["and"], vision_id)
    elif "or" in expression:
        return _resolve_or(expression["or"], vision_id)
    elif "not" in expression:
        return _resolve_not(expression["not"], vision_id)
    elif "tag" in expression:
        # Simple {"tag": "tag_name"} format
        return _get_projects_with_tag(expression["tag"])

    return set()


def _get_projects_with_tag(tag_name: str) -> set[str]:
    """Get all projects with a specific tag using taggit."""
    return set(
        Component.objects.filter(tags__name=tag_name).values_list('key', flat=True)
    )


def _get_all_project_keys() -> set[str]:
    """Get all project keys in the system."""
    return set(Component.objects.values_list('key', flat=True))


def _resolve_and(operands: list, vision_id: Optional[int]) -> set[str]:
    """Resolve AND expression - intersection of all operands."""
    if not operands:
        return set()

    result = resolve_tag_expression(operands[0], vision_id)
    for operand in operands[1:]:
        result &= resolve_tag_expression(operand, vision_id)
    return result


def _resolve_or(operands: list, vision_id: Optional[int]) -> set[str]:
    """Resolve OR expression - union of all operands."""
    result = set()
    for operand in operands:
        result |= resolve_tag_expression(operand, vision_id)
    return result


def _resolve_not(operand: dict | str, vision_id: Optional[int]) -> set[str]:
    """Resolve NOT expression - all projects except those matching operand."""
    all_projects = _get_all_project_keys()
    matching = resolve_tag_expression(operand, vision_id)
    return all_projects - matching


def get_tags_for_project(project_key: str) -> list[dict]:
    """
    Get all tags assigned to a project using taggit.

    Args:
        project_key: The project key

    Returns:
        List of tag info dicts with keys: name, slug
    """
    try:
        project = Component.objects.get(key=project_key)
    except Component.DoesNotExist:
        return []

    return [
        {
            'name': tag.name,
            'slug': tag.slug,
        }
        for tag in project.tags.all()
    ]


def assign_tag_to_project(tag_name: str, project_key: str) -> bool:
    """
    Assign a tag to a project using taggit.

    Args:
        tag_name: The tag name
        project_key: The project key

    Returns:
        True if tag was added, False if project not found
    """
    try:
        project = Component.objects.get(key=project_key)
    except Component.DoesNotExist:
        return False

    project.tags.add(tag_name)
    return True


def remove_tag_from_project(tag_name: str, project_key: str) -> bool:
    """
    Remove a tag from a project using taggit.

    Args:
        tag_name: The tag name
        project_key: The project key

    Returns:
        True if tag was removed, False if project not found or tag didn't exist
    """
    try:
        project = Component.objects.get(key=project_key)
    except Component.DoesNotExist:
        return False

    if tag_name in [t.name for t in project.tags.all()]:
        project.tags.remove(tag_name)
        return True
    return False


def get_all_tags() -> list[dict]:
    """
    Get all tags in the system.

    Returns:
        List of tag info dicts with keys: name, slug, count
    """
    from django.db.models import Count

    tags = Tag.objects.annotate(
        usage_count=Count('taggit_taggeditem_items')
    ).order_by('name')

    return [
        {
            'name': tag.name,
            'slug': tag.slug,
            'count': tag.usage_count,
        }
        for tag in tags
    ]


def get_projects_by_tags(tag_names: list[str], match_all: bool = False) -> set[str]:
    """
    Get projects that have specified tags.

    Args:
        tag_names: List of tag names to match
        match_all: If True, project must have ALL tags. If False, ANY tag.

    Returns:
        Set of project keys
    """
    if not tag_names:
        return set()

    if match_all:
        # AND logic - must have all tags
        queryset = Component.objects.all()
        for tag_name in tag_names:
            queryset = queryset.filter(tags__name=tag_name)
        return set(queryset.values_list('key', flat=True))
    else:
        # OR logic - must have any tag
        return set(
            Component.objects.filter(tags__name__in=tag_names)
            .distinct()
            .values_list('key', flat=True)
        )
