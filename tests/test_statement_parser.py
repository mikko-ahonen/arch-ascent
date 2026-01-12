"""Tests for the statement parser."""

import pytest
from dependencies.services.statement_parser import (
    parse_statement,
    detect_statement_type,
    validate_references,
    format_statement_template,
    get_all_templates,
    analyze_statement,
    suggest_syntax,
    StatementParseError,
)


class TestExistenceStatements:
    """Test parsing of existence statements."""

    def test_there_must_be(self):
        result = parse_statement("there must be $$$payment-services$$$")
        assert result == {'type': 'existence', 'reference': 'payment-services'}

    def test_there_should_be(self):
        result = parse_statement("there should be $$$payment-services$$$")
        assert result == {'type': 'existence', 'reference': 'payment-services'}

    def test_must_exist(self):
        result = parse_statement("$$$api-gateway$$$ must exist")
        assert result == {'type': 'existence', 'reference': 'api-gateway'}

    def test_should_exist(self):
        result = parse_statement("$$$api-gateway$$$ should exist")
        assert result == {'type': 'existence', 'reference': 'api-gateway'}

    def test_case_insensitive(self):
        result = parse_statement("There Must Be $$$MyService$$$")
        assert result == {'type': 'existence', 'reference': 'MyService'}

    def test_with_underscores(self):
        result = parse_statement("there must be $$$payment_service$$$")
        assert result == {'type': 'existence', 'reference': 'payment_service'}

    def test_with_numbers(self):
        result = parse_statement("there must be $$$service123$$$")
        assert result == {'type': 'existence', 'reference': 'service123'}


class TestContainmentStatements:
    """Test parsing of containment statements."""

    def test_must_be_in(self):
        result = parse_statement("$$$payment-api$$$ must be in $$$domain-layer$$$")
        assert result == {
            'type': 'containment',
            'subject': 'payment-api',
            'container': 'domain-layer'
        }

    def test_should_be_in(self):
        result = parse_statement("$$$payment-api$$$ should be in $$$domain-layer$$$")
        assert result == {
            'type': 'containment',
            'subject': 'payment-api',
            'container': 'domain-layer'
        }

    def test_must_be_contained_in(self):
        result = parse_statement("$$$payment-api$$$ must be contained in $$$domain-layer$$$")
        assert result == {
            'type': 'containment',
            'subject': 'payment-api',
            'container': 'domain-layer'
        }

    def test_must_contain(self):
        result = parse_statement("$$$domain-layer$$$ must contain $$$payment-api$$$")
        assert result == {
            'type': 'containment',
            'subject': 'payment-api',
            'container': 'domain-layer'
        }

    def test_should_contain(self):
        result = parse_statement("$$$domain-layer$$$ should contain $$$payment-api$$$")
        assert result == {
            'type': 'containment',
            'subject': 'payment-api',
            'container': 'domain-layer'
        }

    def test_containment_symmetric(self):
        """Both forms should produce the same result."""
        result1 = parse_statement("$$$api$$$ must be in $$$layer$$$")
        result2 = parse_statement("$$$layer$$$ must contain $$$api$$$")
        assert result1 == result2

    def test_every_prefix_be_in(self):
        """Test optional 'every' prefix for readability."""
        result = parse_statement("every $$$payment-api$$$ must be in $$$domain-layer$$$")
        assert result == {
            'type': 'containment',
            'subject': 'payment-api',
            'container': 'domain-layer'
        }

    def test_all_prefix_be_in(self):
        """Test optional 'all' prefix for readability."""
        result = parse_statement("all $$$services$$$ must be in $$$domain$$$")
        assert result == {
            'type': 'containment',
            'subject': 'services',
            'container': 'domain'
        }

    def test_every_prefix_must_contain(self):
        result = parse_statement("every $$$layer$$$ must contain $$$api$$$")
        assert result == {
            'type': 'containment',
            'subject': 'api',
            'container': 'layer'
        }


