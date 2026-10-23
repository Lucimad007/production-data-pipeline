# ADR 0001: Use daily micro-batches, not streaming

- **Status:** Accepted
- **Date:** 2026-10-23
- **Deciders:** Breakout maintainer

## Context

Breakout ingests public YouTube data: channel metadata, uploads, lifetime view/like/comment counts, and top comments. The source is a pull API, not an event stream. The product answers daily creator questions: what broke out, which topics work, when to publish, and whether the pipeline is healthy.

There is no live chat, clickstream, or sub-minute SLA. YouTube statistics change on the order of minutes to hours, and the public API does not expose historical view counts.

## Decision

Run a daily Dagster job that pulls the newest 500 uploads and comments for the top 20 videos. Treat each pull as a micro-batch. Persist every API response before parsing so the batch is replayable. Do not add Kafka, Flink, or a streaming warehouse.

## Alternatives considered

- **Kafka + Flink:** Would add operational surface, watermark handling, and state management for a source that is polled anyway.
- **15-minute polling:** More quota, more snapshots, no product decision that needs it.
- **Direct API-to-warehouse:** Fast to demo, but loses the raw payload, replay, and schema-drift story.

## Consequences

**Positive**

- One process, one schedule, one quota ledger.
- Idempotent replay from raw JSON.
- The failure modes are observable and cheap to test.
- Local development works without Docker.

**Negative**

- Freshness is measured in hours, not seconds.
- There is no event-time watermark or exactly-once stream semantics.
- A 24-hour gap is a product limitation, not just an engineering one.

## Revisit when

- A real event source appears (live chat, clickstream, webhooks).
- The product needs a sub-minute SLA.
- The volume or concurrency outgrows a single DuckDB process.
