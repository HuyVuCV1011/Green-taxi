# Work Breakdown Structure

## Milestone 1 - Source package

Status: `COMPLETED`

- Scope and user decisions.
- Synthetic data contracts.
- Driver/Fleet/Dispatch/Assignment generation.
- Manifest and validation.
- Linked repository sample.

## Milestone 2 - Staging

Status: `COMPLETED`

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

Full-release source-to-staging reconciliation đã được lưu trong validation
evidence.

## Milestone 3 - DQ and NDS

Status: `COMPLETED`

- Type/schema validation.
- Driver/vehicle upsert.
- SCD event processing.
- Missing-master/inferred-member workflow.
- Trip-assignment integration.
- Rejected/quarantine tables.

Deliverable: integrated relational model and DQ report.

## Milestone 4 - DDS

Status: `COMPLETED`

- Date/time dimensions.
- Driver/vehicle/location/vendor dimensions.
- Fact driver trip.
- Fact driver shift.
- Indexes and aggregate queries.

Deliverable: reconciled Driver Operations star schema.

## Milestone 5 - Analytics

Status: `COMPLETED`

- Certified KPI definitions.
- Superset metadata DB và read-only warehouse connection.
- 10 Superset datasets, 88 metric instances và dashboard theo
  analytics contract.
- Driver/shift peer comparison.
- Business anomaly rules.
- Health, permission, query và browser smoke tests.

Deliverable: dashboard answering BQ01-BQ05 with OLAP demo and Data Mining insights.

## Milestone 5B - OLAP extension

Status: `IMPLEMENTED AND SMOKE-TESTED`

- PostgreSQL ROLAP views cho trip và shift.
- Superset datasets/charts thể hiện slice, dice, drill-down, roll-up và pivot.
- Reconciliation với certified metrics.
- Superset smoke test và benchmark artifact đã bao phủ đủ dashboard 6 tabs.

Deliverable: OLAP demo trên Superset phục vụ phân tích đa chiều vận hành.

## Milestone 5C - Data Mining extension

Status: `IMPLEMENTED AND BENCHMARKED`

- Driver feature dataset.
- K-Means driver segmentation.
- Route/demand association rules.
- Superset views/charts cho segment và top rules.
- Benchmark artifact đã refresh đủ 42 charts sau khi thêm Data Mining tab.

Deliverable: Data Mining outputs hỗ trợ điều phối/đào tạo dựa trên dữ liệu lịch sử.

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
| OLAP ROLAP extension | Member C | Member B |
| Data Mining extension | Member B | Member C |
| Report/slide integration | Team lead | All |
