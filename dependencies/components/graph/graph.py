import fnmatch
import json
import math
import re
import time
from django_components import Component, register

# Time limits for expensive operations (in seconds)
MAX_SCC_TIME = 2.0
MAX_TRANSITIVE_TIME = 2.0
MAX_CYCLE_TIME = 1.0
MAX_TRAVERSAL_TIME = 2.0
MAX_TOPO_SORT_TIME = 2.0
MAX_CENTRALITY_TIME = 5.0
from django.http import HttpRequest, JsonResponse, HttpResponse
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from dependencies.models import Project, Dependency, NodeGroup


# =============================================================================
# Graph Algorithms for Refactoring Analysis
# =============================================================================


def find_sccs_kosaraju(adjacency: dict[str, set[str]], timeout: float = None) -> list[list[str]]:
    """
    Find all strongly connected components using Kosaraju's algorithm (iterative).

    Returns list of SCCs, each SCC is a list of node IDs.
    SCCs with size >= 2 indicate cyclic dependencies.

    Includes timeout to prevent hanging on large graphs.
    """
    if timeout is None:
        timeout = MAX_SCC_TIME

    start_time = time.time()

    # Ensure all nodes are included
    all_nodes = set(adjacency.keys())
    for targets in adjacency.values():
        all_nodes.update(targets)

    if not all_nodes:
        return []

    # Build reverse graph
    reverse_adj: dict[str, set[str]] = {node: set() for node in all_nodes}
    for source, targets in adjacency.items():
        for target in targets:
            reverse_adj[target].add(source)

    # Step 1: DFS on original graph to get finish order
    visited = set()
    finish_order = []

    for start in all_nodes:
        if time.time() - start_time > timeout:
            return []  # Timeout - return empty

        if start in visited:
            continue
        # Iterative DFS
        stack = [(start, False)]
        while stack:
            node, processed = stack.pop()
            if processed:
                finish_order.append(node)
                continue
            if node in visited:
                continue
            visited.add(node)
            stack.append((node, True))  # Mark for post-processing
            for neighbor in adjacency.get(node, set()):
                if neighbor not in visited:
                    stack.append((neighbor, False))

    # Step 2: DFS on reverse graph in reverse finish order
    visited.clear()
    sccs = []

    for node in reversed(finish_order):
        if time.time() - start_time > timeout:
            break  # Timeout - return what we have

        if node in visited:
            continue
        # Iterative DFS on reverse graph
        scc = []
        stack = [node]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            scc.append(current)
            for neighbor in reverse_adj.get(current, set()):
                if neighbor not in visited:
                    stack.append(neighbor)
        sccs.append(scc)

    return sccs


# Alias for backward compatibility
find_sccs_tarjan = find_sccs_kosaraju


def build_condensed_dag(
    adjacency: dict[str, set[str]], sccs: list[list[str]]
) -> tuple[dict[int, set[int]], dict[str, int]]:
    """
    Build a condensed DAG where each SCC is collapsed into a single node.

    Returns:
        - Condensed adjacency list: {scc_index: {target_scc_indices}}
        - Node to SCC mapping: {node_id: scc_index}
    """
    # Map each node to its SCC index
    node_to_scc = {}
    for scc_idx, scc in enumerate(sccs):
        for node in scc:
            node_to_scc[node] = scc_idx

    # Build condensed DAG
    condensed = {i: set() for i in range(len(sccs))}
    for source, targets in adjacency.items():
        source_scc = node_to_scc.get(source)
        if source_scc is None:
            continue
        for target in targets:
            target_scc = node_to_scc.get(target)
            if target_scc is not None and source_scc != target_scc:
                condensed[source_scc].add(target_scc)

    return condensed, node_to_scc


def calculate_node_metrics(adjacency: dict[str, set[str]]) -> dict[str, dict]:
    """
    Calculate fan-in, fan-out, and coupling metrics for each node.

    Returns dict: {node_id: {fan_in, fan_out, coupling_score}}
    """
    # Ensure all nodes are included
    all_nodes = set(adjacency.keys())
    for targets in adjacency.values():
        all_nodes.update(targets)

    metrics = {node: {'fan_in': 0, 'fan_out': 0, 'coupling_score': 0.0} for node in all_nodes}

    # Calculate fan-out (outgoing edges)
    for source, targets in adjacency.items():
        metrics[source]['fan_out'] = len(targets)

    # Calculate fan-in (incoming edges)
    for targets in adjacency.values():
        for target in targets:
            metrics[target]['fan_in'] += 1

    # Calculate coupling score (weighted combination)
    # Higher score = more problematic (high fan-in and fan-out)
    for node, m in metrics.items():
        m['coupling_score'] = m['fan_in'] * 0.6 + m['fan_out'] * 0.4

    return metrics


