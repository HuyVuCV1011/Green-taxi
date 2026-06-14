# Work Breakdown Structure

## Milestone 1 - Source package

Status: `COMPLETED`

- Scope and user decisions.
- Synthetic data contracts.
- Driver/Fleet/Dispatch/Assignment generation.
- Manifest and validation.
- Linked repository sample.

## Milestone 2 - Staging

Status: `IMPLEMENTED BASELINE / REVIEW PENDING`

### M2A - Warehouse staging baseline

- PostgreSQL warehouse schemas and DDL.
- Common staging metadata contract.
- Sample/file adapters for lightweight tests.
- Batch metadata, checksum/watermark and row hash.
- Idempotent staging reload test.

### M2B - Heterogeneous source simulation

- Docker Compose cho MySQL HR, MongoDB Fleet, PostgreSQL Dispatch và warehouse.
- Idempotent seed scripts từ Google Drive release.
- MySQL, MongoDB và PostgreSQL source adapters.
- Source health checks và connection configuration.
- Release-to-source và source-to-staging reconciliation.

Deliverable: source systems được seed đồng nhất và records được extract vào
staging với audit counts/lineage.

Current baseline đã có Docker Compose, source seed scripts, warehouse DDL và
source-to-staging loader. Trước khi khóa Milestone 2, cần review chéo loader,
chạy smoke/full setup trên môi trường sạch và lưu lại kết quả reconciliation.

## Milestone 3 - DQ and NDS

Status: `IMPLEMENTED; INTEGRATION REPORT PENDING`

- Type/schema validation.
- Driver/vehicle upsert.
- SCD event processing.
- Missing-master/inferred-member workflow.
- Trip-assignment integration.
- Rejected/quarantine tables.

Deliverable: integrated relational model and DQ report.

## Milestone 4 - DDS

Status: `IMPLEMENTED; INTEGRATION REPORT PENDING`

- Date/time dimensions.
- Driver/vehicle/location/vendor dimensions.
- Fact driver trip.
- Fact driver shift.
- Indexes and aggregate queries.

Deliverable: reconciled Driver Operations star schema.

## Milestone 5 - Analytics

Status: `PLANNED`

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
| Data release, source seeding and ingestion | Member A | Member B |
| DQ, NDS and SQL | Member B | Member C |
| DDS, dashboard and analytics | Member C | Member A |
| Report/slide integration | Team lead | All |
