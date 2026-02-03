"""
Tests for graph algorithms in dependencies/components/graph/graph.py
"""
import pytest
from dependencies.components.graph.graph import (
    traverse_graph,
    topological_sort,
    assign_topological_layers,
    detect_layer_violations,
    calculate_instability,
    calculate_degree_centrality,
    calculate_betweenness_centrality,
    calculate_all_metrics,
    find_sccs_kosaraju,
    louvain_communities,
    get_cycle_edges,
    enumerate_cycles,
)


class TestTraverseGraph:
    """Tests for traverse_graph function."""

    def test_bfs_downstream_simple(self, sample_adjacency):
        """Test BFS downstream traversal."""
        result = traverse_graph(sample_adjacency, 'A', 'downstream', 'bfs')

        assert 0 in result
        assert result[0] == ['A']
        assert set(result[1]) == {'B', 'C'}
        assert set(result[2]) == {'D', 'E'}
        assert result[3] == ['F']

    def test_bfs_upstream(self, sample_adjacency):
        """Test BFS upstream traversal."""
        result = traverse_graph(sample_adjacency, 'F', 'upstream', 'bfs')

        assert result[0] == ['F']
        assert set(result[1]) == {'D', 'E'}

    def test_dfs_downstream(self, sample_adjacency):
        """Test DFS downstream traversal."""
        result = traverse_graph(sample_adjacency, 'A', 'downstream', 'dfs')

        assert 0 in result
        assert result[0] == ['A']
        # DFS order may vary, but all nodes should be reached
        all_reached = set()
        for nodes in result.values():
            all_reached.update(nodes)
        assert all_reached == {'A', 'B', 'C', 'D', 'E', 'F'}

    def test_depth_limiting(self, sample_adjacency):
        """Test traversal with depth limit."""
        result = traverse_graph(sample_adjacency, 'A', 'downstream', 'bfs', max_depth=1)

        assert 0 in result
        assert 1 in result
        assert 2 not in result
        assert result[0] == ['A']
        assert set(result[1]) == {'B', 'C'}

    def test_nonexistent_start_node(self, sample_adjacency):
        """Test traversal from non-existent node."""
        result = traverse_graph(sample_adjacency, 'Z', 'downstream', 'bfs')

        assert result == {0: ['Z']}

    def test_leaf_node_downstream(self, sample_adjacency):
        """Test traversal from leaf node (no outgoing edges)."""
        result = traverse_graph(sample_adjacency, 'F', 'downstream', 'bfs')

        assert result == {0: ['F']}

    def test_both_directions(self, linear_adjacency):
        """Test traversal in both directions."""
        result = traverse_graph(linear_adjacency, 'B', 'both', 'bfs')

        assert result[0] == ['B']
        assert set(result[1]) == {'A', 'C'}


class TestTopologicalSort:
    """Tests for topological_sort function."""

    def test_dag_produces_valid_ordering(self, sample_adjacency):
        """Test that DAG produces valid topological ordering."""
        ordering, is_dag, back_edges = topological_sort(sample_adjacency)

        assert is_dag is True
        assert len(back_edges) == 0
        assert len(ordering) == 6

        # Verify ordering constraints
        order_idx = {node: i for i, node in enumerate(ordering)}
        assert order_idx['A'] < order_idx['B']
        assert order_idx['A'] < order_idx['C']
        assert order_idx['B'] < order_idx['D']
        assert order_idx['C'] < order_idx['D']
        assert order_idx['D'] < order_idx['F']

    def test_cyclic_graph_detected(self, cyclic_adjacency):
        """Test that cycles are detected."""
        ordering, is_dag, back_edges = topological_sort(cyclic_adjacency)

        assert is_dag is False
        assert len(back_edges) > 0

    def test_empty_graph(self):
        """Test empty graph."""
        ordering, is_dag, back_edges = topological_sort({})

        assert ordering == []
        assert is_dag is True
        assert back_edges == []

    def test_single_node(self):
        """Test single node graph."""
        ordering, is_dag, back_edges = topological_sort({'A': set()})

        assert ordering == ['A']
        assert is_dag is True
        assert back_edges == []


