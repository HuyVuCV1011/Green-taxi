# Analytics Semantic Contract

Status: `CERTIFIED`

Base commit: `720a60beeddddece58d3efde7d3810942f958140`

## 1. Analytics boundary

- Dashboard nghiệp vụ chỉ đọc các bảng `dds` hoặc view được phê duyệt trong
  schema `analytics`.
- Dashboard nghiệp vụ không query trực tiếp `staging`, `nds`, `audit` hoặc `dq`.
  View `analytics.shift` được phép dùng NDS chỉ để đưa two location roles còn
  thiếu trong DDS ra một dataset có protected grain. View
  `analytics.dq_summary` là ranh giới DQ riêng, không phải business fact.
- Không tạo hoặc truy vấn `dds.dim_shift`. `shift_id` là degenerate dimension
  trong cả hai fact.
- Không join trực tiếp hai fact ở row level. Khi cần phối hợp, dùng
  `analytics.shift_trip_aggregate` (một dòng mỗi `shift_id`) rồi join 1:1 với
  `analytics.shift`, hoặc lấy metric từ đúng fact sở hữu.
- Các summary views như `analytics.pareto_pickup_zone` và
  `analytics.driver_performance_summary` đã aggregate trước theo grain bảo vệ;
  dashboard không dùng chúng để thay thế fact grain chi tiết.
- Business timestamps là local wall-clock time `America/New_York` và dùng
  `TIMESTAMP WITHOUT TIME ZONE`. Audit timestamps là UTC và dùng `TIMESTAMPTZ`.
  Đây là contract đã triển khai trong DDL/loader, không phải assumption.
- ROLAP views và Data Mining outputs phải nằm trong schema `analytics`
  hoặc một schema kết quả được phê duyệt, chỉ đọc từ DDS/approved views và giữ
  đúng grain. Chúng không được query trực tiếp `staging`/`nds` để phục vụ
  dashboard.

## 2. Fact grain và metric ownership

| Fact | Grain | Unique business key | Metric ownership |
|---|---|---|---|
| `dds.fact_driver_trip` | Một dòng cho một trip được gán | `trip_id` | Trip count, fare, revenue, tip, distance, trip duration, trip anomaly, active driver/vehicle theo trip |
| `dds.fact_driver_shift` | Một dòng cho một completed shift | `shift_id` | Shift count, shift duration, occupied/idle minutes, utilization, shift anomaly, revenue/hour, trips/revenue per shift |

`fact_driver_shift.total_revenue` là shift-level aggregate của
`fact_driver_trip.total_amount`. Không cộng doanh thu từ hai fact trong cùng KPI.

## 3. Relationships

Mọi relationship là many-to-one, filter một chiều từ dimension sang fact.
Không dùng many-to-many hoặc bidirectional semantics.

| Fact | Dimension/role | Fact FK | Dimension PK | Required | Default role | Null/Unknown | SCD behavior |
|---|---|---|---|---|---|---|---|
| trip | `dim_date` pickup | `pickup_date_key` | `date_key` | Yes | Default | Không null | Type 0 |
| trip | `dim_time` pickup | `pickup_time_key` | `time_key` | Yes | Default | Không null | Type 0 |
| trip | `dim_date` dropoff | `dropoff_date_key` | `date_key` | Yes | Explicit dropoff dataset | Không null | Type 0 |
| trip | `dim_time` dropoff | `dropoff_time_key` | `time_key` | Yes | Explicit dropoff dataset | Không null | Type 0 |
| trip | `dim_driver` | `driver_key` | `driver_key` | Yes | Fact-time version | Inferred được giữ và tính mặc định | SCD2 lookup tại pickup |
| trip | `dim_vehicle` | `vehicle_key` | `vehicle_key` | Yes | Fact-time version | Inferred được giữ và tính mặc định | SCD2 lookup tại pickup |
| trip | `dim_vendor` | `vendor_key` | `vendor_key` | Yes | Default | Vendor 0 hợp lệ | Type 1 |
| trip | `dim_location` pickup | `pickup_location_key` | `location_key` | Yes | Default | Không null | Type 0 |
| trip | `dim_location` dropoff | `dropoff_location_key` | `location_key` | Yes | Explicit dropoff dataset | Không null | Type 0 |
| trip | `dim_junk_trip` | `junk_trip_key` | `junk_trip_key` | Yes | Default | Nhãn `Unknown` được giữ | Type 1 combination |
| shift | `dim_date` start | `shift_start_date_key` | `date_key` | Yes | Default | Không null | Type 0 |
| shift | `dim_time` start | `shift_start_time_key` | `time_key` | Yes | Default | Không null | Type 0 |
| shift | `dim_driver` | `driver_key` | `driver_key` | Yes | Fact-time version | Inferred được giữ và tính mặc định | SCD2 lookup tại shift start |
| shift | `dim_vehicle` | `vehicle_key` | `vehicle_key` | Yes | Fact-time version | Inferred được giữ và tính mặc định | SCD2 lookup tại shift start |
| shift | `dim_vendor` | `vendor_key` | `vendor_key` | Yes | Default | Vendor 0 hợp lệ | Type 1 |

