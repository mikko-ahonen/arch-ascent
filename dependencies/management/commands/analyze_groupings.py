"""
Analyze existing groupings in the codebase to understand current structure.

Reports on:
- GitLab group hierarchy and distribution
- Maven groupId patterns
- Naming conventions (prefixes/suffixes)
- Dependency clusters and hubs
- Activity distribution
"""
import json
import re
from collections import defaultdict, Counter
from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
import random

from dependencies.models import Component, Dependency, NodeGroup, GitProject


class Command(BaseCommand):
    help = 'Analyze existing groupings and structure in the project data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--json',
            action='store_true',
            help='Output as JSON instead of human-readable format',
        )
        parser.add_argument(
            '--output',
            type=str,
            help='Write output to file',
        )

    def handle(self, *args, **options):
        report = {
            'summary': self._build_summary(),
            'gitlab_groups': self._analyze_gitlab_groups(),
            'maven_domains': self._analyze_maven_domains(),
            'naming_patterns': self._analyze_naming_patterns(),
            'dependency_clusters': self._analyze_dependency_clusters(),
            'activity': self._analyze_activity(),
        }

        if options['json']:
            output = json.dumps(report, indent=2, default=str)
        else:
            output = self._format_report(report)

        if options['output']:
            with open(options['output'], 'w') as f:
                f.write(output)
            self.stdout.write(f"Report written to {options['output']}")
        else:
            self.stdout.write(output)

    def _build_summary(self):
        """Build high-level summary stats."""
        total = Component.objects.count()
        with_deps = Component.objects.filter(
            Q(dependencies__isnull=False) |
            Q(dependents__isnull=False)
        ).distinct().count()

        return {
            'total_components': total,
            'with_dependencies': with_deps,
            'orphans': total - with_deps,
            'total_dependencies': Dependency.objects.count(),
            'gitlab_projects': GitProject.objects.count(),
            'node_groups': NodeGroup.objects.count(),
        }

    def _analyze_gitlab_groups(self):
        """Analyze GitLab group structure."""
        groups = defaultdict(list)
        ungrouped = []

        for gp in GitProject.objects.select_related('component'):
            path = gp.path_with_namespace
            if '/' in path:
                # Extract group path (everything except last segment)
                group_path = '/'.join(path.split('/')[:-1])
                groups[group_path].append({
                    'name': gp.name,
                    'path': path,
                    'component_key': gp.component.key if gp.component else None,
                })
            else:
                ungrouped.append(gp.name)

        # Build hierarchy
        hierarchy = self._build_group_hierarchy(groups)

        return {
            'groups': {k: len(v) for k, v in sorted(groups.items(), key=lambda x: -len(x[1]))},
            'hierarchy': hierarchy,
            'ungrouped_count': len(ungrouped),
            'total_grouped': sum(len(v) for v in groups.values()),
        }

    def _build_group_hierarchy(self, groups):
        """Build a nested hierarchy from flat group paths."""
        hierarchy = {}

        for path, projects in groups.items():
            parts = path.split('/')
            current = hierarchy
            for part in parts:
                if part not in current:
                    current[part] = {'_projects': 0, '_children': {}}
                current = current[part]['_children']
            # Go back up and increment count
            current = hierarchy
            for part in parts:
                current[part]['_projects'] += len(projects)
                current = current[part]['_children']

        return hierarchy

    def _analyze_maven_domains(self):
        """Analyze Maven groupId patterns."""
        domains = defaultdict(list)

        for comp in Component.objects.exclude(maven_group_id=''):
            group_id = comp.maven_group_id
            # Get first 2-3 segments as domain
            parts = group_id.split('.')
            if len(parts) >= 3:
                domain = '.'.join(parts[:3])
            elif len(parts) >= 2:
                domain = '.'.join(parts[:2])
            else:
                domain = group_id

            domains[domain].append({
                'key': comp.key,
                'name': comp.name,
                'full_group_id': group_id,
            })

        return {
            'domains': {k: len(v) for k, v in sorted(domains.items(), key=lambda x: -len(x[1]))[:20]},
            'total_with_group_id': sum(len(v) for v in domains.values()),
            'unique_domains': len(domains),
        }

    def _analyze_naming_patterns(self):
        """Analyze naming conventions in project names."""
        suffixes = Counter()
        prefixes = Counter()

        for comp in Component.objects.all():
            name = comp.name.lower()

            # Common suffixes
            for suffix in ['-service', '-api', '-worker', '-lib', '-library',
                          '-gateway', '-proxy', '-client', '-common', '-core',
                          '-utils', '-tools', '-config', '-admin', '-web',
                          '-batch', '-scheduler', '-connector', '-adapter']:
                if name.endswith(suffix):
                    suffixes[suffix] += 1
                    break

            # Extract prefix (first word before hyphen)
            if '-' in name:
                prefix = name.split('-')[0]
                if len(prefix) > 2:  # Skip short prefixes
                    prefixes[prefix] += 1

        return {
            'suffixes': dict(suffixes.most_common(15)),
            'prefixes': dict(prefixes.most_common(15)),
        }

    def _analyze_dependency_clusters(self):
        """Analyze dependency structure - clusters, hubs, anchors, orphans."""
        # Build adjacency lists
        components = {c.id: c for c in Component.objects.all()}
        outgoing = defaultdict(set)  # component_id -> set of target_ids
        incoming = defaultdict(set)  # component_id -> set of source_ids

        for dep in Dependency.objects.all():
            outgoing[dep.source_id].add(dep.target_id)
            incoming[dep.target_id].add(dep.source_id)

        # Detect domain anchors vs infrastructure
        anchor_result = self._detect_domain_anchors(components, incoming, outgoing)
        domain_anchors = anchor_result['domain_anchors']
        infrastructure = anchor_result['infrastructure']
        anchor_clusters = self._cluster_by_anchors(components, outgoing, domain_anchors)

        # Find connected components (undirected)
        visited = set()
        clusters = []

        def bfs(start_id):
            cluster = set()
            queue = [start_id]
            while queue:
                node = queue.pop(0)
                if node in visited:
                    continue
                visited.add(node)
                cluster.add(node)
                # Add neighbors (both directions)
                for neighbor in outgoing[node] | incoming[node]:
                    if neighbor not in visited and neighbor in components:
                        queue.append(neighbor)
            return cluster

        for comp_id in components:
            if comp_id not in visited:
                cluster = bfs(comp_id)
                if cluster:
                    clusters.append(cluster)

        # Sort clusters by size
        clusters.sort(key=len, reverse=True)

        # Calculate hub scores
        hub_scores = {}
        for comp_id in components:
            in_deg = len(incoming[comp_id])
            out_deg = len(outgoing[comp_id])
            hub_scores[comp_id] = {
                'in_degree': in_deg,
                'out_degree': out_deg,
                'hub_score': in_deg * 2 + out_deg,
                'name': components[comp_id].name,
            }

        # Top hubs
        top_hubs = sorted(hub_scores.items(), key=lambda x: -x[1]['hub_score'])[:20]

        # Identify orphans (no dependencies at all)
        orphans = [
            comp_id for comp_id in components
            if not outgoing[comp_id] and not incoming[comp_id]
        ]

        # Run label propagation for community detection on largest cluster
        communities = {}
        if clusters and len(clusters[0]) > 10:
            communities = self._label_propagation(
                clusters[0], outgoing, incoming, components
            )

        # Format cluster info
        cluster_info = []
        for i, cluster in enumerate(clusters[:10]):  # Top 10 clusters
            # Find hub in this cluster
            cluster_hubs = [(cid, hub_scores[cid]) for cid in cluster]
            cluster_hubs.sort(key=lambda x: -x[1]['hub_score'])
            top_hub = cluster_hubs[0] if cluster_hubs else None

            cluster_info.append({
                'id': i + 1,
                'size': len(cluster),
                'hub': top_hub[1]['name'] if top_hub else None,
                'hub_score': top_hub[1]['hub_score'] if top_hub else 0,
            })

        return {
            'total_clusters': len(clusters),
            'largest_cluster_size': len(clusters[0]) if clusters else 0,
            'clusters': cluster_info,
            'top_hubs': [
                {'name': h[1]['name'], 'in': h[1]['in_degree'],
                 'out': h[1]['out_degree'], 'score': h[1]['hub_score']}
                for h in top_hubs
            ],
            'orphan_count': len(orphans),
            'communities': communities,
            'domain_anchors': domain_anchors,
            'infrastructure': infrastructure,
            'anchor_clusters': anchor_clusters,
        }

    def _detect_domain_anchors(self, components, incoming, outgoing):
        """Detect domain anchor projects - distinguishing domain anchors from infrastructure."""
        ANCHOR_PATTERNS = [
            r'-domain$', r'-parent$', r'-bom$', r'-common$', r'-core$',
            r'-base$', r'-shared$', r'-platform$', r'-framework$',
            r'^common-', r'^shared-', r'^platform-', r'^core-',
        ]

        # Infrastructure patterns - these are shared across domains, not domain-specific
        INFRA_PATTERNS = [
            r'^kafka', r'^redis', r'^mongo', r'^postgres', r'^mysql',
            r'^elastic', r'^rabbit', r'logging', r'monitoring', r'tracing',
            r'gateway', r'config.*server', r'discovery', r'eureka', r'consul',
            r'^cache', r'metrics', r'zipkin', r'jaeger', r'prometheus',
            r'^auth[-_]service$', r'^identity[-_]', r'^sso[-_]', r'^oauth[-_]',
        ]

        anchors = []
        infra = []

        for comp_id, comp in components.items():
            in_deg = len(incoming[comp_id])
            out_deg = len(outgoing[comp_id])
            name_lower = comp.name.lower().replace(' ', '-').replace('_', '-')

            # Check patterns
            name_is_anchor = any(re.search(p, name_lower) for p in ANCHOR_PATTERNS)
            name_is_infra = any(re.search(p, name_lower) for p in INFRA_PATTERNS)

            # Anchor ratio: high in-degree, low out-degree
            if in_deg > 0:
                anchor_ratio = in_deg / (out_deg + 1)
            else:
                anchor_ratio = 0

            # Calculate name coherence: do dependents share naming pattern with this anchor?
            domain = self._extract_domain_from_name(comp.name)
            dependent_names = [
                components[dep_id].name.lower().replace(' ', '-').replace('_', '-')
                for dep_id in incoming[comp_id]
                if dep_id in components
            ]

            # Count how many dependents contain the domain prefix
            if domain and dependent_names:
                domain_prefix = domain.split('-')[0] if '-' in domain else domain[:4]
                matching_deps = sum(1 for n in dependent_names if domain_prefix in n)
                name_coherence = matching_deps / len(dependent_names)
            else:
                name_coherence = 0

            # Classify as domain anchor if:
            # - Has anchor-like name pattern and at least 2 dependents, OR
            # - High name coherence (>0.3) with dependents, OR
            # - High anchor ratio AND not infrastructure
            is_domain_anchor = (
                (name_is_anchor and in_deg >= 2 and not name_is_infra) or
                (name_coherence >= 0.3 and in_deg >= 3) or
                (anchor_ratio >= 5 and in_deg >= 5 and not name_is_infra and name_coherence >= 0.2)
            )

            is_infra = (
                name_is_infra and anchor_ratio >= 3 and in_deg >= 5
            )

            entry = {
                'id': comp_id,
                'name': comp.name,
                'domain': domain,
                'in_degree': in_deg,
                'out_degree': out_deg,
                'anchor_ratio': round(anchor_ratio, 2),
                'name_coherence': round(name_coherence, 2),
                'name_match': name_is_anchor,
            }

            if is_domain_anchor:
                anchors.append(entry)
            elif is_infra:
                infra.append(entry)

        # Sort by in_degree
        anchors.sort(key=lambda x: (-x['name_coherence'], -x['in_degree']))
        infra.sort(key=lambda x: -x['in_degree'])

        return {
            'domain_anchors': anchors,
            'infrastructure': infra,
        }

    def _extract_domain_from_name(self, name):
        """Extract domain name from anchor project name."""
        name_lower = name.lower()

        # Remove common suffixes
        for suffix in ['-domain', '-parent', '-bom', '-common', '-core',
                       '-base', '-shared', '-platform', '-framework']:
            if name_lower.endswith(suffix):
                return name_lower[:-len(suffix)]

        # Remove common prefixes
        for prefix in ['common-', 'shared-', 'platform-', 'core-']:
            if name_lower.startswith(prefix):
                return name_lower[len(prefix):]

        # Fallback: return first segment before hyphen
        if '-' in name_lower:
            return name_lower.split('-')[0]

        return name_lower

    def _cluster_by_anchors(self, components, outgoing, anchors):
        """Cluster projects based on which domain anchors they depend on."""
        if not anchors:
            return {'clusters': [], 'unassigned_count': len(components)}

        anchor_ids = {a['id'] for a in anchors}
        anchor_by_id = {a['id']: a for a in anchors}

        # For each non-anchor component, find which anchors it depends on (directly or transitively)
        component_anchors = defaultdict(set)  # comp_id -> set of anchor_ids

        for comp_id in components:
            if comp_id in anchor_ids:
                continue

            # BFS to find reachable anchors (limit depth to avoid explosion)
            visited = set()
            queue = [(comp_id, 0)]  # (node, depth)
            max_depth = 3  # Only look 3 levels deep

            while queue:
                node, depth = queue.pop(0)
                if node in visited or depth > max_depth:
                    continue
                visited.add(node)

                for target in outgoing[node]:
                    if target in anchor_ids:
                        component_anchors[comp_id].add(target)
                    elif target not in visited and depth < max_depth:
                        queue.append((target, depth + 1))

        # Group components by their primary anchor (first/strongest connection)
        # If a component depends on multiple anchors, assign to the one with highest in-degree
        clusters = defaultdict(list)
        unassigned = []

        for comp_id, comp in components.items():
            if comp_id in anchor_ids:
                # Anchors belong to their own domain
                clusters[comp_id].append({
                    'id': comp_id,
                    'name': comp.name,
                    'is_anchor': True,
                })
                continue

            anchor_set = component_anchors.get(comp_id, set())
            if anchor_set:
                # Pick the anchor with highest in-degree
                best_anchor = max(anchor_set, key=lambda a: anchor_by_id[a]['in_degree'])
                clusters[best_anchor].append({
                    'id': comp_id,
                    'name': comp.name,
                    'is_anchor': False,
                })
            else:
                unassigned.append({
                    'id': comp_id,
                    'name': comp.name,
                })

        # Format output
        formatted_clusters = []
        for anchor_id, members in sorted(clusters.items(), key=lambda x: -len(x[1])):
            anchor = anchor_by_id.get(anchor_id)
            if anchor:
                formatted_clusters.append({
                    'anchor': anchor['name'],
                    'domain': anchor['domain'],
                    'size': len(members),
                    'members': [m['name'] for m in members[:10]],
                    'has_more': len(members) > 10,
                })

        return {
            'clusters': formatted_clusters,
            'unassigned_count': len(unassigned),
            'unassigned_sample': [u['name'] for u in unassigned[:10]],
        }

    def _label_propagation(self, cluster, outgoing, incoming, components, iterations=10):
        """Simple label propagation for community detection."""
        # Initialize each node with its own label
        labels = {node: node for node in cluster}
        node_list = list(cluster)

        for _ in range(iterations):
            random.shuffle(node_list)
            changed = False

            for node in node_list:
                # Get neighbor labels
                neighbors = (outgoing[node] | incoming[node]) & cluster
                if not neighbors:
                    continue

                neighbor_labels = [labels[n] for n in neighbors]
                if neighbor_labels:
                    # Pick most common label
                    label_counts = Counter(neighbor_labels)
                    most_common = label_counts.most_common(1)[0][0]
                    if labels[node] != most_common:
                        labels[node] = most_common
                        changed = True

            if not changed:
                break

        # Group by label
        communities = defaultdict(list)
        for node, label in labels.items():
            communities[label].append(node)

        # Format output - top communities
        sorted_communities = sorted(communities.items(), key=lambda x: -len(x[1]))[:10]

        return {
            'total_communities': len(communities),
            'top_communities': [
                {
                    'size': len(members),
                    'representative': components[label].name if label in components else str(label),
                    'members_sample': [
                        components[m].name for m in members[:5]
                    ] if len(members) <= 5 else [
                        components[m].name for m in members[:3]
                    ] + [f'... and {len(members) - 3} more'],
                }
                for label, members in sorted_communities
            ],
        }

    def _analyze_activity(self):
        """Analyze project activity based on sync times."""
        now = timezone.now()

        # Activity buckets
        active_30d = 0
        stale_90d = 0
        dormant = 0
        never_synced = 0

        for comp in Component.objects.all():
            if not comp.synced_at:
                never_synced += 1
            elif comp.synced_at > now - timedelta(days=30):
                active_30d += 1
            elif comp.synced_at > now - timedelta(days=90):
                stale_90d += 1
            else:
                dormant += 1

        return {
            'active_30d': active_30d,
            'stale_30_90d': stale_90d,
            'dormant_90d_plus': dormant,
            'never_synced': never_synced,
        }

    def _format_report(self, report):
        """Format report as human-readable text."""
        lines = []
        lines.append("=" * 60)
        lines.append("PROJECT GROUPINGS ANALYSIS")
        lines.append("=" * 60)

        # Summary
        s = report['summary']
        lines.append(f"\nSUMMARY")
        lines.append(f"  Total components:    {s['total_components']}")
        lines.append(f"  With dependencies:   {s['with_dependencies']}")
        lines.append(f"  Orphans (no deps):   {s['orphans']}")
        lines.append(f"  Total dependencies:  {s['total_dependencies']}")
        lines.append(f"  GitLab projects:     {s['gitlab_projects']}")

        # GitLab Groups
        gl = report['gitlab_groups']
        lines.append(f"\nGITLAB GROUPS ({len(gl['groups'])} groups)")
        for group, count in list(gl['groups'].items())[:15]:
            lines.append(f"  {group:40} {count:4} projects")
        if len(gl['groups']) > 15:
            lines.append(f"  ... and {len(gl['groups']) - 15} more groups")
        lines.append(f"  (ungrouped): {gl['ungrouped_count']} projects")

        # Maven Domains
        mv = report['maven_domains']
        lines.append(f"\nMAVEN DOMAINS ({mv['unique_domains']} unique)")
        for domain, count in list(mv['domains'].items())[:15]:
            lines.append(f"  {domain:40} {count:4} projects")

        # Naming Patterns
        np = report['naming_patterns']
        lines.append(f"\nNAMING PATTERNS")
        lines.append(f"  Suffixes:")
        for suffix, count in list(np['suffixes'].items())[:10]:
            lines.append(f"    {suffix:20} {count:4}")
        lines.append(f"  Prefixes (top 10):")
        for prefix, count in list(np['prefixes'].items())[:10]:
            lines.append(f"    {prefix:20} {count:4}")

        # Dependency Clusters
        dc = report['dependency_clusters']
        lines.append(f"\nDEPENDENCY CLUSTERS")
        lines.append(f"  Total clusters:      {dc['total_clusters']}")
        lines.append(f"  Largest cluster:     {dc['largest_cluster_size']} projects")
        lines.append(f"  Orphans (isolated):  {dc['orphan_count']}")

        lines.append(f"\n  Top Clusters:")
        for c in dc['clusters'][:5]:
            lines.append(f"    Cluster {c['id']}: {c['size']} projects, hub: {c['hub']}")

        lines.append(f"\n  Top Hubs (most dependencies):")
        for h in dc['top_hubs'][:10]:
            lines.append(f"    {h['name']:35} in:{h['in']:3} out:{h['out']:3} score:{h['score']}")

        if dc.get('communities'):
            comm = dc['communities']
            lines.append(f"\n  Communities (via label propagation): {comm['total_communities']}")
            for c in comm['top_communities'][:5]:
                members = ', '.join(c['members_sample'][:3])
                lines.append(f"    Size {c['size']:3}: {members}")

        # Infrastructure (shared across domains)
        if dc.get('infrastructure'):
            lines.append(f"\n  Infrastructure (shared): {len(dc['infrastructure'])}")
            for a in dc['infrastructure'][:10]:
                lines.append(f"    {a['name']:35} in:{a['in_degree']:3} out:{a['out_degree']:3}")

        # Domain Anchors
        if dc.get('domain_anchors'):
            lines.append(f"\n  Domain Anchors Detected: {len(dc['domain_anchors'])}")
            for a in dc['domain_anchors'][:15]:
                flag = " [name]" if a['name_match'] else ""
                coh = f" coh:{a['name_coherence']}" if a.get('name_coherence') else ""
                lines.append(f"    {a['name']:35} domain:{a['domain']:15} in:{a['in_degree']:3}{coh}{flag}")

        # Anchor-based Clusters
        if dc.get('anchor_clusters'):
            ac = dc['anchor_clusters']
            lines.append(f"\n  Anchor-based Clusters:")
            for c in ac['clusters'][:15]:
                members_preview = ', '.join(c['members'][:3])
                more = f" +{c['size'] - 3} more" if c['size'] > 3 else ""
                lines.append(f"    [{c['domain']}] {c['size']} projects: {members_preview}{more}")
            if ac['unassigned_count'] > 0:
                lines.append(f"    (unassigned): {ac['unassigned_count']} projects")
                if ac.get('unassigned_sample'):
                    lines.append(f"      sample: {', '.join(ac['unassigned_sample'][:5])}")

        # Activity
        ac = report['activity']
        lines.append(f"\nACTIVITY DISTRIBUTION")
        lines.append(f"  Active (30d):        {ac['active_30d']}")
        lines.append(f"  Stale (30-90d):      {ac['stale_30_90d']}")
        lines.append(f"  Dormant (90d+):      {ac['dormant_90d_plus']}")
        lines.append(f"  Never synced:        {ac['never_synced']}")

        lines.append("\n" + "=" * 60)

        return '\n'.join(lines)
