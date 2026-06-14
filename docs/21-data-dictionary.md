# DDS Data Dictionary

Status: `CERTIFIED`

Nguồn vật lý chuẩn: `sql/warehouse/04_dds_tables.sql`.

DDS hiện có **9 bảng, 107 cột**, gồm 7 dimensions và 2 facts. Con số 97 trong
draft trước reconciliation đã thiếu các cột lineage/effective metadata và không
còn đúng. Không có `dim_shift`; `shift_id` là degenerate dimension.

## Table summary

| Table | Type | Grain | Columns | Business key |
|---|---|---|---:|---|
| `dds.dim_date` | Type 0 dimension | Một ngày | 12 | `date` |
| `dds.dim_time` | Type 0 dimension | Một phút trong ngày | 6 | `time_of_day` |
| `dds.dim_driver` | SCD2 dimension | Một version tài xế | 15 | `driver_id`, `start_date` |
| `dds.dim_vehicle` | SCD2 dimension | Một version phương tiện | 13 | `vehicle_id`, `start_date` |
| `dds.dim_vendor` | Type 1 dimension | Một vendor | 4 | `vendor_id` |
| `dds.dim_location` | Type 0 dimension | Một taxi zone | 5 | `location_id` |
| `dds.dim_junk_trip` | Type 1 junk dimension | Một tổ hợp thuộc tính trip | 6 | Tổ hợp 5 thuộc tính |
| `dds.fact_driver_trip` | Transaction fact | Một trip | 27 | `trip_id` |
| `dds.fact_driver_shift` | Periodic summary fact | Một completed shift | 19 | `shift_id` |

## Column catalog

Ký hiệu: `PK` primary key, `FK` foreign key, `UK` unique business key,
`NN` not null. Business timestamps là giờ local `America/New_York`; `batch_id`
tham chiếu audit timestamp UTC.

### `dds.dim_date` (12)

| Column | Type | Constraint | Meaning |
|---|---|---|---|
| `date_key` | `INT` | PK | Khóa ngày `YYYYMMDD` |
| `date` | `DATE` | NN, UK | Ngày dương lịch |
| `day` | `INT` | NN, 1-31 | Ngày trong tháng |
| `month` | `INT` | NN, 1-12 | Tháng |
| `month_name` | `VARCHAR(20)` | NN | Tên tháng |
| `quarter` | `INT` | NN, 1-4 | Quý |
| `year` | `INT` | NN | Năm |
| `day_of_week` | `INT` | NN, 1-7 | ISO day of week |
| `day_name` | `VARCHAR(20)` | NN | Tên thứ |
| `is_weekend` | `BOOLEAN` | NN | Cờ cuối tuần |
| `is_holiday` | `BOOLEAN` | NN, default false | Cờ ngày lễ; chưa có holiday lookup phê duyệt |
| `week_of_year` | `INT` | NN, 1-53 | Tuần ISO |

### `dds.dim_time` (6)

| Column | Type | Constraint | Meaning |
|---|---|---|---|
| `time_key` | `INT` | PK | Khóa phút `HHMM` |
| `time_of_day` | `TIME` | NN, UK | Phút trong ngày |
| `hour` | `INT` | NN, 0-23 | Giờ |
| `minute` | `INT` | NN, 0-59 | Phút |
| `time_bucket` | `VARCHAR(20)` | NN | Morning/Afternoon/Evening/Night |
| `is_peak_hour` | `BOOLEAN` | NN, default false | Thuộc tính chưa có business window certified |

### `dds.dim_driver` (15)

