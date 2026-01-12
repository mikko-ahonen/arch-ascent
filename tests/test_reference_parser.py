"""
Tests for the reference definition parser.
"""
import pytest
from dependencies.services.reference_parser import (
    parse_reference_definition,
    detect_definition_type,
    get_definition_templates,
    format_tag_expression,
    analyze_reference_definition,
    ReferenceParseError,
)


class TestTagExpressions:
    """Test parsing of tag-based reference definitions."""

    def test_single_tag_quoted(self):
        result = parse_reference_definition("components tagged with 'payment'")
        assert result == {
            'type': 'tag_expression',
            'expression': {'tag': 'payment'}
        }

    def test_single_tag_double_quoted(self):
        result = parse_reference_definition('components tagged with "payment"')
        assert result == {
            'type': 'tag_expression',
            'expression': {'tag': 'payment'}
        }

    def test_single_tag_unquoted(self):
        result = parse_reference_definition("components tagged with payment")
        assert result == {
            'type': 'tag_expression',
            'expression': {'tag': 'payment'}
        }

    def test_tag_with_hyphen(self):
        result = parse_reference_definition("components tagged with 'payment-api'")
        assert result == {
            'type': 'tag_expression',
            'expression': {'tag': 'payment-api'}
        }

    def test_tag_with_underscore(self):
        result = parse_reference_definition("components tagged with 'payment_service'")
        assert result == {
            'type': 'tag_expression',
            'expression': {'tag': 'payment_service'}
        }

    def test_two_tags_and(self):
        result = parse_reference_definition("components tagged with 'api' and 'payment'")
        assert result == {
            'type': 'tag_expression',
            'expression': {'and': ['api', 'payment']}
        }

    def test_three_tags_and(self):
        result = parse_reference_definition("components tagged with 'api' and 'payment' and 'v2'")
        assert result == {
            'type': 'tag_expression',
            'expression': {'and': ['api', 'payment', 'v2']}
        }

    def test_two_tags_or(self):
        result = parse_reference_definition("components tagged with 'api' or 'payment'")
        assert result == {
            'type': 'tag_expression',
            'expression': {'or': ['api', 'payment']}
        }

    def test_three_tags_or(self):
        result = parse_reference_definition("components tagged with 'frontend' or 'backend' or 'shared'")
        assert result == {
            'type': 'tag_expression',
            'expression': {'or': ['frontend', 'backend', 'shared']}
        }

    def test_not_tagged_with(self):
        """NOT is now part of the expression: 'components tagged with not deprecated'"""
        result = parse_reference_definition("components tagged with not 'deprecated'")
        assert result == {
            'type': 'tag_expression',
            'expression': {'not': {'tag': 'deprecated'}}
        }

    def test_not_tagged_unquoted(self):
        result = parse_reference_definition("components tagged with not legacy")
        assert result == {
            'type': 'tag_expression',
            'expression': {'not': {'tag': 'legacy'}}
        }

    def test_case_insensitive_keywords(self):
        result = parse_reference_definition("Components Tagged With 'payment'")
        assert result == {
            'type': 'tag_expression',
            'expression': {'tag': 'payment'}
        }

    def test_case_insensitive_and(self):
        result = parse_reference_definition("components tagged with 'api' AND 'payment'")
        assert result == {
            'type': 'tag_expression',
            'expression': {'and': ['api', 'payment']}
        }


