# Work Breakdown Structure

## Milestone 1 - Source package

Status: `COMPLETED`

- Scope and user decisions.
- Synthetic data contracts.
- Driver/Fleet/Dispatch/Assignment generation.
- Manifest and validation.
- Linked repository sample.

## Milestone 2 - Staging

- PostgreSQL schemas and DDL.
- Source-specific loaders.
- Batch metadata and file checksum.
- Row hash and raw row traceability.
- Idempotent reload test.

Deliverable: raw files loaded into staging with audit counts.

## Milestone 3 - DQ and NDS

- Type/schema validation.
- Driver/vehicle upsert.
- SCD event processing.
- Missing-master/inferred-member workflow.
- Trip-assignment integration.
- Rejected/quarantine tables.

Deliverable: integrated relational model and DQ report.

## Milestone 4 - DDS

- Date/time dimensions.
- Driver/vehicle/location/vendor dimensions.
- Fact driver trip.
- Fact driver shift.
- Indexes and aggregate queries.

Deliverable: reconciled Driver Operations star schema.

## Milestone 5 - Analytics

- KPI definitions.
- Dashboard wireframe.
- Power BI/Superset implementation.
- Driver/shift peer comparison.
- Business anomaly rules.

Deliverable: dashboard answering BQ01-BQ05.

## Milestone 6 - Submission

- Final report.
- Final slide deck.
- Demo recording.
- Team contribution table.
- AI-use log and meeting notes.
- Reproducibility guide.

## Suggested ownership

| Workstream | Owner | Reviewer |
|---|---|---|
| Data generation and ingestion | Member A | Member B |
| DQ, NDS and SQL | Member B | Member C |
| DDS, dashboard and analytics | Member C | Member A |
| Report/slide integration | Team lead | All |

