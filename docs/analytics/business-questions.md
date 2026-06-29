# Analytics Requirements

## Business questions

| ID | Question | Primary output |
|---|---|---|
| BQ01 | Khu vực/khung giờ nào cần ưu tiên năng lực? | Zone-hour heatmap |
| BQ02 | Ca nào sử dụng thời gian hiệu quả? | Shift utilization ranking |
| BQ03 | Driver nào có revenue/hour thấp hoặc idle cao? | Peer comparison |
| BQ04 | Vehicle nào hoạt động dưới mức thông thường? | Vehicle utilization |
| BQ05 | Trường hợp nào cần kiểm tra? | DQ/anomaly queue |
| BQ06 | Có thể phân nhóm driver theo hiệu suất để hỗ trợ điều phối/đào tạo không? | Driver segmentation |
| BQ07 | Những pattern pickup/dropoff nào lặp lại theo khung giờ/khu vực? | Route association rules |

## Measures

- `trip_count = COUNT(*)`
- `occupied_minutes = SUM(trip_duration_minutes)`
- `idle_minutes = shift_minutes - occupied_minutes`, gồm buffer đầu/cuối ca và gap giữa trip
- `shift_minutes = shift_end - shift_start`
- `utilization_rate = occupied_minutes / shift_minutes`
- `revenue_per_hour = SUM(total_revenue) * 60 / SUM(shift_duration_minutes)`
- `average_fare = SUM(fare_amount) / COUNT(trip_id)`
- `invalid_trip_count` được biểu diễn qua `quarantine_count` tại DQ boundary.
- Trip anomaly và shift anomaly dùng metric riêng theo đúng grain.

Ratios phải được tính từ tổng tử số/tổng mẫu số, không cộng các ratio cấp dòng.
`revenue_per_hour` dùng toàn bộ shift duration, gồm cả idle time, theo
[semantic contract](semantic-contract.md).

## Monitoring Dashboard Structure

Dashboard `NYC Green Taxi - Driver Operations` là một **operational monitoring
dashboard**, không phải một báo cáo narrative dài. Layout theo phong cách light
enterprise dashboard: KPI strip ở đầu tab, visual chính ở giữa, ranking/detail
table ở cuối luồng điều tra. Trạng thái hiện tại được provision tự động trong
Superset với 10 datasets, 88 metric instances, 42 charts và 6 tabs.

1. **Operations Overview**
   - KPI cards: total revenue, total trips, active drivers, active vehicles,
     overall shift utilization.
   - Monthly revenue/trip trend.
   - Pickup borough ranking, top pickup zones và ordered weekday profile.

2. **Demand Patterns**
   - Ordered weekday x hour heatmap để tránh đọc sai thứ tự ngày trong tuần.
   - Hourly demand profile.
   - Zone concentration table với cumulative trip percentage.
   - Top pickup zones by revenue.
   - Pickup/dropoff borough volume và average trip distance by borough.

3. **Driver & Fleet Performance**
   - Shift KPIs: completed shifts, revenue per shift hour, trips per shift,
     shift utilization.
   - Driver performance matrix dùng `analytics.driver_performance_summary`.
   - Driver review queue dựa trên rule `needs_review`, không hard-code tên tài
     xế.
   - Vehicle type performance và vehicle detail table.

4. **Data Quality & Anomalies**
   - DQ issue, quarantine, trip anomaly và shift anomaly KPI.
   - DQ trend, severity/source breakdown và top data-quality rules.
   - DQ, quarantine, trip anomaly và shift anomaly là các khái niệm riêng,
     không cộng thành một tổng.

## Superset implementation scope

- `analytics.trip_pickup` và `analytics.trip_dropoff` tách riêng pickup/dropoff
  date-location role để tránh ambiguity trong BI tool.
- `pickup_weekday_label`, `dropoff_weekday_label` và
  `shift_start_weekday_label` dùng nhãn có tiền tố thứ tự để các chart weekday
  hiển thị theo thứ tự vận hành thay vì thứ tự chữ cái.
- `analytics.shift` giữ shift-grain metrics; không join trực tiếp trip và shift
  ở row level.
- `analytics.pareto_pickup_zone` và `analytics.driver_performance_summary` là
  summary datasets phục vụ concentration analysis, driver matrix và review
  queue.
- `analytics.dq_summary` là DQ boundary riêng; không dùng để thay thế business
  fact.
- `analytics.shift_trip_aggregate` chỉ là view kỹ thuật chống fan-out, không
  provision thành Superset dataset.

## Implemented OLAP and Data Mining extension

Các dashboard hiện tại trả lời BQ01-BQ05 ở dạng operational monitoring, có tab
OLAP demo và tab Data Mining Insights.

- **ROLAP layer**: `analytics.olap_trip_cube` và
  `analytics.olap_shift_cube` demo slice, dice, drill-down, roll-up và pivot
  trực tiếp trên Superset. Chi tiết nằm ở [olap-plan.md](olap-plan.md).

- **Data Mining**: triển khai driver segmentation bằng K-Means và route/demand
  association rules bằng Apriori. Chi tiết nằm ở
  [data-mining-plan.md](data-mining-plan.md).

Hai phần này phải phục vụ quyết định vận hành, không dùng để thay thế semantic
contract hoặc certified metric catalog hiện có.
