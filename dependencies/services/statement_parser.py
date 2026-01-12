"""
Statement Parser

Parses natural language architectural statements into formal expressions
using pyparsing. References are passed as $$$reference-id$$$ tokens.

Supported statement types:
1. Existence: "there must be $$$ref$$$" or "$$$ref$$$ must exist"
2. Containment: "$$$X$$$ must be in $$$Y$$$" or "$$$Y$$$ must contain $$$X$$$"
3. Exclusion: "$$$X$$$ must not depend on $$$Y$$$"
4. Cardinality: "there must be exactly/at least/at most/more than/fewer than N $$$ref$$$"
5. Coverage: "all $$$X$$$ must have an owner on $$$layer$$$" or "$$$X$$$ must be covered by $$$layer$$$"
            Also: "all components" or "every component in the system" as built-in keywords
6. Correspondence: "$$$layer-A$$$ corresponds with $$$layer-B$$$" (1:1 group alignment)
7. Refinement: "$$$layer-A$$$ refines $$$layer-B$$$" (many:1 - finer partitioning)
"""

import re
from difflib import SequenceMatcher
from typing import Optional
from pyparsing import (
    CaselessKeyword,
    Combine,
    Literal,
    OneOrMore,
    Optional as OptionalP,
    ParseException,
    Regex,
    Suppress,
    Word,
    alphanums,
    alphas,
    nums,
    oneOf,
    pyparsing_common,
)


class StatementParseError(Exception):
    """Raised when a statement cannot be parsed."""
    pass