class TestComplexBooleanExpressions:
    """Test parsing of complex boolean expressions with parentheses."""

    def test_parentheses_simple(self):
        """Parentheses around a single tag."""
        result = parse_reference_definition("components tagged with ('payment')")
        assert result == {
            'type': 'tag_expression',
            'expression': {'tag': 'payment'}
        }

    def test_parentheses_and(self):
        """Parentheses around AND expression."""
        result = parse_reference_definition("components tagged with ('api' and 'payment')")
        assert result == {
            'type': 'tag_expression',
            'expression': {'and': ['api', 'payment']}
        }

    def test_or_with_parenthesized_and(self):
        """OR with parenthesized AND: 'legacy' or ('api' and 'payment')"""
        result = parse_reference_definition("components tagged with 'legacy' or ('api' and 'payment')")
        assert result['type'] == 'tag_expression'
        expr = result['expression']
        assert 'or' in expr
        # Should be: {'or': ['legacy', {'and': ['api', 'payment']}]}
        assert 'legacy' in expr['or']

    def test_and_with_parenthesized_or(self):
        """AND with parenthesized OR: 'api' and ('payment' or 'billing')"""
        result = parse_reference_definition("components tagged with 'api' and ('payment' or 'billing')")
        assert result['type'] == 'tag_expression'
        expr = result['expression']
        assert 'and' in expr
        # Should have 'api' and an OR expression

    def test_not_with_tag(self):
        """NOT operator: not 'deprecated'"""
        result = parse_reference_definition("components tagged with not 'deprecated'")
        assert result == {
            'type': 'tag_expression',
            'expression': {'not': {'tag': 'deprecated'}}
        }

    def test_not_with_parentheses(self):
        """NOT with parentheses: not ('api' and 'legacy')"""
        result = parse_reference_definition("components tagged with not ('api' and 'legacy')")
        assert result['type'] == 'tag_expression'
        expr = result['expression']
        assert 'not' in expr

    def test_and_not(self):
        """AND with NOT: 'api' and not 'deprecated'"""
        result = parse_reference_definition("components tagged with 'api' and not 'deprecated'")
        assert result['type'] == 'tag_expression'
        expr = result['expression']
        assert 'and' in expr

    def test_complex_nested(self):
        """Complex nested expression: ('api' or 'service') and not 'deprecated'"""
        result = parse_reference_definition("components tagged with ('api' or 'service') and not 'deprecated'")
        assert result['type'] == 'tag_expression'
        expr = result['expression']
        assert 'and' in expr

    def test_operator_precedence_and_before_or(self):
        """AND has higher precedence than OR: 'a' or 'b' and 'c' = 'a' or ('b' and 'c')"""
        result = parse_reference_definition("components tagged with 'a' or 'b' and 'c'")
        assert result['type'] == 'tag_expression'
        expr = result['expression']
        # Should be: {'or': ['a', {'and': ['b', 'c']}]}
        assert 'or' in expr

    def test_multiple_parentheses(self):
        """Multiple parenthesized groups."""
        result = parse_reference_definition("components tagged with ('api' and 'v2') or ('legacy' and 'deprecated')")
        assert result['type'] == 'tag_expression'
        expr = result['expression']
        assert 'or' in expr


class TestLayerDefinitions:
    """Test parsing of layer-based reference definitions."""

    def test_groups_on_layer(self):
        result = parse_reference_definition("groups on $$$team-ownership$$$")
        assert result == {
            'type': 'layer',
            'layer': 'team-ownership'
        }

    def test_components_on_layer(self):
        result = parse_reference_definition("components on $$$domain-layer$$$")
        assert result == {
            'type': 'layer',
            'layer': 'domain-layer'
        }

    def test_groups_on_layer_explicit(self):
        result = parse_reference_definition("groups on layer $$$team-ownership$$$")
        assert result == {
            'type': 'layer',
            'layer': 'team-ownership'
        }

    def test_components_in_layer(self):
        result = parse_reference_definition("components in $$$infrastructure$$$")
        assert result == {
            'type': 'layer',
            'layer': 'infrastructure'
        }

    def test_case_insensitive_layer(self):
        result = parse_reference_definition("Groups On $$$Team-Layer$$$")
        assert result == {
            'type': 'layer',
            'layer': 'Team-Layer'
        }


