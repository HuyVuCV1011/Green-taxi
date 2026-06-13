# Implementation Plan

## Phase 0 - Baseline

- Đóng băng tài liệu trước feedback trong `archive/`.
- Ghi rõ phạm vi trip hiện có: 01/2020-07/2021.
- Tạo manifest và checksum cho nguồn.

## Phase 1 - Synthetic source generation

- Sinh Driver HR master.
- Sinh Vehicle/Fleet master.
- Gán trip vào driver/vehicle khả dụng.
- Sinh shift từ chuỗi trip liên tục.
- Sinh HR change feed cho SCD/upsert.
- Xuất summary, manifest và validation report.

Exit criteria:

- Không có overlap driver/vehicle trong baseline clean data.
- Mọi assignment liên kết được trip, driver, vehicle và shift.
- Mọi trip hợp lệ được assignment hoặc ghi rõ lý do không assignment.
- Cùng seed và input tạo cùng output.

## Phase 2 - Staging

- Tạo schema/table riêng cho từng source.
- Load raw data gần nguyên bản.
- Gắn batch metadata, checksum và row hash.
- Lưu source row number để truy vết.

## Phase 3 - DQ and NDS

- Chuẩn hóa type và timestamp.
- Upsert driver, vehicle, vendor và location.
- Xử lý inferred/late-arriving master.
- Validate assignment/shift temporal constraints.
- Tích hợp trip và assignment.

## Phase 4 - DDS

- Sinh `dim_date` và `dim_time`.
- Load SCD2 `dim_driver`, `dim_vehicle`.
- Load `fact_driver_trip`.
- Tổng hợp `fact_driver_shift`.
- Reconcile row counts, revenue và distance với NDS.

## Phase 5 - Analytics

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

- Báo cáo kiến trúc, ETL, DQ, NDS/DDS và kết quả.
- Slide trình bày.
- Demo script chạy pipeline.
- Data dictionary và source-to-target mapping.
- Release tag phục vụ nộp bài.

## Definition of done

- Một lệnh có thể sinh lại synthetic sources.
- Một lệnh có thể chạy pipeline với sample.
- Full pipeline chạy thành công trên toàn bộ dữ liệu local.
- Tests và reconciliation pass.
- Dashboard trả lời đúng năm quyết định trong scope.