def louvain_communities(adjacency: dict[str, set[str]], resolution: float = 1.0, timeout: float = 2.0) -> list[list[str]]:
    """
    Simplified Louvain-like community detection based on modularity optimization.

    This is a greedy algorithm that iteratively moves nodes between communities
    to maximize modularity.

    Args:
        adjacency: Graph as adjacency list
        resolution: Higher values produce more communities
        timeout: Maximum time in seconds

    Returns:
        List of communities, each community is a list of node IDs
    """
    start_time = time.time()

    # Build undirected edge set for modularity calculation
    all_nodes = set(adjacency.keys())
    for targets in adjacency.values():
        all_nodes.update(targets)

    nodes = list(all_nodes)
    if not nodes:
        return []

    # Count total edges (treating as undirected)
    edges = set()
    for source, targets in adjacency.items():
        for target in targets:
            edge = tuple(sorted([source, target]))
            edges.add(edge)
    m = len(edges)
    if m == 0:
        # No edges, each node is its own community
        return [[node] for node in nodes]

    # Calculate degree for each node (undirected)
    degree = {node: 0 for node in nodes}
    for source, targets in adjacency.items():
        degree[source] += len(targets)
        for target in targets:
            degree[target] += 1

    # Pre-compute incoming edges for faster lookup
    incoming = {node: set() for node in nodes}
    for source, targets in adjacency.items():
        for target in targets:
            incoming[target].add(source)

    # Initialize: each node in its own community
    node_to_community = {node: i for i, node in enumerate(nodes)}
    communities = {i: {node} for i, node in enumerate(nodes)}

    def modularity_gain(node, target_comm):
        """Calculate modularity gain from moving node to target_comm."""
        current_comm = node_to_community[node]
        if current_comm == target_comm:
            return 0.0

        # Edges from node to target community (outgoing + incoming)
        k_i_in = sum(1 for neighbor in adjacency.get(node, set())
                     if node_to_community.get(neighbor) == target_comm)
        k_i_in += sum(1 for source in incoming.get(node, set())
                      if node_to_community.get(source) == target_comm)

        # Sum of degrees in target community
        sigma_tot = sum(degree[n] for n in communities.get(target_comm, set()))
        k_i = degree[node]

        return (k_i_in / m) - resolution * (sigma_tot * k_i) / (2 * m * m)

    # Greedy optimization
    improved = True
    max_iterations = 20  # Reduced from 100
    iteration = 0

    while improved and iteration < max_iterations:
        if time.time() - start_time > timeout:
            break

        improved = False
        iteration += 1

        for node in nodes:
            current_comm = node_to_community[node]

            # Find neighboring communities (using pre-computed incoming)
            neighbor_comms = set()
            for neighbor in adjacency.get(node, set()):
                neighbor_comms.add(node_to_community[neighbor])
            for source in incoming.get(node, set()):
                neighbor_comms.add(node_to_community[source])

            best_comm = current_comm
            best_gain = 0.0

            for target_comm in neighbor_comms:
                gain = modularity_gain(node, target_comm)
                if gain > best_gain:
                    best_gain = gain
                    best_comm = target_comm

            if best_comm != current_comm:
                # Move node to best community
                communities[current_comm].remove(node)
                if not communities[current_comm]:
                    del communities[current_comm]
                if best_comm not in communities:
                    communities[best_comm] = set()
                communities[best_comm].add(node)
                node_to_community[node] = best_comm
                improved = True

    # Convert to list format
    return [list(comm) for comm in communities.values() if comm]


def get_high_coupling_services(
    adjacency: dict[str, set[str]], threshold_percentile: float = 90
) -> list[tuple[str, dict]]:
    """
    Identify services with high coupling (high fan-in or fan-out).

    Returns list of (node_id, metrics) tuples for services above the threshold.
    """
    metrics = calculate_node_metrics(adjacency)

    # Calculate threshold based on percentile
    scores = [m['coupling_score'] for m in metrics.values()]
    if not scores:
        return []

    scores.sort()
    threshold_idx = int(len(scores) * threshold_percentile / 100)
    threshold = scores[min(threshold_idx, len(scores) - 1)]

    # Return high-coupling services
    return [
        (node, m) for node, m in metrics.items()
        if m['coupling_score'] >= threshold
    ]


def find_cycles_rocha_thatte(adjacency: dict[str, set[str]], max_iterations: int = 100) -> list[list[str]]:
    """
    Find all cycles using the Rocha-Thatte algorithm.

    This is a message-passing algorithm designed for large sparse graphs.
    Each node maintains sequences (paths) and propagates them to neighbors.
    When a node receives a sequence starting with itself, a cycle is detected.

    Args:
        adjacency: Graph as adjacency list {node: {neighbors}}
        max_iterations: Maximum iterations to prevent infinite loops

    Returns:
        List of cycles, where each cycle is a list of node IDs
    """
    if not adjacency:
        return []

    # Initialize: each node starts with a sequence containing just itself
    # sequences[node] = list of paths that are currently at this node
    sequences: dict[str, list[list[str]]] = {
        node: [[node]] for node in adjacency
    }

    cycles: list[list[str]] = []
    seen_cycles: set[tuple[str, ...]] = set()  # To deduplicate cycles

    for iteration in range(max_iterations):
        # New sequences after this iteration
        new_sequences: dict[str, list[list[str]]] = {node: [] for node in adjacency}
        made_progress = False

        # Each node sends its sequences to its neighbors
        for node, paths in sequences.items():
            for neighbor in adjacency.get(node, set()):
                for path in paths:
                    # Extend path to neighbor
                    extended_path = path + [neighbor]

                    # Check if this creates a cycle (path starts with neighbor)
                    if path[0] == neighbor:
                        # Found a cycle! Normalize it for deduplication
                        cycle = path  # Don't include the repeated node

                        # Normalize: rotate to start with smallest node
                        min_idx = cycle.index(min(cycle))
                        normalized = tuple(cycle[min_idx:] + cycle[:min_idx])

                        if normalized not in seen_cycles:
                            seen_cycles.add(normalized)
                            cycles.append(list(normalized))
                            made_progress = True
                    else:
                        # Continue propagating if path doesn't revisit nodes (except potential cycle)
                        if neighbor not in path:
                            new_sequences[neighbor].append(extended_path)
                            made_progress = True

        if not made_progress:
            break

        sequences = new_sequences

    return cycles