def _build_parser():
    """Build and return the pyparsing grammar for statements."""

    # Reference token: $$$reference-id$$$
    # Allow alphanumeric, hyphens, and underscores in the ID
    reference = Combine(
        Literal('$$$') +
        Regex(r'[a-zA-Z0-9_-]+') +
        Literal('$$$')
    ).set_parse_action(lambda t: t[0][3:-3])  # Strip $$$ markers

    # Keywords (case-insensitive)
    THERE = CaselessKeyword('there')
    MUST = CaselessKeyword('must') | CaselessKeyword('should')
    BE = CaselessKeyword('be')
    EXIST = CaselessKeyword('exist')
    IN = CaselessKeyword('in')
    CONTAINED = CaselessKeyword('contained')
    CONTAIN = CaselessKeyword('contain')
    NOT = CaselessKeyword('not')
    DEPEND = CaselessKeyword('depend')
    ON = CaselessKeyword('on')
    EXACTLY = CaselessKeyword('exactly')
    AT = CaselessKeyword('at')
    LEAST = CaselessKeyword('least')
    MOST = CaselessKeyword('most')
    MORE = CaselessKeyword('more')
    FEWER = CaselessKeyword('fewer')
    LESS = CaselessKeyword('less')
    THAN = CaselessKeyword('than')
    ALL = CaselessKeyword('all')
    EVERY = CaselessKeyword('every')
    HAVE = CaselessKeyword('have')
    AN = CaselessKeyword('an') | CaselessKeyword('a')
    OWNER = CaselessKeyword('owner')
    COVERED = CaselessKeyword('covered')
    BY = CaselessKeyword('by')

    # Number for cardinality
    number = pyparsing_common.integer

    # =========================================================================
    # Existence statements
    # =========================================================================

    # "there must be $$$ref$$$"
    existence_there_must_be = (
        Suppress(THERE + MUST + BE) +
        reference
    ).set_parse_action(lambda t: {
        'type': 'existence',
        'reference': t[0]
    })

    # "$$$ref$$$ must exist"
    existence_must_exist = (
        reference +
        Suppress(MUST + EXIST)
    ).set_parse_action(lambda t: {
        'type': 'existence',
        'reference': t[0]
    })

    existence = existence_there_must_be | existence_must_exist

    # =========================================================================
    # Containment statements
    # =========================================================================

    # Optional "all" or "every" prefix (non-functional, for readability)
    optional_quantifier = OptionalP(Suppress(ALL | EVERY))

    # "$$$X$$$ must be in $$$Y$$$" or "every $$$X$$$ must be in $$$Y$$$"
    containment_be_in = (
        optional_quantifier +
        reference +
        Suppress(MUST + BE + OptionalP(CONTAINED) + IN) +
        reference
    ).set_parse_action(lambda t: {
        'type': 'containment',
        'subject': t[0],
        'container': t[1]
    })

    # "$$$Y$$$ must contain $$$X$$$"
    containment_must_contain = (
        optional_quantifier +
        reference +
        Suppress(MUST + CONTAIN) +
        reference
    ).set_parse_action(lambda t: {
        'type': 'containment',
        'subject': t[1],  # What is contained
        'container': t[0]  # The container
    })

    containment = containment_be_in | containment_must_contain

    # =========================================================================
    # Exclusion statements
    # =========================================================================

    # "$$$X$$$ must not depend on $$$Y$$$" or "every $$$X$$$ must not depend on $$$Y$$$"
    exclusion = (
        optional_quantifier +
        reference +
        Suppress(MUST + NOT + DEPEND + ON) +
        reference
    ).set_parse_action(lambda t: {
        'type': 'exclusion',
        'subject': t[0],
        'excluded': t[1]
    })

    # =========================================================================
    # Cardinality statements
    # =========================================================================

    # Operators with their formal equivalents
    exactly_op = EXACTLY.set_parse_action(lambda: '==')
    at_least_op = (AT + LEAST).set_parse_action(lambda: '>=')
    at_most_op = (AT + MOST).set_parse_action(lambda: '<=')
    more_than_op = (MORE + THAN).set_parse_action(lambda: '>')
    fewer_than_op = ((FEWER | LESS) + THAN).set_parse_action(lambda: '<')

    cardinality_op = exactly_op | at_least_op | at_most_op | more_than_op | fewer_than_op

    # "there must be exactly/at least/at most/more than/fewer than N $$$ref$$$"
    cardinality = (
        Suppress(THERE + MUST + BE) +
        cardinality_op +
        number +
        reference
    ).set_parse_action(lambda t: {
        'type': 'cardinality',
        'operator': t[0],
        'value': t[1],
        'reference': t[2]
    })

    # =========================================================================
    # Coverage statements (ownership)
    # =========================================================================

    # Built-in keywords for "all components" (no reference needed)
    COMPONENTS = CaselessKeyword('components')
    COMPONENT = CaselessKeyword('component')
    THE = CaselessKeyword('the')
    SYSTEM = CaselessKeyword('system')

    # "all components" or "every component in the system" -> '*'
    ALL_COMPONENTS = (ALL + COMPONENTS).set_parse_action(lambda: '*')
    EVERY_COMPONENT = (EVERY + COMPONENT + IN + THE + SYSTEM).set_parse_action(lambda: '*')
    BUILTIN_ALL = ALL_COMPONENTS | EVERY_COMPONENT

    # "all $$$reference$$$" or "every $$$reference$$$" - user-defined reference with prefix
    ALL_REFERENCE = (Suppress(ALL | EVERY) + reference)

    # Subject can be:
    # 1. "all components" or "every component in the system" - built-in keyword producing '*'
    # 2. "all $$$reference$$$" or "every $$$reference$$$" - user-defined reference with prefix
    # 3. "$$$reference$$$" - just a reference
    # Note: Order matters - try most specific first
    coverage_subject = BUILTIN_ALL | ALL_REFERENCE | reference

    # "all components must have an owner on $$$team-ownership$$$"
    # "all $$$my-services$$$ must have an owner on $$$team-ownership$$$"
    coverage_have_owner = (
        coverage_subject +
        Suppress(MUST + HAVE + AN + OWNER + ON) +
        reference
    ).set_parse_action(lambda t: {
        'type': 'coverage',
        'subject': t[0],
        'layer': t[1]
    })

    # "all components must be covered by $$$team-ownership$$$"
    # "$$$components$$$ must be covered by $$$team-ownership$$$"
    coverage_covered_by = (
        coverage_subject +
        Suppress(MUST + BE + COVERED + BY) +
        reference
    ).set_parse_action(lambda t: {
        'type': 'coverage',
        'subject': t[0],
        'layer': t[1]
    })

    # "all components must belong to a group on $$$team-ownership$$$"
    # "all $$$microservices$$$ must belong to a group on $$$team-ownership$$$"
    coverage_belong_to = (
        coverage_subject +
        Suppress(MUST + CaselessKeyword('belong') + CaselessKeyword('to') + AN + CaselessKeyword('group') + ON) +
        reference
    ).set_parse_action(lambda t: {
        'type': 'coverage',
        'subject': t[0],
        'layer': t[1]
    })

    coverage = coverage_have_owner | coverage_covered_by | coverage_belong_to

    # =========================================================================
    # Correspondence statements (layer alignment - 1:1)
    # =========================================================================
    # Check that group memberships in one layer correspond exactly to another layer.
    # Correspondence is based on GROUP MEMBERS, not group names.
    # e.g., "team ownership corresponds with gitlab groups" means:
    # - For each group G1 on layer A with members {X, Y, Z},
    # - There should be a group G2 on layer B with the same members {X, Y, Z}.
    # Use this for 1:1 relationships between layers.

    CORRESPONDS = CaselessKeyword('corresponds')
    CORRESPOND = CaselessKeyword('correspond')
    ALIGNS = CaselessKeyword('aligns')
    ALIGN = CaselessKeyword('align')
    MATCHES = CaselessKeyword('matches')
    MATCH = CaselessKeyword('match')
    WITH = CaselessKeyword('with')
    TO = CaselessKeyword('to')

    # "$$$team-ownership$$$ must corresponds with $$$gitlab-groups$$$"
    # Note: MUST already includes 'should' via: CaselessKeyword('must') | CaselessKeyword('should')
    correspondence_with = (
        reference +
        Suppress(MUST + (CORRESPONDS | ALIGNS | MATCHES) + WITH) +
        reference
    ).set_parse_action(lambda t: {
        'type': 'correspondence',
        'layer_a': t[0],
        'layer_b': t[1]
    })

    # "$$$team-ownership$$$ must correspond to $$$gitlab-groups$$$"
    correspondence_to = (
        reference +
        Suppress(MUST + (CORRESPOND | ALIGN | MATCH) + (TO | WITH)) +
        reference
    ).set_parse_action(lambda t: {
        'type': 'correspondence',
        'layer_a': t[0],
        'layer_b': t[1]
    })

    # "team ownership corresponds with gitlab groups" (without must/should)
    correspondence_simple = (
        reference +
        Suppress((CORRESPONDS | ALIGNS | MATCHES) + WITH) +
        reference
    ).set_parse_action(lambda t: {
        'type': 'correspondence',
        'layer_a': t[0],
        'layer_b': t[1]
    })

    correspondence = correspondence_with | correspondence_to | correspondence_simple

    # =========================================================================
    # Refinement statements (layer alignment - many:1)
    # =========================================================================
    # Check that one layer's grouping is a refinement (finer partitioning) of another.
    # e.g., "$$$gitlab-groups$$$ refines $$$team-ownership$$$" means:
    # - If components X and Y are in the same group on gitlab-groups layer,
    # - Then X and Y must also be in the same group on team-ownership layer.
    # - But a team can own multiple gitlab groups (many:1 relationship).
    # Use this when one layer is a finer-grained partitioning than another.

    REFINES = CaselessKeyword('refines')
    REFINE = CaselessKeyword('refine')
    REFINEMENT = CaselessKeyword('refinement')
    NESTS = CaselessKeyword('nests')
    NEST = CaselessKeyword('nest')
    WITHIN = CaselessKeyword('within')
    OF = CaselessKeyword('of')

    # "$$$gitlab-groups$$$ refines $$$team-ownership$$$"
    refinement_simple = (
        reference +
        Suppress(REFINES) +
        reference
    ).set_parse_action(lambda t: {
        'type': 'refinement',
        'fine': t[0],  # finer-grained layer
        'coarse': t[1]  # coarser-grained layer
    })

    # "$$$gitlab-groups$$$ must refine $$$team-ownership$$$"
    refinement_must = (
        reference +
        Suppress(MUST + REFINE) +
        reference
    ).set_parse_action(lambda t: {
        'type': 'refinement',
        'fine': t[0],
        'coarse': t[1]
    })

    # "$$$gitlab-groups$$$ must be a refinement of $$$team-ownership$$$"
    refinement_be_a = (
        reference +
        Suppress(MUST + BE + AN + REFINEMENT + OF) +
        reference
    ).set_parse_action(lambda t: {
        'type': 'refinement',
        'fine': t[0],
        'coarse': t[1]
    })

    # "$$$gitlab-groups$$$ must nest within $$$team-ownership$$$"
    refinement_nest = (
        reference +
        Suppress(MUST + NEST + WITHIN) +
        reference
    ).set_parse_action(lambda t: {
        'type': 'refinement',
        'fine': t[0],
        'coarse': t[1]
    })

    # "$$$gitlab-groups$$$ nests within $$$team-ownership$$$"
    refinement_nest_simple = (
        reference +
        Suppress(NESTS + WITHIN) +
        reference
    ).set_parse_action(lambda t: {
        'type': 'refinement',
        'fine': t[0],
        'coarse': t[1]
    })

    refinement = refinement_simple | refinement_must | refinement_be_a | refinement_nest | refinement_nest_simple

    # =========================================================================
    # Complete grammar - try cardinality first (more specific) before existence
    # =========================================================================

    statement = cardinality | coverage | correspondence | refinement | existence | containment | exclusion

    return statement