class TestExclusionStatements:
    """Test parsing of exclusion statements."""

    def test_must_not_depend_on(self):
        result = parse_statement("$$$ui-layer$$$ must not depend on $$$database$$$")
        assert result == {
            'type': 'exclusion',
            'subject': 'ui-layer',
            'excluded': 'database'
        }

    def test_should_not_depend_on(self):
        result = parse_statement("$$$ui-layer$$$ should not depend on $$$database$$$")
        assert result == {
            'type': 'exclusion',
            'subject': 'ui-layer',
            'excluded': 'database'
        }

    def test_case_insensitive(self):
        result = parse_statement("$$$UI$$$ Must Not Depend On $$$DB$$$")
        assert result == {
            'type': 'exclusion',
            'subject': 'UI',
            'excluded': 'DB'
        }

    def test_every_prefix(self):
        """Test optional 'every' prefix for readability."""
        result = parse_statement("every $$$ui-layer$$$ must not depend on $$$database$$$")
        assert result == {
            'type': 'exclusion',
            'subject': 'ui-layer',
            'excluded': 'database'
        }

    def test_all_prefix(self):
        """Test optional 'all' prefix for readability."""
        result = parse_statement("all $$$frontend$$$ should not depend on $$$db$$$")
        assert result == {
            'type': 'exclusion',
            'subject': 'frontend',
            'excluded': 'db'
        }


class TestCardinalityStatements:
    """Test parsing of cardinality statements."""

    def test_exactly(self):
        result = parse_statement("there must be exactly 1 $$$api-gateway$$$")
        assert result == {
            'type': 'cardinality',
            'operator': '==',
            'value': 1,
            'reference': 'api-gateway'
        }

    def test_should_exactly(self):
        result = parse_statement("there should be exactly 1 $$$api-gateway$$$")
        assert result == {
            'type': 'cardinality',
            'operator': '==',
            'value': 1,
            'reference': 'api-gateway'
        }

    def test_at_least(self):
        result = parse_statement("there must be at least 2 $$$payment-handlers$$$")
        assert result == {
            'type': 'cardinality',
            'operator': '>=',
            'value': 2,
            'reference': 'payment-handlers'
        }

    def test_should_at_least(self):
        result = parse_statement("there should be at least 2 $$$payment-handlers$$$")
        assert result == {
            'type': 'cardinality',
            'operator': '>=',
            'value': 2,
            'reference': 'payment-handlers'
        }

    def test_at_most(self):
        result = parse_statement("there must be at most 3 $$$replicas$$$")
        assert result == {
            'type': 'cardinality',
            'operator': '<=',
            'value': 3,
            'reference': 'replicas'
        }

    def test_more_than(self):
        result = parse_statement("there must be more than 0 $$$validators$$$")
        assert result == {
            'type': 'cardinality',
            'operator': '>',
            'value': 0,
            'reference': 'validators'
        }

    def test_fewer_than(self):
        result = parse_statement("there must be fewer than 10 $$$connections$$$")
        assert result == {
            'type': 'cardinality',
            'operator': '<',
            'value': 10,
            'reference': 'connections'
        }

    def test_less_than(self):
        result = parse_statement("there must be less than 5 $$$instances$$$")
        assert result == {
            'type': 'cardinality',
            'operator': '<',
            'value': 5,
            'reference': 'instances'
        }


class TestParseErrors:
    """Test error handling."""

    def test_invalid_statement(self):
        with pytest.raises(StatementParseError):
            parse_statement("this is not a valid statement")

    def test_missing_reference(self):
        with pytest.raises(StatementParseError):
            parse_statement("there must be")

    def test_malformed_reference(self):
        with pytest.raises(StatementParseError):
            parse_statement("there must be $$invalid$$")

    def test_incomplete_containment(self):
        with pytest.raises(StatementParseError):
            parse_statement("$$$api$$$ must be in")


class TestDetectStatementType:
    """Test statement type detection."""

    def test_detect_existence_there(self):
        assert detect_statement_type("there must be something") == 'existence'

    def test_detect_existence_exist(self):
        assert detect_statement_type("something must exist") == 'existence'

    def test_detect_containment_in(self):
        assert detect_statement_type("X must be in Y") == 'containment'

    def test_detect_containment_contain(self):
        assert detect_statement_type("X must contain Y") == 'containment'

    def test_detect_exclusion(self):
        assert detect_statement_type("X must not depend on Y") == 'exclusion'

    def test_detect_cardinality_exactly(self):
        assert detect_statement_type("there must be exactly 1") == 'cardinality'

    def test_detect_cardinality_at_least(self):
        assert detect_statement_type("there must be at least 2") == 'cardinality'

    def test_detect_unknown(self):
        assert detect_statement_type("random text") is None