def enumerate_cycles(
    adjacency: dict[str, set[str]],
    max_cycles: int = 100,
    max_length: int = 10,
    timeout: float = None
) -> list[list[str]]:
    """
    Enumerate individual cycles in the graph, limited for performance.

    Uses Johnson's algorithm within each SCC to find elementary cycles.

    Args:
        adjacency: Graph as adjacency list
        max_cycles: Maximum number of cycles to return
        max_length: Maximum cycle length to consider
        timeout: Maximum time in seconds

    Returns:
        List of cycles, each cycle is a list of node IDs in order
    """
    if timeout is None:
        timeout = 2.0

    start_time = time.time()
    cycles = []

    # Find SCCs - cycles only exist within SCCs
    sccs = find_sccs_kosaraju(adjacency, timeout=timeout / 2)

    # Filter to SCCs with 2+ nodes (can have cycles)
    cyclic_sccs = [scc for scc in sccs if len(scc) >= 2]

    for scc in cyclic_sccs:
        if time.time() - start_time > timeout or len(cycles) >= max_cycles:
            break

        scc_set = set(scc)

        # Build subgraph for this SCC
        subgraph = {}
        for node in scc:
            neighbors = adjacency.get(node, set()) & scc_set
            if neighbors:
                subgraph[node] = neighbors

        # Find cycles using DFS within this SCC
        # Johnson's algorithm simplified
        for start_node in scc:
            if time.time() - start_time > timeout or len(cycles) >= max_cycles:
                break

            # DFS to find cycles starting from start_node
            stack = [(start_node, [start_node], {start_node})]

            while stack and len(cycles) < max_cycles:
                if time.time() - start_time > timeout:
                    break

                node, path, visited = stack.pop()

                if len(path) > max_length:
                    continue

                for neighbor in subgraph.get(node, set()):
                    if neighbor == start_node and len(path) >= 2:
                        # Found a cycle back to start
                        cycles.append(path[:])
                        if len(cycles) >= max_cycles:
                            break
                    elif neighbor not in visited and neighbor > start_node:
                        # Only explore nodes > start_node to avoid duplicates
                        new_visited = visited | {neighbor}
                        stack.append((neighbor, path + [neighbor], new_visited))

    # Validate cycles - ensure all edges exist
    valid_cycles = []
    for cycle in cycles:
        is_valid = True
        for i in range(len(cycle)):
            source = cycle[i]
            target = cycle[(i + 1) % len(cycle)]
            if target not in adjacency.get(source, set()):
                is_valid = False
                break
        if is_valid:
            valid_cycles.append(cycle)

    # Sort cycles by length
    valid_cycles.sort(key=len)

    return valid_cycles


def get_cycle_edges(adjacency: dict[str, set[str]], timeout: float = None) -> set[tuple[str, str]]:
    """
    Find all edges that are part of any cycle using SCC detection.

    An edge is in a cycle if both endpoints are in the same SCC of size >= 2,
    or if it's a self-loop.
    This is much faster than enumerating all cycles (O(V+E) vs exponential).

    Returns a set of (source, target) tuples.
    """
    if timeout is None:
        timeout = MAX_CYCLE_TIME

    start_time = time.time()

    cycle_edges = set()

    # First, detect self-loops (A -> A) - these are cycles of length 1
    for source, targets in adjacency.items():
        if source in targets:
            cycle_edges.add((source, source))

    # Find SCCs using Kosaraju's algorithm
    sccs = find_sccs_kosaraju(adjacency, timeout=timeout)

    # Check timeout
    if time.time() - start_time > timeout:
        return cycle_edges  # Return at least the self-loops we found

    # Build a mapping from node to its SCC (only for SCCs with cycles)
    node_to_scc = {}
    for scc_idx, scc in enumerate(sccs):
        if len(scc) >= 2:  # Only SCCs with 2+ nodes have cycles
            for node in scc:
                node_to_scc[node] = scc_idx

    # An edge is in a cycle if both endpoints are in the same multi-node SCC
    for source, targets in adjacency.items():
        source_scc = node_to_scc.get(source)
        if source_scc is not None:
            for target in targets:
                if node_to_scc.get(target) == source_scc:
                    cycle_edges.add((source, target))

    return cycle_edges


def matches_filter(text: str, pattern: str) -> bool:
    """
    Check if text matches the filter pattern.

    Supports:
    - Simple substring match: "foo" matches "foobar"
    - Wildcard patterns: "foo:*" matches "foo:bar", "*:foo:*" matches "x:foo:y"
    """
    text_lower = text.lower()
    pattern_lower = pattern.lower()

    if '*' in pattern:
        # Convert to regex: * becomes .*, escape other special chars
        regex_pattern = fnmatch.translate(pattern_lower)
        return bool(re.match(regex_pattern, text_lower))
    else:
        # Simple substring match
        return pattern_lower in text_lower


def calculate_optimal_eps(points: list[dict], target_clusters: int, min_samples: int = 2) -> float:
    """
    Calculate an eps value that results in approximately target_clusters clusters.
    Uses binary search to find the optimal eps.
    """
    if len(points) < 2:
        return 150.0

    # Calculate all pairwise distances
    distances = []
    for i, p1 in enumerate(points):
        for p2 in points[i + 1:]:
            d = math.sqrt((p1['x'] - p2['x'])**2 + (p1['y'] - p2['y'])**2)
            distances.append(d)

    if not distances:
        return 150.0

    distances.sort()

    # Binary search for optimal eps
    min_eps = distances[0] if distances else 1.0
    max_eps = distances[-1] if distances else 1000.0

    best_eps = (min_eps + max_eps) / 2
    best_diff = float('inf')

    for _ in range(20):  # 20 iterations of binary search
        mid_eps = (min_eps + max_eps) / 2
        clusters = dbscan_cluster(points, mid_eps, min_samples)
        num_clusters = len(clusters)

        diff = abs(num_clusters - target_clusters)
        if diff < best_diff:
            best_diff = diff
            best_eps = mid_eps

        if num_clusters == target_clusters:
            return mid_eps
        elif num_clusters > target_clusters:
            # Too many clusters, increase eps to merge them
            min_eps = mid_eps
        else:
            # Too few clusters, decrease eps to split them
            max_eps = mid_eps

    return best_eps


def dbscan_cluster(points: list[dict], eps: float, min_samples: int) -> list[list[str]]:
    """
    Simple DBSCAN clustering implementation.
    Returns list of clusters, each cluster is a list of node IDs.
    """
    def distance(p1, p2):
        return math.sqrt((p1['x'] - p2['x'])**2 + (p1['y'] - p2['y'])**2)

    def get_neighbors(point_idx):
        neighbors = []
        for i, p in enumerate(points):
            if i != point_idx and distance(points[point_idx], p) <= eps:
                neighbors.append(i)
        return neighbors

    n = len(points)
    labels = [-1] * n  # -1 = unvisited, -2 = noise, >= 0 = cluster id
    cluster_id = 0

    for i in range(n):
        if labels[i] != -1:
            continue

        neighbors = get_neighbors(i)
        if len(neighbors) < min_samples:
            labels[i] = -2  # noise
            continue

        # Start new cluster
        labels[i] = cluster_id
        seed_set = list(neighbors)

        while seed_set:
            q = seed_set.pop(0)
            if labels[q] == -2:
                labels[q] = cluster_id
            if labels[q] != -1:
                continue

            labels[q] = cluster_id
            q_neighbors = get_neighbors(q)
            if len(q_neighbors) >= min_samples:
                seed_set.extend(q_neighbors)

        cluster_id += 1

    # Group points by cluster
    clusters = {}
    for i, label in enumerate(labels):
        if label >= 0:
            clusters.setdefault(label, []).append(points[i]['id'])

    return list(clusters.values())


