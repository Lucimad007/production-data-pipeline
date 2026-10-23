# ADR 0003: Dagster for orchestration

- **Status:** Accepted
- **Date:** 2026-10-23
- **Deciders:** Breakout maintainer

## Context

The pipeline has three observable stages: ingest, transform, and health. The operating surface should show lineage, run metadata, asset checks, and a schedule. The project runs on Windows, and the maintainer needs a fast local loop.

Airflow is still the enterprise default and the most common orchestration keyword in job postings. Dagster is smaller but asset-centric: the unit of work is a data asset, not a task.

## Decision

Use **Dagster OSS**. Model `ingest`, `dbt_models`, and `pipeline_health` as assets. Attach checks for bronze rows, quota, and mart presence. Schedule a daily refresh at 06:00 UTC.

## Alternatives considered

- **Airflow 3.3:** Strong hiring signal, asset partitioning, and a large ecosystem. Heavier local setup on Windows and less natural for asset checks and lineage.
- **Prefect:** Good Python ergonomics, but less opinionated about data assets and checks.
- **Cron + scripts:** Simplest, but no lineage, retries, or observable run metadata.

## Consequences

**Positive**

- The UI tells the data story: assets, dependencies, checks, metadata.
- Checks and run metadata are first-class, not an afterthought.
- The pipeline runs natively on Windows without WSL or Docker.

**Negative**

- Dagster appears in fewer job descriptions than Airflow.
- The ingestion asset is intentionally coarse; splitting it into five assets would duplicate API calls and complicate quota accounting.
- A move to Airflow requires porting the asset functions into a DAG; the logic lives in plain Python, so the port is mechanical.

## Revisit when

- The target team runs Airflow and wants a direct contribution.
- The pipeline needs multi-tenant scheduling, complex SLAs, or a managed control plane.
- The asset graph grows beyond a single team's ownership.