class TestValidateReferences:
    """Test reference extraction."""

    def test_single_reference(self):
        refs = validate_references("there must be $$$api$$$")
        assert refs == ['api']

    def test_multiple_references(self):
        refs = validate_references("$$$api$$$ must not depend on $$$db$$$")
        assert refs == ['api', 'db']

    def test_no_references(self):
        refs = validate_references("there must be something")
        assert refs == []

    def test_reference_with_special_chars(self):
        refs = validate_references("$$$my-service_123$$$")
        assert refs == ['my-service_123']


class TestTemplates:
    """Test template functions."""

    def test_format_existence_template(self):
        template = format_statement_template('existence')
        assert '$$$reference$$$' in template

    def test_format_containment_template(self):
        template = format_statement_template('containment')
        assert '$$$subject$$$' in template
        assert '$$$container$$$' in template

    def test_format_exclusion_template(self):
        template = format_statement_template('exclusion')
        assert 'must not depend on' in template

    def test_format_cardinality_template(self):
        template = format_statement_template('cardinality')
        assert 'exactly' in template

    def test_format_unknown_type(self):
        template = format_statement_template('unknown')
        assert template == ''

    def test_get_all_templates(self):
        templates = get_all_templates()
        assert 'existence' in templates
        assert 'containment' in templates
        assert 'exclusion' in templates
        assert 'cardinality' in templates
        assert len(templates['existence']) >= 2
        assert len(templates['containment']) >= 3
        assert len(templates['cardinality']) >= 5


class TestWhitespaceHandling:
    """Test handling of various whitespace scenarios."""

    def test_extra_spaces(self):
        result = parse_statement("there   must   be   $$$api$$$")
        assert result == {'type': 'existence', 'reference': 'api'}

    def test_leading_trailing_whitespace(self):
        result = parse_statement("   there must be $$$api$$$   ")
        assert result == {'type': 'existence', 'reference': 'api'}

    def test_newlines_and_tabs(self):
        result = parse_statement("there\tmust\nbe $$$api$$$")
        assert result == {'type': 'existence', 'reference': 'api'}


class TestAnalyzeStatement:
    """Test the analyze_statement function for auto-inference."""

    def test_formal_existence(self):
        result = analyze_statement("there must be $$$payment-api$$$")
        assert result['statement_type'] == 'existence'
        assert result['status'] == 'formal'
        assert result['formal_expression'] == {
            'type': 'existence',
            'reference': 'payment-api'
        }
        assert result['references'] == ['payment-api']
        assert result['error'] is None

    def test_formal_containment(self):
        result = analyze_statement("$$$api$$$ must be in $$$layer$$$")
        assert result['statement_type'] == 'containment'
        assert result['status'] == 'formal'
        assert result['formal_expression']['type'] == 'containment'
        assert result['references'] == ['api', 'layer']

    def test_formal_exclusion(self):
        result = analyze_statement("$$$ui$$$ must not depend on $$$db$$$")
        assert result['statement_type'] == 'exclusion'
        assert result['status'] == 'formal'
        assert result['formal_expression']['type'] == 'exclusion'

    def test_formal_cardinality(self):
        result = analyze_statement("there must be exactly 1 $$$gateway$$$")
        assert result['statement_type'] == 'cardinality'
        assert result['status'] == 'formal'
        assert result['formal_expression']['operator'] == '=='
        assert result['formal_expression']['value'] == 1

    def test_informal_no_references(self):
        result = analyze_statement("payment services are important")
        assert result['statement_type'] is None
        assert result['status'] == 'informal'
        assert result['formal_expression'] is None
        assert result['references'] == []
        assert result['error'] is None

    def test_informal_plain_text(self):
        result = analyze_statement("The API layer handles all requests")
        assert result['status'] == 'informal'
        assert result['statement_type'] is None

    def test_semi_formal_has_refs_but_no_structure(self):
        result = analyze_statement("$$$api$$$ is important")
        assert result['status'] == 'semi_formal'
        assert result['references'] == ['api']
        assert result['formal_expression'] is None

    def test_semi_formal_incomplete_containment(self):
        result = analyze_statement("$$$api$$$ must be in somewhere")
        assert result['statement_type'] == 'containment'
        assert result['status'] == 'semi_formal'
        assert result['formal_expression'] is None
        assert result['error'] is not None
        assert 'Could not parse' in result['error']

    def test_semi_formal_missing_second_ref(self):
        result = analyze_statement("$$$api$$$ must not depend on the database")
        assert result['statement_type'] == 'exclusion'
        assert result['status'] == 'semi_formal'
        assert result['references'] == ['api']


