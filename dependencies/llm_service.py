"""
LLM-based architectural analysis service for refactoring recommendations.

This service uses Claude to analyze dependency graph structures and generate
actionable refactoring proposals based on the prompt templates defined in
doc/refactor-planning.md.
"""

import os
import json
import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
    logger.warning("anthropic package not installed. LLM analysis will be disabled.")


@dataclass
class AnalysisContext:
    """Context data for LLM analysis."""
    services: list[str]
    edges: list[tuple[str, str]]
    shared_concepts: list[str] = None
    existing_groups: list[str] = None
    internal_clusters: list[list[str]] = None
    external_dependencies: list[str] = None
    downstream_services: list[str] = None
    dependency_types: list[str] = None
    internal_vs_external_edges: dict = None
    service_names: list[str] = None
    metrics: dict = None


@dataclass
class RefactoringResult:
    """Result from LLM analysis."""
    root_cause: str = ""
    shared_concepts: list[str] = None
    steps: list[str] = None
    expected_improvement: str = ""
    summary: str = ""
    candidates: list[dict] = None
    stable_elements: list[str] = None
    volatile_elements: list[str] = None
    boundary_issues: list[str] = None
    suggested_regroupings: list[dict] = None
    raw_response: str = ""


class RefactoringAnalyzer:
    """LLM-based architectural analysis service."""

    def __init__(self, api_key: str = None, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY', '')
        self.model = model
        self._client = None

    @property
    def client(self):
        if self._client is None and HAS_ANTHROPIC and self.api_key:
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    @property
    def is_available(self) -> bool:
        return HAS_ANTHROPIC and bool(self.api_key)

    def _call_llm(self, prompt: str) -> str:
        """Make API call to Claude."""
        if not self.is_available:
            logger.warning("LLM not available, returning empty response")
            return ""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            return ""

    def _parse_markdown_sections(self, text: str) -> dict[str, str]:
        """Parse markdown response into sections."""
        sections = {}
        current_section = "intro"
        current_content = []

        for line in text.split('\n'):
            if line.startswith('## ') or line.startswith('### '):
                if current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = line.lstrip('#').strip().lower().replace(' ', '_')
                current_content = []
            else:
                current_content.append(line)

        if current_content:
            sections[current_section] = '\n'.join(current_content).strip()

        return sections

    def _parse_list_items(self, text: str) -> list[str]:
        """Extract list items from markdown."""
        items = []
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('- ') or line.startswith('* '):
                items.append(line[2:].strip())
            elif re.match(r'^\d+\.', line):
                items.append(re.sub(r'^\d+\.\s*', '', line).strip())
        return items

    def analyze_scc(self, context: AnalysisContext) -> RefactoringResult:
        """
        Generate cycle-breaking proposal for a strongly connected component.
        Uses prompt template 3.1 from refactor-planning.md.
        """
        prompt = f"""You are an expert software architect.

Context:
- The following services form a cyclic dependency group:
  {json.dumps(context.services, indent=2)}
- Dependencies:
  {json.dumps([f"{s} -> {t}" for s, t in context.edges], indent=2)}
- Shared types / libraries:
  {json.dumps(context.shared_concepts or [], indent=2)}
- Known groupings:
  {json.dumps(context.existing_groups or [], indent=2)}

Goal:
Propose a stepwise refactoring plan to break this cycle while preserving system behavior.

Constraints:
- Do not assume runtime behavior
- Do not introduce new business concepts
- Each step must reduce coupling or dependency directionality

Output format (use these exact section headers):
## Root Cause Analysis
[Analysis of why this cycle exists]

## Identified Shared Concepts
[List of shared concepts that could be extracted]

## Step-by-Step Refactoring Plan
[Numbered steps to break the cycle]

## Expected Architectural Improvement
[What improves after each step]

## Summary
[One-sentence summary of the proposal]
"""

        response = self._call_llm(prompt)
        sections = self._parse_markdown_sections(response)

        return RefactoringResult(
            root_cause=sections.get('root_cause_analysis', ''),
            shared_concepts=self._parse_list_items(sections.get('identified_shared_concepts', '')),
            steps=self._parse_list_items(sections.get('step-by-step_refactoring_plan', '')),
            expected_improvement=sections.get('expected_architectural_improvement', ''),
            summary=sections.get('summary', ''),
            raw_response=response,
        )

    def analyze_extraction(self, service_name: str, context: AnalysisContext) -> RefactoringResult:
        """
        Generate service extraction proposal.
        Uses prompt template 3.2 from refactor-planning.md.
        """
        prompt = f"""You are analyzing a large microservice for potential extraction.

Context:
- Service: {service_name}
- Internal dependency clusters:
  {json.dumps(context.internal_clusters or [], indent=2)}
- External dependencies:
  {json.dumps(context.external_dependencies or [], indent=2)}
- Metrics: Fan-in={context.metrics.get('fan_in', 0)}, Fan-out={context.metrics.get('fan_out', 0)}

Goal:
Identify candidate sub-domains that could be extracted into independent services.

Constraints:
- No new domain logic
- Prefer minimal API surface

Output format (use these exact section headers):
## Candidate Extractions
[List candidate services to extract]

## Rationale for Cohesion
[Why these candidates are cohesive]

## Staged Extraction Plan
[Step-by-step extraction plan]

## Risk Assessment
[Potential risks and mitigations]

## Summary
[One-sentence summary]
"""

        response = self._call_llm(prompt)
        sections = self._parse_markdown_sections(response)

        candidates = []
        for item in self._parse_list_items(sections.get('candidate_extractions', '')):
            candidates.append({'name': item, 'rationale': ''})

        return RefactoringResult(
            candidates=candidates,
            steps=self._parse_list_items(sections.get('staged_extraction_plan', '')),
            expected_improvement=sections.get('risk_assessment', ''),
            summary=sections.get('summary', ''),
            raw_response=response,
        )

    def analyze_api_stability(self, service_name: str, context: AnalysisContext) -> RefactoringResult:
        """
        Generate API stabilization proposal.
        Uses prompt template 3.3 from refactor-planning.md.
        """
        prompt = f"""You are evaluating API stability for a central service.

Context:
- Service: {service_name}
- Consumers:
  {json.dumps(context.downstream_services or [], indent=2)}
- Dependency types:
  {json.dumps(context.dependency_types or ['API'], indent=2)}
- Metrics: Fan-in={context.metrics.get('fan_in', 0)}, Fan-out={context.metrics.get('fan_out', 0)}

Goal:
Propose a plan to stabilize APIs and reduce downstream coupling.

Constraints:
- Backward compatibility preferred
- No runtime assumptions

Output format (use these exact section headers):
## Stable API Elements
[List of API elements that should remain stable]

## Volatile API Elements
[List of API elements that are changing frequently]

## Proposed Contract Boundary
[Description of the stable contract]

## Migration Strategy
[Steps to migrate consumers]

## Summary
[One-sentence summary]
"""

        response = self._call_llm(prompt)
        sections = self._parse_markdown_sections(response)

        return RefactoringResult(
            stable_elements=self._parse_list_items(sections.get('stable_api_elements', '')),
            volatile_elements=self._parse_list_items(sections.get('volatile_api_elements', '')),
            steps=self._parse_list_items(sections.get('migration_strategy', '')),
            expected_improvement=sections.get('proposed_contract_boundary', ''),
            summary=sections.get('summary', ''),
            raw_response=response,
        )

    def analyze_boundaries(self, context: AnalysisContext) -> RefactoringResult:
        """
        Generate boundary redefinition proposal.
        Uses prompt template 3.4 from refactor-planning.md.
        """
        prompt = f"""You are analyzing service groupings for boundary clarity.

Context:
- Service cluster:
  {json.dumps(context.services, indent=2)}
- Dependency density:
  {json.dumps(context.internal_vs_external_edges or {}, indent=2)}
- Naming patterns:
  {json.dumps(context.service_names or context.services, indent=2)}

Goal:
Recommend clearer service or domain boundaries.

Constraints:
- Use existing concepts
- Prefer fewer, more cohesive groups

Output format (use these exact section headers):
## Identified Boundary Issues
[List of boundary issues found]

## Suggested Regroupings
[List of suggested new groupings]

## Expected Benefits
[What improves with new boundaries]

## Summary
[One-sentence summary]
"""

        response = self._call_llm(prompt)
        sections = self._parse_markdown_sections(response)

        regroupings = []
        for item in self._parse_list_items(sections.get('suggested_regroupings', '')):
            regroupings.append({'group': item, 'services': []})

        return RefactoringResult(
            boundary_issues=self._parse_list_items(sections.get('identified_boundary_issues', '')),
            suggested_regroupings=regroupings,
            expected_improvement=sections.get('expected_benefits', ''),
            summary=sections.get('summary', ''),
            raw_response=response,
        )
