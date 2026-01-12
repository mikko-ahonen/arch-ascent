"""
Tests for Tag Expression Resolver Service (using django-taggit).
"""
import pytest
from dependencies.models import Project
from vision.models import Vision, Reference
from dependencies.services.tag_resolver import (
    resolve_tag_expression,
    get_tags_for_project,
    assign_tag_to_project,
    remove_tag_from_project,
    get_all_tags,
    get_projects_by_tags,
)
from vision.services.tag_resolver import resolve_reference


@pytest.fixture
def sample_projects():
    """Create sample projects for testing."""
    projects = [
        Project.objects.create(key="payment-api", name="Payment API"),
        Project.objects.create(key="payment-worker", name="Payment Worker"),
        Project.objects.create(key="user-api", name="User API"),
        Project.objects.create(key="user-worker", name="User Worker"),
        Project.objects.create(key="gateway", name="Gateway"),
    ]
    return {p.key: p for p in projects}


def tag_project(project, tag_name):
    """Helper to tag a project using taggit."""
    project.tags.add(tag_name)


@pytest.mark.django_db
class TestResolveTagExpression:
    """Tests for resolve_tag_expression function."""

    def test_simple_tag(self, sample_projects):
        """Test resolving a single tag."""
        tag_project(sample_projects["payment-api"], "payment")
        tag_project(sample_projects["payment-worker"], "payment")

        result = resolve_tag_expression("payment")
        assert result == {"payment-api", "payment-worker"}

    def test_and_expression(self, sample_projects):
        """Test AND expression resolves to intersection."""
        tag_project(sample_projects["payment-api"], "payment")
        tag_project(sample_projects["payment-worker"], "payment")
        tag_project(sample_projects["payment-api"], "api")
        tag_project(sample_projects["user-api"], "api")

        result = resolve_tag_expression({"and": ["payment", "api"]})
        assert result == {"payment-api"}

    def test_or_expression(self, sample_projects):
        """Test OR expression resolves to union."""
        tag_project(sample_projects["payment-api"], "payment")
        tag_project(sample_projects["user-api"], "user")

        result = resolve_tag_expression({"or": ["payment", "user"]})
        assert result == {"payment-api", "user-api"}

    def test_not_expression(self, sample_projects):
        """Test NOT expression excludes matching projects."""
        tag_project(sample_projects["payment-api"], "api")
        tag_project(sample_projects["user-api"], "api")

        result = resolve_tag_expression({"not": "api"})
        # Should include all projects without 'api' tag
        assert "payment-api" not in result
        assert "user-api" not in result
        assert "payment-worker" in result
        assert "gateway" in result

    def test_nested_expression(self, sample_projects):
        """Test nested expression evaluation."""
        # Setup tags
        for proj_key, tags in [
            ("payment-api", ["payment", "api", "public"]),
            ("payment-worker", ["payment", "worker"]),
            ("user-api", ["user", "api", "public"]),
        ]:
            project = sample_projects[proj_key]
            for tag_name in tags:
                project.tags.add(tag_name)

        # (payment OR user) AND api
        result = resolve_tag_expression({
            "and": [
                {"or": ["payment", "user"]},
                "api"
            ]
        })
        assert result == {"payment-api", "user-api"}

    def test_empty_expression(self, sample_projects):
        """Test empty or invalid expressions return empty set."""
        assert resolve_tag_expression({}) == set()
        assert resolve_tag_expression({"and": []}) == set()
        assert resolve_tag_expression("nonexistent-tag") == set()


@pytest.mark.django_db
class TestResolveReference:
    """Tests for resolve_reference function."""

    def test_resolve_explicit_list_reference(self, sample_projects):
        """Test resolving explicit list reference."""
        vision = Vision.objects.create(name="Test Vision")
        ref = Reference.objects.create(
            name="CoreServices",
            vision=vision,
            definition_type="explicit_list",
            explicit_members=["payment-api", "user-api", "nonexistent"]
        )

        result = resolve_reference(ref)
        # Should only include existing projects
        assert result == {"payment-api", "user-api"}

    def test_resolve_tag_expression_reference(self, sample_projects):
        """Test resolving tag expression reference."""
        vision = Vision.objects.create(name="Test Vision")

        tag_project(sample_projects["payment-api"], "api")
        tag_project(sample_projects["user-api"], "api")

        ref = Reference.objects.create(
            name="AllAPIs",
            vision=vision,
            definition_type="tag_expression",
            tag_expression="api"
        )

        result = resolve_reference(ref)
        assert result == {"payment-api", "user-api"}

    def test_resolve_informal_reference(self, sample_projects):
        """Test that informal references return empty set."""
        vision = Vision.objects.create(name="Test Vision")
        ref = Reference.objects.create(
            name="SomeServices",
            vision=vision,
            definition_type="informal",
            description="Services that do something"
        )

        result = resolve_reference(ref)
        assert result == set()


@pytest.mark.django_db
class TestTagHelperFunctions:
    """Tests for tag helper functions."""

    def test_get_tags_for_project(self, sample_projects):
        """Test getting all tags for a project."""
        sample_projects["payment-api"].tags.add("payment", "api")

        tags = get_tags_for_project("payment-api")
        assert len(tags) == 2
        tag_names = {t["name"] for t in tags}
        assert tag_names == {"payment", "api"}

    def test_assign_tag_to_project(self, sample_projects):
        """Test assigning a tag to a project."""
        result = assign_tag_to_project("payment", "gateway")
        assert result is True

        # Verify tag was added
        tags = get_tags_for_project("gateway")
        assert len(tags) == 1
        assert tags[0]["name"] == "payment"

    def test_remove_tag_from_project(self, sample_projects):
        """Test removing a tag from a project."""
        assign_tag_to_project("payment", "gateway")

        result = remove_tag_from_project("payment", "gateway")
        assert result is True

        # Second removal should return False (doesn't exist)
        result = remove_tag_from_project("payment", "gateway")
        assert result is False

    def test_get_tags_for_nonexistent_project(self):
        """Test getting tags for nonexistent project returns empty list."""
        tags = get_tags_for_project("nonexistent")
        assert tags == []

    def test_get_all_tags(self, sample_projects):
        """Test getting all tags in the system."""
        sample_projects["payment-api"].tags.add("api", "payment")
        sample_projects["user-api"].tags.add("api", "user")

        tags = get_all_tags()
        tag_names = {t["name"] for t in tags}
        assert "api" in tag_names
        assert "payment" in tag_names
        assert "user" in tag_names

        # Check count
        api_tag = next(t for t in tags if t["name"] == "api")
        assert api_tag["count"] == 2  # Used by 2 projects

    def test_get_projects_by_tags_any(self, sample_projects):
        """Test getting projects with any of the specified tags."""
        sample_projects["payment-api"].tags.add("payment")
        sample_projects["user-api"].tags.add("user")
        sample_projects["gateway"].tags.add("gateway")

        result = get_projects_by_tags(["payment", "user"], match_all=False)
        assert result == {"payment-api", "user-api"}

    def test_get_projects_by_tags_all(self, sample_projects):
        """Test getting projects with all specified tags."""
        sample_projects["payment-api"].tags.add("payment", "api")
        sample_projects["payment-worker"].tags.add("payment")
        sample_projects["user-api"].tags.add("api")

        result = get_projects_by_tags(["payment", "api"], match_all=True)
        assert result == {"payment-api"}

    def test_assign_tag_to_nonexistent_project(self, sample_projects):
        """Test assigning tag to nonexistent project returns False."""
        result = assign_tag_to_project("payment", "nonexistent")
        assert result is False