class TestAssignTopologicalLayers:
    """Tests for assign_topological_layers function."""

    def test_layers_assigned_correctly(self, sample_adjacency):
        """Test layer assignment on DAG."""
        layers = assign_topological_layers(sample_adjacency)

        assert layers['A'] == 0  # Root
        assert layers['B'] >= 1
        assert layers['C'] >= 1
        assert layers['F'] >= 3  # Deepest

    def test_roots_at_layer_zero(self, sample_adjacency):
        """Test that root nodes are at layer 0."""
        layers = assign_topological_layers(sample_adjacency)

        # A is the only root (no incoming edges)
        assert layers['A'] == 0

    def test_linear_chain_layers(self, linear_adjacency):
        """Test layers on linear chain."""
        layers = assign_topological_layers(linear_adjacency)

        assert layers['A'] == 0
        assert layers['B'] == 1
        assert layers['C'] == 2
        assert layers['D'] == 3


class TestDetectLayerViolations:
    """Tests for detect_layer_violations function."""

    def test_no_violations_in_proper_layers(self, layered_adjacency, sample_layer_assignments):
        """Test that properly layered graph has no violations."""
        violations = detect_layer_violations(layered_adjacency, sample_layer_assignments)

        # Filter only critical violations (lower depending on higher)
        critical = [v for v in violations if v['severity'] == 'critical']
        assert len(critical) == 0

    def test_detects_violations(self, layered_with_violations, sample_layer_assignments):
        """Test that violations are detected."""
        violations = detect_layer_violations(layered_with_violations, sample_layer_assignments)

        critical = [v for v in violations if v['severity'] == 'critical']
        assert len(critical) >= 1

        # Check specific violation: infra:db -> domain:user
        violation_pairs = [(v['source'], v['target']) for v in critical]
        assert ('infra:db', 'domain:user') in violation_pairs


class TestCalculateInstability:
    """Tests for calculate_instability function."""

    def test_stable_node(self, sample_adjacency):
        """Test that node with only incoming edges is stable."""
        metrics = calculate_instability(sample_adjacency)

        # F has no outgoing edges, only incoming
        assert metrics['F']['efferent'] == 0
        assert metrics['F']['afferent'] > 0
        assert metrics['F']['instability'] == 0.0

    def test_unstable_node(self, sample_adjacency):
        """Test that node with only outgoing edges is unstable."""
        metrics = calculate_instability(sample_adjacency)

        # A has only outgoing edges, no incoming
        assert metrics['A']['efferent'] == 2
        assert metrics['A']['afferent'] == 0
        assert metrics['A']['instability'] == 1.0

    def test_mixed_stability(self, sample_adjacency):
        """Test node with both incoming and outgoing edges."""
        metrics = calculate_instability(sample_adjacency)

        # D has both incoming (from B, C) and outgoing (to F)
        assert metrics['D']['afferent'] == 2
        assert metrics['D']['efferent'] == 1
        # I = 1 / (2 + 1) = 0.333...
        assert abs(metrics['D']['instability'] - 1/3) < 0.01


class TestCalculateDegreeCentrality:
    """Tests for calculate_degree_centrality function."""

    def test_centrality_range(self, sample_adjacency):
        """Test that centrality values are in valid range."""
        centrality = calculate_degree_centrality(sample_adjacency)

        for node, score in centrality.items():
            assert 0.0 <= score <= 1.0

    def test_hub_has_higher_centrality(self, sample_adjacency):
        """Test that well-connected nodes have higher centrality."""
        centrality = calculate_degree_centrality(sample_adjacency)

        # D and C are more central than edge nodes
        assert centrality['D'] > centrality['A']
        assert centrality['C'] > centrality['A']


class TestCalculateBetweennessCentrality:
    """Tests for calculate_betweenness_centrality function."""

    def test_centrality_range(self, sample_adjacency):
        """Test that centrality values are in valid range."""
        centrality = calculate_betweenness_centrality(sample_adjacency)

        for node, score in centrality.items():
            assert 0.0 <= score <= 1.0

    def test_bridge_node_has_higher_centrality(self, linear_adjacency):
        """Test that bridge nodes have higher betweenness."""
        centrality = calculate_betweenness_centrality(linear_adjacency)

        # In a linear chain A->B->C->D, B and C are bridges
        assert centrality['B'] > centrality['A']
        assert centrality['C'] > centrality['D']


