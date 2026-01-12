"""
Reference Definition Parser

Parses natural language reference definitions into formal expressions
using pyparsing. This allows users to define references in English.

Supported definition types:
1. Tag-based: Boolean expressions with AND, OR, NOT, and parentheses
2. Layer-based: "components on $$$layer-name$$$" or "groups on $$$layer-name$$$"
3. Explicit list: "components: service-a, service-b, service-c"

Tag expression examples:
    >>> parse_reference_definition("components tagged with 'payment'")
    {'type': 'tag_expression', 'expression': {'tag': 'payment'}}

    >>> parse_reference_definition("components tagged with 'api' and 'payment'")
    {'type': 'tag_expression', 'expression': {'and': ['api', 'payment']}}

    >>> parse_reference_definition("components tagged with 'api' or 'payment'")
    {'type': 'tag_expression', 'expression': {'or': ['api', 'payment']}}

    >>> parse_reference_definition("components tagged with not 'deprecated'")
    {'type': 'tag_expression', 'expression': {'not': {'tag': 'deprecated'}}}

    >>> parse_reference_definition("components tagged with ('api' or 'service') and not 'deprecated'")
    # Complex boolean with parentheses and NOT

    >>> parse_reference_definition("components tagged with 'frontend' or ('api' and 'v2')")
    # OR with parenthesized AND

Layer examples:
    >>> parse_reference_definition("groups on $$$team-ownership$$$")
    {'type': 'layer', 'layer': 'team-ownership'}

    >>> parse_reference_definition("components in $$$infrastructure$$$")
    {'type': 'layer', 'layer': 'infrastructure'}

Explicit list example:
    >>> parse_reference_definition("components: service-a, service-b, service-c")
    {'type': 'explicit_list', 'members': ['service-a', 'service-b', 'service-c']}
"""

import re
from typing import Optional
from pyparsing import (
    CaselessKeyword,
    Combine,
    DelimitedList,
    Literal,
    OneOrMore,
    Optional as OptionalP,
    ParseException,
    QuotedString,
    Regex,
    Suppress,
    Word,
    alphanums,
    alphas,
    nums,
    oneOf,
    infix_notation,
    OpAssoc,
)


class ReferenceParseError(Exception):
    """Raised when a reference definition cannot be parsed."""
    pass