# =============================================================================
# Graph Traversal and Topological Algorithms
# =============================================================================


def traverse_graph(
    adjacency: dict[str, set[str]],
    start_node: str,
    direction: str = 'downstream',
    algorithm: str = 'bfs',
    max_depth: int = None,
    timeout: float = None,
) -> dict[int, list[str]]:
    """
    Traverse graph from start_node with depth tracking.

    Args:
        adjacency: Graph as adjacency list {node: {neighbors}}
        start_node: Node to start traversal from
        direction: 'downstream' (outgoing), 'upstream' (incoming), or 'both'
        algorithm: 'bfs' (breadth-first) or 'dfs' (depth-first)
        max_depth: Maximum traversal depth (None for unlimited)
        timeout: Maximum time in seconds

    Returns:
        Dict mapping depth level to list of node IDs at that depth.
        {0: [start_node], 1: [direct_deps], 2: [transitive_deps], ...}
    """
    if timeout is None:
        timeout = MAX_TRAVERSAL_TIME

    start_time = time.time()

    # Build reverse adjacency for upstream traversal
    if direction in ('upstream', 'both'):
        reverse_adj: dict[str, set[str]] = {}
        all_nodes = set(adjacency.keys())
        for targets in adjacency.values():
            all_nodes.update(targets)
        for node in all_nodes:
            reverse_adj[node] = set()
        for source, targets in adjacency.items():
            for target in targets:
                reverse_adj[target].add(source)
    else:
        reverse_adj = {}

    # Get neighbors based on direction
    def get_neighbors(node: str) -> set[str]:
        neighbors = set()
        if direction in ('downstream', 'both'):
            neighbors.update(adjacency.get(node, set()))
        if direction in ('upstream', 'both'):
            neighbors.update(reverse_adj.get(node, set()))
        return neighbors

    # Check if start node exists
    all_nodes = set(adjacency.keys())
    for targets in adjacency.values():
        all_nodes.update(targets)

    if start_node not in all_nodes:
        return {0: [start_node]}

    result: dict[int, list[str]] = {0: [start_node]}
    visited = {start_node}

    if algorithm == 'bfs':
        # BFS with level tracking
        current_level = [start_node]
        depth = 0

        while current_level:
            if time.time() - start_time > timeout:
                break
            if max_depth is not None and depth >= max_depth:
                break

            next_level = []
            for node in current_level:
                for neighbor in get_neighbors(node):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_level.append(neighbor)

            if next_level:
                depth += 1
                result[depth] = next_level
            current_level = next_level

    else:  # DFS
        # DFS with depth tracking using iterative approach
        stack = [(start_node, 0)]
        depth_nodes: dict[int, list[str]] = {0: [start_node]}

        while stack:
            if time.time() - start_time > timeout:
                break

            node, depth = stack.pop()

            if max_depth is not None and depth >= max_depth:
                continue

            for neighbor in get_neighbors(node):
                if neighbor not in visited:
                    visited.add(neighbor)
                    new_depth = depth + 1
                    if new_depth not in depth_nodes:
                        depth_nodes[new_depth] = []
                    depth_nodes[new_depth].append(neighbor)
                    stack.append((neighbor, new_depth))

        result = depth_nodes

    return result


def topological_sort(
    adjacency: dict[str, set[str]],
    timeout: float = None,
) -> tuple[list[str], bool, list[tuple[str, str]]]:
    """
    Compute topological ordering using Kahn's algorithm.

    Args:
        adjacency: Graph as adjacency list {node: {neighbors}}
        timeout: Maximum time in seconds

    Returns:
        - Ordered list of nodes (partial if cycles exist)
        - Boolean indicating if graph is a DAG (True = no cycles)
        - List of back edges that would need to be removed for DAG (if cycles exist)
    """
    if timeout is None:
        timeout = MAX_TOPO_SORT_TIME

    start_time = time.time()

    # Get all nodes
    all_nodes = set(adjacency.keys())
    for targets in adjacency.values():
        all_nodes.update(targets)

    if not all_nodes:
        return [], True, []

    # Calculate in-degree for each node
    in_degree = {node: 0 for node in all_nodes}
    for targets in adjacency.values():
        for target in targets:
            in_degree[target] += 1

    # Queue of nodes with no incoming edges
    queue = [node for node in all_nodes if in_degree[node] == 0]
    result = []

    while queue:
        if time.time() - start_time > timeout:
            break

        # Sort queue for deterministic output
        queue.sort()
        node = queue.pop(0)
        result.append(node)

        for neighbor in adjacency.get(node, set()):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # Check if we processed all nodes (DAG) or have cycles
    is_dag = len(result) == len(all_nodes)

    # Find back edges (edges that create cycles)
    back_edges = []
    if not is_dag:
        # Nodes with remaining in-degree are in cycles
        cycle_nodes = {node for node, degree in in_degree.items() if degree > 0}
        for source, targets in adjacency.items():
            if source in cycle_nodes:
                for target in targets:
                    if target in cycle_nodes:
                        back_edges.append((source, target))

    return result, is_dag, back_edges


