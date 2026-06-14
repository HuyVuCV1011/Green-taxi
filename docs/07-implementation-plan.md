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

Status: `IMPLEMENTED BASELINE; FRESH-ENV FULL VALIDATION PENDING`

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

Repo hiện đã có Docker Compose, source seed scripts và source-to-staging loader
baseline. Công việc còn lại của Phase 2B là review trên fresh environment, bổ
sung integration tests có kiểm soát chi phí và chuẩn hóa lỗi/retry trước khi
đóng milestone; DQ/NDS và DDS đã được triển khai ở các phase sau.

## Phase 3 - DQ and NDS

Status: `IMPLEMENTED; FRESH-ENV FULL VALIDATION PENDING`

- Chuẩn hóa type và timestamp.
- Upsert driver, vehicle, vendor và location.
- Xử lý inferred/late-arriving master.
- Validate assignment/shift temporal constraints.
- Tích hợp trip và assignment.
- Ghi quarantine, DQ issue và missing-master audit.

## Phase 4 - DDS

Status: `IMPLEMENTED; FRESH-ENV FULL VALIDATION PENDING`

- Sinh `dim_date` và `dim_time`.
- Load SCD2 `dim_driver`, `dim_vehicle`.
- Load `fact_driver_trip`.
- Tổng hợp `fact_driver_shift`.
- Reconcile row counts, revenue, distance và shift measures với NDS.

## Phase 5 - Analytics

Status: `PLANNED`

Dashboard tối thiểu:

1. Operations overview.
2. Driver and shift performance.
3. Zone/time utilization.
4. Data quality and anomaly review.

Measures:

- Trip count.
- Occupied minutes.
- Idle minutes.
- Shift utilization.
- Revenue per hour.
- Revenue per mile.
- Average trip duration/distance.
- DQ/anomaly counts.

## Phase 6 - Delivery

- Báo cáo kiến trúc, source simulation, ETL, DQ, NDS/DDS và kết quả.
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