def _build_parser():
    """Build and return the pyparsing grammar for reference definitions."""

    # Reference token: $$$reference-id$$$
    reference = Combine(
        Literal('$$$') +
        Regex(r'[a-zA-Z0-9_-]+') +
        Literal('$$$')
    ).set_parse_action(lambda t: t[0][3:-3])  # Strip $$$ markers

    # Tag name: quoted string or simple identifier
    tag_name_quoted = QuotedString("'") | QuotedString('"')
    tag_name_simple = Word(alphanums + "-_")
    tag_name = tag_name_quoted | tag_name_simple

    # Keywords
    COMPONENTS = CaselessKeyword('components')
    GROUPS = CaselessKeyword('groups')
    TAGGED = CaselessKeyword('tagged')
    WITH = CaselessKeyword('with')
    AND = CaselessKeyword('and')
    OR = CaselessKeyword('or')
    NOT = CaselessKeyword('not')
    ON = CaselessKeyword('on')
    IN = CaselessKeyword('in')
    LAYER = CaselessKeyword('layer')

    # =========================================================================
    # Tag-based definitions with full boolean expression support
    # =========================================================================

    # Base tag operand: a single tag name -> {'tag': 'name'}
    tag_operand = tag_name.copy().set_parse_action(lambda t: {'tag': t[0]})

    # Helper functions to build expression trees
    def make_not_expr(tokens):
        """Handle NOT operator."""
        # tokens is [[NOT, operand]]
        inner = tokens[0]
        if len(inner) == 2 and inner[0].lower() == 'not':
            return {'not': inner[1]}
        return inner[0]

    def make_and_expr(tokens):
        """Handle AND operator - flatten nested ANDs."""
        items = tokens[0]
        # Filter out 'and' keywords and collect operands
        operands = []
        for item in items:
            if isinstance(item, str) and item.lower() == 'and':
                continue
            # Flatten nested AND expressions
            if isinstance(item, dict) and 'and' in item:
                operands.extend(item['and'])
            elif isinstance(item, dict) and 'tag' in item:
                operands.append(item['tag'])
            elif isinstance(item, dict):
                operands.append(item)
            else:
                operands.append(item)
        if len(operands) == 1:
            if isinstance(operands[0], str):
                return {'tag': operands[0]}
            return operands[0]
        return {'and': operands}

    def make_or_expr(tokens):
        """Handle OR operator - flatten nested ORs."""
        items = tokens[0]
        # Filter out 'or' keywords and collect operands
        operands = []
        for item in items:
            if isinstance(item, str) and item.lower() == 'or':
                continue
            # Flatten nested OR expressions
            if isinstance(item, dict) and 'or' in item:
                operands.extend(item['or'])
            elif isinstance(item, dict) and 'tag' in item:
                operands.append(item['tag'])
            elif isinstance(item, dict):
                operands.append(item)
            else:
                operands.append(item)
        if len(operands) == 1:
            if isinstance(operands[0], str):
                return {'tag': operands[0]}
            return operands[0]
        return {'or': operands}

    # Build boolean expression grammar using infix_notation
    # This handles operator precedence: NOT > AND > OR, and parentheses
    tag_expr = infix_notation(
        tag_operand,
        [
            (NOT, 1, OpAssoc.RIGHT, make_not_expr),
            (AND, 2, OpAssoc.LEFT, make_and_expr),
            (OR, 2, OpAssoc.LEFT, make_or_expr),
        ]
    )

    # "components tagged with ..."
    tagged_with = (
        Suppress(COMPONENTS + TAGGED + WITH) +
        tag_expr
    ).set_parse_action(lambda t: {
        'type': 'tag_expression',
        'expression': t[0]
    })

    # =========================================================================
    # Layer-based definitions
    # =========================================================================

    # "groups on $$$layer-name$$$" or "components on $$$layer-name$$$"
    on_layer = (
        Suppress((GROUPS | COMPONENTS) + ON) +
        reference
    ).set_parse_action(lambda t: {
        'type': 'layer',
        'layer': t[0]
    })

    # "groups on layer $$$layer-name$$$" (alternative syntax)
    on_layer_explicit = (
        Suppress((GROUPS | COMPONENTS) + ON + LAYER) +
        reference
    ).set_parse_action(lambda t: {
        'type': 'layer',
        'layer': t[0]
    })

    # "components in $$$layer-name$$$"
    in_layer = (
        Suppress(COMPONENTS + IN) +
        reference
    ).set_parse_action(lambda t: {
        'type': 'layer',
        'layer': t[0]
    })

    # =========================================================================
    # Explicit list definitions
    # =========================================================================

    # Project key: alphanumeric with hyphens, underscores, colons
    project_key = Word(alphanums + "-_:")

    # "components: service-a, service-b, service-c"
    explicit_list = (
        Suppress(COMPONENTS + Literal(':')) +
        DelimitedList(project_key, delim=',')
    ).set_parse_action(lambda t: {
        'type': 'explicit_list',
        'members': list(t)
    })

    # =========================================================================
    # Complete grammar
    # =========================================================================

    definition = (
        tagged_with |
        on_layer_explicit |
        on_layer |
        in_layer |
        explicit_list
    )

    return definition


# Build parser once at module load
_parser = _build_parser()


