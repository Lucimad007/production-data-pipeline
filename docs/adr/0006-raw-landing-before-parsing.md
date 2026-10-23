# ADR 0006: Preserve raw API responses before parsing

- **Status:** Accepted
- **Date:** 2026-10-23
- **Deciders:** Breakout maintainer

## Context

API payloads change. Fields disappear, counts become hidden, new fields appear, and a parser bug can silently drop rows. Re-fetching is expensive against a quota-limited API, and historical statistics cannot be reconstructed from the public API.

## Decision

Write every API response to an immutable raw landing zone before parsing. The file name is a hash of the request, fetch time, and payload. The envelope includes the endpoint, safe params, status, timestamps, payload, and hashes. Bronze tables are derived from the raw layer and can be rebuilt without another API call.

## Alternatives considered

- **Parse and insert directly:** Fewer files, but no replay and no audit trail.
- **Log only errors:** Misses the payloads that parse successfully but later prove wrong.
- **Warehouse-only staging:** Better than nothing, but a warehouse restore is heavier than reading a JSON file.

## Consequences

**Positive**

- A parser fix can replay history without spending quota.
- Schema drift is diagnosable from the exact payload.
- The raw layer is the audit trail for "what did we actually receive?"
- Idempotency is easier: the response identity is explicit.

**Negative**

- More storage and file count.
- A retention policy is required in production.
- The raw layer contains public comments; PII handling and retention must be explicit.

## Revisit when

- Storage cost or retention policy demands compression/tiering.
- The source provides a replayable change feed.
- Compliance requires redaction before landing, not after.