`shift start zone` và `shift end zone` không có FK trong DDS fact. Dataset
`analytics.shift` resolve chúng bằng `shift_id` sang `nds.nds_shift`, sau đó
alias rõ `shift_start_*` và `shift_end_*`; join vẫn 1:1 và không nhân fact.

## 4. Date và location roles

| Dataset | Default temporal column | Default location | Vai trò phụ |
|---|---|---|---|
| `analytics.trip_pickup` | `pickup_datetime` | `pickup_*` | Có cột `dropoff_*` để tham chiếu, không dùng làm default |
| `analytics.trip_dropoff` | `dropoff_datetime` | `dropoff_*` | Có cột `pickup_*` để tham chiếu |
| `analytics.shift` | `shift_start` | `shift_start_*` | Chọn `shift_end` và `shift_end_*` tường minh khi phân tích kết thúc ca |
| `analytics.shift_trip_aggregate` | Không áp đặt; join theo `shift_id` | Không có | Aggregate kỹ thuật chống fan-out |
| `analytics.dq_summary` | `event_date_utc` | Không có | Audit/DQ UTC |
| `analytics.pareto_pickup_zone` | Không áp đặt | `pickup_*` | Một dòng mỗi pickup zone, phục vụ concentration/ranking |
| `analytics.driver_performance_summary` | Không áp đặt | Driver | Một dòng mỗi driver, phục vụ peer benchmark và review queue |

Pickup là default role vì nhu cầu vận hành phát sinh tại nơi/thời điểm đón.
Dropoff analysis phải dùng dataset dropoff. Semantic model chỉ dùng default role
và dataset alias độc lập công cụ.

## 5. SCD2 và inferred members

- Driver natural key: `driver_id`; surrogate key: `driver_key`.
- Vehicle natural key: `vehicle_id`; surrogate key: `vehicle_key`.
- Validity interval là `[start_date, end_date)`. Dòng hiện hành (current row) có
  `is_current = true` và `end_date IS NULL`.
- Trip giữ version driver/vehicle tại `pickup_datetime`; shift giữ version tại
  `shift_start`. Dashboard không join fact với current dimension bằng natural
  key.
- Inferred member có natural key hợp lệ và thuộc tính skeleton `Unknown`; fact
  vẫn được giữ trong KPI mặc định để bảo toàn reconciliation. Khi cần xem master data quality, dùng DQ rule `DQ_MISSING_MASTER`.
- DDS dimension chưa lưu cờ `is_inferred`, vì vậy không được suy diễn lịch sử
  inferred chỉ từ nhãn `Unknown`, và không được tự loại chúng khỏi KPI.

## 6. Metric decisions

Catalog chuẩn nằm tại [metric-catalog.md](metric-catalog.md).

- `total_revenue = SUM(total_amount)`. `total_amount` là total payment được TLC cung cấp, gồm fare và các thành phần charge/tax/tip/toll/surcharge
  được phản ánh trong total; không tự cộng lại các cột thành phần.
