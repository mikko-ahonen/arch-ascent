# Vision Structure: Groupings, References, and Intent

This document clarifies the **big-picture mental model** behind vision creation in the system, with a focus on how **groupings** and **references** interact. It revises and replaces the earlier framing of “two orthogonal axes” to better reflect how architects actually think and work at scale.

No new concepts are introduced. This document consolidates and sharpens terminology already present in the Vision Creation UI model and interaction patterns.

---

## 1. Core Problem Being Addressed

Large-scale architectures (e.g. 300–500 microservices) exceed human cognitive capacity when approached purely through structural diagrams or dependency graphs.

To form and communicate a vision, architects need:

- A way to **sketch structure** without committing too early
- A way to **name concepts** before they can be precisely defined
- A way to let meaning and structure co-evolve

This system addresses the problem by deliberately separating *structural sketching* from *concept formation*.

---

## 2. Two Complementary Dimensions (Revised)

Rather than two symmetric “axes”, the vision model consists of **two complementary dimensions with different cognitive roles**:

1. **Groupings** — externalized structural sketches
2. **References** — emergent architectural vocabulary

They interact, but neither subsumes the other.

---

## 3. Groupings: Structural Sketches

**Groupings** are the primary mechanism for visual and spatial reasoning.

They answer the question:

> “Which things do I currently see as belonging together?”

Characteristics:

- Visual and spatial
- Exploratory and reversible
- Semantically neutral by default
- May overlap across drafts
- May contradict each other across perspectives

Groupings:

- Do *not* require formal meaning
- Do *not* imply correctness or commitment
- Exist to externalize intuition

They are analogous to **sketches on a whiteboard** — valuable precisely because they are imprecise.

---

## 4. References: Architectural Vocabulary

**References** introduce *language* into architectural thinking.

They answer the question:

> “What concept am I trying to talk about?”

A reference is a **named set of elements**.

References may be defined:

- **Semi-formally**, via natural language
  - e.g. “Payment public APIs”
- **Formally**, via tag-based expressions
  ```
  PaymentPublicApiEndpoints =
    endpoints tagged payment AND api AND public
  ```

Key properties:

- References name concepts before structure stabilizes
- They are independent of groupings
- They may evolve in definition while keeping the same name

In this sense, references are **new vocabulary** introduced into the architectural conversation.

---

## 5. Tags: Precision Mechanism (Not Vocabulary)

Tags support references, but are not architectural vocabulary by themselves.

Tags:

- Are low-level labels
- Enable machine-resolvable definitions
- Allow references to become precise over time

A reference may:

- Start with no tags at all
- Gradually acquire tag-based definition
- Be redefined without changing its conceptual role

This allows architects to *name first, define later*.

---

## 6. How Groupings and References Interact

Groupings and references deliberately **do not collapse into one concept**.

### Allowed (and Valuable) Tensions

- A reference may span multiple groupings
- A grouping may contain elements from many references
- A grouping may fail to align with a reference

Such misalignment is **signal**, not error.

It highlights:

- Ambiguity in intent
- Inconsistencies in structure
- Areas needing further thought

---

## 7. Intent Uses References, Not Groupings

Architectural intent is expressed *using references*.

Examples:

- “There must be only one `$PaymentApiGrouping`”
- “All `$PaymentPublicApiEndpoints` should belong to `$PaymentApiGrouping`”

Intent:

- Refers to named concepts (references)
- Is independent of any particular sketch
- Can survive changes in grouping drafts

This makes intent more stable than structure during vision formation.

---

## 8. Cognitive Payoff at Scale

This separation allows architects to:

- Sketch structure without linguistic burden
- Introduce vocabulary without structural commitment
- Iterate on both independently

As a result:

- Vision creation becomes tractable even at hundreds of services
- The system supports human sensemaking rather than replacing it
- Long-term architectural reasoning becomes possible

---

## 9. Summary Mental Model

The corrected and precise mental model is:

> **Groupings are sketches.**  
> **References are vocabulary, defined first in language and later formalized via tags.**

Structure and meaning co-evolve, but neither is forced prematurely.

This balance is what makes the vision creation process both realistic and scalable.

