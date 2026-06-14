# Analytics Requirements Traceability Matrix
**NYC Green Taxi Driver Operations BI - Requirements Audit**

Tài liệu này ánh xạ các câu hỏi nghiệp vụ (Business Questions) và chỉ số hiệu suất (KPIs) với cấu trúc Dimensional Data Store (DDS) hiện tại. Đây là bản rà soát kỹ thuật độc lập để xác định mức độ sẵn sàng và các rủi ro trùng lặp dữ liệu trước khi khóa thiết kế.

---

## 1. Phân loại trạng thái hỗ trợ (Support Status Classification)

Mỗi yêu cầu phân tích được phân loại vào một trong các trạng thái sau:
- `SUPPORTED_NOW`: Đầy đủ cột nguồn, đúng hạt dữ liệu, không phụ thuộc đối soát, ngữ nghĩa thời gian rõ ràng.
- `PARTIALLY_SUPPORTED`: Thiếu một phần cột hoặc cần xử lý thêm qua view/join nghiệp vụ.
- `NOT_SUPPORTED`: Không có dữ liệu hỗ trợ trong DDS hoặc sai hạt dữ liệu nghiêm trọng.
- `PENDING_RECONCILIATION`: Cần số liệu hoặc logic đối soát từ Prompt 2 xác nhận trước khi đưa vào sử dụng.

---

## 2. Ma trận truy vết yêu cầu (Traceability Matrix)

### REQ-BQ01: Phân tích khu vực và khung giờ ưu tiên năng lực tài xế
- **Business question**: Khu vực/khung giờ nào cần ưu tiên năng lực?
- **Intended audience**: Quản lý vận hành đội xe và điều phối viên.
- **Decision supported**: Bố trí phân bổ tài xế đến các khu vực và khung giờ cao điểm có nhu cầu lớn để tối ưu doanh thu.
- **Candidate metric name**: `trip_count`, `total_revenue`.
- **Fact table**: `dds.fact_driver_trip`.
- **Dimension tables**: `dds.dim_location`, `dds.dim_date`, `dds.dim_time`.
- **Required columns**:
  - `dds.fact_driver_trip.pickup_location_key`
  - `dds.fact_driver_trip.pickup_date_key`
  - `dds.fact_driver_trip.pickup_time_key`
  - `dds.fact_driver_trip.total_amount`
  - `dds.dim_location.borough`, `dds.dim_location.zone`
  - `dds.dim_date.date`
  - `dds.dim_time.hour`
- **Grain**: Một dòng cho một chuyến đi (trip grain).
- **Date role**: `pickup_date_key` (Vai trò ngày đón khách - Candidate active), `dropoff_date_key` (Vai trò ngày trả khách - Candidate inactive). Mối quan hệ active/inactive chưa được khóa chính thức.
- **Filter context**: Lọc theo Quận/Khu vực (Borough/Zone), Ngày dương lịch, Khung giờ (Hour/Time bucket).
- **Unit/format**: Số nguyên (chuyến đi), USD (doanh thu).
- **Current support status**: `PENDING_RECONCILIATION`.
- **Reconciliation dependency**: Phụ thuộc vào việc thống nhất vai trò ngày hoạt động chính thức (pickup hay dropoff) làm trục thời gian mặc định của báo cáo (Prompt 3A).
- **Double-count risk**: Thấp khi truy vấn độc lập trên `fact_driver_trip`. Tuy nhiên, nếu thực hiện join chéo với dữ liệu ca làm việc để tính hiệu suất vùng, có nguy cơ nhân đôi số liệu do quan hệ một-nhiều giữa ca làm và chuyến đi.
- **Notes/open questions**: Quyết định mối quan hệ nào là Active/Inactive trong semantic model vẫn là câu hỏi mở cho Prompt 3A.

---

### REQ-BQ02: Phân tích ca làm việc hiệu quả
- **Business question**: Ca nào sử dụng thời gian hiệu quả?
- **Intended audience**: Quản lý vận hành đội xe.
- **Decision supported**: Đánh giá hiệu suất các ca làm việc của tài xế để tối ưu hóa thời gian chạy xe có khách và giảm thời gian chờ.
- **Candidate metric name**: `utilization_rate`, `occupied_minutes`, `shift_duration_minutes`, `idle_minutes`.
- **Fact table**: `dds.fact_driver_shift`.
- **Dimension tables**: `dds.dim_driver`, `dds.dim_vehicle`, `dds.dim_date`, `dds.dim_time`.
- **Required columns**:
  - `dds.fact_driver_shift.utilization_rate`
  - `dds.fact_driver_shift.occupied_minutes`
  - `dds.fact_driver_shift.shift_duration_minutes`
  - `dds.fact_driver_shift.idle_minutes`
  - `dds.fact_driver_shift.shift_start_date_key`