# Build parser once at module load
_parser = _build_parser()


def parse_statement(text: str) -> dict:
    """
    Parse a natural language statement into a formal expression.

    Args:
        text: The natural language statement with references as $$$ref-id$$$ tokens.

    Returns:
        A dictionary with the formal expression:
        - Existence: {"type": "existence", "reference": "ref-id"}
        - Containment: {"type": "containment", "subject": "X", "container": "Y"}
        - Exclusion: {"type": "exclusion", "subject": "X", "excluded": "Y"}
        - Cardinality: {"type": "cardinality", "operator": "==", "value": N, "reference": "ref-id"}

    Raises:
        StatementParseError: If the statement cannot be parsed.

    Examples:
        >>> parse_statement("there must be $$$payment-services$$$")
        {'type': 'existence', 'reference': 'payment-services'}

        >>> parse_statement("$$$api-gateway$$$ must exist")
        {'type': 'existence', 'reference': 'api-gateway'}

        >>> parse_statement("$$$payment-api$$$ must be in $$$domain-layer$$$")
        {'type': 'containment', 'subject': 'payment-api', 'container': 'domain-layer'}

        >>> parse_statement("$$$domain-layer$$$ must contain $$$payment-api$$$")
        {'type': 'containment', 'subject': 'payment-api', 'container': 'domain-layer'}

        >>> parse_statement("$$$ui-layer$$$ must not depend on $$$database$$$")
        {'type': 'exclusion', 'subject': 'ui-layer', 'excluded': 'database'}

        >>> parse_statement("there must be exactly 1 $$$api-gateway$$$")
        {'type': 'cardinality', 'operator': '==', 'value': 1, 'reference': 'api-gateway'}

        >>> parse_statement("there must be at least 2 $$$payment-handlers$$$")
        {'type': 'cardinality', 'operator': '>=', 'value': 2, 'reference': 'payment-handlers'}
    """
    # Normalize whitespace
    text = ' '.join(text.strip().split())

    try:
        result = _parser.parse_string(text, parse_all=True)
        return result[0]
    except ParseException as e:
        raise StatementParseError(
            f"Could not parse statement: '{text}'. "
            f"Error at position {e.loc}: {e.msg}"
        ) from e