def parse_reference_definition(text: str) -> dict:
    """
    Parse a natural language reference definition into a formal expression.

    Args:
        text: The natural language definition.

    Returns:
        A dictionary with the formal definition:
        - Tag expression: {"type": "tag_expression", "expression": {...}}
        - Layer: {"type": "layer", "layer": "layer-name"}
        - Explicit list: {"type": "explicit_list", "members": [...]}

    Raises:
        ReferenceParseError: If the definition cannot be parsed.

    Examples:
        >>> parse_reference_definition("components tagged with 'payment'")
        {'type': 'tag_expression', 'expression': {'tag': 'payment'}}

        >>> parse_reference_definition("components tagged with 'api' and 'payment'")
        {'type': 'tag_expression', 'expression': {'and': ['api', 'payment']}}

        >>> parse_reference_definition("groups on $$$team-ownership$$$")
        {'type': 'layer', 'layer': 'team-ownership'}
    """
    # Normalize whitespace
    text = ' '.join(text.strip().split())

    try:
        result = _parser.parse_string(text, parse_all=True)
        return result[0]
    except ParseException as e:
        raise ReferenceParseError(
            f"Could not parse reference definition: '{text}'. "
            f"Error at position {e.loc}: {e.msg}"
        ) from e


def detect_definition_type(text: str) -> Optional[str]:
    """
    Attempt to detect the definition type without full parsing.

    Args:
        text: The natural language definition (may be incomplete).

    Returns:
        The detected definition type ('tag_expression', 'layer', 'explicit_list')
        or None if type cannot be determined.
    """
    text_lower = text.lower()

    if 'tagged with' in text_lower:
        return 'tag_expression'
    if ' on ' in text_lower and '$$$' in text:
        return 'layer'
    if ' in ' in text_lower and '$$$' in text:
        return 'layer'
    if 'components:' in text_lower:
        return 'explicit_list'

    return None


def get_definition_templates() -> dict[str, list[str]]:
    """
    Get all supported definition templates organized by type.

    Returns:
        Dictionary mapping definition types to lists of template variations.
    """
    return {
        'tag_expression': [
            "components tagged with 'tag-name'",
            "components tagged with 'tag1' and 'tag2'",
            "components tagged with 'tag1' or 'tag2'",
            "components tagged with not 'tag-name'",
            "components tagged with ('tag1' or 'tag2') and 'tag3'",
            "components tagged with 'tag1' and not 'deprecated'",
        ],
        'layer': [
            "groups on $$$layer-name$$$",
            "components on $$$layer-name$$$",
            "components in $$$layer-name$$$",
        ],
        'explicit_list': [
            "components: key1, key2, key3",
        ],
    }


def format_tag_expression(expression: dict) -> str:
    """
    Format a tag expression back to natural language.

    Args:
        expression: The tag expression dict (e.g., {'and': ['api', 'payment']})

    Returns:
        Natural language string (e.g., "components tagged with 'api' and 'payment'")
    """
    if 'tag' in expression:
        return f"components tagged with '{expression['tag']}'"
    elif 'and' in expression:
        tags = "' and '".join(expression['and'])
        return f"components tagged with '{tags}'"
    elif 'or' in expression:
        tags = "' or '".join(expression['or'])
        return f"components tagged with '{tags}'"
    elif 'not' in expression:
        return f"components not tagged with '{expression['not']}'"
    else:
        return str(expression)


def analyze_reference_definition(text: str) -> dict:
    """
    Analyze a reference definition to determine its type and parse it if possible.

    Args:
        text: The natural language definition.

    Returns:
        A dictionary with:
        - definition_type: str or None - The detected definition type
        - parsed: dict or None - The parsed definition if successful
        - error: str or None - Parse error message if failed
    """
    result = {
        'definition_type': None,
        'parsed': None,
        'error': None,
    }

    # Detect type
    result['definition_type'] = detect_definition_type(text)

    # Try to parse
    try:
        parsed = parse_reference_definition(text)
        result['parsed'] = parsed
        result['definition_type'] = parsed.get('type')
    except ReferenceParseError as e:
        result['error'] = str(e)

    return result
