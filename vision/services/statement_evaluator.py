"""
Statement Evaluator Service.

Evaluates architectural intent statements against current state.
"""
from typing import Optional
from django.utils import timezone
from vision.models import Statement, Reference, Group, GroupMembership
from dependencies.models import Project, Dependency
from vision.services.tag_resolver import resolve_reference, resolve_tag_expression


def evaluate_statement(statement: Statement) -> bool:
    """
    Evaluate whether a formal statement is satisfied.

    Statement types and their formal_expression format:
    - existence: {"reference": "RefName"} - reference must have members
    - containment: {"subject": "RefName", "container": "GroupKey"} - all subject members in container
    - exclusion: {"subject": "RefName", "excluded": "RefName"} - no deps from subject to excluded
    - cardinality: {"reference": "RefName", "operator": "==|<=|>=|<|>", "value": N}

    Args:
        statement: Statement model instance

    Returns:
        True if satisfied, False otherwise
    """
    if statement.status == 'informal' or not statement.formal_expression:
        # Can't evaluate informal statements
        return None

    expr = statement.formal_expression
    statement_type = statement.statement_type

    try:
        if statement_type == 'existence':
            result = _evaluate_existence(expr, statement.vision_id)
        elif statement_type == 'containment':
            result = _evaluate_containment(expr, statement.vision_id)
        elif statement_type == 'exclusion':
            result = _evaluate_exclusion(expr, statement.vision_id)
        elif statement_type == 'cardinality':
            result = _evaluate_cardinality(expr, statement.vision_id)
        else:
            result = None

        # Update statement with evaluation result
        statement.is_satisfied = result
        statement.last_evaluated_at = timezone.now()
        statement.save(update_fields=['is_satisfied', 'last_evaluated_at'])

        return result

    except Exception:
        statement.is_satisfied = None
        statement.last_evaluated_at = timezone.now()
        statement.save(update_fields=['is_satisfied', 'last_evaluated_at'])
        return None


def _resolve_reference_by_name(name: str, vision_id: Optional[int]) -> set[str]:
    """Resolve a reference by name to project keys."""
    try:
        ref = Reference.objects.get(name=name, vision_id=vision_id)
        return resolve_reference(ref)
    except Reference.DoesNotExist:
        # Try global reference
        try:
            ref = Reference.objects.get(name=name, vision_id__isnull=True)
            return resolve_reference(ref)
        except Reference.DoesNotExist:
            # Treat as tag expression (single tag)
            return resolve_tag_expression(name, vision_id)


def _evaluate_existence(expr: dict, vision_id: Optional[int]) -> bool:
    """
    Evaluate existence statement.

    Format: {"reference": "RefName"}
    True if the reference resolves to at least one member.
    """
    ref_name = expr.get('reference')
    if not ref_name:
        return False

    members = _resolve_reference_by_name(ref_name, vision_id)
    return len(members) > 0


def _evaluate_containment(expr: dict, vision_id: Optional[int]) -> bool:
    """
    Evaluate containment statement.

    Format: {"subject": "RefName", "container": "GroupKey"}
    True if all members of subject are in the container group.
    """
    subject_name = expr.get('subject')
    container_key = expr.get('container')

    if not subject_name or not container_key:
        return False

    # Get subject members
    subject_members = _resolve_reference_by_name(subject_name, vision_id)
    if not subject_members:
        # Empty subject is vacuously true
        return True

    # Get container group members
    try:
        # Find the group (could be in any layer of the vision)
        if vision_id:
            group = Group.objects.filter(
                key=container_key,
                layer__vision_id=vision_id
            ).first()
        else:
            group = Group.objects.filter(key=container_key).first()

        if not group:
            return False

        container_members = set(
            GroupMembership.objects.filter(group=group)
            .values_list('project__key', flat=True)
        )

        # Check if all subject members are in container
        return subject_members.issubset(container_members)

    except Exception:
        return False


def _evaluate_exclusion(expr: dict, vision_id: Optional[int]) -> bool:
    """
    Evaluate exclusion statement.

    Format: {"subject": "RefName", "excluded": "RefName"}
    True if no member of subject has a dependency on any member of excluded.
    """
    subject_name = expr.get('subject')
    excluded_name = expr.get('excluded')

    if not subject_name or not excluded_name:
        return False

    subject_members = _resolve_reference_by_name(subject_name, vision_id)
    excluded_members = _resolve_reference_by_name(excluded_name, vision_id)

    if not subject_members or not excluded_members:
        # No members means no violations possible
        return True

    # Check for any dependency from subject to excluded
    has_violation = Dependency.objects.filter(
        source__key__in=subject_members,
        target__key__in=excluded_members
    ).exists()

    return not has_violation


def _evaluate_cardinality(expr: dict, vision_id: Optional[int]) -> bool:
    """
    Evaluate cardinality statement.

    Format: {"reference": "RefName", "operator": "==|<=|>=|<|>", "value": N}
    True if the count of reference members satisfies the operator/value condition.
    """
    ref_name = expr.get('reference')
    operator = expr.get('operator')
    value = expr.get('value')

    if not ref_name or not operator or value is None:
        return False

    members = _resolve_reference_by_name(ref_name, vision_id)
    count = len(members)

    if operator == '==':
        return count == value
    elif operator == '!=':
        return count != value
    elif operator == '<=':
        return count <= value
    elif operator == '>=':
        return count >= value
    elif operator == '<':
        return count < value
    elif operator == '>':
        return count > value
    else:
        return False


def evaluate_all_statements(vision_id: int) -> dict:
    """
    Evaluate all statements in a vision.

    Args:
        vision_id: Vision ID

    Returns:
        Dict with evaluation summary and details
    """
    statements = Statement.objects.filter(vision_id=vision_id)

    results = {
        'total': statements.count(),
        'satisfied': 0,
        'violated': 0,
        'not_evaluated': 0,
        'statements': []
    }

    for statement in statements:
        result = evaluate_statement(statement)

        statement_info = {
            'id': statement.id,
            'type': statement.statement_type,
            'natural_language': statement.natural_language,
            'status': statement.status,
            'is_satisfied': result,
        }
        results['statements'].append(statement_info)

        if result is True:
            results['satisfied'] += 1
        elif result is False:
            results['violated'] += 1
        else:
            results['not_evaluated'] += 1

    return results


def get_statement_violations(vision_id: int) -> list[dict]:
    """
    Get all violated statements in a vision.

    Args:
        vision_id: Vision ID

    Returns:
        List of violated statement info dicts
    """
    # First evaluate all
    evaluate_all_statements(vision_id)

    # Then get violations
    violated = Statement.objects.filter(
        vision_id=vision_id,
        is_satisfied=False
    )

    return [
        {
            'id': s.id,
            'type': s.statement_type,
            'natural_language': s.natural_language,
            'formal_expression': s.formal_expression,
        }
        for s in violated
    ]
