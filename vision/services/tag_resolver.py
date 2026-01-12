"""
Tag Expression Resolver for Vision app.

Re-exports tag functions from dependencies and adds Reference resolution.
"""
from dependencies.models import Project

# Re-export tag functions from dependencies
from dependencies.services.tag_resolver import (
    resolve_tag_expression,
    get_tags_for_project,
    assign_tag_to_project,
    remove_tag_from_project,
    get_all_tags,
    get_projects_by_tags,
)


def resolve_reference(reference) -> set[str]:
    """
    Resolve a Reference model instance to its member project keys.

    Args:
        reference: Reference model instance (from vision.models)

    Returns:
        Set of project keys that match the reference definition
    """
    if reference.definition_type == 'explicit_list':
        # Return explicit members (validate they exist)
        explicit_keys = set(reference.explicit_members or [])
        existing_keys = set(
            Project.objects.filter(key__in=explicit_keys).values_list('key', flat=True)
        )
        return existing_keys

    elif reference.definition_type == 'tag_expression':
        if not reference.tag_expression:
            return set()
        return resolve_tag_expression(
            reference.tag_expression,
            reference.vision_id
        )

    else:  # informal - no automatic resolution
        return set()