def detect_statement_type(text: str) -> Optional[str]:
    """
    Attempt to detect the statement type without full parsing.

    This is useful for providing hints or validation feedback before
    the statement is fully formed.

    Args:
        text: The natural language statement (may be incomplete).

    Returns:
        The detected statement type ('existence', 'containment', 'exclusion',
        'cardinality', 'coverage', 'correspondence') or None if type cannot be determined.
    """
    text_lower = text.lower()

    # Check for cardinality indicators first (more specific)
    cardinality_indicators = ['exactly', 'at least', 'at most', 'more than', 'fewer than', 'less than']
    if any(indicator in text_lower for indicator in cardinality_indicators):
        return 'cardinality'

    # Check for coverage/ownership indicators
    coverage_indicators = ['have an owner', 'have a owner', 'covered by', 'belong to a group on', 'belong to an group on']
    if any(indicator in text_lower for indicator in coverage_indicators):
        return 'coverage'

    # Check for correspondence/alignment indicators
    correspondence_indicators = ['correspond', 'aligns with', 'align with', 'matches with', 'match with']
    if any(indicator in text_lower for indicator in correspondence_indicators):
        return 'correspondence'

    # Check for refinement indicators
    refinement_indicators = ['refine', 'refinement of', 'nests within', 'nest within']
    if any(indicator in text_lower for indicator in refinement_indicators):
        return 'refinement'

    # Check for exclusion (must/should not depend on)
    if 'not depend on' in text_lower or 'not depend' in text_lower:
        return 'exclusion'

    # Check for containment (must/should be in, must/should contain)
    containment_indicators = ['be in', 'be contained', 'must contain', 'should contain']
    if any(indicator in text_lower for indicator in containment_indicators):
        return 'containment'

    # Check for existence (must/should exist, there must/should be)
    if 'exist' in text_lower:
        return 'existence'
    if ('there must be' in text_lower or 'there should be' in text_lower) and not any(c in text_lower for c in cardinality_indicators):
        return 'existence'

    return None