def assign_topological_layers(
    adjacency: dict[str, set[str]],
    timeout: float = None,
) -> dict[str, int]:
    """
    Assign layer depth to each node based on longest path from roots.

    Nodes with no incoming edges are at layer 0.
    Each other node is at max(predecessors' layers) + 1.

    Args:
        adjacency: Graph as adjacency list
        timeout: Maximum time in seconds

    Returns:
        Dict mapping node ID to layer depth (0 = root/no incoming edges).
    """
    if timeout is None:
        timeout = MAX_TOPO_SORT_TIME

    start_time = time.time()

    # Get all nodes
    all_nodes = set(adjacency.keys())
    for targets in adjacency.values():
        all_nodes.update(targets)

    if not all_nodes:
        return {}

    # Build reverse adjacency
    reverse_adj: dict[str, set[str]] = {node: set() for node in all_nodes}
    for source, targets in adjacency.items():
        for target in targets:
            reverse_adj[target].add(source)

    # Initialize layers
    layers: dict[str, int] = {}

    # BFS from roots (nodes with no incoming edges)
    roots = [node for node in all_nodes if not reverse_adj[node]]

    # If no roots (all in cycles), pick arbitrary starting points
    if not roots:
        roots = list(all_nodes)[:1]

    for root in roots:
        layers[root] = 0

    # Process in topological order
    queue = list(roots)
    processed = set()

    while queue:
        if time.time() - start_time > timeout:
            break

        node = queue.pop(0)
        if node in processed:
            continue
        processed.add(node)

        current_layer = layers.get(node, 0)

        for neighbor in adjacency.get(node, set()):
            # Update neighbor's layer to be at least current + 1
            if neighbor not in layers or layers[neighbor] < current_layer + 1:
                layers[neighbor] = current_layer + 1
            if neighbor not in processed:
                queue.append(neighbor)

    # Handle any unprocessed nodes (in cycles)
    for node in all_nodes:
        if node not in layers:
            layers[node] = 0

    return layers


def detect_layer_violations(
    adjacency: dict[str, set[str]],
    layer_assignments: dict[str, int],
) -> list[dict]:
    """
    Detect edges that violate layer rules.

    A violation occurs when:
    - A lower layer depends on a higher layer (critical)
    - Same layer has circular dependencies (warning)

    Args:
        adjacency: Graph as adjacency list
        layer_assignments: Dict mapping node ID to layer level (lower = lower in architecture)

    Returns:
        List of violation dicts: {source, target, source_layer, target_layer, severity}
    """
    violations = []

    for source, targets in adjacency.items():
        source_layer = layer_assignments.get(source)
        if source_layer is None:
            continue

        for target in targets:
            target_layer = layer_assignments.get(target)
            if target_layer is None:
                continue

            # Check for violations
            if source_layer < target_layer:
                # Lower layer depending on higher layer - critical violation
                violations.append({
                    'source': source,
                    'target': target,
                    'source_layer': source_layer,
                    'target_layer': target_layer,
                    'severity': 'critical',
                    'reason': f'Layer {source_layer} depends on layer {target_layer}',
                })
            elif source_layer == target_layer:
                # Same layer - check if it creates a cycle (warning)
                # For same-layer, we just note it as potential coupling
                violations.append({
                    'source': source,
                    'target': target,
                    'source_layer': source_layer,
                    'target_layer': target_layer,
                    'severity': 'info',
                    'reason': 'Same-layer dependency',
                })

    return violations


# =============================================================================
# Extended Metrics (Robert Martin, Centrality)
# =============================================================================


def calculate_instability(adjacency: dict[str, set[str]]) -> dict[str, dict]:
    """
    Calculate Robert Martin's instability metric for each node.

    I = Ce / (Ca + Ce) where:
    - Ca = afferent coupling (incoming dependencies)
    - Ce = efferent coupling (outgoing dependencies)

    Instability ranges from 0 (stable) to 1 (unstable).
    - I=0: maximally stable (only incoming, no outgoing)
    - I=1: maximally unstable (only outgoing, no incoming)

    Args:
        adjacency: Graph as adjacency list

    Returns:
        Dict: {node_id: {afferent, efferent, instability}}
    """
    # Get all nodes
    all_nodes = set(adjacency.keys())
    for targets in adjacency.values():
        all_nodes.update(targets)

    metrics = {node: {'afferent': 0, 'efferent': 0, 'instability': 0.0} for node in all_nodes}

    # Calculate efferent coupling (outgoing)
    for source, targets in adjacency.items():
        metrics[source]['efferent'] = len(targets)

    # Calculate afferent coupling (incoming)
    for targets in adjacency.values():
        for target in targets:
            metrics[target]['afferent'] += 1

    # Calculate instability
    for node, m in metrics.items():
        ca = m['afferent']
        ce = m['efferent']
        if ca + ce > 0:
            m['instability'] = ce / (ca + ce)
        else:
            m['instability'] = 0.0  # Isolated node

    return metrics


def calculate_degree_centrality(adjacency: dict[str, set[str]]) -> dict[str, float]:
    """
    Calculate degree centrality for each node.

    Degree centrality = (in_degree + out_degree) / (2 * (n - 1))
    where n is the number of nodes.

    Args:
        adjacency: Graph as adjacency list

    Returns:
        Dict mapping node ID to centrality score (0.0 to 1.0).
    """
    # Get all nodes
    all_nodes = set(adjacency.keys())
    for targets in adjacency.values():
        all_nodes.update(targets)

    n = len(all_nodes)
    if n <= 1:
        return {node: 0.0 for node in all_nodes}

    # Calculate degrees
    out_degree = {node: len(adjacency.get(node, set())) for node in all_nodes}
    in_degree = {node: 0 for node in all_nodes}
    for targets in adjacency.values():
        for target in targets:
            in_degree[target] += 1

    # Normalize
    max_possible = 2 * (n - 1)  # Max possible degree in directed graph
    centrality = {}
    for node in all_nodes:
        total_degree = in_degree[node] + out_degree[node]
        centrality[node] = total_degree / max_possible if max_possible > 0 else 0.0

    return centrality


