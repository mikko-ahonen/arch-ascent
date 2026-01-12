"""
Tests for Vision Creation System models.
"""
import pytest
from django.test import TestCase
from taggit.models import Tag
from dependencies.models import Project
from vision.models import (
    Vision, Layer, Group, GroupMembership, LayerNodePosition,
    Reference, Statement
)


@pytest.mark.django_db
class TestVisionModel:
    """Tests for Vision model."""

    def test_create_vision(self):
        """Test creating a basic vision."""
        vision = Vision.objects.create(
            name="Test Vision",
            description="A test vision",
            status="draft"
        )
        assert vision.id is not None
        assert vision.name == "Test Vision"
        assert vision.status == "draft"

    def test_vision_branching(self):
        """Test vision parent-child relationship."""
        parent = Vision.objects.create(name="Parent Vision")
        child = Vision.objects.create(name="Child Vision", parent=parent)

        assert child.parent == parent
        assert parent.children.count() == 1
        assert parent.children.first() == child

    def test_vision_status_choices(self):
        """Test vision status transitions."""
        vision = Vision.objects.create(name="Test", status="draft")
        assert vision.status == "draft"

        vision.status = "shared"
        vision.save()
        vision.refresh_from_db()
        assert vision.status == "shared"


@pytest.mark.django_db
class TestLayerModel:
    """Tests for Layer model."""

    def test_create_layer(self):
        """Test creating a layer within a vision."""
        vision = Vision.objects.create(name="Test Vision")
        layer = Layer.objects.create(
            key="test-layer",
            name="Test Layer",
            vision=vision,
            layer_type="freeform"
        )
        assert layer.id is not None
        assert layer.vision == vision
        assert vision.layers.count() == 1

    def test_layer_types(self):
        """Test different layer types."""
        vision = Vision.objects.create(name="Test Vision")

        for layer_type, _ in Layer.LAYER_TYPES:
            layer = Layer.objects.create(
                key=f"layer-{layer_type}",
                name=f"Layer {layer_type}",
                vision=vision,
                layer_type=layer_type
            )
            assert layer.layer_type == layer_type

    def test_layer_unique_key_per_vision(self):
        """Test that layer keys must be unique within a vision."""
        vision = Vision.objects.create(name="Test Vision")
        Layer.objects.create(key="unique-key", name="Layer 1", vision=vision)

        with pytest.raises(Exception):
            Layer.objects.create(key="unique-key", name="Layer 2", vision=vision)


@pytest.mark.django_db
class TestGroupModel:
    """Tests for Group model."""

    def test_create_group(self):
        """Test creating a group within a layer."""
        vision = Vision.objects.create(name="Test Vision")
        layer = Layer.objects.create(key="layer", name="Layer", vision=vision)
        group = Group.objects.create(
            key="test-group",
            name="Test Group",
            layer=layer
        )
        assert group.id is not None
        assert group.layer == layer
        assert layer.groups.count() == 1

    def test_hierarchical_groups(self):
        """Test parent-child group relationships."""
        vision = Vision.objects.create(name="Test Vision")
        layer = Layer.objects.create(key="layer", name="Layer", vision=vision)
        parent_group = Group.objects.create(key="parent", name="Parent", layer=layer)
        child_group = Group.objects.create(key="child", name="Child", layer=layer, parent=parent_group)

        assert child_group.parent == parent_group
        assert parent_group.children.count() == 1


@pytest.mark.django_db
class TestGroupMembership:
    """Tests for GroupMembership model."""

    def test_add_project_to_group(self):
        """Test adding a project to a group."""
        project = Project.objects.create(key="service-a", name="Service A")
        vision = Vision.objects.create(name="Test Vision")
        layer = Layer.objects.create(key="layer", name="Layer", vision=vision)
        group = Group.objects.create(key="group", name="Group", layer=layer)

        membership = GroupMembership.objects.create(
            group=group,
            project=project,
            membership_type="explicit"
        )
        assert membership.id is not None
        assert group.memberships.count() == 1

    def test_project_in_multiple_groups(self):
        """Test that a project can be in multiple groups (overlapping)."""
        project = Project.objects.create(key="service-a", name="Service A")
        vision = Vision.objects.create(name="Test Vision")
        layer = Layer.objects.create(key="layer", name="Layer", vision=vision)
        group1 = Group.objects.create(key="group1", name="Group 1", layer=layer)
        group2 = Group.objects.create(key="group2", name="Group 2", layer=layer)

        GroupMembership.objects.create(group=group1, project=project)
        GroupMembership.objects.create(group=group2, project=project)

        assert project.vision_group_memberships.count() == 2