def validate_references(text: str) -> list[str]:
    """
    Extract all reference IDs from a statement text.

    Args:
        text: The statement text with $$$ref-id$$$ tokens.

    Returns:
        List of reference IDs found in the text.

    Example:
        >>> validate_references("$$$api$$$ must not depend on $$$db$$$")
        ['api', 'db']
    """
    pattern = r'\$\$\$([a-zA-Z0-9_-]+)\$\$\$'
    return re.findall(pattern, text)


def format_statement_template(statement_type: str) -> str:
    """
    Get a template for a given statement type.

    Args:
        statement_type: One of 'existence', 'containment', 'exclusion', 'cardinality', 'coverage'.

    Returns:
        A template string showing the expected format.
    """
    templates = {
        'existence': 'there must be $$$reference$$$',
        'containment': '$$$subject$$$ must be in $$$container$$$',
        'exclusion': '$$$subject$$$ must not depend on $$$excluded$$$',
        'cardinality': 'there must be exactly N $$$reference$$$',
        'coverage': 'all $$$subject$$$ must have an owner on $$$layer$$$',
        'correspondence': '$$$layer-a$$$ corresponds with $$$layer-b$$$',
        'refinement': '$$$fine-layer$$$ refines $$$coarse-layer$$$',
    }
    return templates.get(statement_type, '')


