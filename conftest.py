"""
Pytest configuration and shared fixtures for testing.
"""
import pytest
from django.test import Client


@pytest.fixture
def client():
    """Django test client."""
    return Client()


@pytest.fixture
def sample_adjacency():
    """Sample DAG for testing algorithms."""
    return {
        'A': {'B', 'C'},
        'B': {'D'},
        'C': {'D', 'E'},
        'D': {'F'},
        'E': {'F'},
        'F': set(),
    }


@pytest.fixture
def cyclic_adjacency():
    """Graph with cycles for SCC testing."""
    return {
        'A': {'B'},
        'B': {'C'},
        'C': {'A', 'D'},  # C->A creates cycle A->B->C->A
        'D': {'E'},
        'E': {'F'},
        'F': {'D'},  # F->D creates cycle D->E->F->D
    }


@pytest.fixture
def linear_adjacency():
    """Simple linear chain for testing."""
    return {
        'A': {'B'},
        'B': {'C'},
        'C': {'D'},
        'D': set(),
    }


@pytest.fixture
def disconnected_adjacency():
    """Disconnected graph with multiple components."""
    return {
        'A': {'B'},
        'B': set(),
        'C': {'D'},
        'D': set(),
        'E': set(),
    }


@pytest.fixture
def sample_layer_assignments():
    """Sample layer assignments for violation testing."""
    return {
        'infra:db': 0,
        'infra:cache': 0,
        'domain:user': 1,
        'domain:order': 1,
        'app:api': 2,
        'app:web': 2,
    }


@pytest.fixture
def layered_adjacency():
    """Graph with layer structure for violation testing."""
    return {
        'app:api': {'domain:user', 'domain:order'},
        'app:web': {'domain:user'},
        'domain:user': {'infra:db'},
        'domain:order': {'infra:db', 'infra:cache'},
        'infra:db': set(),
        'infra:cache': set(),
    }


@pytest.fixture
def layered_with_violations():
    """Graph with layer violations."""
    return {
        'app:api': {'domain:user'},
        'domain:user': {'infra:db', 'app:api'},  # Violation: domain -> app
        'infra:db': {'domain:user'},  # Violation: infra -> domain
    }


@pytest.fixture(scope='function')
def sample_projects(db):
    """Create sample projects in database."""
    from dependencies.models import Project

    projects = []
    for name in ['A', 'B', 'C', 'D', 'E', 'F']:
        project = Project.objects.create(
            key=name,
            name=f'Project {name}',
            description=f'Test project {name}'
        )
        projects.append(project)
    return projects


@pytest.fixture(scope='function')
def sample_dependencies(db, sample_projects):
    """Create sample dependencies in database."""
    from dependencies.models import Dependency

    # Create DAG: A->B, A->C, B->D, C->D, C->E, D->F, E->F
    project_map = {p.key: p for p in sample_projects}

    deps = [
        ('A', 'B'), ('A', 'C'),
        ('B', 'D'),
        ('C', 'D'), ('C', 'E'),
        ('D', 'F'),
        ('E', 'F'),
    ]

    dependencies = []
    for source_key, target_key in deps:
        dep = Dependency.objects.create(
            source=project_map[source_key],
            target=project_map[target_key]
        )
        dependencies.append(dep)

    return dependencies


@pytest.fixture(scope='function')
def sample_layers(db):
    """Create sample layer definitions in database."""
    from dependencies.models import LayerDefinition

    layers = [
        LayerDefinition.objects.create(
            name='infrastructure',
            level=0,
            description='Infrastructure layer (databases, caches)',
            pattern='^infra:.*'
        ),
        LayerDefinition.objects.create(
            name='domain',
            level=1,
            description='Domain/business logic layer',
            pattern='^domain:.*'
        ),
        LayerDefinition.objects.create(
            name='application',
            level=2,
            description='Application layer (APIs, UIs)',
            pattern='^app:.*'
        ),
    ]
    return layers
