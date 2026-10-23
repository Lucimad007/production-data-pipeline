# ADR 0005: A small metric registry before a semantic layer

- **Status:** Accepted
- **Date:** 2026-10-23
- **Deciders:** Breakout maintainer

## Context

The eventual AI analyst must answer questions such as "which topics broke out?" without inventing metric definitions. Raw text-to-SQL against raw tables is the wrong default: it picks the wrong grain, invents joins, and treats hidden counts as zero.

Cube and the dbt Semantic Layer are mature products, but they add a service, configuration surface, and operational cost. This project has one product, one owner, and roughly 10-15 metrics.

## Decision

Start with a **small YAML metric registry**: name, description, grain, owner, SQL, dimensions, examples, and tests. Compile it into a read-only query surface. Expose that surface through an MCP server when the AI workstream lands. Adopt Cube or the dbt Semantic Layer when multiple teams need the same definitions.

## Alternatives considered

- **Raw text-to-SQL:** Fast to demo, hard to govern, and prone to plausible wrong answers.
- **Cube:** Strong semantic layer and MCP support, but another service to run and configure.
- **dbt Semantic Layer / MetricFlow:** Natural if the team already runs dbt Cloud; heavier for a local-first project.
- **Vendor agent:** Convenient, but locks the interface and hides the metric contract.

## Consequences

**Positive**

- The agent can only query metrics a human defined and tested.
- Definitions live in version control with the models.
- The contract is small enough to review in one sitting.
- The upgrade path to a real semantic layer is clear.

**Negative**

- Custom code to compile and validate metrics.
- Not a full semantic layer: no complex joins, caching, or multi-tenant access control.
- The registry must be maintained as the marts evolve.

## Revisit when

- More than one team or product consumes the metrics.
- Metric definitions need joins, hierarchies, or governed access control.
- The agent needs a richer context graph than a YAML file can express.