class TestCalculateAllMetrics:
    """Tests for calculate_all_metrics function."""

    def test_all_metrics_present(self, sample_adjacency):
        """Test that all expected metrics are calculated."""
        metrics = calculate_all_metrics(sample_adjacency)

        expected_keys = {
            'fan_in', 'fan_out', 'coupling_score',
            'afferent', 'efferent', 'instability',
            'degree_centrality', 'betweenness_centrality',
        }

        for node, node_metrics in metrics.items():
            assert expected_keys.issubset(set(node_metrics.keys()))

    def test_all_nodes_have_metrics(self, sample_adjacency):
        """Test that all nodes have metrics."""
        metrics = calculate_all_metrics(sample_adjacency)

        all_nodes = {'A', 'B', 'C', 'D', 'E', 'F'}
        assert set(metrics.keys()) == all_nodes


class TestFindSccsKosaraju:
    """Tests for find_sccs_kosaraju function."""

    def test_dag_has_singleton_sccs(self, sample_adjacency):
        """Test that DAG has only singleton SCCs."""
        sccs = find_sccs_kosaraju(sample_adjacency)

        # All SCCs should be size 1 in a DAG
        for scc in sccs:
            assert len(scc) == 1

    def test_cycle_detected_as_scc(self, cyclic_adjacency):
        """Test that cycles are detected as multi-node SCCs."""
        sccs = find_sccs_kosaraju(cyclic_adjacency)

        # Should have at least one SCC with size > 1
        multi_node_sccs = [scc for scc in sccs if len(scc) > 1]
        assert len(multi_node_sccs) >= 1

        # The cycle A->B->C->A should be in one SCC
        cycle_nodes = {'A', 'B', 'C'}
        found_cycle = any(cycle_nodes.issubset(set(scc)) for scc in sccs)
        assert found_cycle


class TestLouvainCommunities:
    """Tests for louvain_communities function."""

    def test_disconnected_components_separate(self, disconnected_adjacency):
        """Test that disconnected components form separate communities."""
        communities = louvain_communities(disconnected_adjacency)

        # Should have multiple communities
        assert len(communities) >= 2

    def test_all_nodes_assigned(self, sample_adjacency):
        """Test that all nodes are assigned to a community."""
        communities = louvain_communities(sample_adjacency)

        all_nodes = set()
        for comm in communities:
            all_nodes.update(comm)

        expected = {'A', 'B', 'C', 'D', 'E', 'F'}
        assert all_nodes == expected


class TestGetCycleEdges:
    """Tests for get_cycle_edges function."""

    def test_dag_has_no_cycle_edges(self, sample_adjacency):
        """Test that DAG has no cycle edges."""
        cycle_edges = get_cycle_edges(sample_adjacency)
        assert len(cycle_edges) == 0

    def test_simple_cycle_detected(self):
        """Test that a simple 2-node cycle is detected."""
        adjacency = {
            'A': {'B'},
            'B': {'A'},  # A <-> B cycle
        }
        cycle_edges = get_cycle_edges(adjacency)

        assert ('A', 'B') in cycle_edges
        assert ('B', 'A') in cycle_edges
        assert len(cycle_edges) == 2

    def test_three_node_cycle_detected(self):
        """Test that a 3-node cycle is detected."""
        adjacency = {
            'A': {'B'},
            'B': {'C'},
            'C': {'A'},  # A -> B -> C -> A
        }
        cycle_edges = get_cycle_edges(adjacency)

        assert ('A', 'B') in cycle_edges
        assert ('B', 'C') in cycle_edges
        assert ('C', 'A') in cycle_edges
        assert len(cycle_edges) == 3

    def test_longer_cycle_detected(self):
        """Test that a 4-node cycle is detected."""
        adjacency = {
            'A': {'B'},
            'B': {'C'},
            'C': {'D'},
            'D': {'A'},  # A -> B -> C -> D -> A
        }
        cycle_edges = get_cycle_edges(adjacency)

        assert ('A', 'B') in cycle_edges
        assert ('B', 'C') in cycle_edges
        assert ('C', 'D') in cycle_edges
        assert ('D', 'A') in cycle_edges
        assert len(cycle_edges) == 4

    def test_multiple_cycles_detected(self, cyclic_adjacency):
        """Test that multiple independent cycles are detected."""
        cycle_edges = get_cycle_edges(cyclic_adjacency)

        # Should detect edges in both cycles:
        # Cycle 1: A -> B -> C -> A
        # Cycle 2: D -> E -> F -> D
        assert ('A', 'B') in cycle_edges
        assert ('B', 'C') in cycle_edges
        assert ('C', 'A') in cycle_edges
        assert ('D', 'E') in cycle_edges
        assert ('E', 'F') in cycle_edges
        assert ('F', 'D') in cycle_edges

    def test_self_loop_detected(self):
        """Test that self-loops are detected as cycles."""
        adjacency = {
            'A': {'A'},  # Self-loop
            'B': set(),
        }
        cycle_edges = get_cycle_edges(adjacency)

        assert ('A', 'A') in cycle_edges
        assert len(cycle_edges) == 1

    def test_mixed_cycle_and_dag_edges(self):
        """Test graph with both cycle and non-cycle edges."""
        adjacency = {
            'A': {'B', 'X'},
            'B': {'C'},
            'C': {'A'},  # Cycle: A -> B -> C -> A
            'X': {'Y'},  # DAG branch
            'Y': set(),
        }
        cycle_edges = get_cycle_edges(adjacency)

        # Cycle edges should be detected
        assert ('A', 'B') in cycle_edges
        assert ('B', 'C') in cycle_edges
        assert ('C', 'A') in cycle_edges

        # DAG edges should not be in cycle_edges
        assert ('A', 'X') not in cycle_edges
        assert ('X', 'Y') not in cycle_edges

    def test_empty_graph(self):
        """Test empty graph has no cycle edges."""
        cycle_edges = get_cycle_edges({})
        assert len(cycle_edges) == 0