class TestSuggestSyntax:
    """Test syntax suggestion functionality."""

    def test_partial_existence_there_must(self):
        result = suggest_syntax("there must")
        assert result['best_match']['type'] in ('existence', 'cardinality')
        assert result['next_token'] == 'be'
        assert len(result['suggestions']) > 0

    def test_partial_existence_there_must_be(self):
        result = suggest_syntax("there must be")
        # Could match existence or cardinality
        assert result['best_match']['type'] in ('existence', 'cardinality')
        assert len(result['suggestions']) > 0

    def test_partial_containment(self):
        result = suggest_syntax("$$$api$$$ must be")
        assert result['best_match']['type'] == 'containment'
        assert 'in' in result['next_token'] or result['next_token'] == 'in'

    def test_partial_exclusion(self):
        result = suggest_syntax("$$$ui$$$ must not depend")
        assert result['best_match']['type'] == 'exclusion'
        assert result['next_token'] == 'on'

    def test_complete_existence(self):
        result = suggest_syntax("there must be $$$api$$$")
        assert result['best_match']['type'] == 'existence'
        assert result['best_match']['similarity'] > 0.8
        assert any('complete' in s.lower() for s in result['suggestions'])

    def test_complete_containment(self):
        result = suggest_syntax("$$$api$$$ must be in $$$layer$$$")
        assert result['best_match']['type'] == 'containment'
        assert result['best_match']['similarity'] > 0.8

    def test_complete_exclusion(self):
        result = suggest_syntax("$$$ui$$$ must not depend on $$$db$$$")
        assert result['best_match']['type'] == 'exclusion'
        assert result['best_match']['similarity'] > 0.8

    def test_cardinality_partial(self):
        result = suggest_syntax("there must be exactly")
        assert result['best_match']['type'] == 'cardinality'
        # Next token suggests adding a number
        assert 'number' in ' '.join(result['suggestions']).lower() or result['next_token'].lower() == 'n'

    def test_cardinality_with_number(self):
        result = suggest_syntax("there must be exactly 3")
        assert result['best_match']['type'] == 'cardinality'
        # Next should suggest adding a reference
        assert 'reference' in ' '.join(result['suggestions']).lower()

    def test_should_variant(self):
        result = suggest_syntax("$$$api$$$ should be in")
        assert result['best_match']['type'] == 'containment'
        assert '$$$' in result['next_token'] or 'reference' in result['next_token'].lower()

    def test_alternatives_provided(self):
        result = suggest_syntax("there must be")
        assert 'alternatives' in result
        assert len(result['alternatives']) > 0

    def test_similarity_score_range(self):
        result = suggest_syntax("$$$api$$$ must be in $$$layer$$$")
        assert 0 <= result['best_match']['similarity'] <= 1

    def test_empty_input(self):
        result = suggest_syntax("")
        assert result['best_match']['template'] is not None
        assert result['best_match']['similarity'] < 0.5

    def test_gibberish_input(self):
        result = suggest_syntax("foo bar baz qux")
        assert result['best_match']['similarity'] < 0.3