- **Grain**: Một dòng cho một ca làm việc hoàn tất (shift grain).
- **Date role**: `shift_start_date_key` (Ngày bắt đầu ca).
- **Filter context**: Lọc theo tài xế, phương tiện, ngày bắt đầu ca.
- **Unit/format**: Tỷ lệ phần trăm (`0.00%`), Phút.
- **Current support status**: `PENDING_RECONCILIATION`.
- **Reconciliation dependency**: Cần Prompt 2 xác nhận thuật toán tính toán `occupied_minutes` (tổng hợp từ trips thực tế thuộc ca) và `idle_minutes` (chênh lệch giữa tổng thời lượng ca và thời gian chở khách). 
- **Double-count risk**: Không có nguy cơ trùng lặp khi chạy riêng trên `fact_driver_shift`.
- **Notes/open questions**: 
  - Tỷ lệ tận dụng ở cấp độ tổng hợp (ví dụ: trung bình tháng của tài xế) bắt buộc phải tính theo tỷ số của các tổng (`SUM(occupied_minutes) / SUM(shift_duration_minutes)`) để tránh lỗi tính trung bình của các tỷ lệ (average-of-ratios). Điều này cần được định nghĩa dưới dạng certified metric tập trung.

---

### REQ-BQ03: So sánh hiệu suất tài xế (Peer comparison)
- **Business question**: Driver nào có revenue/hour thấp hoặc idle cao?
- **Intended audience**: Quản lý vận hành, Bộ phận nhân sự tài xế.
- **Decision supported**: Nhận diện các tài xế hoạt động kém hiệu quả để đào tạo lại hoặc hỗ trợ điều phối ca làm việc tốt hơn.
- **Candidate metric name**: `revenue_per_hour` (hoặc `revenue_per_shift_hour` / `revenue_per_occupied_hour`), `idle_minutes`, `total_revenue`.
- **Fact table**: `dds.fact_driver_shift`.
- **Dimension tables**: `dds.dim_driver`, `dds.dim_date`.
- **Required columns**:
  - `dds.fact_driver_shift.total_revenue`
  - `dds.fact_driver_shift.shift_duration_minutes`
  - `dds.fact_driver_shift.idle_minutes`
  - `dds.dim_driver.driver_id`, `dds.dim_driver.display_name`
- **Grain**: Một dòng cho một ca làm việc hoàn tất (shift grain).
- **Date role**: `shift_start_date_key`.
- **Filter context**: Lọc theo từng tài xế hoặc nhóm tài xế, khoảng thời gian.
- **Unit/format**: USD/Giờ, Phút.
- **Current support status**: `PENDING_RECONCILIATION`.
- **Reconciliation dependency**: Phụ thuộc vào đối soát tổng revenue của ca làm việc (`total_revenue` tổng hợp từ các trip thuộc ca) với tổng tiền ghi nhận thực tế trên từng chuyến đi trong `fact_driver_trip`.
- **Double-count risk**: Cực kỳ cao nếu cố gắng join bảng `fact_driver_shift` với `fact_driver_trip` ở cấp độ dòng (row-level) để phân tích chi tiết. Mọi phân tích so sánh phải thực hiện tổng hợp độc lập trên từng bảng trước khi so khớp kết quả.
- **Notes/open questions**: Định nghĩa của `revenue_per_hour` cần được làm rõ: sử dụng tổng thời gian ca (`shift_duration_minutes`) hay chỉ tính thời gian chở khách thực tế (`occupied_minutes`).

---

### REQ-BQ04: Phân tích hiệu quả sử dụng phương tiện (Vehicle utilization)
- **Business question**: Vehicle nào hoạt động dưới mức thông thường?
- **Intended audience**: Quản lý đội xe.
- **Decision supported**: Lên kế hoạch bảo dưỡng, thanh lý xe hoạt động kém hiệu quả hoặc điều chuyển xe sang khu vực khác.
- **Candidate metric name**: `utilization_rate` (xe), `trip_count` (xe), `total_revenue` (xe).
- **Fact table**: `dds.fact_driver_shift`.
- **Dimension tables**: `dds.dim_vehicle`, `dds.dim_date`.
- **Required columns**:
  - `dds.fact_driver_shift.utilization_rate`
  - `dds.fact_driver_shift.trip_count`
  - `dds.fact_driver_shift.total_revenue`
  - `dds.dim_vehicle.vehicle_id`, `dds.dim_vehicle.vehicle_status`, `dds.dim_vehicle.vehicle_type`
