# Integration Review Report

Date: 2026-06-14

Status: `PASS - PIPELINE AND SUPERSET LOCAL DEMO VALIDATED`

Superset runtime evidence hiện hành:
[../analytics/superset-local-demo-runbook.md](../analytics/superset-local-demo-runbook.md).

## Commit lineage

Base common ancestor for all sibling workstreams:
`90f6dfeb2bd6663259572e102ec1eee46eb8faa3`.

Integrated order:

1. `720a60be` reconciliation/idempotency.
2. `12442455` analytics semantic/metric contract.
3. `15bb69cf` analytics requirements audit, cherry-picked as `646053b7`.
4. `87a93017` data dictionary draft, cherry-picked as `a86a77ad`.
5. `babf3bbe` Superset readiness draft, cherry-picked as `18584aec`.

All three draft commits had parent `90f6dfe`; cherry-picks completed without
conflicts. Đoạn lineage này là lịch sử trước khi Superset implementation được
bổ sung; không mô tả trạng thái repository hiện tại.

## Full-data reconciliation

Validated database: `green_taxi_warehouse_clean_validation_v2`.

| Check | Result |
|---|---:|
| TLC CSV files | 19, 2020-01 through 2021-07 |
| TLC release bytes | 208,865,428 |
| Source-to-staging audit | 4,768,237 / 4,768,237 |
| Staging TLC rows | 2,304,517 |
| Staging assignments | 2,304,276 |
| NDS trips / assignments | 2,304,276 / 2,304,276 |
| NDS shifts | 157,379 |
| DDS trip / shift facts | 2,304,276 / 157,379 |
| Revenue | 48,535,884.47 |
| Distance | 87,426,352.1700 miles |
| Duration | 48,423,718.63 minutes |
| DQ issues | 6,206 WARN `DQ_NEGATIVE_VAL` |
| Quarantine | 0 |
| Duplicate NDS trip / DDS trip / DDS shift | 0 / 0 / 0 |
| Multiple-current driver / vehicle SCD2 | 0 / 0 |
| Invalid shift minute balance | 0 |

Pipeline runtime in this clean snapshot: staging `385.16s`, NDS `460.93s`,
DDS `345.16s`.

Con số `6,206` là clean full-release snapshot. Số `6,211` trong
[full-release-reconciliation.md](full-release-reconciliation.md)
thuộc database reconciliation cũ hơn và được giữ lại để chứng minh idempotency
tại thời điểm chạy hai lần liên tiếp; không dùng làm clean integration total
hiện hành.

The older `green_taxi_warehouse_reconciliation_v1` now contains DQ fixture
rows (+1 trip/assignment, +2 shifts, +1 quarantine), so generic release
validation fails its two source-count checks. No data was deleted. Idempotency
evidence remains documented from the two full reruns: fact/SCD2/DQ/quarantine
business-state deltas were zero and successful batch history was retained.

## Integration decisions

- Data dictionary promoted to `docs/warehouse/dds-data-dictionary.md`; corrected from 97
  to 107 columns based on executable DDL.
- Requirements audit promoted to a certified traceability matrix with DDS,
  DQ-dataset and unsupported-data boundaries.
- Semantic diagram promoted with pickup/dropoff/shift roles and explicit
  fact-to-fact fan-out prevention.
- Tool-specific relationship terminology removed from current docs.
- Historical TLC=0 validation retained but marked superseded.
- Factual reconciliation totals corrected where a DQ fixture had contaminated
  revenue and distance.
- Superseded Superset và OLAP proposal artifacts đã được loại khỏi cây tài liệu;
  lịch sử review vẫn được bảo toàn trong Git.
- Superset `6.1.0` dùng metadata PostgreSQL riêng và custom image bổ sung
  `psycopg2-binary==2.9.11`.
- BI login chỉ có quyền trên approved `analytics` views; quyền đọc DDS trực tiếp
  và quyền ghi đều bị smoke test từ chối.
- Sáu datasets, 51 certified metric instances, 32 charts và monitoring dashboard BQ01-BQ05 trên 4 tabs được provision tự động và idempotent.
- Mỗi chart đều được cấu hình tự động sinh `query_context` giúp REST API v1 truy vấn trực tiếp thành công.
- Benchmark local ghi nhận trung bình các giá trị P95 của 32 charts là
  `0.615` giây; đây không phải end-to-end dashboard P95. Dữ liệu chi tiết nằm
  tại `deliverables/benchmark/superset_benchmark_results.json`.

## Validation and security

- Python compile: pass cho Superset setup/provision/smoke scripts.
- Unit tests: 136 pass.
- Main Docker Compose config: pass; four services healthy.
- Full clean warehouse validation: 14/14 checks pass.
- Superset Compose config: pass.
- Superset app và metadata DB: healthy.
- Superset runtime/API login/dashboard/dataset smoke tests: pass.
- Read-only analytics query và write-denial tests: pass.
- Browser walkthrough: 4 tabs render hoàn chỉnh, không có Data/Network error
  hoặc loading treo.
- `.env`, `.env.superset`, raw/full data, database files và volumes remain ignored.
- No secret, database dump, full data or metadata database was added to Git.