class TestCoverageStatements:
    """Test parsing of coverage/ownership statements."""

    def test_all_components_builtin(self):
        """Test built-in 'all components' keyword (no reference needed)."""
        result = parse_statement("all components must have an owner on $$$team-ownership$$$")
        assert result == {
            'type': 'coverage',
            'subject': '*',  # '*' indicates all components
            'layer': 'team-ownership'
        }

    def test_all_components_covered_by(self):
        result = parse_statement("all components must be covered by $$$teams$$$")
        assert result == {
            'type': 'coverage',
            'subject': '*',
            'layer': 'teams'
        }

    def test_all_components_belong_to_group(self):
        result = parse_statement("all components must belong to a group on $$$ownership$$$")
        assert result == {
            'type': 'coverage',
            'subject': '*',
            'layer': 'ownership'
        }

    def test_have_owner_on_with_reference(self):
        result = parse_statement("all $$$services$$$ must have an owner on $$$team-ownership$$$")
        assert result == {
            'type': 'coverage',
            'subject': 'services',
            'layer': 'team-ownership'
        }

    def test_should_have_owner(self):
        result = parse_statement("all $$$services$$$ should have an owner on $$$teams$$$")
        assert result == {
            'type': 'coverage',
            'subject': 'services',
            'layer': 'teams'
        }

    def test_covered_by(self):
        result = parse_statement("$$$api-services$$$ must be covered by $$$ownership-layer$$$")
        assert result == {
            'type': 'coverage',
            'subject': 'api-services',
            'layer': 'ownership-layer'
        }

    def test_should_be_covered_by(self):
        result = parse_statement("$$$endpoints$$$ should be covered by $$$team-layer$$$")
        assert result == {
            'type': 'coverage',
            'subject': 'endpoints',
            'layer': 'team-layer'
        }

    def test_belong_to_group_on(self):
        result = parse_statement("all $$$microservices$$$ must belong to a group on $$$team-ownership$$$")
        assert result == {
            'type': 'coverage',
            'subject': 'microservices',
            'layer': 'team-ownership'
        }

    def test_case_insensitive_all_components(self):
        result = parse_statement("All Components Must Have An Owner On $$$Teams$$$")
        assert result == {
            'type': 'coverage',
            'subject': '*',
            'layer': 'Teams'
        }

    def test_case_insensitive_with_reference(self):
        result = parse_statement("All $$$Components$$$ Must Have An Owner On $$$Teams$$$")
        assert result == {
            'type': 'coverage',
            'subject': 'Components',
            'layer': 'Teams'
        }

    def test_every_component_in_the_system(self):
        """Test alternative 'every component in the system' syntax."""
        result = parse_statement("every component in the system must have an owner on $$$team-ownership$$$")
        assert result == {
            'type': 'coverage',
            'subject': '*',
            'layer': 'team-ownership'
        }

    def test_every_component_covered_by(self):
        result = parse_statement("every component in the system must be covered by $$$teams$$$")
        assert result == {
            'type': 'coverage',
            'subject': '*',
            'layer': 'teams'
        }

    def test_every_component_belong_to_group(self):
        result = parse_statement("every component in the system should belong to a group on $$$ownership$$$")
        assert result == {
            'type': 'coverage',
            'subject': '*',
            'layer': 'ownership'
        }

    def test_every_with_reference(self):
        """Test 'every $$$reference$$$' syntax (alternative to 'all')."""
        result = parse_statement("every $$$services$$$ must have an owner on $$$teams$$$")
        assert result == {
            'type': 'coverage',
            'subject': 'services',
            'layer': 'teams'
        }

    def test_case_insensitive_every_component(self):
        result = parse_statement("Every Component In The System Must Have An Owner On $$$Teams$$$")
        assert result == {
            'type': 'coverage',
            'subject': '*',
            'layer': 'Teams'
        }


class TestDetectCoverageType:
    """Test detection of coverage statement type."""

    def test_detect_have_owner(self):
        assert detect_statement_type("all X must have an owner on Y") == 'coverage'

    def test_detect_covered_by(self):
        assert detect_statement_type("X must be covered by Y") == 'coverage'

    def test_detect_belong_to_group(self):
        assert detect_statement_type("all X must belong to a group on Y") == 'coverage'