- **Grain**: Một dòng cho một ca làm việc hoàn tất (shift grain).
- **Date role**: `shift_start_date_key`.
- **Filter context**: Lọc theo phương tiện, trạng thái xe, loại xe, khoảng thời gian.
- **Unit/format**: Tỷ lệ phần trăm (`0.00%`), Số nguyên, USD.
- **Current support status**: `PENDING_RECONCILIATION`.
- **Reconciliation dependency**: Phụ thuộc vào việc đối soát trạng thái lịch sử của xe (SCD Type 2) trong `dim_vehicle` khớp chính xác với thời điểm diễn ra ca làm việc.
- **Double-count risk**: Nếu tính tổng doanh thu xe chạy bằng cách cộng dồn trực tiếp từ `fact_driver_shift` và `fact_driver_trip` qua mối quan hệ join trực tiếp, sẽ gây ra sai số nhân đôi doanh thu nếu không gom nhóm theo xe trước.
- **Notes/open questions**: Xe chạy ở trạng thái bảo dưỡng (`MAINTENANCE`) có phát sinh ca làm hay không? Cách xử lý các ca chạy thử của đội kỹ thuật.

---

### REQ-BQ05: Danh sách bất thường vận hành và dữ liệu
- **Business question**: Trường hợp nào cần kiểm tra?
- **Intended audience**: Giám sát vận hành và kỹ sư chất lượng dữ liệu (DQ Engineer).
- **Decision supported**: Điều tra các ca làm trùng lặp, tài xế gian lận thời gian, hoặc lỗi dữ liệu hệ thống nguồn để xử lý cách ly hoặc phạt.
- **Candidate metric name**: `anomaly_count`, `invalid_trip_count`.
- **Fact table**: `dds.fact_driver_shift`, `dds.fact_driver_trip`.
- **Dimension tables**: `dds.dim_junk_trip`, `dds.dim_driver`, `dds.dim_vehicle`, `dds.dim_date`.
- **Required columns**:
  - `dds.fact_driver_shift.is_anomaly`
  - `dds.dim_junk_trip.is_anomaly`
- **Grain**: Cả hai hạt dữ liệu (trip grain và shift grain).
- **Date role**: `shift_start_date_key` và `pickup_date_key`.
- **Filter context**: Cờ `is_anomaly = true` hoặc `junk_trip_key.is_anomaly = true`.
- **Unit/format**: Số nguyên (số vụ việc).
- **Current support status**: `PARTIALLY_SUPPORTED` / `PENDING_RECONCILIATION`.
- **Reconciliation dependency**: Phụ thuộc vào việc chốt bộ quy tắc xác định cờ `is_anomaly` ở Gate 2 (trùng ca tài xế, trùng ca xe, chuyến đi ngoài ca).
- **Double-count risk**: Không có nguy cơ lớn nếu đếm số ca bất thường và số chuyến bất thường độc lập. Tuy nhiên, không được cộng gộp trực tiếp hai số này với nhau vì hạt dữ liệu khác nhau.
- **Notes/open questions**: 
  - Chỉ số `invalid_trip_count` (số chuyến đi bị loại bỏ do lỗi nặng) **KHÔNG THỂ HỖ TRỢ** trong tầng DDS vì toàn bộ các chuyến lỗi nặng (`ERROR` ở Gate 1) đã bị cách ly trực tiếp từ staging vào bảng `dq.quarantine_record` và không bao giờ được load vào DDS. Muốn đo lường chỉ số này phải truy vấn trực tiếp schema `dq` hoặc `audit`, nằm ngoài ranh giới phân tích của DDS.

---

## 3. Tổng hợp các rủi ro trùng lặp dữ liệu (Double-counting Risks)

Khi thực hiện phân tích nghiệp vụ trên hai hạt dữ liệu khác nhau (trip grain và shift grain), nhà phân tích hoặc công cụ BI rất dễ gặp phải các rủi ro kỹ thuật sau:

1.  **Join trực tiếp hai Fact (Fact-to-Fact Join)**:
    - *Rủi ro*: Join `fact_driver_trip` với `fact_driver_shift` bằng khóa `shift_id` ở cấp độ dòng sẽ tạo ra mối quan hệ một-nhiều. Phép join này làm nhân bản các thuộc tính của ca làm việc (như doanh thu ca, tổng thời gian ca) lên nhiều lần tương ứng với số chuyến đi trong ca đó.
    - *Giải pháp*: Không bao giờ thực hiện join trực tiếp hai fact này trong cùng một truy vấn cấp dòng. Báo cáo bắt buộc phải tổng hợp (group by) dữ liệu chuyến đi theo `shift_id` trước khi thực hiện join với dữ liệu ca làm việc.
2.  **Định nghĩa trùng lặp doanh thu**:
    - *Rủi ro*: `fact_driver_shift.total_revenue` và `fact_driver_trip.total_amount` đều đại diện cho doanh thu. Nếu báo cáo tổng hợp doanh thu toàn hệ thống bằng cách cộng dồn cả hai trường này hoặc lấy nhầm trường này thay cho trường kia mà không làm rõ phạm vi, sẽ dẫn đến sai số đối soát.
    - *Giải pháp*: Xác định rõ `total_revenue` trên ca làm là chỉ số tổng hợp (certified metric) chỉ dùng cho phân tích ca, còn doanh thu tổng của doanh nghiệp phải được tính từ tổng của `fact_driver_trip.total_amount`.
