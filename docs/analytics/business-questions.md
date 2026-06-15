# Analytics Requirements

## Business questions

| ID | Question | Primary output |
|---|---|---|
| BQ01 | Khu vực/khung giờ nào cần ưu tiên năng lực? | Zone-hour heatmap |
| BQ02 | Ca nào sử dụng thời gian hiệu quả? | Shift utilization ranking |
| BQ03 | Driver nào có revenue/hour thấp hoặc idle cao? | Peer comparison |
| BQ04 | Vehicle nào hoạt động dưới mức thông thường? | Vehicle utilization |
| BQ05 | Trường hợp nào cần kiểm tra? | DQ/anomaly queue |

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
