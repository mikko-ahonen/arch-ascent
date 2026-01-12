"""
Tests for Statement Evaluator Service.
"""
import pytest
from dependencies.models import Project, Dependency
from vision.models import (
    Vision, Layer, Group, GroupMembership, Reference, Statement
)
from vision.services.statement_evaluator import (
    evaluate_statement,
    evaluate_all_statements,
    get_statement_violations,
)


@pytest.fixture
def vision_with_structure():
    """Create a vision with layers, groups, and projects."""
    # Create projects
    projects = {
        "payment-api": Project.objects.create(key="payment-api", name="Payment API"),
        "payment-worker": Project.objects.create(key="payment-worker", name="Payment Worker"),
        "user-api": Project.objects.create(key="user-api", name="User API"),
        "gateway": Project.objects.create(key="gateway", name="Gateway"),
    }

    # Create vision with layer and groups
    vision = Vision.objects.create(name="Test Vision")
    layer = Layer.objects.create(key="main", name="Main Layer", vision=vision)

    payment_group = Group.objects.create(key="payment-domain", name="Payment Domain", layer=layer)
    GroupMembership.objects.create(group=payment_group, project=projects["payment-api"])
    GroupMembership.objects.create(group=payment_group, project=projects["payment-worker"])

    user_group = Group.objects.create(key="user-domain", name="User Domain", layer=layer)
    GroupMembership.objects.create(group=user_group, project=projects["user-api"])

    # Tag projects using taggit
    projects["payment-api"].tags.add("payment", "api")
    projects["payment-worker"].tags.add("payment")
    projects["user-api"].tags.add("api")

    # Create reference
    Reference.objects.create(
        name="PaymentServices",
        vision=vision,
        definition_type="tag_expression",
        tag_expression="payment"
    )

    return {
        "vision": vision,
        "layer": layer,
        "projects": projects,
        "payment_group": payment_group,
        "user_group": user_group,
    }


@pytest.mark.django_db
class TestEvaluateExistenceStatement:
    """Tests for existence statement evaluation."""

    def test_existence_satisfied(self, vision_with_structure):
        """Test existence statement is satisfied when reference has members."""
        stmt = Statement.objects.create(
            vision=vision_with_structure["vision"],
            statement_type="existence",
            natural_language="Payment services must exist",
            formal_expression={"reference": "PaymentServices"},
            status="formal"
        )

        result = evaluate_statement(stmt)
        assert result is True
        stmt.refresh_from_db()
        assert stmt.is_satisfied is True

    def test_existence_not_satisfied(self, vision_with_structure):
        """Test existence statement fails when reference has no members."""
        # Create reference with no matching members
        Reference.objects.create(
            name="EmptyRef",
            vision=vision_with_structure["vision"],
            definition_type="tag_expression",
            tag_expression="nonexistent-tag"
        )

        stmt = Statement.objects.create(
            vision=vision_with_structure["vision"],
            statement_type="existence",
            natural_language="Must have nonexistent services",
            formal_expression={"reference": "EmptyRef"},
            status="formal"
        )

        result = evaluate_statement(stmt)
        assert result is False


@pytest.mark.django_db
class TestEvaluateContainmentStatement:
    """Tests for containment statement evaluation."""

    def test_containment_satisfied(self, vision_with_structure):
        """Test containment when all subject members are in container."""
        stmt = Statement.objects.create(
            vision=vision_with_structure["vision"],
            statement_type="containment",
            natural_language="All payment services must be in payment domain",
            formal_expression={
                "subject": "PaymentServices",
                "container": "payment-domain"
            },
            status="formal"
        )

        result = evaluate_statement(stmt)
        assert result is True

    def test_containment_not_satisfied(self, vision_with_structure):
        """Test containment fails when some members are outside container."""
        # Create reference that includes gateway (not in any group)
        Reference.objects.create(
            name="AllServices",
            vision=vision_with_structure["vision"],
            definition_type="explicit_list",
            explicit_members=["payment-api", "gateway"]
        )

        stmt = Statement.objects.create(
            vision=vision_with_structure["vision"],
            statement_type="containment",
            natural_language="All services must be in payment domain",
            formal_expression={
                "subject": "AllServices",
                "container": "payment-domain"
            },
            status="formal"
        )

        result = evaluate_statement(stmt)
        assert result is False


