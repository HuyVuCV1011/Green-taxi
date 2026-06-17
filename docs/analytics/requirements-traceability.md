# Analytics Requirements Traceability

Status: `CERTIFIED`

Nguồn quyết định: analytics requirements, full reconciliation, semantic
contract và metric catalog. Mọi dependency reconciliation trong draft đã được
đóng.

| ID | Requirement | Dataset/fact | Certified metrics | Default role | Support |
|---|---|---|---|---|---|
| `BQ01` | Khu vực/khung giờ cần ưu tiên năng lực | `analytics.trip_pickup` | `total_trips`, `total_revenue` | Pickup date/time/location | DDS supported |
| `BQ01` (zone concentration) | Phân tích tập trung nhu cầu khu vực đón | `analytics.pareto_pickup_zone` | `total_trips`, `cum_trips_pct`, `total_revenue`, `cum_revenue_pct` | Pickup location | Concentration view |
| `BQ02` | Ca sử dụng thời gian hiệu quả | `analytics.shift` | `utilization_rate`, `occupied_minutes`, `idle_minutes`, `avg_idle_minutes`, `shift_duration_minutes` | Shift start | DDS supported |
| `BQ03` | Driver revenue/hour thấp hoặc idle cao | `analytics.driver_performance_summary` | `revenue_per_hour`, `idle_minutes_per_shift`, `utilization_rate`, `completed_shifts`, `review_driver_count` | Driver summary | Peer-review view |
| `BQ04` | Vehicle hoạt động dưới mức thông thường | `analytics.shift` | `utilization_rate`, `trips_per_shift`, `revenue_per_shift` | Shift start | DDS supported |
| `BQ05A` | Trip bất thường cần kiểm tra | `analytics.trip_pickup` | `anomaly_trip_count`, `anomaly_rate` | Pickup | DDS supported |
| `BQ05B` | Shift bất thường cần kiểm tra | `analytics.shift` | `anomaly_shift_count` | Shift start | DDS supported |
| `DQ01` | Issue theo severity/rule/source/release | `analytics.dq_summary` | `dq_issue_count` | UTC event date | DQ dataset supported |
| `DQ02` | Invalid/rejected trip count | `analytics.dq_summary` | `quarantine_count` với trip ERROR filter | UTC event date | DQ dataset supported, không thuộc DDS fact |
| `KPI01` | Total và fare revenue | Trip hoặc shift theo ownership | `total_revenue`, `fare_revenue` | Dataset default | DDS supported |
| `KPI02` | Active driver count | `analytics.trip_pickup` | `active_driver_count` | Pickup | DDS fact activity |
| `KPI03` | Active vehicle count | `analytics.trip_pickup` | `active_vehicle_count` | Pickup | DDS fact activity |
| `OLAP01` | Slice/dice/drill-down/roll-up/pivot theo time, location, driver, vehicle | `analytics.olap_trip_cube`, `analytics.olap_shift_cube` | Existing certified measures where applicable | Dataset default | Implemented ROLAP |
| `DM01` | Phân nhóm driver theo hiệu suất vận hành | Planned `analytics.driver_segments` | Exploratory clustering metrics | Driver hoặc driver-month | Planned Data Mining |
| `DM02` | Khám phá luật kết hợp pickup/dropoff/time pattern | Planned `analytics.route_association_rules` | `support`, `confidence`, `lift` | Rule output | Planned Data Mining |

## Locked decisions

- Pickup là default cho trip demand; dropoff analysis dùng
  `analytics.trip_dropoff`.
- Shift start là default; shift end được chọn tường minh trong
  `analytics.shift`.
- `revenue_per_hour` dùng toàn bộ shift duration.
- `utilization_rate` dùng ratio-of-sums, không average row ratios.
- Active driver/vehicle dựa trên fact activity trong filter period.
- Unknown/inferred members được giữ mặc định để bảo toàn reconciliation.
- Trip và shift anomaly là hai metric khác grain, không cộng thành một count.
- Chi phí vận hành, payroll và net profit không được hỗ trợ vì không có dữ liệu.
- OLAP extension dùng PostgreSQL ROLAP + Superset, không dùng MDX/MOLAP
  trong scope hiện tại.
- Data Mining extension chỉ dùng output để hỗ trợ quyết định vận hành; không tự
  động điều phối hoặc đánh giá nhân sự.

## Fan-out prevention

Không join `fact_driver_trip` với `fact_driver_shift` ở row level. Khi cần đối
chiếu theo ca, aggregate trip trước bằng `analytics.shift_trip_aggregate`, sau
đó join 1:1 theo `shift_id`. Revenue chỉ lấy từ fact sở hữu của dataset, không
cộng trip revenue và shift revenue.

## Remaining business item

Khung peak-hour cụ thể chưa được business owner phê duyệt. `is_peak_hour` là
thuộc tính DDS hiện có nhưng chưa phải certified metric hoặc requirement.
