# OLAP Plan

Status: `IMPLEMENTED`

## Business purpose

OLAP extension phải giúp quản lý vận hành trả lời nhanh các câu hỏi đa chiều:

- Khu vực và khung giờ nào cần ưu tiên tài xế hoặc xe?
- Driver/vendor/vehicle type nào tạo doanh thu tốt hoặc có idle time cao?
- Hiệu suất thay đổi thế nào khi roll-up từ zone lên borough, hoặc từ ngày lên tháng?
- Khi thấy KPI xấu, người dùng drill-down được tới driver, vehicle, zone hoặc ca liên quan.

Mục tiêu không phải xây cube vật lý riêng để trình diễn kỹ thuật. Với stack hiện
tại, hướng phù hợp là **ROLAP trên PostgreSQL + Superset**.

## Scope

Tạo lớp OLAP bằng SQL views trong schema `analytics`, đọc từ DDS star schema và
không phá vỡ semantic contract hiện có.

Implemented views:

| View | Grain | Business use |
|---|---|---|
| `analytics.olap_trip_cube` | Một dòng cho tổ hợp dimension ở trip grain hoặc view detail có đủ dimension role | Slice/dice doanh thu, trip, distance, tip theo thời gian, location, driver, vehicle |
| `analytics.olap_shift_cube` | Một dòng cho tổ hợp dimension ở shift grain hoặc view detail có đủ dimension role | Phân tích utilization, idle time, revenue/hour và shift performance |

Các view này là ROLAP datasets cho Superset. Chúng không thay thế các certified
datasets hiện tại, mà bổ sung một lớp demo OLAP rõ ràng hơn.

## Dimensions and hierarchies

| Dimension | Hierarchy | Source |
|---|---|---|
| Time | `year -> quarter -> month -> day -> hour` | `dim_date`, `dim_time` |
| Location | `borough -> zone` | `dim_location` pickup/dropoff |
| Driver | `vendor -> driver` | `dim_vendor`, `dim_driver` |
| Vehicle | `vehicle_type -> vehicle` | `dim_vehicle` |

Pickup là default role cho trip demand. Dropoff analysis phải dùng cột hoặc
dataset dropoff tường minh để tránh ambiguity.

## Measures

Core OLAP measures:

- `total_trips`
- `total_revenue`
- `fare_revenue`
- `total_tips`
- `total_distance`
- `average_fare`
- `average_trip_distance`
- `completed_shifts`
- `shift_duration_minutes`
- `occupied_minutes`
- `idle_minutes`
- `utilization_rate`
- `revenue_per_hour`
- `active_driver_count`
- `active_vehicle_count`
- `anomaly_trip_count`
- `anomaly_shift_count`

Ratio measures phải dùng ratio-of-sums, không average các ratio cấp dòng.

## Superset demo operations

| OLAP operation | Superset demonstration |
|---|---|
| Slice | Lọc một tháng, vendor hoặc borough |
| Dice | Lọc đồng thời tháng + borough + vehicle type |
| Drill-down | `year -> month -> day -> hour` hoặc `borough -> zone` |
| Roll-up | `zone -> borough`, `day -> month` |
| Pivot | Pivot table: revenue/trips theo `borough x hour_bucket` hoặc `vehicle_type x month` |

## Implementation notes

- Chỉ đọc từ DDS và approved `analytics` views.
- Không join trực tiếp `fact_driver_trip` và `fact_driver_shift` ở row level.
- Nếu cần so sánh trip với shift theo ca, dùng aggregate một dòng mỗi `shift_id`.
- Superset chỉ dùng warehouse role read-only.
- Không dùng Power BI, MDX, DAX, DirectLake hoặc Fabric cho scope hiện tại.

## Acceptance criteria

- Có 2 ROLAP views cho trip và shift: `analytics.olap_trip_cube` và
  `analytics.olap_shift_cube`.
- Superset provision datasets từ các views này.
- Có chart/demo thể hiện slice, dice, drill-down, roll-up và pivot.
- Số liệu trong OLAP views reconcile theo certified metric catalog, với
  `utilization_rate` và `revenue_per_hour` tính bằng ratio-of-sums.
- Tài liệu demo giải thích rõ đây là ROLAP, không phải MOLAP cube vật lý.
