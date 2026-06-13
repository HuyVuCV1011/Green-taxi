# Synthetic Source Data Contracts

## Driver HR - `drivers.csv`

| Column | Type | Description |
|---|---|---|
| driver_id | string | Synthetic natural key `DRV######` |
| vendor_id | integer | 0=Legacy/Unknown, 1=CMT, 2=VeriFone |
| driver_code | string | Mã nhân sự nội bộ |
| display_name | string | Tên synthetic, không phải người thật |
| hire_date | date | Ngày bắt đầu |
| employment_status | string | ACTIVE/LEAVE/INACTIVE |
| license_status | string | ACTIVE/EXPIRED/SUSPENDED |
| license_expiry_date | date | Ngày hết hạn synthetic |
| experience_years | integer | Thâm niên tại đầu kỳ |
| home_borough | string | Borough synthetic |
| source_updated_at | timestamp | Thời điểm nguồn cập nhật |

## Fleet - `vehicles.jsonl`

| Field | Type | Description |
|---|---|---|
| vehicle_id | string | Synthetic natural key `VEH######` |
| vendor_id | integer | Vendor quản lý |
| plate_token | string | Token synthetic, không phải biển số thật |
| model_year | integer | Năm sản xuất |
| vehicle_type | string | SEDAN/HYBRID/WAV |
| service_start_date | date | Bắt đầu khai thác |
| vehicle_status | string | ACTIVE/MAINTENANCE/RETIRED |
| last_inspection_date | date | Ngày kiểm định synthetic |
| source_updated_at | timestamp | Thời điểm nguồn cập nhật |

## Dispatch - `shifts.tsv`

| Column | Type | Description |
|---|---|---|
| shift_id | string | Synthetic key `SHF##########` |
| driver_id | string | Driver assigned |
| vehicle_id | string | Vehicle assigned |
| vendor_id | integer | Vendor |
| shift_start | timestamp | 30 phút trước pickup đầu |
| shift_end | timestamp | 30 phút sau dropoff cuối |
| assigned_start_zone | integer | Zone đầu ca |
| actual_end_zone | integer | Zone cuối ca |
| trip_count | integer | Số trip trong ca |
| occupied_minutes | decimal | Tổng duration trip |
| idle_minutes | decimal | Khoảng trống giữa trip |
| shift_status | string | COMPLETED |

## Trip Assignment - monthly CSV

| Column | Type | Description |
|---|---|---|
| trip_key | string | SHA-256 truncated business key |
| source_file | string | TLC source filename |
| source_row_number | integer | Row number in source |
| driver_id | string | Assigned driver |
| vehicle_id | string | Assigned vehicle |
| shift_id | string | Dispatch shift |
| assignment_timestamp | timestamp | Synthetic dispatch time |
| assignment_method | string | CONTINUITY/AVAILABLE_POOL |

## HR Change Feed - `driver_changes.jsonl`

Mỗi record gồm `event_id`, `driver_id`, `event_type`, `effective_at`,
`delivered_at`, `changes` và `is_late_arriving`. Feed dùng để minh họa upsert,
SCD Type 2 và sự kiện đến trễ.

## Temporal rules

1. Driver và vehicle không có trip chồng thời gian.
2. Trip phải nằm trong shift.
3. Một shift dùng một driver và một vehicle.
4. Shift mới được mở nếu gap lớn hơn cấu hình hoặc vượt max shift duration.
5. Driver/vehicle/trip phải cùng vendor, trừ vendor 0 được mô tả là legacy pool.
6. Assignment timestamp không sau pickup timestamp.

