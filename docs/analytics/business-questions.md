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

Dashboard `NYC Green Taxi - Driver Operations` là một **decision-first
operational dashboard**. Bản clean-slate dùng light enterprise canvas, card
trắng, một semantic accent và màu trạng thái có chủ đích. Mỗi tab bắt đầu bằng
context, sau đó mới đến KPI/visual hành động. Superset provision 14 datasets,
109 metric instances, 35 decision-focused visuals trên 6 tabs:

1. **Executive pulse**
   - All-history KPI strip có period/timezone rõ: total payment revenue,
     observed trips, drivers/vehicles with trip activity và shift utilization.
   - Revenue và observed trips là hai aligned small multiples, không shared
     mixed-unit axis.
   - Pickup-borough ranking là breakdown duy nhất ở overview.

2. **Demand patterns**
   - Hero heatmap top-12 pickup zone × 24 giờ giữ đủ mọi ô của cohort.
   - Weekday × hour heatmap và hourly profile dùng trục có thứ tự.
   - Pareto concentration table và zone value profile (volume × revenue/trip)
     thay cho nhiều ranking lặp lại.
   - Tab chỉ diễn giải observed/served activity, không gọi là unmet demand.

3. **Workforce actions**
   - Tất cả KPI và queue dùng latest reporting month.
   - Driver review queue là hero; peer matrix chỉ dùng ba status hành động.
   - Top-30 lowest-utilization shifts có rank, driver, vehicle và metric context.
   - Vehicle peer-review queue tách rõ trạng thái provisional.

4. **Trust & data health**
   - Latest successful NDS run lấy từ audit metadata kể cả khi có 0 issue.
   - DQ issue events, quarantined rows và rows loaded là ba KPI riêng.
   - Successful-run health table thay chart trend bị scale distortion.
   - Historical findings by rule/source giữ đường điều tra; anomaly queues rỗng
     được suppress thay vì render `No results`.

5. **OLAP lab**
   - Năm operation tường minh: slice, dice, drill-down, roll-up và pivot.
   - Mỗi visual ghi rõ member đang chọn và chỉ dùng một đơn vị trên mỗi axis.

6. **Exploratory models**
   - Driver-segmentation và association-rule provenance tách khỏi results.
   - Model run, training window, parameters/quality metrics và publication cap luôn hiển thị; dashboard chỉ đọc current successful run.
   - Outputs được gắn exploratory, không trình bày như certified KPI.

## Superset implementation scope

- `analytics.trip_pickup` và `analytics.trip_dropoff` tách riêng pickup/dropoff
  date-location role để tránh ambiguity trong BI tool.
- `pickup_weekday_label`, `dropoff_weekday_label` và
  `shift_start_weekday_label` dùng nhãn có tiền tố thứ tự để các chart weekday
  hiển thị theo thứ tự vận hành thay vì thứ tự chữ cái.
- `analytics.shift` giữ shift-grain metrics; không join trực tiếp trip và shift
  ở row level.
- `analytics.pareto_pickup_zone` phục vụ concentration/value analysis;
  `analytics.driver_performance_monthly` và
  `analytics.vehicle_performance_monthly` phục vụ latest-month action queues.
- `analytics.dq_summary` là DQ boundary riêng; không dùng để thay thế business
  fact.
- `analytics.shift_trip_aggregate` chỉ là view kỹ thuật chống fan-out, không
  provision thành Superset dataset.

## Implemented OLAP and Data Mining extension

Các dashboard hiện tại trả lời BQ01-BQ05 ở dạng operational monitoring, có tab
OLAP lab và tab Exploratory models.

- **ROLAP layer**: `analytics.olap_trip_cube` và
  `analytics.olap_shift_cube` demo slice, dice, drill-down, roll-up và pivot
  trực tiếp trên Superset. Chi tiết nằm ở [olap-plan.md](olap-plan.md).

- **Data Mining**: triển khai driver segmentation bằng K-Means và route/demand
  association rules bằng Apriori. Chi tiết nằm ở
  [data-mining-plan.md](data-mining-plan.md).

Hai phần này phải phục vụ quyết định vận hành, không dùng để thay thế semantic
contract hoặc certified metric catalog hiện có.