def get_all_templates() -> dict[str, list[str]]:
    """
    Get all supported statement templates organized by type.

    Returns:
        Dictionary mapping statement types to lists of template variations.
    """
    return {
        'existence': [
            'there must/should be $$$reference$$$',
            '$$$reference$$$ must/should exist',
        ],
        'containment': [
            '$$$subject$$$ must/should be in $$$container$$$',
            'every/all $$$subject$$$ must/should be in $$$container$$$',
            '$$$subject$$$ must/should be contained in $$$container$$$',
            '$$$container$$$ must/should contain $$$subject$$$',
        ],
        'exclusion': [
            '$$$subject$$$ must/should not depend on $$$excluded$$$',
            'every/all $$$subject$$$ must/should not depend on $$$excluded$$$',
        ],
        'cardinality': [
            'there must/should be exactly N $$$reference$$$',
            'there must/should be at least N $$$reference$$$',
            'there must/should be at most N $$$reference$$$',
            'there must/should be more than N $$$reference$$$',
            'there must/should be fewer than N $$$reference$$$',
        ],
        'coverage': [
            'all components must/should have an owner on $$$layer$$$',
            'every component in the system must/should have an owner on $$$layer$$$',
            'all $$$subject$$$ must/should have an owner on $$$layer$$$',
            'every $$$subject$$$ must/should have an owner on $$$layer$$$',
            'all components must/should be covered by $$$layer$$$',
            'every component in the system must/should be covered by $$$layer$$$',
            '$$$subject$$$ must/should be covered by $$$layer$$$',
            'all components must/should belong to a group on $$$layer$$$',
            'every component in the system must/should belong to a group on $$$layer$$$',
            'all $$$subject$$$ must/should belong to a group on $$$layer$$$',
        ],
        'correspondence': [
            '$$$layer-a$$$ must/should correspond with $$$layer-b$$$',
            '$$$layer-a$$$ must/should align with $$$layer-b$$$',
            '$$$layer-a$$$ must/should match with $$$layer-b$$$',
            '$$$layer-a$$$ corresponds with $$$layer-b$$$',
            '$$$layer-a$$$ aligns with $$$layer-b$$$',
        ],
        'refinement': [
            '$$$fine-layer$$$ refines $$$coarse-layer$$$',
            '$$$fine-layer$$$ must/should refine $$$coarse-layer$$$',
            '$$$fine-layer$$$ must/should be a refinement of $$$coarse-layer$$$',
            '$$$fine-layer$$$ must/should nest within $$$coarse-layer$$$',
            '$$$fine-layer$$$ nests within $$$coarse-layer$$$',
        ],
    }


def suggest_syntax(text: str) -> dict:
    """
    Suggest syntax corrections or completions for a statement.

    Compares the input against all supported templates to find the best match
    and suggest what to add or fix.

    Args:
        text: The natural language statement (may be incomplete).

    Returns:
        A dictionary with:
        - best_match: dict with 'template', 'type', 'similarity' score
        - suggestions: list of specific suggestions
        - next_token: what the user should type next (if determinable)
        - alternatives: list of other possible templates with scores

    Example:
        >>> suggest_syntax("$$$api$$$ must be")
        {
            'best_match': {
                'template': '$$$subject$$$ must/should be in $$$container$$$',
                'type': 'containment',
                'similarity': 0.65
            },
            'suggestions': ['Add "in $$$container$$$" to complete containment statement'],
            'next_token': 'in',
            'alternatives': [...]
        }
    """
    text_lower = text.lower().strip()
    text_normalized = ' '.join(text_lower.split())

    # Get all templates
    all_templates = get_all_templates()

    # Flatten templates with their types
    template_list = []
    for stmt_type, templates in all_templates.items():
        for template in templates:
            template_list.append({
                'template': template,
                'type': stmt_type,
                'normalized': _normalize_template(template)
            })

    # Calculate similarity scores
    scored_templates = []
    for t in template_list:
        score = _calculate_similarity(text_normalized, t['normalized'])
        scored_templates.append({
            'template': t['template'],
            'type': t['type'],
            'similarity': score,
            'normalized': t['normalized']
        })

    # Sort by similarity (descending)
    scored_templates.sort(key=lambda x: x['similarity'], reverse=True)

    best = scored_templates[0] if scored_templates else None
    alternatives = scored_templates[1:4] if len(scored_templates) > 1 else []

    # Generate suggestions based on best match
    suggestions = []
    next_token = None

    if best:
        suggestions, next_token = _generate_suggestions(text_normalized, best)

    return {
        'best_match': {
            'template': best['template'] if best else None,
            'type': best['type'] if best else None,
            'similarity': best['similarity'] if best else 0,
        },
        'suggestions': suggestions,
        'next_token': next_token,
        'alternatives': [
            {'template': a['template'], 'type': a['type'], 'similarity': a['similarity']}
            for a in alternatives
        ]
    }