class TestExplicitListDefinitions:
    """Test parsing of explicit list reference definitions."""

    def test_simple_list(self):
        result = parse_reference_definition("components: service-a, service-b, service-c")
        assert result == {
            'type': 'explicit_list',
            'members': ['service-a', 'service-b', 'service-c']
        }

    def test_single_member(self):
        result = parse_reference_definition("components: my-service")
        assert result == {
            'type': 'explicit_list',
            'members': ['my-service']
        }

    def test_list_with_colons_in_keys(self):
        result = parse_reference_definition("components: org:service-a, org:service-b")
        assert result == {
            'type': 'explicit_list',
            'members': ['org:service-a', 'org:service-b']
        }

    def test_list_with_underscores(self):
        result = parse_reference_definition("components: service_a, service_b")
        assert result == {
            'type': 'explicit_list',
            'members': ['service_a', 'service_b']
        }


class TestParseErrors:
    """Test error handling."""

    def test_invalid_definition(self):
        with pytest.raises(ReferenceParseError):
            parse_reference_definition("random text here")

    def test_incomplete_tagged_with(self):
        with pytest.raises(ReferenceParseError):
            parse_reference_definition("components tagged with")

    def test_missing_layer_reference(self):
        with pytest.raises(ReferenceParseError):
            parse_reference_definition("groups on layer")


class TestDetectDefinitionType:
    """Test definition type detection."""

    def test_detect_tag_expression(self):
        assert detect_definition_type("components tagged with 'api'") == 'tag_expression'

    def test_detect_layer_on(self):
        assert detect_definition_type("groups on $$$layer$$$") == 'layer'

    def test_detect_layer_in(self):
        assert detect_definition_type("components in $$$layer$$$") == 'layer'

    def test_detect_explicit_list(self):
        assert detect_definition_type("components: a, b, c") == 'explicit_list'

    def test_detect_unknown(self):
        assert detect_definition_type("something else") is None


class TestGetTemplates:
    """Test template retrieval."""

    def test_all_types_present(self):
        templates = get_definition_templates()
        assert 'tag_expression' in templates
        assert 'layer' in templates
        assert 'explicit_list' in templates

    def test_tag_expression_templates(self):
        templates = get_definition_templates()
        assert len(templates['tag_expression']) >= 3


class TestFormatTagExpression:
    """Test formatting tag expressions back to natural language."""

    def test_format_single_tag(self):
        result = format_tag_expression({'tag': 'payment'})
        assert result == "components tagged with 'payment'"

    def test_format_and_expression(self):
        result = format_tag_expression({'and': ['api', 'payment']})
        assert result == "components tagged with 'api' and 'payment'"

    def test_format_or_expression(self):
        result = format_tag_expression({'or': ['frontend', 'backend']})
        assert result == "components tagged with 'frontend' or 'backend'"

    def test_format_not_expression(self):
        result = format_tag_expression({'not': 'deprecated'})
        assert result == "components not tagged with 'deprecated'"


class TestAnalyzeReferenceDefinition:
    """Test the analyze function."""

    def test_analyze_valid_tag_expression(self):
        result = analyze_reference_definition("components tagged with 'payment'")
        assert result['definition_type'] == 'tag_expression'
        assert result['parsed'] is not None
        assert result['error'] is None

    def test_analyze_valid_layer(self):
        result = analyze_reference_definition("groups on $$$team-layer$$$")
        assert result['definition_type'] == 'layer'
        assert result['parsed'] is not None
        assert result['error'] is None

    def test_analyze_invalid(self):
        result = analyze_reference_definition("invalid definition here")
        assert result['parsed'] is None
        assert result['error'] is not None


class TestWhitespaceHandling:
    """Test handling of various whitespace scenarios."""

    def test_extra_spaces(self):
        result = parse_reference_definition("components   tagged   with   'payment'")
        assert result == {
            'type': 'tag_expression',
            'expression': {'tag': 'payment'}
        }

    def test_leading_trailing_whitespace(self):
        result = parse_reference_definition("  components tagged with 'api'  ")
        assert result == {
            'type': 'tag_expression',
            'expression': {'tag': 'api'}
        }

    def test_spaces_in_list(self):
        result = parse_reference_definition("components: a,  b,   c")
        assert result == {
            'type': 'explicit_list',
            'members': ['a', 'b', 'c']
        }