def calculate_betweenness_centrality(
    adjacency: dict[str, set[str]],
    timeout: float = None,
) -> dict[str, float]:
    """
    Calculate betweenness centrality for each node using Brandes' algorithm.

    Betweenness centrality measures how often a node lies on shortest paths
    between other nodes. High betweenness indicates a "bridge" or "bottleneck".

    Args:
        adjacency: Graph as adjacency list
        timeout: Maximum time in seconds

    Returns:
        Dict mapping node ID to centrality score (normalized 0.0 to 1.0).
    """
    if timeout is None:
        timeout = MAX_CENTRALITY_TIME

    start_time = time.time()

    # Get all nodes
    all_nodes = set(adjacency.keys())
    for targets in adjacency.values():
        all_nodes.update(targets)

    nodes = list(all_nodes)
    n = len(nodes)

    if n <= 2:
        return {node: 0.0 for node in nodes}

    # Initialize betweenness
    betweenness = {node: 0.0 for node in nodes}

    # Brandes' algorithm
    for s in nodes:
        if time.time() - start_time > timeout:
            break

        # Single-source shortest paths
        stack = []
        predecessors: dict[str, list[str]] = {node: [] for node in nodes}
        sigma = {node: 0 for node in nodes}  # Number of shortest paths
        sigma[s] = 1
        dist = {node: -1 for node in nodes}  # Distance from s
        dist[s] = 0

        queue = [s]
        while queue:
            v = queue.pop(0)
            stack.append(v)
            for w in adjacency.get(v, set()):
                # Path discovery
                if dist[w] < 0:
                    dist[w] = dist[v] + 1
                    queue.append(w)
                # Path counting
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
                    predecessors[w].append(v)

        # Back-propagation
        delta = {node: 0.0 for node in nodes}
        while stack:
            w = stack.pop()
            for v in predecessors[w]:
                if sigma[w] > 0:
                    delta[v] += (sigma[v] / sigma[w]) * (1 + delta[w])
            if w != s:
                betweenness[w] += delta[w]

    # Normalize by (n-1)(n-2) for directed graphs
    norm = (n - 1) * (n - 2) if n > 2 else 1
    for node in nodes:
        betweenness[node] /= norm

    return betweenness


def calculate_all_metrics(
    adjacency: dict[str, set[str]],
    timeout: float = 10.0,
) -> dict[str, dict]:
    """
    Calculate all metrics for each node in one pass.

    Combines: fan_in, fan_out, coupling_score, afferent, efferent,
    instability, degree_centrality, betweenness_centrality

    Args:
        adjacency: Graph as adjacency list
        timeout: Maximum total time in seconds

    Returns:
        Dict: {node_id: {all metrics}}
    """
    start_time = time.time()

    # Get all nodes
    all_nodes = set(adjacency.keys())
    for targets in adjacency.values():
        all_nodes.update(targets)

    # Initialize with basic metrics
    basic = calculate_node_metrics(adjacency)
    instability = calculate_instability(adjacency)

    # Combine metrics
    metrics = {}
    for node in all_nodes:
        metrics[node] = {
            'fan_in': basic[node]['fan_in'],
            'fan_out': basic[node]['fan_out'],
            'coupling_score': basic[node]['coupling_score'],
            'afferent': instability[node]['afferent'],
            'efferent': instability[node]['efferent'],
            'instability': instability[node]['instability'],
        }

    # Add degree centrality (fast)
    if time.time() - start_time < timeout:
        degree = calculate_degree_centrality(adjacency)
        for node in all_nodes:
            metrics[node]['degree_centrality'] = degree[node]

    # Add betweenness centrality (slower)
    remaining_time = timeout - (time.time() - start_time)
    if remaining_time > 0:
        betweenness = calculate_betweenness_centrality(adjacency, timeout=remaining_time)
        for node in all_nodes:
            metrics[node]['betweenness_centrality'] = betweenness.get(node, 0.0)

    # Add topological info
    remaining_time = timeout - (time.time() - start_time)
    if remaining_time > 0:
        ordering, is_dag, _ = topological_sort(adjacency, timeout=remaining_time / 2)
        layers = assign_topological_layers(adjacency, timeout=remaining_time / 2)

        for i, node in enumerate(ordering):
            if node in metrics:
                metrics[node]['topological_order'] = i

        for node, layer in layers.items():
            if node in metrics:
                metrics[node]['layer_depth'] = layer

    return metrics


