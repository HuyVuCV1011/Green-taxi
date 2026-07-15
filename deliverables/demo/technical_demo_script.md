# Technical Demo Script

Project: NYC Green Taxi Driver Operations BI
Audience: Technical grading / instructor review
Goal: Prove design, implementation, data correctness and BI usability end to end.

## Recording Style

This is not a customer-sales demo. The video should feel like a technical defense:

- Explain why each layer exists.
- Show evidence, not only screens.
- Use exact table/view names where useful.
- Keep dashboard discussion tied to certified metrics and business questions.
- Avoid credentials, `.env` files and old Power BI/Fabric scope.

Recommended length: 12-18 minutes after cuts. No strict time limit is required.

## Chapter Plan

| Chapter | Target length | Screen | Technical point | Subtitle overlay |
|---|---:|---|---|---|
| 1. Problem and scope | 1m | README + `docs/context/scope.md` | Driver Operations scope, end user and decisions supported. | `Scope: Driver Operations, not marketing or real-time dispatch` |
| 2. Architecture | 1m 30s | Architecture diagram / Streamlit flow diagram | TLC files + MySQL HR + MongoDB Fleet + PostgreSQL Dispatch -> Staging -> DQ/Audit -> NDS -> DDS -> Superset. | `Architecture: Staging -> DQ/Audit -> NDS -> DDS -> BI` |
| 3. Source systems | 1m 30s | Terminal queries or Streamlit Source Explorer | Four business source roles and heterogeneous interfaces. | `Feature: Heterogeneous source integration` |
| 4. Pipeline evidence | 2m | Streamlit Pipeline tab + terminal | Show ordered steps and latest full run ID. Do not wait 16 minutes unless intentionally recording full run. | `Pipeline: full release loaded and reconciled` |
| 5. Row reconciliation | 1m 30s | Terminal validation output | Counts, revenue, distance, duration, duplicate keys and SCD current-row checks. | `Validation: row counts, measures and grain checks pass` |
| 6. Data quality | 1m 30s | Superset DQ tab + DQ docs/tests | Separate DQ issue, quarantine, trip anomaly and shift anomaly. | `Quality Gate: DQ errors are separate from business anomalies` |
| 7. NDS and DDS design | 1m 30s | DB/schema docs or table counts | NDS integrates entities; DDS star schema serves BI metrics. | `Warehouse: NDS integration and DDS star schema` |
| 8. Superset dashboard | 3m | Superset dashboard in Chrome | Executive pulse, Demand patterns, Workforce actions, Trust & data health, OLAP lab, Exploratory models. | `BI Layer: 14 datasets, 109 metric instances, 35 visuals` |
| 9. Security and permissions | 45s | Smoke test output | `superset_ro` reads analytics views only; DDS/write access denied. | `Security: BI role is read-only on approved analytics views` |
| 10. Test evidence | 1m | Terminal test output | 141 automated tests pass. | `Evidence: 141 automated tests pass` |
| 11. Limitations | 45s | Audit report | Local batch demo, no ODS, no streaming, no production HA. | `Boundary: local historical batch, no ODS or streaming` |

## Live Commands To Show

Use these live commands because they are fast and safe:

```powershell
python scripts/validate_warehouse_pipeline.py --release-id green-taxi-full-v1
python -m scripts.smoke_test_superset
python -m unittest discover -s tests -v
```

Optional short command:

```powershell
python scripts/run_pipeline.py --release-id green-taxi-full-v1 --dry-run
```

Avoid showing:

```powershell
python -m scripts.show_superset_login
Get-Content .env
Get-Content .env.superset
```

## Evidence Numbers To Mention

| Evidence | Value |
|---|---:|
| Staging full-release audit | 4,768,237 rows |
| NDS loaded rows | 4,767,996 rows |
| DDS loaded rows in latest full run | 2,463,943 rows |
| Driver trip fact rows | 2,304,276 |
| Completed shift fact rows | 157,379 |
| Total revenue | 48,535,884.47 USD |
| Active drivers on dashboard | 795 |
| Active vehicles on dashboard | 795 |
| Shift utilization | 69.26% |
| Superset datasets | 14 |
| Superset metric instances | 109 |
| Superset charts | 35 |
| Automated tests | 141 passed |

## Narration Notes

### Opening

"Dự án này không cố làm một dashboard tổng hợp mọi phòng ban. Phạm vi được chốt là Driver Operations: quản lý vận hành đội xe và tài xế, với dữ liệu lịch sử theo batch."

### Architecture

"Google Drive release chỉ là gói phân phối dữ liệu. Source nghiệp vụ trong runtime là HR MySQL, Fleet MongoDB, Dispatch PostgreSQL và TLC/lookup file batch. Warehouse PostgreSQL là hệ thống đích riêng."

### DQ

"DQ issue không được cộng lẫn với business anomaly. DQ/quarantine là boundary chất lượng dữ liệu; trip/shift anomaly là tín hiệu vận hành cần kiểm tra."

### BI

"Superset không đọc trực tiếp DDS bằng quyền rộng. Dashboard dùng analytics views và role read-only, để metric được kiểm soát theo semantic contract."

### Close

"Điểm mạnh của hệ thống là reproducibility: pipeline chạy lại được, row counts reconcile được, semantic layer được test, và dashboard chỉ là phần trình diễn cuối cùng của dữ liệu đã kiểm soát."

## Subtitle Caption Bank

Use these as burn-in captions or chapter overlays:

- `Scope: Driver Operations for fleet and driver managers`
- `Source Systems: TLC files, MySQL HR, MongoDB Fleet, PostgreSQL Dispatch`
- `Pipeline: source health -> staging -> NDS -> DDS -> reconciliation -> mining`
- `Lineage: release_id, batch_id, row_hash and audit metadata`
- `DQ Boundary: ERROR quarantine, WARN retained with lineage`
- `Warehouse: NDS integrates, DDS serves analytics`
- `SCD2: one current row per driver and vehicle`
- `Semantic Layer: certified analytics views`
- `Superset: 14 datasets, 109 metric instances, 35 visuals`
- `OLAP: slice, dice, drill-down, roll-up and pivot`
- `Data Mining: driver segmentation and route association rules`
- `Validation: revenue, distance, duration and grain checks pass`
- `Security: read-only BI role on approved analytics views`
- `Tests: 141 automated tests passed`
