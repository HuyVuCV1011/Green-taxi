# Synthetic Source Data Contracts

## Contract layers

Mỗi nguồn synthetic có hai biểu diễn:

1. **Release contract**: file trong Google Drive package dùng để checksum, seed
   và phục hồi source systems.
2. **Operational source contract**: table/collection mà ingestion adapter đọc.

Seed process phải bảo toàn natural key, business values và temporal semantics.
Định dạng lưu trữ có thể khác nhưng không được làm thay đổi nội dung nghiệp vụ.

## Quy ước chung

- `Required = Yes` nghĩa là `NOT NULL` trong relational source/staging và field
  bắt buộc trong MongoDB document validation.
- Chuỗi ID phải được trim, không rỗng và giữ nguyên chữ hoa như release.
- Các giá trị enum không hợp lệ bị reject/quarantine, không tự đổi sang default.
- Default chỉ áp dụng khi tạo record nghiệp vụ mới; seed release không được tự
  điền giá trị thiếu để che giấu lỗi dữ liệu.
- Release `green-taxi-full-v1` không chứa null trong các synthetic contracts
  dưới đây. Nullable fields chỉ được chấp nhận khi được ghi rõ.

## Quy ước thời gian

Timestamps nghiệp vụ trong TLC và synthetic release không chứa offset. Chúng
được hiểu là giờ địa phương New York theo timezone IANA
`America/New_York`, bao gồm quy tắc EST/EDT.

- MySQL lưu timestamp nghiệp vụ bằng `DATETIME`, không phụ thuộc timezone session.
- PostgreSQL nguồn/staging lưu timestamp nghiệp vụ bằng
  `TIMESTAMP WITHOUT TIME ZONE`.
- MongoDB BSON Date lưu instant UTC; seed adapter phải gắn
  `America/New_York` vào release value trước khi chuyển sang UTC. Extract adapter
  phải phục hồi đúng business-time semantics.
- Timestamp kỹ thuật như `seeded_at`, `source_extract_at`, `load_timestamp`,
  `batch_started_at` và `batch_completed_at` dùng UTC, lưu bằng
  `TIMESTAMP WITH TIME ZONE`/`TIMESTAMPTZ` ở PostgreSQL.
- Không được parse timestamp nghiệp vụ không offset như UTC.
- DQ và tính duration/overlap sử dụng cùng một temporal representation. Các
  thời điểm DST mơ hồ hoặc không tồn tại phải được flag thay vì tự điều chỉnh.

## Driver HR - `drivers.csv`

Operational source: MySQL table `drivers`.

| Column | Logical type | Required | Key/default | Description |
|---|---|---|---|---|
| driver_id | string | Yes | PK; `DRV######` | Synthetic natural key |
| vendor_id | integer | Yes | FK vendor; no default | 0=Legacy/Unknown, 1=CMT, 2=VeriFone |
| driver_code | string | Yes | UNIQUE; no default | Mã nhân sự nội bộ |
| display_name | string | Yes | No default | Tên synthetic, không phải người thật |
| hire_date | date | Yes | No default | Ngày bắt đầu, không sau kỳ dữ liệu |
| employment_status | string | Yes | Default `ACTIVE` | ACTIVE/LEAVE/INACTIVE |
| license_status | string | Yes | Default `ACTIVE` | ACTIVE/EXPIRED/SUSPENDED |
| license_expiry_date | date | Yes | No default | Ngày hết hạn synthetic; release v1 luôn có |
| experience_years | integer | Yes | Default `0`; check `>= 0` | Thâm niên tại đầu kỳ |
| home_borough | string | Yes | No default | Borough synthetic |
| source_updated_at | local timestamp | Yes | No default | Thời điểm nguồn cập nhật, `America/New_York` |

## Fleet - `vehicles.jsonl`

Operational source: MongoDB collection `vehicles`. `vehicle_id` là unique key.

| Field | Logical type | Required | Key/default | Description |
|---|---|---|---|---|
| vehicle_id | string | Yes | UNIQUE; `VEH######` | Synthetic natural key |
| vendor_id | integer | Yes | FK-like vendor reference; no default | Vendor quản lý |
| plate_token | string | Yes | UNIQUE; no default | Token synthetic, không phải biển số thật |
| model_year | integer | Yes | No default | Năm sản xuất |
| vehicle_type | string | Yes | No default | SEDAN/HYBRID/WAV |
| service_start_date | date | Yes | No default | Bắt đầu khai thác |
| vehicle_status | string | Yes | Default `ACTIVE` | ACTIVE/MAINTENANCE/RETIRED |
| last_inspection_date | date | Yes | No default | Không trước `service_start_date` |
| source_updated_at | local timestamp | Yes | No default | Snapshot time, `America/New_York` |

## Dispatch - `shifts.tsv`

Operational source: PostgreSQL source table `shifts`.

| Column | Logical type | Required | Key/default | Description |
|---|---|---|---|---|
| shift_id | string | Yes | PK; `SHF##########` | Synthetic shift key |
| driver_id | string | Yes | FK Driver; no default | Driver assigned |
| vehicle_id | string | Yes | FK Vehicle; no default | Vehicle assigned |
| vendor_id | integer | Yes | FK Vendor; no default | Vendor |
| shift_start | local timestamp | Yes | No default | Tối đa 30 phút trước pickup đầu |
| shift_end | local timestamp | Yes | No default; check `>= shift_start` | Buffer động sau dropoff cuối |
| assigned_start_zone | integer | Yes | FK-like zone; no default | Zone đầu ca |
| actual_end_zone | integer | Yes | FK-like zone; no default | Zone cuối ca |
| trip_count | integer | Yes | Default `0`; check `>= 0` | Số trip trong ca |
| occupied_minutes | decimal(12,2) | Yes | Default `0`; check `>= 0` | Tổng duration trip |
| idle_minutes | decimal(12,2) | Yes | Default `0`; check `>= 0` | Buffer đầu/cuối và gap giữa trip |
| shift_status | string | Yes | Default `COMPLETED` | COMPLETED |