class TestEnumerateCycles:
    """Tests for enumerate_cycles function."""

    def test_dag_has_no_cycles(self, sample_adjacency):
        """Test that DAG has no cycles."""
        cycles = enumerate_cycles(sample_adjacency)
        assert len(cycles) == 0

    def test_simple_cycle_enumerated(self):
        """Test that a simple 3-node cycle is enumerated."""
        adjacency = {
            'A': {'B'},
            'B': {'C'},
            'C': {'A'},
        }
        cycles = enumerate_cycles(adjacency)

        assert len(cycles) == 1
        assert set(cycles[0]) == {'A', 'B', 'C'}
        assert len(cycles[0]) == 3

    def test_longer_cycle_enumerated(self):
        """Test that a longer cycle is enumerated."""
        adjacency = {
            'A': {'B'},
            'B': {'C'},
            'C': {'D'},
            'D': {'E'},
            'E': {'A'},
        }
        cycles = enumerate_cycles(adjacency, max_length=10)

        assert len(cycles) >= 1
        assert len(cycles[0]) == 5

    def test_multiple_cycles_enumerated(self, cyclic_adjacency):
        """Test that multiple cycles are found."""
        cycles = enumerate_cycles(cyclic_adjacency, max_cycles=10)

        # Should find at least 2 cycles (A->B->C->A and D->E->F->D)
        assert len(cycles) >= 2

    def test_max_cycles_limit(self):
        """Test that max_cycles parameter limits results."""
        # Create a graph with many cycles
        adjacency = {
            'A': {'B', 'C', 'D'},
            'B': {'A', 'C'},
            'C': {'A', 'B'},
            'D': {'A'},
        }
        cycles = enumerate_cycles(adjacency, max_cycles=2)

        assert len(cycles) <= 2

    def test_max_length_limit(self):
        """Test that max_length parameter limits cycle length."""
        adjacency = {
            'A': {'B'},
            'B': {'C'},
            'C': {'D'},
            'D': {'E'},
            'E': {'F'},
            'F': {'A'},  # 6-node cycle
        }
        # Only look for cycles up to length 4
        cycles = enumerate_cycles(adjacency, max_length=4)
        assert len(cycles) == 0

        # Now look for longer cycles
        cycles = enumerate_cycles(adjacency, max_length=10)
        assert len(cycles) >= 1

    def test_cycles_sorted_by_length(self):
        """Test that cycles are sorted by length."""
        adjacency = {
            'A': {'B', 'C'},
            'B': {'A', 'C'},  # A-B-A is 2-node cycle
            'C': {'D'},
            'D': {'A'},  # A-C-D-A is 3-node cycle
        }
        cycles = enumerate_cycles(adjacency, max_cycles=10)

        # Cycles should be sorted by length
        for i in range(1, len(cycles)):
            assert len(cycles[i]) >= len(cycles[i-1])
