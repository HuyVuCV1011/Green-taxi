# ADR-006: Dashboard semantics và trạng thái exploratory cho Data Mining

Status: Accepted

## Context

Dashboard có các visual đặt measure khác đơn vị trên cùng y-axis, thiếu ngữ
cảnh batch DQ và trình bày Data Mining như certified KPI. Điều này có thể làm
người xem suy luận sai dù SQL source vẫn đúng.

## Decision

- Tách measure khác đơn vị thành visual riêng; chỉ dùng secondary axis khi unit,
  scale và tooltip đã được kiểm thử.
- Bổ sung dataset batch-level cho DQ và queue điều tra anomaly ở trip/shift grain.
- Bổ sung driver-month trend và vehicle-month peer queue; vehicle threshold là
  provisional cho đến khi business owner xác nhận.
- K-Means/Apriori được đánh dấu `exploratory`, lưu lịch sử trong model-run ledger;
  dashboard chỉ đọc current successful run, hiển thị training window, parameters
  và quality/stability metrics; không gắn certification owner.
- Giữ native filters tắt trên Superset 6.1 do lỗi time filter đã biết; thêm
  context card và điều kiện chart-level minh bạch.

## Consequences

Dashboard hiện có 35 decision-focused visuals và 14 datasets. Các metric certified
không đổi công thức; output mining và peer threshold không được dùng để tự động
ra quyết định vận hành/nhân sự.