@register("dependency_graph")
class DependencyGraph(Component):
    template_name = "graph/graph.html"

    def get_context_data(self, height="600px"):
        graph_data = self.get_graph_data()
        return {
            "height": height,
            "graph_data": json.dumps(graph_data),
            "has_positions": graph_data.get("has_positions", False),
        }

    @staticmethod
    def get_graph_data() -> dict:
        """Build Cytoscape-compatible graph data from database."""
        nodes = []
        edges = []
        has_positions = False

        # Add group nodes first
        for group in NodeGroup.objects.all():
            node_data = {
                "data": {
                    "id": group.key,
                    "label": group.name,
                    "isGroup": True,
                }
            }
            if group.position_x is not None and group.position_y is not None:
                node_data["position"] = {"x": group.position_x, "y": group.position_y}
                has_positions = True
            nodes.append(node_data)

        # Add project nodes
        for project in Project.objects.select_related('group').all():
            node_data = {
                "data": {
                    "id": project.key,
                    "label": project.name,
                    "description": project.description,
                }
            }
            if project.group:
                node_data["data"]["parent"] = project.group.key
            if project.position_x is not None and project.position_y is not None:
                node_data["position"] = {"x": project.position_x, "y": project.position_y}
                has_positions = True
            nodes.append(node_data)

        deps = list(Dependency.objects.select_related('source', 'target').all())

        # Build adjacency list
        adjacency: dict[str, set[str]] = {}
        for dep in deps:
            adjacency.setdefault(dep.source.key, set()).add(dep.target.key)

        # Check which edges are transitive
        transitive_edges = DependencyGraph._find_transitive_edges(adjacency)

        # Check which edges are part of cycles
        cycle_edges = get_cycle_edges(adjacency)

        for dep in deps:
            edge_key = (dep.source.key, dep.target.key)
            edges.append({
                "data": {
                    "id": f"{dep.source.key}->{dep.target.key}",
                    "source": dep.source.key,
                    "target": dep.target.key,
                    "scope": dep.scope,
                    "transitive": edge_key in transitive_edges,
                    "inCycle": edge_key in cycle_edges,
                }
            })

        return {"nodes": nodes, "edges": edges, "has_positions": has_positions}

    @staticmethod
    def _find_transitive_edges(adjacency: dict[str, set[str]]) -> set[tuple[str, str]]:
        """
        Find edges that are transitive using proper transitive reduction.

        An edge is transitive if it can be removed while still maintaining
        reachability. This algorithm processes edges and only marks an edge
        as transitive if the target is still reachable without it.

        Includes time limit to prevent UI hanging on large graphs.
        """
        start_time = time.time()

        # Make a mutable copy of the adjacency list
        adj_copy = {k: set(v) for k, v in adjacency.items()}
        transitive = set()

        # Get all edges
        all_edges = [(u, v) for u, targets in adjacency.items() for v in targets]

        for u, v in all_edges:
            # Check time limit
            if time.time() - start_time > MAX_TRANSITIVE_TIME:
                break

            # Temporarily remove this edge
            if v in adj_copy.get(u, set()):
                adj_copy[u].remove(v)

                # Check if v is still reachable from u without this edge
                if DependencyGraph._is_reachable(u, v, adj_copy):
                    # Edge is redundant, keep it removed and mark as transitive
                    transitive.add((u, v))
                else:
                    # Edge is necessary, restore it
                    adj_copy[u].add(v)

        return transitive

    @staticmethod
    def _is_reachable(source: str, target: str, adjacency: dict[str, set[str]]) -> bool:
        """Check if target is reachable from source using BFS."""
        if source == target:
            return True

        visited = {source}
        queue = list(adjacency.get(source, set()))
        visited.update(queue)

        while queue:
            current = queue.pop(0)
            if current == target:
                return True
            for neighbor in adjacency.get(current, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        return False

    @staticmethod
    def htmx_graph_data(request: HttpRequest):
        """Return graph data as JSON for HTMX refresh."""
        return JsonResponse(DependencyGraph.get_graph_data())

    @staticmethod
    def htmx_graph(request: HttpRequest):
        """Return full graph component for HTMX swap."""
        return DependencyGraph.render_to_response(
            kwargs={"height": "650px"},
            request=request
        )

    @staticmethod
    @csrf_exempt
    def htmx_save_layout(request: HttpRequest):
        """Save node positions and groups."""
        if request.method != 'POST':
            return HttpResponse(status=405)

        try:
            data = json.loads(request.body)
            nodes = data.get('nodes', [])
            groups = data.get('groups', [])

            # Save/create groups
            group_keys = set()
            for group_data in groups:
                group_key = group_data['id']
                group_keys.add(group_key)
                NodeGroup.objects.update_or_create(
                    key=group_key,
                    defaults={
                        'name': group_data.get('label', group_key),
                        'position_x': group_data.get('x'),
                        'position_y': group_data.get('y'),
                    }
                )

            # Delete groups that no longer exist
            NodeGroup.objects.exclude(key__in=group_keys).delete()

            # Update project positions and groups
            for node_data in nodes:
                node_id = node_data['id']
                parent_key = node_data.get('parent')
                group = None
                if parent_key:
                    group = NodeGroup.objects.filter(key=parent_key).first()

                Project.objects.filter(key=node_id).update(
                    position_x=node_data.get('x'),
                    position_y=node_data.get('y'),
                    group=group,
                )

            return HttpResponse(
                '<div class="alert alert-success alert-dismissible fade show">'
                '<i class="bi bi-check-circle me-2"></i>'
                'Layout saved.'
                '<button type="button" class="btn-close" data-bs-dismiss="alert"></button>'
                '</div>'
            )
        except Exception as e:
            return HttpResponse(
                f'<div class="alert alert-danger alert-dismissible fade show">'
                f'<i class="bi bi-x-circle me-2"></i>'
                f'Save failed: {e}'
                f'<button type="button" class="btn-close" data-bs-dismiss="alert"></button>'
                f'</div>'
            )


    @staticmethod
    @csrf_exempt
    def htmx_cluster(request: HttpRequest):
        """Automatically cluster nodes based on positions."""
        if request.method != 'POST':
            return HttpResponse(status=405)

        try:
            data = json.loads(request.body)
            nodes = data.get('nodes', [])
            eps_param = data.get('eps', 'auto')  # 'auto' or a number
            min_samples = int(data.get('min_samples', 2))  # Min nodes per cluster

            # Filter out nodes that are already in groups (only cluster ungrouped nodes)
            ungrouped = [n for n in nodes if not n.get('parent')]

            if len(ungrouped) < min_samples:
                return HttpResponse(
                    '<div class="alert alert-warning alert-dismissible fade show">'
                    '<i class="bi bi-exclamation-triangle me-2"></i>'
                    'Not enough ungrouped nodes to cluster.'
                    '<button type="button" class="btn-close" data-bs-dismiss="alert"></button>'
                    '</div>'
                )

            # Calculate eps: auto mode targets n/10 clusters
            if eps_param == 'auto':
                target_clusters = max(2, len(ungrouped) // 10)
                eps = calculate_optimal_eps(ungrouped, target_clusters, min_samples)
            else:
                eps = float(eps_param)

            # Run clustering
            clusters = dbscan_cluster(ungrouped, eps, min_samples)

            if not clusters:
                return HttpResponse(
                    '<div class="alert alert-info alert-dismissible fade show">'
                    '<i class="bi bi-info-circle me-2"></i>'
                    'No clusters found. Try adjusting the distance threshold.'
                    '<button type="button" class="btn-close" data-bs-dismiss="alert"></button>'
                    '</div>'
                )

            # Create groups for each cluster
            # First, filter valid clusters
            valid_clusters = [c for c in clusters if len(c) >= min_samples]

            if not valid_clusters:
                return HttpResponse(
                    '<div class="alert alert-info alert-dismissible fade show">'
                    'No valid clusters found.'
                    '<button type="button" class="btn-close" data-bs-dismiss="alert"></button>'
                    '</div>'
                )

            # Calculate grid layout for distributing groups
            num_clusters = len(valid_clusters)
            cols = math.ceil(math.sqrt(num_clusters))
            rows = math.ceil(num_clusters / cols)

            # Grid spacing (pixels between group centers)
            grid_spacing_x = 400
            grid_spacing_y = 300

            # Starting position (top-left of grid)
            start_x = 200
            start_y = 200

            cluster_count = 0
            for i, cluster_node_ids in enumerate(valid_clusters):
                # Calculate grid position for this cluster
                row = i // cols
                col = i % cols
                grid_x = start_x + col * grid_spacing_x
                grid_y = start_y + row * grid_spacing_y

                # Create group at grid position
                group_key = f"cluster-{i}"
                group, _ = NodeGroup.objects.update_or_create(
                    key=group_key,
                    defaults={
                        'name': f"Cluster {i + 1}",
                        'position_x': grid_x,
                        'position_y': grid_y,
                    }
                )

                # Assign projects to group and distribute them within the group
                cluster_nodes = [n for n in ungrouped if n['id'] in cluster_node_ids]
                for j, node in enumerate(cluster_nodes):
                    # Arrange nodes in a small grid within the group
                    inner_cols = math.ceil(math.sqrt(len(cluster_nodes)))
                    inner_row = j // inner_cols
                    inner_col = j % inner_cols
                    node_x = grid_x + (inner_col - inner_cols / 2) * 80
                    node_y = grid_y + (inner_row - len(cluster_nodes) / inner_cols / 2) * 60

                    Project.objects.filter(key=node['id']).update(
                        group=group,
                        position_x=node_x,
                        position_y=node_y,
                    )

                cluster_count += 1

            eps_info = f" (threshold: {eps:.1f})" if eps_param == 'auto' else ""
            return HttpResponse(
                f'<div class="alert alert-success alert-dismissible fade show">'
                f'<i class="bi bi-check-circle me-2"></i>'
                f'Created {cluster_count} clusters{eps_info}.'
                f'<button type="button" class="btn-close" data-bs-dismiss="alert"></button>'
                f'</div>'
            )
        except Exception as e:
            return HttpResponse(
                f'<div class="alert alert-danger alert-dismissible fade show">'
                f'<i class="bi bi-x-circle me-2"></i>'
                f'Clustering failed: {e}'
                f'<button type="button" class="btn-close" data-bs-dismiss="alert"></button>'
                f'</div>'
            )

    @staticmethod
    @csrf_exempt
    def htmx_filter(request: HttpRequest):
        """Filter graph to show only matching projects and their connections."""
        if request.method != 'POST':
            return HttpResponse(status=405)

        try:
            data = json.loads(request.body)
            filter_terms = data.get('filter', [])

            if not filter_terms:
                return JsonResponse(DependencyGraph.get_graph_data())

            # Find matching projects (by key or name)
            # Supports wildcards: "foo:*" matches "foo:bar", "*:foo:*" matches "x:foo:y"
            matching_projects = set()
            all_projects = {p.key: p for p in Project.objects.select_related('group').all()}

            for project_key, project in all_projects.items():
                for term in filter_terms:
                    if matches_filter(project_key, term) or matches_filter(project.name, term):
                        matching_projects.add(project_key)
                        break

            if not matching_projects:
                return JsonResponse({"nodes": [], "edges": [], "has_positions": False})

            # Find all connected projects (dependencies and dependents)
            connected_projects = set(matching_projects)
            deps = list(Dependency.objects.select_related('source', 'target').all())

            for dep in deps:
                if dep.source.key in matching_projects:
                    connected_projects.add(dep.target.key)
                if dep.target.key in matching_projects:
                    connected_projects.add(dep.source.key)

            # Build filtered graph data
            nodes = []
            groups_needed = set()

            for project_key in connected_projects:
                project = all_projects.get(project_key)
                if not project:
                    continue

                # Mark if this node directly matches the filter (vs just connected)
                is_matched = project_key in matching_projects

                node_data = {
                    "data": {
                        "id": project.key,
                        "label": project.name,
                        "description": project.description,
                        "matched": is_matched,
                    }
                }
                if project.group:
                    node_data["data"]["parent"] = project.group.key
                    groups_needed.add(project.group.key)
                if project.position_x is not None and project.position_y is not None:
                    node_data["position"] = {"x": project.position_x, "y": project.position_y}
                nodes.append(node_data)

            # Add group nodes
            for group in NodeGroup.objects.filter(key__in=groups_needed):
                node_data = {
                    "data": {
                        "id": group.key,
                        "label": group.name,
                        "isGroup": True,
                    }
                }
                if group.position_x is not None and group.position_y is not None:
                    node_data["position"] = {"x": group.position_x, "y": group.position_y}
                nodes.append(node_data)

            # Build edges (only between visible nodes)
            edges = []
            adjacency: dict[str, set[str]] = {}
            for dep in deps:
                if dep.source.key in connected_projects and dep.target.key in connected_projects:
                    adjacency.setdefault(dep.source.key, set()).add(dep.target.key)

            transitive_edges = DependencyGraph._find_transitive_edges(adjacency)
            cycle_edges = get_cycle_edges(adjacency)

            for dep in deps:
                if dep.source.key in connected_projects and dep.target.key in connected_projects:
                    edge_key = (dep.source.key, dep.target.key)
                    edges.append({
                        "data": {
                            "id": f"{dep.source.key}->{dep.target.key}",
                            "source": dep.source.key,
                            "target": dep.target.key,
                            "scope": dep.scope,
                            "transitive": edge_key in transitive_edges,
                            "inCycle": edge_key in cycle_edges,
                        }
                    })

            return JsonResponse({
                "nodes": nodes,
                "edges": edges,
                "has_positions": any("position" in n for n in nodes),
            })
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    @classmethod
    def get_urls(cls):
        return [
            path('graph/data/', cls.htmx_graph_data, name='graph_data'),
            path('graph/', cls.htmx_graph, name='graph_refresh'),
            path('graph/save/', cls.htmx_save_layout, name='graph_save'),
            path('graph/cluster/', cls.htmx_cluster, name='graph_cluster'),
            path('graph/filter/', cls.htmx_filter, name='graph_filter'),
        ]