def _normalize_template(template: str) -> str:
    """Normalize a template for comparison."""
    # Replace $$$...$$$  with a placeholder token
    normalized = re.sub(r'\$\$\$[^$]+\$\$\$', '<REF>', template.lower())
    # Replace N with number placeholder
    normalized = re.sub(r'\bN\b', '<NUM>', normalized)
    # Replace must/should with single token
    normalized = normalized.replace('must/should', 'MODAL')
    return normalized


def _normalize_input(text: str) -> str:
    """Normalize user input for comparison."""
    # Replace $$$...$$$  with a placeholder token
    normalized = re.sub(r'\$\$\$[^$]+\$\$\$', '<REF>', text.lower())
    # Replace numbers with placeholder
    normalized = re.sub(r'\b\d+\b', '<NUM>', normalized)
    # Normalize must/should to single token
    normalized = re.sub(r'\b(must|should)\b', 'MODAL', normalized)
    return normalized


def _calculate_similarity(text: str, template_normalized: str) -> float:
    """
    Calculate similarity between input text and a normalized template.

    Uses a combination of:
    - Sequence matching (overall structure similarity)
    - Token overlap (keyword presence)
    - Position-aware matching (tokens in correct order)
    """
    text_normalized = _normalize_input(text)

    # Sequence matcher similarity
    seq_ratio = SequenceMatcher(None, text_normalized, template_normalized).ratio()

    # Token-based similarity
    text_tokens = set(text_normalized.split())
    template_tokens = set(template_normalized.split())

    if not template_tokens:
        return 0.0

    # Jaccard similarity for tokens
    intersection = text_tokens & template_tokens
    union = text_tokens | template_tokens
    token_ratio = len(intersection) / len(union) if union else 0

    # Order-aware token matching
    text_token_list = text_normalized.split()
    template_token_list = template_normalized.split()
    order_score = _calculate_order_score(text_token_list, template_token_list)

    # Weighted combination
    return (0.4 * seq_ratio) + (0.3 * token_ratio) + (0.3 * order_score)


def _calculate_order_score(text_tokens: list, template_tokens: list) -> float:
    """Calculate how well tokens appear in the correct order."""
    if not text_tokens or not template_tokens:
        return 0.0

    # Find matching tokens and check their relative order
    matches = 0
    last_pos = -1

    for text_token in text_tokens:
        for i, template_token in enumerate(template_tokens):
            if text_token == template_token and i > last_pos:
                matches += 1
                last_pos = i
                break

    return matches / len(template_tokens)