class TestCorrespondenceStatements:
    """Test parsing of correspondence statements for layer alignment."""

    def test_corresponds_with(self):
        """Basic 'corresponds with' pattern."""
        result = parse_statement("$$$team-ownership$$$ must correspond with $$$gitlab-groups$$$")
        assert result == {
            'type': 'correspondence',
            'layer_a': 'team-ownership',
            'layer_b': 'gitlab-groups'
        }

    def test_should_correspond_with(self):
        result = parse_statement("$$$team-layer$$$ should correspond with $$$org-structure$$$")
        assert result == {
            'type': 'correspondence',
            'layer_a': 'team-layer',
            'layer_b': 'org-structure'
        }

    def test_aligns_with(self):
        result = parse_statement("$$$ownership$$$ must align with $$$gitlab$$$")
        assert result == {
            'type': 'correspondence',
            'layer_a': 'ownership',
            'layer_b': 'gitlab'
        }

    def test_matches_with(self):
        result = parse_statement("$$$teams$$$ should match with $$$projects$$$")
        assert result == {
            'type': 'correspondence',
            'layer_a': 'teams',
            'layer_b': 'projects'
        }

    def test_correspond_to(self):
        result = parse_statement("$$$team-ownership$$$ must correspond to $$$gitlab-groups$$$")
        assert result == {
            'type': 'correspondence',
            'layer_a': 'team-ownership',
            'layer_b': 'gitlab-groups'
        }

    def test_simple_corresponds_with(self):
        """Without must/should."""
        result = parse_statement("$$$team-ownership$$$ corresponds with $$$gitlab-groups$$$")
        assert result == {
            'type': 'correspondence',
            'layer_a': 'team-ownership',
            'layer_b': 'gitlab-groups'
        }

    def test_simple_aligns_with(self):
        result = parse_statement("$$$ownership$$$ aligns with $$$structure$$$")
        assert result == {
            'type': 'correspondence',
            'layer_a': 'ownership',
            'layer_b': 'structure'
        }

    def test_case_insensitive(self):
        result = parse_statement("$$$Teams$$$ Must Correspond With $$$GitLab$$$")
        assert result == {
            'type': 'correspondence',
            'layer_a': 'Teams',
            'layer_b': 'GitLab'
        }


class TestDetectCorrespondenceType:
    """Test detection of correspondence statement type."""

    def test_detect_corresponds_with(self):
        assert detect_statement_type("X must correspond with Y") == 'correspondence'

    def test_detect_aligns_with(self):
        assert detect_statement_type("X aligns with Y") == 'correspondence'

    def test_detect_matches_with(self):
        assert detect_statement_type("X should match with Y") == 'correspondence'


class TestRefinementStatements:
    """Test parsing of refinement statements for many:1 layer alignment."""

    def test_refines_simple(self):
        """Basic 'refines' pattern without must/should."""
        result = parse_statement("$$$gitlab-groups$$$ refines $$$team-ownership$$$")
        assert result == {
            'type': 'refinement',
            'fine': 'gitlab-groups',
            'coarse': 'team-ownership'
        }

    def test_must_refine(self):
        result = parse_statement("$$$gitlab-groups$$$ must refine $$$team-ownership$$$")
        assert result == {
            'type': 'refinement',
            'fine': 'gitlab-groups',
            'coarse': 'team-ownership'
        }

    def test_should_refine(self):
        result = parse_statement("$$$technical-groups$$$ should refine $$$business-domains$$$")
        assert result == {
            'type': 'refinement',
            'fine': 'technical-groups',
            'coarse': 'business-domains'
        }

    def test_be_a_refinement_of(self):
        result = parse_statement("$$$gitlab-groups$$$ must be a refinement of $$$team-ownership$$$")
        assert result == {
            'type': 'refinement',
            'fine': 'gitlab-groups',
            'coarse': 'team-ownership'
        }

    def test_nest_within(self):
        result = parse_statement("$$$gitlab-groups$$$ must nest within $$$team-ownership$$$")
        assert result == {
            'type': 'refinement',
            'fine': 'gitlab-groups',
            'coarse': 'team-ownership'
        }

    def test_nests_within_simple(self):
        result = parse_statement("$$$projects$$$ nests within $$$teams$$$")
        assert result == {
            'type': 'refinement',
            'fine': 'projects',
            'coarse': 'teams'
        }

    def test_case_insensitive(self):
        result = parse_statement("$$$GitLab$$$ Refines $$$Teams$$$")
        assert result == {
            'type': 'refinement',
            'fine': 'GitLab',
            'coarse': 'Teams'
        }


class TestDetectRefinementType:
    """Test detection of refinement statement type."""

    def test_detect_refines(self):
        assert detect_statement_type("X refines Y") == 'refinement'

    def test_detect_must_refine(self):
        assert detect_statement_type("X must refine Y") == 'refinement'

    def test_detect_refinement_of(self):
        assert detect_statement_type("X must be a refinement of Y") == 'refinement'

    def test_detect_nests_within(self):
        assert detect_statement_type("X nests within Y") == 'refinement'

    def test_detect_nest_within(self):
        assert detect_statement_type("X must nest within Y") == 'refinement'
