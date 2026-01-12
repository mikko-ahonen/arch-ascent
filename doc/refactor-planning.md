# LLM‑Guided Refactoring of Large‑Scale Microservice Dependency Graphs

This document defines:

1. **Prompt templates** for LLM‑based architectural refactoring analysis
2. A **fully automated pipeline** integrating static dependency graphs from SonarQube / Checkmarx
3. A strategy to generate **actionable, staged refactoring proposals** for 300–500 highly coupled microservices

The goal is **not automatic refactoring**, but a **high‑signal, human‑actionable refactoring plan** that improves:

* Service boundaries
* Cohesion and ownership
* Long‑term evolvability

---

## 1. Core Assumptions & Inputs

### 1.1 Inputs Available

* Directed dependency graph (service → service)
* Groupings / modules (from SonarQube / Checkmarx)
* Dependency types (API, shared library, data, config)
* Basic metadata (service name, repo, owner, language)

### 1.2 Constraints

* Static analysis only (no runtime tracing)
* 300–500 services (graph must be reduced)
* Cyclic dependencies and unclear domain boundaries

---

## 2. Pre‑Processing (Before LLM)

LLMs **must never receive raw graphs** at this scale.

### 2.1 Mandatory Graph Reduction

Perform deterministically:

* Strongly Connected Components (SCC)
* Condensed DAG of SCCs
* Community detection (e.g., Louvain / DSM clustering)
* Fan‑in / fan‑out metrics

Each LLM prompt operates on:

* One SCC
* One cluster
* Or one boundary between clusters

---

## 3. Prompt Templates by Refactoring Type

All prompts follow the same structure:

* **Context** (reduced graph + metadata)
* **Goal** (what architectural improvement is desired)
* **Constraints** (what must not be assumed)
* **Expected Output Format** (machine‑parseable markdown)

---

## 3.1 Stepwise Cycle‑Breaking Prompt

### When to Use

* SCC size ≥ 2
* Bidirectional or cyclic service dependencies

### Prompt Template

```text
You are an expert software architect.

Context:
- The following services form a cyclic dependency group:
  {{SCC_SERVICES}}
- Dependencies:
  {{DEPENDENCY_EDGES}}
- Shared types / libraries:
  {{SHARED_CONCEPTS}}
- Known groupings:
  {{EXISTING_GROUPS}}

Goal:
Propose a stepwise refactoring plan to break this cycle while preserving system behavior.

Constraints:
- Do not assume runtime behavior
- Do not introduce new business concepts
- Each step must reduce coupling or dependency directionality

Output format:
- Root cause analysis
- Identified shared concepts
- Step‑by‑step refactoring plan
- Expected architectural improvement per step
```

### Expected Output (Example)

* Extract shared domain abstraction
* Introduce dependency inversion
* Remove back‑edges incrementally

---

## 3.2 Gradual Service Extraction Prompt

### When to Use

* Large service with internal clusters
* Disparate change rates or responsibilities

### Prompt Template

```text
You are analyzing a large microservice for potential extraction.

Context:
- Service: {{SERVICE_NAME}}
- Internal dependency clusters:
  {{INTERNAL_CLUSTERS}}
- External dependencies:
  {{EXTERNAL_DEPENDENCIES}}

Goal:
Identify candidate sub‑domains that could be extracted into independent services.

Constraints:
- No new domain logic
- Prefer minimal API surface

Output format:
- Candidate extraction(s)
- Rationale for cohesion
- Staged extraction plan
- Risk assessment
```

---

## 3.3 API Stabilization & Contract Hardening Prompt

### When to Use

* High fan‑in services
* Frequent interface changes

### Prompt Template

```text
You are evaluating API stability for a central service.

Context:
- Service: {{SERVICE_NAME}}
- Consumers:
  {{DOWNSTREAM_SERVICES}}
- Dependency types:
  {{DEPENDENCY_TYPES}}

Goal:
Propose a plan to stabilize APIs and reduce downstream coupling.

Constraints:
- Backward compatibility preferred
- No runtime assumptions

Output format:
- Stable vs volatile API elements
- Proposed contract boundary
- Migration strategy
```

---

## 3.4 Module / Service Boundary Redefinition Prompt

### When to Use

* Clusters with mixed responsibilities
* Naming/domain leakage

### Prompt Template

```text
You are analyzing service groupings for boundary clarity.

Context:
- Service cluster:
  {{SERVICE_CLUSTER}}
- Dependency density:
  {{INTERNAL_VS_EXTERNAL_EDGES}}
- Naming patterns:
  {{SERVICE_NAMES}}

Goal:
Recommend clearer service or domain boundaries.

Constraints:
- Use existing concepts
- Prefer fewer, more cohesive groups

Output format:
- Identified boundary issues
- Suggested regroupings
- Expected benefits
```

---

## 4. Fully Automated Pipeline Plan

### 4.1 Pipeline Overview

```text
Git Repos
   ↓
SonarQube / Checkmarx
   ↓
Dependency Graph
   ↓
Graph Algorithms (SCC, clustering)
   ↓
LLM Refactoring Analysis
   ↓
Validation & Scoring
   ↓
Actionable Refactoring Backlog
```

---

### 4.2 Django‑Side Responsibilities

* Fetch and normalize dependency data
* Compute SCCs and clusters
* Serialize reduced graph slices
* Track refactoring suggestions

---

### 4.3 LLM Orchestration

For each iteration:

1. Select target (SCC / cluster / service)
2. Choose appropriate prompt template
3. Inject structured context
4. Parse structured output

---

### 4.4 Validation Layer (Critical)

Each suggestion must be checked:

* Does SCC size decrease?
* Does fan‑in/fan‑out improve?
* Does cluster modularity increase?

Invalid or low‑impact proposals are discarded.

---

## 5. Output: Actionable Refactoring Backlog

Each accepted proposal becomes a backlog item:

```yaml
id: ARC‑042
scope: services
impact: high
risk: medium
summary: Break pricing/order cycle
steps:
  - Extract pricing‑core
  - Introduce interfaces
  - Remove back‑dependency
```

This backlog is the **primary deliverable** for architects.

---

## 6. Key Success Factors

* Aggressive graph reduction
* Strict prompt constraints
* Deterministic validation
* Human‑reviewed execution

---

## 7. Final Note

This approach scales because:

* Graph algorithms provide truth
* LLMs provide meaning and strategy
* Humans provide judgment

If you want, the next step could be:

* A **JSON schema** for LLM outputs
* A **Django model design** for refactoring items
* A **scoring formula** for prioritization

