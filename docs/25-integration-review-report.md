# Integration Review Report

Date: 2026-06-14

Status: `PASS WITH SUPERSET DEPLOYMENT DEFERRED`

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
conflicts. No Superset dashboard/runbook commit exists in local or remote refs.

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

The older `green_taxi_warehouse_reconciliation_v1` now contains DQ fixture
rows (+1 trip/assignment, +2 shifts, +1 quarantine), so generic release
validation fails its two source-count checks. No data was deleted. Idempotency
evidence remains documented from the two full reruns: fact/SCD2/DQ/quarantine
business-state deltas were zero and successful batch history was retained.

## Integration decisions

- Data dictionary promoted to `docs/21-data-dictionary.md`; corrected from 97
  to 107 columns based on executable DDL.
- Requirements audit promoted to a certified traceability matrix with DDS,
  DQ-dataset and unsupported-data boundaries.
- Semantic diagram promoted with pickup/dropoff/shift roles and explicit
  fact-to-fact fan-out prevention.
- Tool-specific relationship terminology removed from current docs.
- Historical TLC=0 validation retained but marked superseded.
- Factual reconciliation totals corrected where a DQ fixture had contaminated
  revenue and distance.
- Superset proposal remains under `docs/drafts`: exact image `6.1.0` manifest
  and compose syntax are verified, PostgreSQL driver requirement documented,
  default privileges fixed for the warehouse object owner, and hard-coded
  password fallbacks removed.

## Validation and security

- Python compile: pass for required five files.
- Unit tests: 125 pass.
- Main Docker Compose config: pass; four services healthy.
- Full clean warehouse validation: 14/14 checks pass.
- Superset proposal Compose config: pass.
- Superset runtime/health/read-only query: not run because no implementation
  workstream exists and the proposal must not be treated as deployed.
- `.env`, raw/full data, database files and volumes remain ignored.
- No secret, database dump, full data or metadata database was added to Git.