- `fare_revenue = SUM(fare_amount)` và khác `total_revenue`.
- `average_fare = SUM(fare_amount) / COUNT(trip_id)`.
- `utilization_rate` là ratio-of-sums:
  `SUM(occupied_minutes) / NULLIF(SUM(shift_duration_minutes), 0)`.
- `revenue_per_hour` dùng toàn bộ `shift_duration_minutes`, vì KPI đo năng suất
  thời gian tài xế/xe được bố trí, bao gồm cả idle time. Revenue per occupied
  hour là metric khác và chưa certified.
- Active driver/vehicle là số khóa surrogate distinct có fact activity trong
  filter period, không phải số master có trạng thái `ACTIVE`.
- `anomaly_rate` certified ở trip grain. Shift anomaly rate phải dùng metric ID
  riêng nếu được bổ sung; không cộng anomaly trip và anomaly shift.
- Driver review queue dùng `needs_review` trong
  `analytics.driver_performance_summary`: revenue/hour thuộc nhóm thấp theo peer
  percentile và idle minutes/shift thuộc nhóm cao. Không dùng tổng idle minutes
  để so sánh driver có số ca khác nhau.
- Unknown/inferred được tính mặc định (calculated by default). Bộ lọc loại trừ chỉ là phân tích DQ có
  chủ đích và phải ghi rõ.

## 7. DQ analytics boundary

`analytics.dq_summary` có grain một dòng cho tổ hợp ngày UTC, batch, release,
source system/entity, rule code, severity và event type. Dataset cung cấp
`issue_count` và `quarantine_count`.

- `ERROR` tạo issue và có thể có quarantine; không cộng hai count như cùng một
  khái niệm.
- `WARN` vẫn có thể đi vào NDS/DDS và không được coi là rejected row.
- `invalid_trip_count` không thuộc DDS business fact. Nó được hỗ trợ ở ranh giới
  DQ bằng `quarantine_count` lọc `source_entity` trip và rule ERROR phù hợp.
- Không join issue/quarantine trực tiếp vào fact. Điều tra chi tiết dùng
  `source_record_id` trong công cụ DQ riêng, không mở rộng grain business fact.

## 8. Reconciliation và certification

Reconciliation tại commit base xác nhận 2,304,276 trips, 157,379 completed
shifts, unique fact keys, SCD2 rerun không sinh version mới, và NDS/DDS khớp
revenue, fare, tip, distance, duration. Superset phải tạo metric theo đúng SQL
trong catalog, đánh dấu certified, khóa owner là Analytics Semantic Contract
Owner và không tạo implicit metric trùng tên.

## 9. Closed questions và remaining limits

Đã đóng: revenue components, fare/total distinction, average fare, utilization
aggregation, revenue/hour denominator, active entity semantics, anomaly grain,
date/location defaults, inferred handling, DQ access và fan-out prevention.

Giới hạn còn lại: peak-hour business window chưa được business owner phê duyệt,
do đó `is_peak_hour` chỉ là thuộc tính DDS hiện có và không phải certified
metric. Exact historical inferred flag không tồn tại trong DDS dimension; dùng
DQ dataset để giám sát thay vì suy diễn.

## 10. Analytical extensions

Các extension OLAP và Data Mining đã được triển khai trong schema `analytics`:

- `analytics.olap_trip_cube`: ROLAP dataset cho trip analysis với time,
  pickup/dropoff location, driver, vehicle và vendor dimensions.
- `analytics.olap_shift_cube`: ROLAP dataset cho shift analysis với time,
  driver, vehicle, vendor, utilization và idle/revenue measures.
- `analytics.driver_segments`: kết quả K-Means driver segmentation, grain là
  một dòng mỗi driver hoặc driver-month theo feature set được xuất.
- `analytics.route_association_rules`: kết quả association rules cho
  pickup/dropoff/time patterns, gồm `support`, `confidence` và `lift`.

Các extension này phải reconcile với metric catalog khi dùng measure hiện có và
phải ghi rõ khi metric là exploratory thay vì certified.
