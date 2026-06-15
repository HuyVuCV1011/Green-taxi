# Certified Metric Catalog

Status: `CERTIFIED`

Quy ước chung: business time dùng `America/New_York`; DQ time dùng UTC. Amount
hiển thị USD `0.00`, distance mile `0.00`, duration minute `0.00`, rate
`0.00%`. Null measure được `COALESCE(..., 0)` khi cộng; denominator 0 trả NULL.
Unknown/inferred được tính mặc định để giữ reconciliation.

| Metric ID | Business name và definition | Source / SQL expression | Grain; additivity | Filter, date role, null/zero | Precision; reconciliation; Superset |
|---|---|---|---|---|---|
| `total_trips` | Tổng số trip được nhận vào DDS | `analytics.trip_pickup`; `COUNT(trip_id)` | Trip; additive | Mọi filter; pickup; trip_id non-null | Integer; DDS trip count; Certified |
| `completed_shifts` | Tổng completed shift | `analytics.shift`; `COUNT(shift_id)` | Shift; additive | Mọi filter; shift start; non-null | Integer; DDS shift count; Certified |
| `total_revenue` | Tổng tiền thanh toán TLC | Trip: `SUM(total_amount)`; shift analysis: `SUM(total_revenue)` | Fact-owned; additive | Không cộng hai fact; pickup/shift start; null to 0 | USD 0.00; NDS/DDS total_amount; Certified |
| `fare_revenue` | Tổng cước gốc, không phải total payment | `analytics.trip_pickup`; `SUM(fare_amount)` | Trip; additive | Mọi filter; pickup; null to 0 | USD 0.00; NDS/DDS fare_amount; Certified |
| `total_tips` | Tổng tip | Trip: `SUM(tip_amount)`; shift: `SUM(total_tips)` | Fact-owned; additive | Không cộng hai fact; default dataset role | USD 0.00; NDS/DDS tip; Certified |
| `total_distance` | Tổng quãng đường trip | `SUM(trip_distance)` | Trip; additive | Pickup; null distance bỏ qua | Mile 0.00; NDS/DDS distance; Certified |
| `total_trip_minutes` | Tổng thời lượng trip đã round từng dòng | `SUM(trip_duration_minutes)` | Trip; additive | Pickup; null duration bỏ qua | Minute 0.00; rounded-row reconciliation; Certified |
| `average_fare` | Cước gốc trung bình mỗi trip | `SUM(fare_amount) / NULLIF(COUNT(trip_id),0)` | Trip; non-additive | Pickup; zero trips -> NULL | USD 0.00; fare_amount; Certified |
| `average_trip_distance` | Quãng đường trung bình của trip có distance | `SUM(trip_distance) / NULLIF(COUNT(trip_distance),0)` | Trip; non-additive | Pickup; null excluded; zero -> NULL | Mile 0.00; distance; Certified |
| `average_trip_duration` | Thời lượng trung bình của trip có duration | `SUM(trip_duration_minutes) / NULLIF(COUNT(trip_duration_minutes),0)` | Trip; non-additive | Pickup; null excluded; zero -> NULL | Minute 0.00; duration; Certified |
| `trips_per_shift` | Số trip trung bình mỗi completed shift | `analytics.shift`; `SUM(trip_count)::numeric / NULLIF(COUNT(shift_id),0)` | Shift; non-additive | Shift start; zero shifts -> NULL | 0.00; shift trip_count; Certified |
| `revenue_per_shift` | Revenue trung bình mỗi completed shift | `SUM(total_revenue) / NULLIF(COUNT(shift_id),0)` | Shift; non-additive | Shift start; zero -> NULL | USD 0.00; shift revenue; Certified |
| `revenue_per_hour` | Revenue trên toàn bộ giờ ca được bố trí | `SUM(total_revenue) * 60 / NULLIF(SUM(shift_duration_minutes),0)` | Shift; non-additive ratio | Shift start; zero minutes -> NULL | USD/hour 0.00; shift totals; Certified |
| `occupied_minutes` | Tổng phút có khách trong completed shifts | `SUM(occupied_minutes)` | Shift; additive | Shift start; null to 0 | Minute 0.00; shift reconciliation; Certified |
| `idle_minutes` | Tổng phút ca không có khách | `SUM(idle_minutes)` | Shift; additive | Shift start; null to 0 | Minute 0.00; duration balance; Certified |
| `shift_duration_minutes` | Tổng phút của completed shifts | `SUM(shift_duration_minutes)` | Shift; additive | Shift start; null to 0 | Minute 0.00; shift timestamps; Certified |
| `utilization_rate` | Tỷ lệ thời gian có khách trên thời gian ca | `SUM(occupied_minutes) / NULLIF(SUM(shift_duration_minutes),0)` | Shift; non-additive ratio-of-sums | Shift start; zero -> NULL; không average row ratio | 0.00%; duration balance; Certified |
| `anomaly_trip_count` | Số trip có business anomaly | `analytics.trip_pickup`; `COUNT(*) FILTER (WHERE is_trip_anomaly)` | Trip; additive | Pickup; unknown included | Integer; junk anomaly flag; Certified |
| `anomaly_shift_count` | Số shift có business anomaly | `analytics.shift`; `COUNT(*) FILTER (WHERE is_shift_anomaly)` | Shift; additive | Shift start; unknown included | Integer; shift anomaly flag; Certified |
| `anomaly_rate` | Tỷ lệ trip anomaly trên tổng trip | `COUNT(*) FILTER (WHERE is_trip_anomaly)::numeric / NULLIF(COUNT(*),0)` | Trip; non-additive | Pickup; zero -> NULL | 0.00%; trip anomaly; Certified as trip rate |
| `active_driver_count` | Driver distinct có trip activity trong kỳ | `analytics.trip_pickup`; `COUNT(DISTINCT driver_key)` | Trip filter context; non-additive | Pickup; không dùng current status | Integer; fact activity; Certified |
| `active_vehicle_count` | Vehicle distinct có trip activity trong kỳ | `analytics.trip_pickup`; `COUNT(DISTINCT vehicle_key)` | Trip filter context; non-additive | Pickup; không dùng current status | Integer; fact activity; Certified |
| `dq_issue_count` | Số DQ issues theo nhóm DQ | `analytics.dq_summary`; `SUM(issue_count)` | DQ event summary; additive | UTC event date; null to 0 | Integer; `dq.dq_issue`; Certified DQ only |
| `quarantine_count` | Số records bị quarantine ERROR | `analytics.dq_summary`; `SUM(quarantine_count)` | DQ event summary; additive | UTC event date; null to 0 | Integer; `dq.quarantine_record`; Certified DQ only |

## Superset implementation notes

- Tạo metric đúng dataset sở hữu; không tạo một metric dùng đồng thời hai fact.
- Đặt verbose name trùng business name, certification status `Certified`, và
  mô tả chứa Metric ID.
- Với dropoff analysis, tái sử dụng trip metrics trên
  `analytics.trip_dropoff`; chỉ date/location role thay đổi.
- Không expose `AVG(utilization_rate)` hay implicit `SUM(total_revenue)` trên
  dataset đã join row-level giữa trip và shift.