@pytest.mark.django_db
class TestEvaluateExclusionStatement:
    """Tests for exclusion statement evaluation."""

    def test_exclusion_satisfied(self, vision_with_structure):
        """Test exclusion when no dependencies exist between sets."""
        # No dependencies created, so exclusion should be satisfied
        Reference.objects.create(
            name="PaymentAPIs",
            vision=vision_with_structure["vision"],
            definition_type="tag_expression",
            tag_expression={"and": ["payment", "api"]}
        )
        Reference.objects.create(
            name="UserAPIs",
            vision=vision_with_structure["vision"],
            definition_type="explicit_list",
            explicit_members=["user-api"]
        )

        stmt = Statement.objects.create(
            vision=vision_with_structure["vision"],
            statement_type="exclusion",
            natural_language="Payment APIs must not depend on User APIs",
            formal_expression={
                "subject": "PaymentAPIs",
                "excluded": "UserAPIs"
            },
            status="formal"
        )

        result = evaluate_statement(stmt)
        assert result is True

    def test_exclusion_not_satisfied(self, vision_with_structure):
        """Test exclusion fails when dependency exists."""
        # Create a dependency
        Dependency.objects.create(
            source=vision_with_structure["projects"]["payment-api"],
            target=vision_with_structure["projects"]["user-api"]
        )

        Reference.objects.create(
            name="PaymentAPIs",
            vision=vision_with_structure["vision"],
            definition_type="tag_expression",
            tag_expression={"and": ["payment", "api"]}
        )
        Reference.objects.create(
            name="UserAPIs",
            vision=vision_with_structure["vision"],
            definition_type="explicit_list",
            explicit_members=["user-api"]
        )

        stmt = Statement.objects.create(
            vision=vision_with_structure["vision"],
            statement_type="exclusion",
            natural_language="Payment APIs must not depend on User APIs",
            formal_expression={
                "subject": "PaymentAPIs",
                "excluded": "UserAPIs"
            },
            status="formal"
        )

        result = evaluate_statement(stmt)
        assert result is False


@pytest.mark.django_db
class TestEvaluateCardinalityStatement:
    """Tests for cardinality statement evaluation."""

    def test_cardinality_equals_satisfied(self, vision_with_structure):
        """Test cardinality with == operator."""
        stmt = Statement.objects.create(
            vision=vision_with_structure["vision"],
            statement_type="cardinality",
            natural_language="There must be exactly 2 payment services",
            formal_expression={
                "reference": "PaymentServices",
                "operator": "==",
                "value": 2
            },
            status="formal"
        )

        result = evaluate_statement(stmt)
        assert result is True

    def test_cardinality_less_than_satisfied(self, vision_with_structure):
        """Test cardinality with < operator."""
        stmt = Statement.objects.create(
            vision=vision_with_structure["vision"],
            statement_type="cardinality",
            natural_language="There must be less than 5 payment services",
            formal_expression={
                "reference": "PaymentServices",
                "operator": "<",
                "value": 5
            },
            status="formal"
        )

        result = evaluate_statement(stmt)
        assert result is True

    def test_cardinality_greater_than_not_satisfied(self, vision_with_structure):
        """Test cardinality with > operator fails when condition not met."""
        stmt = Statement.objects.create(
            vision=vision_with_structure["vision"],
            statement_type="cardinality",
            natural_language="There must be more than 10 payment services",
            formal_expression={
                "reference": "PaymentServices",
                "operator": ">",
                "value": 10
            },
            status="formal"
        )

        result = evaluate_statement(stmt)
        assert result is False


@pytest.mark.django_db
class TestInformalStatements:
    """Tests for informal statement handling."""

    def test_informal_statement_not_evaluated(self, vision_with_structure):
        """Test that informal statements return None."""
        stmt = Statement.objects.create(
            vision=vision_with_structure["vision"],
            statement_type="existence",
            natural_language="Payment services should probably exist",
            status="informal"
        )

        result = evaluate_statement(stmt)
        assert result is None


@pytest.mark.django_db
class TestEvaluateAllStatements:
    """Tests for batch statement evaluation."""

    def test_evaluate_all_statements(self, vision_with_structure):
        """Test evaluating all statements in a vision."""
        # Create multiple statements
        Statement.objects.create(
            vision=vision_with_structure["vision"],
            statement_type="existence",
            natural_language="Payment services exist",
            formal_expression={"reference": "PaymentServices"},
            status="formal"
        )
        Statement.objects.create(
            vision=vision_with_structure["vision"],
            statement_type="cardinality",
            natural_language="Too many payment services",
            formal_expression={"reference": "PaymentServices", "operator": ">", "value": 100},
            status="formal"
        )
        Statement.objects.create(
            vision=vision_with_structure["vision"],
            statement_type="existence",
            natural_language="Informal statement",
            status="informal"
        )

        results = evaluate_all_statements(vision_with_structure["vision"].id)

        assert results["total"] == 3
        assert results["satisfied"] == 1
        assert results["violated"] == 1
        assert results["not_evaluated"] == 1


@pytest.mark.django_db
class TestGetStatementViolations:
    """Tests for getting statement violations."""

    def test_get_violations(self, vision_with_structure):
        """Test getting all violated statements."""
        # Satisfied statement
        Statement.objects.create(
            vision=vision_with_structure["vision"],
            statement_type="existence",
            natural_language="Payment services exist",
            formal_expression={"reference": "PaymentServices"},
            status="formal"
        )
        # Violated statement
        Statement.objects.create(
            vision=vision_with_structure["vision"],
            statement_type="cardinality",
            natural_language="Too many services",
            formal_expression={"reference": "PaymentServices", "operator": ">", "value": 100},
            status="formal"
        )

        violations = get_statement_violations(vision_with_structure["vision"].id)

        assert len(violations) == 1
        assert violations[0]["natural_language"] == "Too many services"
