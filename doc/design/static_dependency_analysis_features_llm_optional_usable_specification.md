# Static Dependency Analysis Features – LLM-Optional Usable Specification

This specification defines the **core static dependency graph analysis features** in a way that ensures the system is **fully usable without LLM-based analysis**, while allowing **progressive enhancement** when LLMs are available.

The guiding principle is:

> **All features must produce deterministic, actionable outputs on their own.**  
> LLMs may *interpret, explain, or prioritize*, but never *enable* core functionality.

---

## 0. Architectural Principle: Deterministic Core, Optional Intelligence

Each feature is defined with:

- **Baseline Mode (No LLM)** – what the tool can do on its own
- **Enhanced Mode (With LLM)** – what additional value LLMs provide

This ensures:
- Offline usability
- Predictable behavior
- Safe degradation if LLMs are unavailable

---

## 1. Graph Traversal (DFS / BFS)

### Purpose
Enable deterministic **dependency reachability and impact analysis**.

---

### Baseline Mode (No LLM)

#### Capabilities
- Traverse outgoing dependencies
- Traverse incoming dependencies
- Limit traversal depth
- Filter by dependency type

#### Outputs
```yaml
start_node: PricingService
reachable:
  direct:
    - TaxService
  transitive:
    - InvoiceService
    - ReportingService
```

#### Usability Without LLM
- Impact analysis for changes
- Manual reasoning by architects
- Used to scope refactoring tasks

---

### Enhanced Mode (With LLM)

LLMs can:
- Explain *why* dependencies exist
- Highlight which dependencies are likely incidental
- Summarize impact in human language

---

## 2. Ordering & Layering (Topological Sort)

### Purpose
Determine **valid dependency orderings** and detect layering violations.

---

### Baseline Mode (No LLM)

#### Capabilities
- Detect DAG vs cyclic graph
- Produce topological ordering when possible
- Flag edges violating declared or inferred layers

#### Outputs
```yaml
is_dag: false
layer_violations:
  - from: InfraService
    to: DomainService
```

#### Usability Without LLM
- Enforce architecture rules
- Support build and deployment ordering
- Manual remediation planning

---

### Enhanced Mode (With LLM)

LLMs can:
- Infer *intended* layering from naming and structure
- Suggest alternative layer definitions

---

## 3. Cycle Detection (Strongly Connected Components)

### Purpose
Identify and scope **cyclic dependencies**, the most critical structural issue in large systems.

---

### Baseline Mode (No LLM)

#### Capabilities
- Detect SCCs
- Rank SCCs by size and external coupling
- Produce condensed SCC DAG

#### Outputs
```yaml
scc_id: 17
members:
  - OrderService
  - PricingService
  - DiscountService
severity:
  size: 3
  external_edges: 6
```

#### Usability Without LLM
- Clear identification of refactoring targets
- Manual cycle-breaking strategies
- Objective prioritization

---

### Enhanced Mode (With LLM)

LLMs can:
- Explain semantic causes of cycles
- Propose staged cycle-breaking plans

---

## 4. Clustering & Community Detection

### Purpose
Reveal **implicit architectural groupings** and structural cohesion.

---

### Baseline Mode (No LLM)

#### Capabilities
- Cluster services using modularity-based algorithms
- Compute cluster cohesion and coupling
- Generate hierarchical clusters

#### Outputs
```yaml
cluster_id: C4
services:
  - BillingService
  - TaxService
  - InvoiceService
modularity: 0.61
```

#### Usability Without LLM
- Identify natural service groups
- Detect distributed monoliths
- Support manual boundary redesign

---

### Enhanced Mode (With LLM)

LLMs can:
- Label clusters with inferred domain names
- Explain boundary violations in natural language

---

## 5. Metric Computation

### Purpose
Provide **objective measurements** of architectural quality.

---

### Baseline Mode (No LLM)

#### Core Metrics

**Structural**
- Fan-in / fan-out
- Afferent / efferent coupling
- Instability

**Graph**
- Degree centrality
- Betweenness centrality

**Cycle**
- SCC size
- External dependency count

#### Outputs
```yaml
service: PricingService
metrics:
  fan_in: 14
  fan_out: 3
  instability: 0.18
```

#### Usability Without LLM
- Ranking hotspots
- Trend analysis over time
- Quantitative refactoring validation

---

### Enhanced Mode (With LLM)

LLMs can:
- Interpret metrics in architectural terms
- Explain trade-offs and risks

---

## 6. Cross-Feature Guarantees

### Determinism
- All baseline features must be reproducible
- Same input graph → same output

### Explainability
- Every finding references concrete nodes and edges

### Scalability
- All algorithms operate on reduced graphs when possible

---

## 7. Minimal Viable Tool (No LLM)

With **no LLM support**, the tool still provides:

- Dependency visualization
- Cycle and hotspot detection
- Cluster-based architecture views
- Quantitative refactoring prioritization

This already matches or exceeds the **core capabilities of classic static analysis tools**.

---

## 8. Progressive Enhancement Path

| Capability | No LLM | With LLM |
|----------|--------|----------|
| Impact analysis | ✔ | ✔ (explained) |
| Cycle detection | ✔ | ✔ (strategies) |
| Clustering | ✔ | ✔ (domain naming) |
| Metrics | ✔ | ✔ (interpretation) |
| Refactoring plans | Manual | Assisted |

---

## 9. Outcome

This design ensures:

- The system is **useful on day one**
- LLMs improve usability, not correctness
- Architectural decisions remain auditable and defensible

The result is a **robust static architecture analysis platform**, not an LLM-dependent experiment.

