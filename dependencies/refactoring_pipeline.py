"""
Refactoring analysis pipeline that orchestrates graph algorithms and LLM analysis.

Pipeline flow:
1. Build adjacency list from database
2. Compute SCCs using Tarjan's algorithm
3. Compute communities using Louvain algorithm
4. Calculate node metrics (fan-in/fan-out)
5. For each SCC with size >= 2: generate cycle-breaking proposal
6. For high fan-in services: generate API stabilization proposal
7. For mixed clusters: generate boundary redefinition proposal
8. Validate and score proposals
9. Save proposals to database
"""

import logging
from datetime import datetime
from typing import Iterator

from django.db import transaction
from django.utils import timezone

from dependencies.models import Component, Dependency, NodeGroup, RefactoringProposal, AnalysisRun
from dependencies.llm_service import RefactoringAnalyzer, AnalysisContext
from dependencies.components.graph.graph import (
    find_sccs_tarjan,
    build_condensed_dag,
    calculate_node_metrics,
    louvain_communities,
    get_high_coupling_services,
)

logger = logging.getLogger(__name__)


class RefactoringPipeline:
    """Orchestrates the refactoring analysis pipeline."""

    def __init__(self, llm_service: RefactoringAnalyzer = None, dry_run: bool = False):
        self.llm = llm_service or RefactoringAnalyzer()
        self.dry_run = dry_run
        self.run: AnalysisRun = None
        self._proposal_counter = 0

    def _generate_proposal_id(self, prefix: str = "ARC") -> str:
        """Generate unique proposal ID."""
        self._proposal_counter += 1
        return f"{prefix}-{self._proposal_counter:03d}"

    def build_adjacency(self) -> dict[str, set[str]]:
        """Build adjacency list from database."""
        adjacency: dict[str, set[str]] = {}

        # Include all components
        for component in Component.objects.all():
            adjacency.setdefault(str(component.id), set())

        # Add edges
        for dep in Dependency.objects.select_related('source', 'target').all():
            source_key = str(dep.source.id)
            target_key = str(dep.target.id)
            adjacency.setdefault(source_key, set()).add(target_key)

        return adjacency

    def get_component_groups(self) -> dict[str, str]:
        """Get mapping of component IDs to their group names."""
        groups = {}
        for component in Component.objects.select_related('group').filter(group__isnull=False):
            groups[str(component.id)] = component.group.name
        return groups

    # Alias for backwards compatibility
    def get_project_groups(self) -> dict[str, str]:
        return self.get_component_groups()

    def get_shared_concepts(self, services: list[str]) -> list[str]:
        """Extract shared concepts from service names."""
        concepts = set()
        for service in services:
            # Extract domain prefixes (e.g., "core:" from "core:api-gateway")
            if ':' in service:
                prefix = service.split(':')[0]
                concepts.add(prefix)
            # Extract common suffixes
            for suffix in ['-service', '-api', '-core', '-common', '-shared']:
                if service.endswith(suffix):
                    concepts.add(suffix.strip('-'))
        return list(concepts)

    def score_proposal(
        self, proposal_type: str, services: list[str], metrics: dict
    ) -> tuple[str, str]:
        """
        Calculate impact and risk scores for a proposal.

        Returns (impact, risk) tuple.
        """
        num_services = len(services)
        avg_coupling = sum(m.get('coupling_score', 0) for m in metrics.values()) / max(len(metrics), 1)

        # Impact based on number of services and coupling
        if num_services >= 5 or avg_coupling >= 10:
            impact = 'high'
        elif num_services >= 3 or avg_coupling >= 5:
            impact = 'medium'
        else:
            impact = 'low'

        # Risk based on proposal type and scope
        if proposal_type == 'cycle_break':
            risk = 'medium' if num_services <= 3 else 'high'
        elif proposal_type == 'service_extraction':
            risk = 'high'  # Extractions are inherently risky
        elif proposal_type == 'api_stabilization':
            risk = 'low' if num_services <= 5 else 'medium'
        else:
            risk = 'medium'

        return impact, risk

    def validate_proposal(self, proposal_type: str, result, metrics: dict) -> bool:
        """
        Validate that a proposal meets quality criteria.

        Returns True if valid, False otherwise.
        """
        # Must have a summary
        if not result.summary:
            return False

        # Must have actionable steps
        if not result.steps or len(result.steps) == 0:
            return False

        # Type-specific validation
        if proposal_type == 'cycle_break':
            # Must identify root cause or shared concepts
            if not result.root_cause and not result.shared_concepts:
                return False

        elif proposal_type == 'api_stabilization':
            # Must identify stable or volatile elements
            if not result.stable_elements and not result.volatile_elements:
                return False

        elif proposal_type == 'boundary_redefinition':
            # Must identify boundary issues
            if not result.boundary_issues:
                return False

        return True

    def analyze_sccs(
        self, adjacency: dict[str, set[str]], min_size: int = 2
    ) -> Iterator[RefactoringProposal]:
        """Analyze SCCs and generate cycle-breaking proposals."""
        sccs = find_sccs_tarjan(adjacency)
        groups = self.get_project_groups()
        metrics = calculate_node_metrics(adjacency)

        # Filter to SCCs with cycles (size >= 2)
        cyclic_sccs = [scc for scc in sccs if len(scc) >= min_size]

        logger.info(f"Found {len(cyclic_sccs)} SCCs with size >= {min_size}")

        for scc in cyclic_sccs:
            # Build context for this SCC
            scc_edges = [
                (s, t) for s in scc for t in adjacency.get(s, set()) if t in scc
            ]
            scc_groups = list(set(groups.get(s) for s in scc if s in groups))
            shared = self.get_shared_concepts(scc)
            scc_metrics = {s: metrics.get(s, {}) for s in scc}

            context = AnalysisContext(
                services=scc,
                edges=scc_edges,
                shared_concepts=shared,
                existing_groups=scc_groups,
                metrics=scc_metrics,
            )

            # Call LLM for analysis
            if self.llm.is_available:
                result = self.llm.analyze_scc(context)
            else:
                # Generate placeholder proposal without LLM
                result = self._generate_placeholder_scc_result(scc, scc_edges)

            # Validate result
            if not self.validate_proposal('cycle_break', result, scc_metrics):
                logger.warning(f"Invalid proposal for SCC: {scc}")
                continue

            # Score proposal
            impact, risk = self.score_proposal('cycle_break', scc, scc_metrics)

            # Create proposal
            proposal = RefactoringProposal(
                proposal_id=self._generate_proposal_id("CYC"),
                analysis_run=self.run,
                proposal_type='cycle_break',
                scope=scc,
                impact=impact,
                risk=risk,
                summary=result.summary or f"Break cycle in {len(scc)} services",
                root_cause=result.root_cause,
                steps=result.steps or [],
                expected_improvement=result.expected_improvement,
                scc_size_before=len(scc),
            )

            yield proposal

    def analyze_high_coupling(
        self, adjacency: dict[str, set[str]], threshold_percentile: float = 90
    ) -> Iterator[RefactoringProposal]:
        """Analyze high-coupling services and generate API stabilization proposals."""
        high_coupling = get_high_coupling_services(adjacency, threshold_percentile)
        metrics = calculate_node_metrics(adjacency)

        logger.info(f"Found {len(high_coupling)} high-coupling services")

        for service, service_metrics in high_coupling:
            # Only analyze services with high fan-in (many consumers)
            if service_metrics['fan_in'] < 3:
                continue

            # Get downstream services (consumers)
            downstream = [
                s for s, targets in adjacency.items()
                if service in targets
            ]

            context = AnalysisContext(
                services=[service],
                edges=[(s, service) for s in downstream],
                downstream_services=downstream,
                dependency_types=['API'],
                metrics=service_metrics,
            )

            # Call LLM for analysis
            if self.llm.is_available:
                result = self.llm.analyze_api_stability(service, context)
            else:
                result = self._generate_placeholder_api_result(service, downstream)

            # Validate result
            if not self.validate_proposal('api_stabilization', result, {service: service_metrics}):
                logger.warning(f"Invalid API proposal for: {service}")
                continue

            # Score proposal
            impact, risk = self.score_proposal(
                'api_stabilization', downstream + [service], {service: service_metrics}
            )

            proposal = RefactoringProposal(
                proposal_id=self._generate_proposal_id("API"),
                analysis_run=self.run,
                proposal_type='api_stabilization',
                scope=[service] + downstream[:5],  # Limit scope size
                impact=impact,
                risk=risk,
                summary=result.summary or f"Stabilize API for {service}",
                root_cause='',
                steps=result.steps or [],
                expected_improvement=result.expected_improvement,
                fan_in_before=service_metrics['fan_in'],
                fan_out_before=service_metrics['fan_out'],
            )

            yield proposal

    def analyze_communities(
        self, adjacency: dict[str, set[str]]
    ) -> Iterator[RefactoringProposal]:
        """Analyze communities and generate boundary proposals."""
        communities = louvain_communities(adjacency)
        metrics = calculate_node_metrics(adjacency)

        # Filter to communities with potential issues (mixed domains)
        for community in communities:
            if len(community) < 3:
                continue

            # Check for domain mixing (different prefixes)
            prefixes = set()
            for service in community:
                if ':' in service:
                    prefixes.add(service.split(':')[0])
            if len(prefixes) <= 1:
                # Homogeneous community, skip
                continue

            # Calculate internal vs external edge ratio
            internal_edges = sum(
                1 for s in community for t in adjacency.get(s, set()) if t in community
            )
            external_edges = sum(
                1 for s in community for t in adjacency.get(s, set()) if t not in community
            )

            context = AnalysisContext(
                services=community,
                edges=[(s, t) for s in community for t in adjacency.get(s, set())],
                internal_vs_external_edges={
                    'internal': internal_edges,
                    'external': external_edges,
                    'ratio': internal_edges / max(external_edges, 1),
                },
                service_names=community,
                metrics={s: metrics.get(s, {}) for s in community},
            )

            # Call LLM for analysis
            if self.llm.is_available:
                result = self.llm.analyze_boundaries(context)
            else:
                result = self._generate_placeholder_boundary_result(community, prefixes)

            # Validate result
            community_metrics = {s: metrics.get(s, {}) for s in community}
            if not self.validate_proposal('boundary_redefinition', result, community_metrics):
                logger.warning(f"Invalid boundary proposal for community of {len(community)} services")
                continue

            # Score proposal
            impact, risk = self.score_proposal('boundary_redefinition', community, community_metrics)

            proposal = RefactoringProposal(
                proposal_id=self._generate_proposal_id("BND"),
                analysis_run=self.run,
                proposal_type='boundary_redefinition',
                scope=community[:10],  # Limit scope size
                impact=impact,
                risk=risk,
                summary=result.summary or f"Redefine boundaries for {len(community)} services",
                root_cause='\n'.join(result.boundary_issues or []),
                steps=result.steps or [],
                expected_improvement=result.expected_improvement,
            )

            yield proposal

    def _generate_placeholder_scc_result(self, scc: list[str], edges: list[tuple]):
        """Generate placeholder result when LLM is not available."""
        from dependencies.llm_service import RefactoringResult

        # Analyze cycle structure
        cycle_str = ' -> '.join(scc[:5])
        if len(scc) > 5:
            cycle_str += f' -> ... ({len(scc)} total)'

        return RefactoringResult(
            root_cause=f"Cyclic dependency detected: {cycle_str}",
            shared_concepts=self.get_shared_concepts(scc),
            steps=[
                "Identify the primary direction of data flow",
                "Extract shared domain models to a common module",
                "Introduce interfaces/abstractions at cycle boundaries",
                "Invert dependencies to break the cycle",
                "Remove redundant direct dependencies",
            ],
            expected_improvement="Breaking this cycle will improve modularity and make services independently deployable.",
            summary=f"Break cyclic dependency involving {len(scc)} services",
        )

    def _generate_placeholder_api_result(self, service: str, downstream: list[str]):
        """Generate placeholder API stabilization result."""
        from dependencies.llm_service import RefactoringResult

        return RefactoringResult(
            stable_elements=["Core data models", "Primary API endpoints"],
            volatile_elements=["Internal implementation details", "Experimental features"],
            steps=[
                f"Identify stable vs volatile API contracts for {service}",
                "Define versioned API interfaces",
                "Create adapter layer for internal changes",
                "Migrate consumers to stable interfaces",
                "Deprecate volatile endpoints with clear timeline",
            ],
            expected_improvement="Stable API contracts will reduce breaking changes for downstream consumers.",
            summary=f"Stabilize API for {service} ({len(downstream)} consumers)",
        )

    def _generate_placeholder_boundary_result(self, community: list[str], prefixes: set[str]):
        """Generate placeholder boundary redefinition result."""
        from dependencies.llm_service import RefactoringResult

        return RefactoringResult(
            boundary_issues=[
                f"Mixed domain prefixes in cluster: {', '.join(prefixes)}",
                "Services with different responsibilities grouped together",
            ],
            suggested_regroupings=[{'group': p, 'services': []} for p in prefixes],
            steps=[
                "Identify natural domain boundaries based on naming",
                f"Separate services by domain: {', '.join(prefixes)}",
                "Move cross-cutting services to shared infrastructure",
                "Update dependency directions to follow domain boundaries",
            ],
            expected_improvement="Clearer boundaries will improve team ownership and reduce cross-domain coupling.",
            summary=f"Redefine boundaries for {len(community)} services across {len(prefixes)} domains",
        )

    @transaction.atomic
    def run_analysis(
        self,
        min_scc_size: int = 2,
        coupling_threshold: float = 90,
        analyze_sccs: bool = True,
        analyze_coupling: bool = True,
        analyze_boundaries: bool = True,
    ) -> AnalysisRun:
        """
        Execute the full refactoring analysis pipeline.

        Args:
            min_scc_size: Minimum SCC size to analyze (default: 2)
            coupling_threshold: Percentile threshold for high coupling (default: 90)
            analyze_sccs: Whether to analyze SCCs for cycles
            analyze_coupling: Whether to analyze high-coupling services
            analyze_boundaries: Whether to analyze community boundaries

        Returns:
            AnalysisRun instance with results
        """
        # Create analysis run record
        self.run = AnalysisRun.objects.create(
            total_projects=Component.objects.count(),
            status='running',
        )
        self._proposal_counter = RefactoringProposal.objects.count()

        try:
            # Build graph
            adjacency = self.build_adjacency()
            logger.info(f"Built adjacency list with {len(adjacency)} nodes")

            # Compute SCCs
            sccs = find_sccs_tarjan(adjacency)
            self.run.total_sccs = len([s for s in sccs if len(s) >= min_scc_size])

            # Compute communities
            communities = louvain_communities(adjacency)
            self.run.total_clusters = len(communities)

            proposals = []

            # Analyze SCCs
            if analyze_sccs:
                for proposal in self.analyze_sccs(adjacency, min_scc_size):
                    proposals.append(proposal)

            # Analyze high coupling
            if analyze_coupling:
                for proposal in self.analyze_high_coupling(adjacency, coupling_threshold):
                    proposals.append(proposal)

            # Analyze boundaries
            if analyze_boundaries:
                for proposal in self.analyze_communities(adjacency):
                    proposals.append(proposal)

            # Save proposals
            if not self.dry_run:
                for proposal in proposals:
                    proposal.save()

            self.run.proposals_generated = len(proposals)
            self.run.status = 'completed'
            self.run.completed_at = timezone.now()
            self.run.save()

            logger.info(f"Analysis complete: {len(proposals)} proposals generated")
            return self.run

        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            self.run.status = 'failed'
            self.run.error_message = str(e)
            self.run.save()
            raise