| Column | Type | Constraint | Meaning |
|---|---|---|---|
| `driver_key` | `INT IDENTITY` | PK | DDS surrogate key |
| `driver_id` | `VARCHAR(50)` | NN | Natural key |
| `driver_code` | `VARCHAR(50)` | NN | Mã nhân sự, Type 1 |
| `display_name` | `VARCHAR(100)` | NN | Tên hiển thị, Type 1 |
| `home_borough` | `VARCHAR(100)` | NN | SCD2 attribute |
| `employment_status` | `VARCHAR(50)` | NN | `ACTIVE`, `LEAVE`, `INACTIVE`; SCD2 |
| `license_status` | `VARCHAR(50)` | NN | `ACTIVE`, `EXPIRED`, `SUSPENDED`; Type 1 |
| `license_expiry_date` | `DATE` | NN | Ngày hết hạn bằng lái |
| `experience_years` | `INT` | NN, >= 0 | Số năm kinh nghiệm |
| `start_date` | `TIMESTAMP` | NN | Bắt đầu hiệu lực, inclusive |
| `end_date` | `TIMESTAMP` | nullable | Kết thúc hiệu lực, exclusive |
| `is_current` | `BOOLEAN` | NN | Tối đa một current row/natural key |
| `source_event_id` | `VARCHAR(50)` | nullable | Change event lineage |
| `source_row_hash` | `CHAR(64)` | NN | Hash thuộc tính SCD để rerun no-op |
| `batch_id` | `UUID` | NN, FK audit | Batch lineage |

### `dds.dim_vehicle` (13)

| Column | Type | Constraint | Meaning |
|---|---|---|---|
| `vehicle_key` | `INT IDENTITY` | PK | DDS surrogate key |
| `vehicle_id` | `VARCHAR(50)` | NN | Natural key |
| `plate_token` | `VARCHAR(100)` | NN | Token biển số, Type 1 |
| `model_year` | `INT` | NN | Năm sản xuất |
| `vehicle_type` | `VARCHAR(50)` | NN | `SEDAN`, `HYBRID`, `WAV` |
| `vehicle_status` | `VARCHAR(50)` | NN | `ACTIVE`, `MAINTENANCE`, `RETIRED`; SCD2 |
| `last_inspection_date` | `DATE` | NN | Ngày kiểm định gần nhất |
| `start_date` | `TIMESTAMP` | NN | Bắt đầu hiệu lực, inclusive |
| `end_date` | `TIMESTAMP` | nullable | Kết thúc hiệu lực, exclusive |
| `is_current` | `BOOLEAN` | NN | Tối đa một current row/natural key |
| `source_event_id` | `VARCHAR(50)` | nullable | Effective-event lineage |
| `source_row_hash` | `CHAR(64)` | NN | Hash trạng thái SCD |
| `batch_id` | `UUID` | NN, FK audit | Batch lineage |

### `dds.dim_vendor` (4)

| Column | Type | Constraint | Meaning |
|---|---|---|---|
| `vendor_key` | `INT IDENTITY` | PK | DDS surrogate key |
| `vendor_id` | `INT` | NN, UK | Natural key; gồm vendor 0 Legacy Pool |
| `vendor_name` | `VARCHAR(100)` | NN | Tên vendor |
| `batch_id` | `UUID` | NN, FK audit | Batch lineage |

### `dds.dim_location` (5)

| Column | Type | Constraint | Meaning |
|---|---|---|---|
| `location_key` | `INT IDENTITY` | PK | DDS surrogate key |
| `location_id` | `INT` | NN, UK | TLC taxi zone ID |
| `borough` | `VARCHAR(100)` | NN | Borough |
| `zone` | `VARCHAR(100)` | NN | Zone |
| `service_zone` | `VARCHAR(50)` | nullable | Service zone |

### `dds.dim_junk_trip` (6)

| Column | Type | Constraint | Meaning |
|---|---|---|---|
| `junk_trip_key` | `INT IDENTITY` | PK | DDS surrogate key |
| `payment_type_desc` | `VARCHAR(50)` | NN | Payment label |
| `ratecode_desc` | `VARCHAR(100)` | NN | Rate-code label |
| `trip_type_desc` | `VARCHAR(50)` | NN | Street-Hail/Dispatch/Unknown |
| `assignment_method` | `VARCHAR(50)` | NN | Assignment method |
| `is_anomaly` | `BOOLEAN` | NN | Trip business anomaly propagated from DQ Gate 2 |

### `dds.fact_driver_trip` (27)

