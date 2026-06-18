# Implementation Plan

## Phase 0 - Baseline

- Đóng băng tài liệu trước feedback trong `archive/`.
- Ghi rõ phạm vi trip hiện có: 01/2020-07/2021.
- Tạo manifest, checksum và validation report cho canonical data release.

## Phase 1 - Synthetic source package

- Sinh Driver HR master và change feed.
- Sinh Vehicle/Fleet master.
- Gán trip vào driver/vehicle khả dụng.
- Sinh shift từ chuỗi trip liên tục.
- Xuất release artifacts, manifest và validation report.

Exit criteria:

- Không có overlap driver/vehicle ở trip hoặc shift.
- Mọi assignment liên kết được trip, driver, vehicle và shift.
- Mọi trip hợp lệ được assignment hoặc ghi rõ lý do không assignment.
- Shift occupied/idle time reconcile với shift duration.
- Cùng seed và input tạo cùng output.
- Data owner công bố một release cố định cho cả nhóm.

## Phase 2A - Warehouse staging baseline

Status: `IMPLEMENTED BASELINE`

- Dựng PostgreSQL warehouse bằng Docker Compose.
- Tạo schema/table staging riêng cho từng source entity.
- Tạo `metadata_etl_batch` và `metadata_source_extract`.
- Định nghĩa common staging metadata cho file/database/document records.
- Viết file loaders làm baseline cho sample và contract tests.
- Gắn `release_id`, checksum/watermark, row hash, source identity và UTC load timestamp.
- Khóa nullability, keys/defaults và timezone semantics bằng contract tests.
- Viết idempotent reload và row-count reconciliation tests.

Mục đích của file baseline là khóa staging contract và cho phép CI/sample chạy
nhẹ. Warehouse DDL hiện nằm trong `sql/warehouse/` và được apply bằng
`scripts/apply_warehouse_ddl.py`.

## Phase 2B - Simulated operational sources

Status: `IMPLEMENTED AND VALIDATED`

- Bổ sung MySQL source cho Driver HR.
- Bổ sung MongoDB source cho Fleet.
- Bổ sung PostgreSQL source riêng cho Dispatch và Trip Assignment.
- Viết seed scripts đọc canonical release và nạp idempotent vào source systems.
- Ghi seed audit theo release ID, checksum và row count.
- Viết adapters extract từ MySQL, MongoDB và PostgreSQL nguồn.
- Giữ output của adapters tương thích staging contract Phase 2A.
- Chạy source-to-staging reconciliation.

Exit criteria:

- Một lệnh dựng được các services local sau khi đã có data release.
- Một lệnh seed được source systems mà không tạo duplicate khi chạy lại.
- Source và warehouse PostgreSQL là hai service/database độc lập.
- Sample mode không bắt buộc chạy toàn bộ source containers.
- Full mode extract từ source interfaces, không đọc HR/Fleet/Dispatch seed files
  trực tiếp vào warehouse.

Repo đã có Docker Compose, source seed scripts, source adapters và
source-to-staging reconciliation trên full release.

## Phase 3 - DQ and NDS

Status: `IMPLEMENTED AND VALIDATED`

- Chuẩn hóa type và timestamp.
- Upsert driver, vehicle, vendor và location.
- Xử lý inferred/late-arriving master.
- Validate assignment/shift temporal constraints.
- Tích hợp trip và assignment.
- Ghi quarantine, DQ issue và missing-master audit.

## Phase 4 - DDS

Status: `IMPLEMENTED AND VALIDATED`

- Sinh `dim_date` và `dim_time`.
- Load SCD2 `dim_driver`, `dim_vehicle`.
- Load `fact_driver_trip`.
- Tổng hợp `fact_driver_shift`.
- Reconcile row counts, revenue, distance và shift measures với NDS.

## Phase 5 - Analytics

Status: `IMPLEMENTED AND SMOKE-TESTED`

Đã triển khai:

1. Superset metadata database và local web app.
2. Warehouse login `superset_ro` chỉ đọc approved analytics views.
3. Superset datasets `trip_pickup`, `trip_dropoff`, `shift`, `dq_summary`,
   `pareto_pickup_zone` và `driver_performance_summary`.
4. Certified metrics theo semantic contract.
5. Operational monitoring dashboard BQ01-BQ05 với OLAP demo và Data Mining
   insights, 42 charts trên 6 tabs: Operations Overview, Demand Patterns,
   Driver & Fleet Performance, Data Quality & Anomalies, OLAP Demo và Data
   Mining Insights.
6. Health, API, permission, query và browser smoke tests.

Measures:

- Trip count.
- Occupied minutes.
- Idle minutes.
- Shift utilization.
- Revenue per hour.
- Average trip duration/distance.
- DQ/anomaly counts.

Dashboard dùng 5 business/summary datasets và 1 DQ dataset theo analytics
boundary. `analytics.shift_trip_aggregate` là view kỹ thuật chống fan-out, không
được provision thành Superset dataset độc lập.
Chi tiết:
[../analytics/superset-local-demo-runbook.md](../analytics/superset-local-demo-runbook.md).

## Phase 5B - OLAP extension

Status: `IMPLEMENTED; PENDING LIVE SUPERSET SMOKE AFTER PROVISION`

- Tạo PostgreSQL ROLAP views `analytics.olap_trip_cube` và
  `analytics.olap_shift_cube`.
- Giữ đúng fact grain, không join trực tiếp trip fact và shift fact ở row level.
- Bổ sung Superset datasets/charts để demo slice, dice, drill-down, roll-up và
  pivot.
- Reconcile các measure OLAP với certified metric catalog.

Chi tiết: [../analytics/olap-plan.md](../analytics/olap-plan.md).

## Phase 5C - Data Mining extension

Status: `IMPLEMENTED; PENDING LIVE SUPERSET BENCHMARK REFRESH`

- Tạo dataset chuẩn cho driver-level hoặc driver-month features.
- Chạy K-Means driver segmentation, đánh giá bằng centroid/silhouette và đặt
  nhãn theo ý nghĩa nghiệp vụ.
- Khai thác route/demand association rules bằng Apriori, đánh
  giá bằng support, confidence và lift.
- Xuất kết quả thành analytics tables/views để Superset trình bày.

Chi tiết: [../analytics/data-mining-plan.md](../analytics/data-mining-plan.md).

## Phase 6 - Delivery

- Báo cáo kiến trúc, source simulation, ETL, DQ, NDS/DDS và kết quả.
- Bổ sung phần OLAP ROLAP và Data Mining vào báo cáo/slide.
- Slide trình bày.
- Demo script chạy sample và full pipeline.
- Data dictionary và source-to-target mapping.
- Reproducibility guide.
- Release tag phục vụ nộp bài.

## Definition of done

- Data owner có thể tái tạo và validate canonical synthetic release.
- Thành viên có thể tải release, kiểm checksum và seed source systems.
- Một lệnh có thể chạy pipeline với sample.
- Full pipeline chạy từ source interfaces đến DDS.
- Seed, ingestion và warehouse reload đều idempotent.
- Tests và reconciliation pass.
- Dashboard trả lời đúng năm quyết định trong scope.
- Nếu triển khai Phase 5B/5C, OLAP và Data Mining phải trả lời được quyết định
  vận hành cụ thể, không chỉ trình diễn thuật toán.