@pytest.mark.django_db
class TestLayerNodePosition:
    """Tests for LayerNodePosition model."""

    def test_set_node_position(self):
        """Test setting a project's position in a layer."""
        project = Project.objects.create(key="service-a", name="Service A")
        vision = Vision.objects.create(name="Test Vision")
        layer = Layer.objects.create(key="layer", name="Layer", vision=vision)

        pos = LayerNodePosition.objects.create(
            layer=layer,
            project=project,
            position_x=100.0,
            position_y=200.0
        )
        assert pos.position_x == 100.0
        assert pos.position_y == 200.0

    def test_unique_position_per_layer(self):
        """Test that a project has one position per layer."""
        project = Project.objects.create(key="service-a", name="Service A")
        vision = Vision.objects.create(name="Test Vision")
        layer = Layer.objects.create(key="layer", name="Layer", vision=vision)

        LayerNodePosition.objects.create(layer=layer, project=project, position_x=100, position_y=100)

        with pytest.raises(Exception):
            LayerNodePosition.objects.create(layer=layer, project=project, position_x=200, position_y=200)


@pytest.mark.django_db
class TestTaggitIntegration:
    """Tests for django-taggit integration on Project model."""

    def test_add_tags_to_project(self):
        """Test adding tags to a project via TaggableManager."""
        project = Project.objects.create(key="service-a", name="Service A")
        project.tags.add("payment", "api")

        assert project.tags.count() == 2
        tag_names = list(project.tags.names())
        assert "payment" in tag_names
        assert "api" in tag_names

    def test_filter_projects_by_tag(self):
        """Test filtering projects by tag."""
        project1 = Project.objects.create(key="service-a", name="Service A")
        project2 = Project.objects.create(key="service-b", name="Service B")
        project1.tags.add("payment")
        project2.tags.add("user")

        payment_projects = Project.objects.filter(tags__name="payment")
        assert payment_projects.count() == 1
        assert payment_projects.first().key == "service-a"

    def test_remove_tag_from_project(self):
        """Test removing a tag from a project."""
        project = Project.objects.create(key="service-a", name="Service A")
        project.tags.add("payment", "api")
        project.tags.remove("payment")

        assert project.tags.count() == 1
        assert list(project.tags.names()) == ["api"]

    def test_tag_creates_on_demand(self):
        """Test that taggit creates tags automatically when assigned."""
        project = Project.objects.create(key="service-a", name="Service A")
        project.tags.add("new-tag")

        # Tag should exist in database
        assert Tag.objects.filter(name="new-tag").exists()

    def test_clear_all_tags(self):
        """Test clearing all tags from a project."""
        project = Project.objects.create(key="service-a", name="Service A")
        project.tags.add("payment", "api", "domain")
        project.tags.clear()

        assert project.tags.count() == 0


@pytest.mark.django_db
class TestReferenceModel:
    """Tests for Reference model."""

    def test_create_informal_reference(self):
        """Test creating an informal reference."""
        vision = Vision.objects.create(name="Test Vision")
        ref = Reference.objects.create(
            name="PaymentServices",
            vision=vision,
            description="All payment-related services",
            definition_type="informal"
        )
        assert ref.id is not None
        assert ref.definition_type == "informal"

    def test_create_tag_expression_reference(self):
        """Test creating a reference with tag expression."""
        vision = Vision.objects.create(name="Test Vision")
        ref = Reference.objects.create(
            name="PaymentAPIs",
            vision=vision,
            definition_type="tag_expression",
            tag_expression={"and": ["payment", "api"]}
        )
        assert ref.tag_expression == {"and": ["payment", "api"]}

    def test_create_explicit_list_reference(self):
        """Test creating a reference with explicit member list."""
        vision = Vision.objects.create(name="Test Vision")
        ref = Reference.objects.create(
            name="CoreServices",
            vision=vision,
            definition_type="explicit_list",
            explicit_members=["service-a", "service-b", "service-c"]
        )
        assert len(ref.explicit_members) == 3


@pytest.mark.django_db
class TestStatementModel:
    """Tests for Statement model."""

    def test_create_informal_statement(self):
        """Test creating an informal statement."""
        vision = Vision.objects.create(name="Test Vision")
        stmt = Statement.objects.create(
            vision=vision,
            statement_type="existence",
            natural_language="There should be a payment service",
            status="informal"
        )
        assert stmt.id is not None
        assert stmt.is_satisfied is None

    def test_create_formal_statement(self):
        """Test creating a formal statement with expression."""
        vision = Vision.objects.create(name="Test Vision")
        stmt = Statement.objects.create(
            vision=vision,
            statement_type="cardinality",
            natural_language="There must be exactly one payment gateway",
            formal_expression={"reference": "PaymentGateway", "operator": "==", "value": 1},
            status="formal"
        )
        assert stmt.formal_expression is not None
        assert stmt.formal_expression["operator"] == "=="

    def test_statement_types(self):
        """Test different statement types."""
        vision = Vision.objects.create(name="Test Vision")

        for stmt_type, _ in Statement.STATEMENT_TYPES:
            stmt = Statement.objects.create(
                vision=vision,
                statement_type=stmt_type,
                natural_language=f"Test {stmt_type} statement"
            )
            assert stmt.statement_type == stmt_type