| Column | Type | Constraint | Meaning / aggregation |
|---|---|---|---|
| `fact_trip_id` | `BIGINT IDENTITY` | PK | Physical row ID |
| `trip_id` | `TEXT` | NN, UK | Trip business key; COUNT |
| `shift_id` | `VARCHAR(50)` | NN | Degenerate shift key |
| `pickup_date_key` | `INT` | NN, FK | Default trip date role |
| `pickup_time_key` | `INT` | NN, FK | Default trip time role |
| `dropoff_date_key` | `INT` | NN, FK | Explicit dropoff date role |
| `dropoff_time_key` | `INT` | NN, FK | Explicit dropoff time role |
| `driver_key` | `INT` | NN, FK | Driver version at pickup |
| `vehicle_key` | `INT` | NN, FK | Vehicle version at pickup |
| `vendor_key` | `INT` | NN, FK | Vendor |
| `pickup_location_key` | `INT` | NN, FK | Default location role |
| `dropoff_location_key` | `INT` | NN, FK | Explicit dropoff role |
| `junk_trip_key` | `INT` | NN, FK | Trip categories/anomaly |
| `passenger_count` | `INT` | nullable | Source passenger count; không mặc định SUM |
| `trip_distance` | `DECIMAL(12,4)` | nullable | Miles; SUM |
| `trip_duration_minutes` | `DECIMAL(10,2)` | nullable | Rounded per trip; SUM |
| `fare_amount` | `DECIMAL(10,2)` | NN | Fare revenue; SUM |
| `extra` | `DECIMAL(10,2)` | NN | Extra charge; SUM |
| `mta_tax` | `DECIMAL(10,2)` | NN | MTA tax; SUM |
| `tip_amount` | `DECIMAL(10,2)` | NN | Tips; SUM |
| `tolls_amount` | `DECIMAL(10,2)` | NN | Tolls; SUM |
| `improvement_surcharge` | `DECIMAL(10,2)` | NN | Surcharge; SUM |
| `total_amount` | `DECIMAL(10,2)` | NN | Certified total revenue source; SUM |
| `assignment_delay_minutes` | `DECIMAL(10,2)` | nullable | NULL khi delay âm/anomaly |
| `source_file` | `VARCHAR(255)` | NN | Source lineage |
| `source_row_number` | `INT` | NN, >= 2 | Source lineage |
| `batch_id` | `UUID` | NN, FK audit | Batch lineage |

### `dds.fact_driver_shift` (19)

| Column | Type | Constraint | Meaning / aggregation |
|---|---|---|---|
| `fact_shift_id` | `BIGINT IDENTITY` | PK | Physical row ID |
| `shift_id` | `VARCHAR(50)` | NN, UK | Completed-shift business key |
| `shift_start_date_key` | `INT` | NN, FK | Default shift date role |
| `shift_start_time_key` | `INT` | NN, FK | Default shift time role |
| `driver_key` | `INT` | NN, FK | Driver version at shift start |
| `vehicle_key` | `INT` | NN, FK | Vehicle version at shift start |
| `vendor_key` | `INT` | NN, FK | Vendor |
| `shift_status` | `VARCHAR(50)` | NN | `COMPLETED` in this fact |
| `shift_start` | `TIMESTAMP` | NN | New York local business time |
| `shift_end` | `TIMESTAMP` | NN | New York local business time |
| `is_anomaly` | `BOOLEAN` | NN | Overlap/out-of-shift business anomaly |
| `shift_duration_minutes` | `DECIMAL(12,2)` | NN | SUM |
| `trip_count` | `INT` | NN, >= 0 | Recomputed assigned trips; SUM |
| `occupied_minutes` | `DECIMAL(12,2)` | NN, >= 0 | Trip duration in shift; SUM |
| `idle_minutes` | `DECIMAL(12,2)` | NN, >= 0 | Duration minus occupied; SUM |
| `utilization_rate` | `DECIMAL(5,4)` | NN | Row diagnostic only; certified aggregate uses ratio-of-sums |
| `total_revenue` | `DECIMAL(12,2)` | NN | Shift aggregate of trip `total_amount`; SUM |
| `total_tips` | `DECIMAL(12,2)` | NN | Shift aggregate of trip tips; SUM |
| `batch_id` | `UUID` | NN, FK audit | Batch lineage |

## Analytics use

Dashboard datasets and certified aggregations are defined by
[22-analytics-semantic-contract.md](22-analytics-semantic-contract.md) and
[23-metric-catalog.md](23-metric-catalog.md). Do not infer aggregation from a
numeric datatype, join facts row-level, or join SCD2 facts to current rows by
natural key.