## Trip Assignment - monthly CSV

Operational source: PostgreSQL source table `trip_assignments`.

| Column | Logical type | Required | Key/default | Description |
|---|---|---|---|---|
| trip_key | string(24) | Yes | PK; lowercase hex | SHA-256 truncated business key |
| source_file | string | Yes | Part of source UNIQUE key | TLC source filename |
| source_row_number | integer | Yes | Part of source UNIQUE key; `>= 2` | CSV physical row number |
| driver_id | string | Yes | FK Driver; no default | Assigned driver |
| vehicle_id | string | Yes | FK Vehicle; no default | Assigned vehicle |
| shift_id | string | Yes | FK Shift; no default | Dispatch shift |
| assignment_timestamp | local timestamp | Yes | No default | Synthetic dispatch time |
| assignment_method | string | Yes | No default | CONTINUITY/AVAILABLE_POOL |

`assignment_exceptions.csv` là release validation/audit artifact cho các trip
không được assignment; nó không phải transaction table nghiệp vụ của Dispatch.
Trong local source simulation, artifact này được seed vào
`public.assignment_exceptions` như một bảng reconciliation/audit để kiểm chứng
release completeness. Adapter không được xử lý bảng này như một nguồn fact
nghiệp vụ của DDS.

## HR Change Feed - `driver_changes.jsonl`

Mỗi record gồm `event_id`, `driver_id`, `event_type`, `effective_at`,
`delivered_at`, `changes` và `is_late_arriving`. Feed dùng để minh họa upsert,
SCD Type 2 và sự kiện đến trễ.

Operational source: MySQL table `driver_changes`. `changes` được lưu dưới dạng
JSON để giữ payload thay đổi; `event_id` là unique key và processing order dùng
`delivered_at`, không dùng thứ tự dòng file.

| Field | Logical type | Required | Key/default | Description |
|---|---|---|---|---|
| event_id | string | Yes | PK; `DRVCHG######` | Change event key |
| driver_id | string | Yes | FK Driver; no default | Driver bị thay đổi |
| event_type | string | Yes | No default | Release v1: `HOME_BOROUGH_CHANGED` |
| effective_at | local timestamp | Yes | No default | Thời điểm nghiệp vụ có hiệu lực |
| delivered_at | local timestamp | Yes | No default; check `>= effective_at` | Thời điểm source gửi event |
| changes | JSON object | Yes | No default; non-empty | Field/value mới; release v1 chỉ có `home_borough` |
| is_late_arriving | boolean | Yes | Default `false` | Có độ trễ nghiệp vụ hay không |

`changes` không chứa full driver snapshot. Với
`HOME_BOROUGH_CHANGED`, payload hợp lệ có đúng key `home_borough` và giá trị
thuộc danh sách borough được công bố. Thứ tự ingestion dùng
`(delivered_at, event_id)`; effective-dated merge dùng
`(effective_at, event_id)` để có tie-break deterministic.

## Seed invariants

- Vendor lookup chứa các business members 0, 1 và 2.
- MySQL driver/change counts khớp release artifacts.
- MongoDB có một document cho mỗi `vehicle_id`.
- PostgreSQL nguồn có một row cho mỗi `shift_id` và `trip_key`.
- Chạy seed lại cùng release không tạo duplicate.
- Seed không tự sinh timestamp mới làm thay đổi row/document hash nghiệp vụ.
- Release ID và seed timestamp được lưu ở bảng/collection audit riêng.

## Staging lineage contract

- File source dùng `source_file` và `source_row_number`.
- MySQL dùng source table và primary/natural key.
- MongoDB dùng collection, `vehicle_id` và có thể lưu `_id` kỹ thuật.
- PostgreSQL nguồn dùng source table và primary/business key.
- Tất cả records có `release_id`, `batch_id`, `source_system`,
  `source_entity`, `source_locator`, `source_record_id`,
  `source_extract_at`, `load_timestamp`, `row_hash` và checksum/watermark phù
  hợp với loại nguồn.

| Metadata field | Required | Semantics |
|---|---|---|
| release_id | Yes | Canonical package, ví dụ `green-taxi-full-v1` |
| batch_id | Yes | Warehouse ETL batch identity; immutable |
| source_system | Yes | TLC_FILE/LOOKUP_FILE/HR_MYSQL/FLEET_MONGODB/DISPATCH_POSTGRES |
| source_entity | Yes | File/table/collection business entity |
| source_locator | Yes | File path hoặc database/schema/table/collection |
| source_record_id | Yes | File-row identity hoặc primary/natural/document key |
| source_extract_at | Yes | UTC technical timestamp |
| load_timestamp | Yes | UTC technical timestamp |
| row_hash | Yes | Deterministic hash của normalized source payload |
| source_checksum | Conditional | Required cho file; nullable cho DB/document extract |
| extraction_watermark | Conditional | Required khi adapter dùng watermark; nullable cho full snapshot |

## Temporal rules

1. Driver và vehicle không có trip chồng thời gian.
2. Driver và vehicle không có shift chồng thời gian.
3. Trip phải nằm trong shift.
4. `occupied_minutes + idle_minutes = shift_end - shift_start`, trong sai số làm tròn.
5. Một shift dùng một driver và một vehicle.
6. Shift mới được mở nếu gap lớn hơn cấu hình hoặc vượt max shift duration.
7. Driver/vehicle/trip phải cùng vendor, trừ vendor 0 được mô tả là legacy pool.
8. Assignment timestamp không sau pickup timestamp.
