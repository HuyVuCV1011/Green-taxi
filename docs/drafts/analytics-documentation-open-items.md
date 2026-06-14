# Analytics Documentation Open Items
**NYC Green Taxi Driver Operations BI - Documentation and Design Tracker**

Tài liệu này theo dõi các nội dung chưa được chốt (open items), các giả định chưa kiểm chứng và các quyết định kỹ thuật cần được giải quyết trong các workstream tiếp theo (Prompt 2 và Prompt 3A).

---

## 1. Nội dung cần Prompt 2 (Reconciliation & Idempotency) xác nhận

| Nội dung cần xác nhận | Tác động đến tài liệu / thiết kế | Trạng thái hiện tại |
|---|---|---|
| Chi tiết hành vi SCD Type 2 khi chạy lại batch (idempotency) | Cần cập nhật mô tả cột `start_date`, `end_date`, `is_current` khi có bản ghi bị ghi đè hoặc chạy lại cùng một batch | `TBD_AFTER_RECONCILIATION` |
| Cơ chế sinh và đối soát `source_row_hash` cho các thực thể chiều | Phải xác nhận cách tính hash có bao gồm các trường kỹ thuật hay không để làm rõ logic transformation trong Data Dictionary | `TBD_AFTER_RECONCILIATION` |
| Các chỉ số đối soát chính xác sau chạy thử nghiệm thực tế | Các hằng số đối soát hoặc tỷ lệ sai số chấp nhận được trong báo cáo đối soát chất lượng dữ liệu | `TBD_AFTER_RECONCILIATION` |
| Cách thức xử lý và cách ly (Quarantine) các bản ghi lỗi nghiệp vụ | Làm rõ cờ `is_anomaly` được cập nhật sau khi đối soát chéo các nguồn dữ liệu hay đi theo từng dòng từ staging | `TBD_AFTER_RECONCILIATION` |

---

## 2. Nội dung cần Prompt 3A (Date Semantics & Metrics Lock) quyết định

| Nội dung quyết định | Tác động đến tài liệu / thiết kế | Trạng thái hiện tại |
|---|---|---|
| Quyết định mối quan hệ active/inactive cho các chiều có nhiều liên kết | Xác định mối quan hệ nào giữa `fact_driver_trip` và `dim_date` (pickup hay dropoff) hoặc `dim_location` (pickup hay dropoff) là mặc định khi thực hiện các truy vấn và semantic layer | `TBD_AFTER_RECONCILIATION` |
| Định nghĩa chính thức của cờ `is_peak_hour` | Khoảng thời gian cụ thể (ví dụ: 07:00-09:00 và 16:00-19:00 ngày thường) được tính là peak hour | `TBD_AFTER_RECONCILIATION` |
| Cách tính `utilization_rate` cấp độ tổng hợp (Aggregation) | Xác định công thức certified metric hoặc phép gộp SQL chuẩn là `SUM(occupied_minutes) / SUM(shift_duration_minutes)` để tránh lỗi tính trung bình của các tỷ lệ | `TBD_AFTER_RECONCILIATION` |
| Ranh giới phân định lỗi chất lượng dữ liệu (DQ anomaly) và bất thường nghiệp vụ (Business anomaly) | Định nghĩa các rule cập nhật cờ `is_anomaly` của `fact_driver_shift` và `fact_driver_trip` | `TBD_AFTER_RECONCILIATION` |

---

## 3. Các giả định chưa được chứng minh (Unproven Assumptions)

- **Múi giờ**: Giả định rằng mọi timestamp nghiệp vụ từ 3 nguồn (MySQL, MongoDB, PostgreSQL) đều đồng bộ theo múi giờ `America/New_York` và không có chênh lệch múi giờ hệ thống khi nạp vào staging.
- **Tính duy nhất của shift_id**: Giả định `shift_id` luôn là duy nhất trên toàn hệ thống nguồn dispatch và không bị trùng lặp giữa các vendor.
- **Grain của dim_location**: Giả định các Taxi Zone ID (1-265) tĩnh và không đổi trong suốt thời gian phân tích (2020-2021).
- **Hành khách âm hoặc bằng 0**: Giả định các chuyến đi có `passenger_count` bằng 0 hoặc NULL vẫn là hợp lệ và không bị quarantine ở mức ERROR.
