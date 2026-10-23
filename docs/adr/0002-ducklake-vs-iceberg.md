# ADR 0002: DuckLake locally, Iceberg as the production path

- **Status:** Accepted
- **Date:** 2026-10-23
- **Deciders:** Breakout maintainer

## Context

The project is local-first and must run on Windows without Docker. It needs ACID tables, time travel, schema evolution, and a credible lakehouse story. The total data is small: hundreds of videos, thousands of snapshots, a few hundred comments.

DuckLake 1.x stores table metadata in a SQL database and data in Parquet. It attaches natively in DuckDB and dbt-duckdb, which makes the local loop fast. Apache Iceberg is the broader industry standard and the stronger hiring signal, especially with a REST catalog.

## Decision

Use **DuckLake** for local development and the public demo. Keep the dbt SQL ANSI and adapter-agnostic. Document **Iceberg with a REST catalog** as the production path, and use the same semantic models when the project moves to a multi-engine environment.

## Alternatives considered

- **Iceberg + PyIceberg/Spark/Trino:** More portable, but a heavier local setup and slower iteration for this data size.
- **Delta Lake:** Strong Databricks signal, but less aligned with the open lakehouse direction in 2026.
- **Plain Parquet:** Simple, but no ACID, schema evolution, or time travel.

## Consequences

**Positive**

- One-command local lakehouse with no Docker.
- dbt builds and tests run in seconds.
- The data files are Parquet, so an Iceberg migration is not a rewrite of the storage format.

**Negative**

- DuckLake does not enforce primary keys; uniqueness is enforced by the loader and dbt tests.
- The DuckLake ecosystem is smaller than Iceberg's.
- Data path identity is strict: the catalog stores the `DATA_PATH` string and rejects a different string, even if it resolves to the same directory. See `docs/postmortem-001-ducklake-path.md`.
- Deletion vectors are still maturing.

## Revisit when

- Multiple engines or teams need the same tables.
- Concurrent writers or catalog-level governance are required.
- The target employer standardizes on Iceberg, Delta, or a specific REST catalog.
