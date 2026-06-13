# System Architecture

Status: `APPROVED FOR IMPLEMENTATION`

## Logical architecture

```text
TLC Trip CSV -------------------+
Driver HR CSV ------------------+
Fleet JSONL --------------------+--> Staging --> DQ/Audit --> NDS --> Driver Operations DDS
Dispatch Shift TSV -------------+                       |                 |
Trip Assignment CSV ------------+                       |                 +--> Dashboard
Driver Change Feed JSONL -------+                       +--> Quarantine    +--> Anomaly analysis
Taxi Zone / Vendor CSV ---------+
```

## Tại sao không dùng ODS

Dự án xử lý dữ liệu lịch sử theo batch và không có quyết định ngắn hạn cần một
operational view gần thời gian thực. Vì vậy ODS không tạo thêm giá trị đủ lớn.

Kiến trúc sử dụng hai tầng kho trung gian/phân tích:

1. **NDS**: tích hợp và chuẩn hóa master/transaction theo quan hệ.
2. **DDS**: star schema tối ưu cho Driver Operations analytics.

Staging và DQ/Audit là vùng tiếp nhận/kiểm soát, không được mô tả như data mart.

## Staging

Mỗi nguồn được mirror gần nguyên bản và bổ sung:

- `source_system`
- `source_file`
- `source_row_number`
- `batch_id`
- `file_checksum`
- `load_timestamp`
- `row_hash`

## DQ/Audit

- Schema/type validation.
- Duplicate detection.
- Temporal and referential validation.
- Quarantine cho record không thể tích hợp.
- Audit row counts và reconciliation totals.

## NDS

Các bảng dự kiến:

- `nds_driver`
- `nds_driver_history`
- `nds_vehicle`
- `nds_vendor`
- `nds_location`
- `nds_shift`
- `nds_trip`
- `nds_trip_assignment`
- `metadata_etl_batch`
- `dq_issue`
- `dq_missing_master`

NDS giữ natural key, surrogate key, source system và lịch sử cần thiết.

## DDS

Dimensions:

- `dim_date`
- `dim_time`
- `dim_driver` - SCD Type 2
- `dim_vehicle` - SCD Type 2
- `dim_vendor` - SCD Type 1
- `dim_location` - Type 0 cho phạm vi case study
- `dim_shift`

Facts:

- `fact_driver_trip`
- `fact_driver_shift`

## Processing cadence

Batch theo tháng cho dữ liệu lịch sử. Thiết kế cho phép chuyển sang batch hằng
ngày nhưng đó không phải yêu cầu của case study hiện tại.

