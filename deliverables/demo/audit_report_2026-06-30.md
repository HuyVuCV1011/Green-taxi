# Audit Report - Technical Demo Readiness

> Historical June 2026 full-system demo audit. The Superset dashboard section
> predates the July 2026 clean-slate dashboard rebuild. Current dashboard
> evidence is documented in
> `dashboard_only_20260713/dashboard_demo_manifest_20260713.md`.

Date: 2026-06-30
Project: NYC Green Taxi Driver Operations BI
Status: READY FOR TECHNICAL DEMO

## Scope Checked

This audit focused on the current implementation scope:

- Heterogeneous source simulation: MySQL HR, MongoDB Fleet, PostgreSQL Dispatch, TLC and lookup files.
- Warehouse flow: Staging -> DQ/Audit/Quarantine -> NDS -> DDS.
- BI layer: Apache Superset certified analytics datasets and dashboard.
- Streamlit Data Pipeline Control Panel.
- OLAP and Data Mining extensions.
- Test, reconciliation and smoke-test evidence for grading.

The audit did not validate archived designs or old Power BI/Fabric ideas as current scope.

## Environment Status

| Item | Result |
|---|---|
| Docker daemon | Running |
| Source containers | Healthy |
| Warehouse container | Healthy |
| Superset container | Healthy |
| Streamlit health | `http://localhost:8501/_stcore/health` returned `ok` |
| Superset health | `http://localhost:8088/health` returned `OK` |
| OBS | Installed at `C:\Program Files\obs-studio\bin\64bit\obs64.exe` |
| FFmpeg | Available |

Running containers verified:

- `green_taxi_mysql_hr`
- `green_taxi_mongodb_fleet`
- `green_taxi_postgres_dispatch`
- `green_taxi_postgres_warehouse`
- `green_taxi_superset_app`
- `green_taxi_superset_metadata_db`

## Issues Found And Fixed

| Issue | Risk | Fix |
|---|---|---|
| `data/raw/tlc` was missing inside the project workspace. Warehouse still had old TLC rows, but a fresh default pipeline run could skip TLC. | End-to-end reproducibility risk and confusing staging lineage. | Copied 19 TLC CSV files from the verified local release folder into ignored `data/raw/tlc`. |
| Latest staging audit before this run showed `2,463,720` rows from an operational-source-only rerun. | Teacher could question why full-release staging evidence does not match docs. | Re-ran the full pipeline. Latest staging audit is now `4,768,237 / 4,768,237`. |
| Data Mining step printed pandas DBAPI warnings. | No functional error, but terminal demo looked noisy. | Added a scoped warning suppression helper in `src/analytics/data_mining.py`. |
| Streamlit Auto-Demo success guidance still referenced Power BI. | Scope mismatch: current BI implementation is Superset. | Updated guidance to Superset dashboard and smoke test; added a regression test. |

## Full Pipeline Evidence

Command:

```powershell
python scripts/run_pipeline.py --release-id green-taxi-full-v1
```

Run ID: `a6714f57-8ee0-45aa-aa40-2118a1050ec4`

| Step | Status | Rows read | Loaded | Rejected | Runtime |
|---|---|---:|---:|---:|---:|
| `source_health` | SUCCEEDED | 4 | 4 | 0 | 0.02s |
| `load_staging` | SUCCEEDED | 4,768,237 | 4,768,237 | 0 | 6m 09s |
| `load_nds` | SUCCEEDED | 4,767,996 | 4,767,996 | 0 | 5m 28s |
| `load_dds` | SUCCEEDED | 2,463,943 | 2,463,943 | 0 | 3m 51s |
| `reconciliation` | SUCCEEDED | 14 | 14 | 0 | 2.85s |
| `data_mining` | SUCCEEDED | 895 | 895 | 0 | 16.84s |
| `mark_dds_ready` | SUCCEEDED | 0 | 1 | 0 | 0.00s |

Total runtime: about 15m 48s.

## Reconciliation Evidence

Command:

```powershell
python scripts/validate_warehouse_pipeline.py --release-id green-taxi-full-v1
```

Key checks:

| Check | Result |
|---|---|
| Source-to-staging audit | `(4,768,237, 4,768,237)` PASS |
| NDS trips to DDS trips | `2,304,276` PASS |
| Completed NDS shifts to DDS shifts | `157,379` PASS |
| Total revenue | `48,535,884.47` PASS |
| Trip distance | `87,426,352.1700` PASS |
| Trip duration | `48,423,718.63` PASS |
| Duplicate NDS trip natural keys | `0` PASS |
| Duplicate DDS trip IDs | `0` PASS |
| Duplicate DDS shift IDs | `0` PASS |
| Multiple current driver/vehicle SCD rows | `0 / 0` PASS |
| Invalid shift minutes | `0` PASS |

## Superset Evidence

Command:

```powershell
python -m scripts.smoke_test_superset
```

Result:

| Item | Value |
|---|---:|
| Health | `OK` |
| Dashboard count | 1 |
| Dataset count | 10 |
| Metric instance count | 88 |
| Chart count | 42 |
| Native filter count | 0 |
| Trip count | 2,304,276 |
| Total revenue | 48,535,884.47 |
| Shift count | 157,379 |
| Benchmark current | true |

Visual checks confirmed:

- Dashboard title: `NYC Green Taxi - Driver Operations`.
- Historical video tabs were present in the June 2026 recording. The current
  July 2026 dashboard uses: Executive pulse, Demand patterns, Workforce actions,
  Trust & data health, OLAP lab and Exploratory models.
- Operations KPI strip renders: total revenue, trips, active drivers, active vehicles and utilization.
- Data Quality tab separates DQ, quarantine and anomaly concepts.
- OLAP tab includes slice, dice, drill-down, roll-up and pivot outputs.
- Data Mining tab includes driver segments and route association rules.

## Automated Tests

Command:

```powershell
python -m unittest discover -s tests -v
```

Result: 139 tests passed.

Covered areas include:

- Analytics contract and certified metrics.
- Warehouse DDL contracts.
- NDS/DDS loaders, SCD2 and DQ issue behavior.
- PipelineRunner ordering, fail-fast, dry-run and sanitization.
- Streamlit control panel lock/concurrency and current Superset guidance.
- Superset provisioning contract and read-only BI role boundaries.
- Markdown documentation link and stale-reference checks.

## Remaining Demo Risks

| Risk | Mitigation |
|---|---|
| Full pipeline takes about 15-18 minutes on local machine. | In video, show latest full run evidence and run short validation/smoke commands live. If showing full run, use OBS pause/cut points. |
| `.env` and `.env.superset` contain local credentials. | Do not open these files or show `show_superset_login.py` output in video. |
| Raw full data is intentionally ignored by Git. | Keep `data/raw/tlc` and `data/raw/synthetic` present locally before recording. |
| Superset login/session may expire. | Open dashboard before recording and verify charts are loaded. |

## Current Decision

The system is technically ready for a grading-focused demo. The video should emphasize architecture, data lineage, reconciliation, DQ/anomaly separation, semantic BI contracts and automated tests, not just dashboard visuals.