def _generate_suggestions(text: str, best_match: dict) -> tuple[list, str]:
    """Generate specific suggestions based on the best matching template."""
    suggestions = []
    next_token = None

    template_normalized = best_match['normalized']
    text_normalized = _normalize_input(text)

    text_tokens = text_normalized.split()
    template_tokens = template_normalized.split()

    # Find where user is in the template
    matched_until = 0
    for i, template_token in enumerate(template_tokens):
        if i < len(text_tokens):
            if text_tokens[i] == template_token or \
               (template_token == '<REF>' and text_tokens[i] == '<REF>') or \
               (template_token == '<NUM>' and text_tokens[i] == '<NUM>'):
                matched_until = i + 1
            else:
                # Mismatch - might be a word that should be different
                if template_token not in ('<REF>', '<NUM>', 'MODAL'):
                    suggestions.append(f'Expected "{template_token}" but found "{text_tokens[i]}"')
                break
        else:
            break

    # Suggest remaining tokens
    if matched_until < len(template_tokens):
        remaining = template_tokens[matched_until:]
        next_token_raw = remaining[0] if remaining else None

        # Translate placeholder back to human-readable
        if next_token_raw == '<REF>':
            next_token = '$$$reference$$$'
            suggestions.append('Add a reference (e.g., $$$service-name$$$)')
        elif next_token_raw == '<NUM>':
            next_token = 'N'
            suggestions.append('Add a number')
        elif next_token_raw == 'MODAL':
            next_token = 'must/should'
            suggestions.append('Add "must" or "should"')
        else:
            next_token = next_token_raw
            # Build readable remaining part
            remaining_readable = []
            for t in remaining:
                if t == '<REF>':
                    remaining_readable.append('$$$reference$$$')
                elif t == '<NUM>':
                    remaining_readable.append('N')
                elif t == 'MODAL':
                    remaining_readable.append('must/should')
                else:
                    remaining_readable.append(t)
            suggestions.append(f'Continue with: {" ".join(remaining_readable)}')

    # Check if statement is complete
    if matched_until >= len(template_tokens) and len(text_tokens) >= len(template_tokens):
        suggestions.append('Statement appears complete!')

    return suggestions, next_token


def analyze_statement(text: str) -> dict:
    """
    Analyze a statement to determine its type and formalization status.

    This function is intended to be called when saving a statement to
    automatically infer:
    - statement_type: The type of statement (existence, containment, etc.)
    - status: The formalization status (informal, semi_formal, formal)
    - formal_expression: The parsed formal expression (if parseable)

    Args:
        text: The natural language statement with references as $$$ref-id$$$ tokens.

    Returns:
        A dictionary with:
        - statement_type: str or None - The detected statement type
        - status: str - One of 'informal', 'semi_formal', 'formal'
        - formal_expression: dict or None - The parsed expression if formal
        - references: list[str] - List of reference IDs found
        - error: str or None - Parse error message if semi-formal

    Examples:
        >>> analyze_statement("there must be $$$payment-api$$$")
        {
            'statement_type': 'existence',
            'status': 'formal',
            'formal_expression': {'type': 'existence', 'reference': 'payment-api'},
            'references': ['payment-api'],
            'error': None
        }

        >>> analyze_statement("payment services should exist")
        {
            'statement_type': None,
            'status': 'informal',
            'formal_expression': None,
            'references': [],
            'error': None
        }

        >>> analyze_statement("$$$api$$$ must be in somewhere")
        {
            'statement_type': 'containment',
            'status': 'semi_formal',
            'formal_expression': None,
            'references': ['api'],
            'error': "Could not parse statement: ..."
        }
    """
    result = {
        'statement_type': None,
        'status': 'informal',
        'formal_expression': None,
        'references': validate_references(text),
        'error': None,
    }

    # Detect statement type from text patterns
    detected_type = detect_statement_type(text)
    result['statement_type'] = detected_type

    # If no references found and no type detected, it's informal
    if not result['references'] and not detected_type:
        return result

    # If has references but no detectable type, it's semi-formal
    if result['references'] and not detected_type:
        result['status'] = 'semi_formal'
        return result

    # Try to parse the statement
    try:
        parsed = parse_statement(text)
        result['formal_expression'] = parsed
        result['statement_type'] = parsed.get('type')
        result['status'] = 'formal'
    except StatementParseError as e:
        # Has structure but doesn't fully parse - semi-formal
        result['status'] = 'semi_formal'
        result['error'] = str(e)

    return result
