# Analytics KPI Open Questions
**NYC Green Taxi Driver Operations BI - KPI Audit Tracker**

Tài liệu này tổng hợp và phân loại các câu hỏi mở, các điểm nghẽn và các quyết định cần được làm rõ bởi các bên liên quan trước khi triển khai chính thức tầng Semantic và Dashboard BI.

---

## 1. Nội dung cần Prompt 2 (Reconciliation & Idempotency) xác nhận
*Trạng thái: PENDING_RECONCILIATION*

- **Thuật toán chốt cờ `is_anomaly` cho Ca làm việc**: Xác định rõ các ngưỡng hoặc điều kiện logic gối ca (overlap) giữa các tài xế hoặc phương tiện để gán cờ `is_anomaly` tự động trong pipeline ETL.
- **Tính ổn định của khóa tự nhiên khi chạy lại (Idempotency Rerun)**: Xác nhận cơ chế xử lý khi chạy lại một batch trùng lặp dữ liệu không làm tăng thêm các phiên bản SCD Type 2 mới trong `dim_driver` và `dim_vehicle`.
- **Số liệu đối soát doanh thu thực tế**: Xác nhận sai số cho phép khi đối soát chênh lệch doanh thu chuyến đi (`SUM(total_amount)`) và doanh thu ca làm việc (`SUM(total_revenue)`) do chênh lệch thời gian cắt ca (cut-off window).
- **Đối soát số lượng chuyến đi**: Cách thức xử lý khi tổng số chuyến đi được chỉ định trong ca làm việc không khớp với `trip_count_source` đẩy về từ hệ thống Dispatch nguồn.

---

## 2. Quyết định thuộc thẩm quyền của Analytics Contract Owner

- **Khóa mối quan hệ Active/Inactive trên Dimension chung (Role-Playing Dimensions)**:
  - Chiều Ngày (`dim_date`): Xác định vai trò ngày đón khách (`pickup_date_key`) hay ngày trả khách (`dropoff_date_key`) là mối quan hệ Active mặc định trên semantic model.
  - Chiều Địa bàn (`dim_location`): Xác định địa bàn đón khách (`pickup_location_key`) hay địa bàn trả khách (`dropoff_location_key`) là mối quan hệ Active mặc định khi thực hiện phân tích luồng địa lý.
- **Định nghĩa công thức Certified Metric chung**: Cần khóa định nghĩa và công thức tính toán thống nhất cho các tỷ số hiệu suất để tránh việc tính toán sai lệch giữa SQL, Python và Dashboard.
- **Định nghĩa khung giờ cao điểm (Peak Hours)**: Chốt khung giờ cụ thể và các ngày áp dụng (ngày thường so với cuối tuần) để đồng bộ cờ `is_peak_hour` trong chiều `dim_time`.

---

## 3. Quyết định thuộc thẩm quyền của Business Owner

- **Định nghĩa Doanh thu (Revenue)**: 
  - Doanh thu phân tích (`total_revenue`) có bao gồm tiền tip, thuế MTA, phí cầu đường (`tolls_amount`) và phụ phí cải thiện hạ tầng (`improvement_surcharge`) hay không? Hay chỉ bao gồm cước gốc (`fare_amount`) và phụ phí ngoài (`extra`)?
  - Sự khác biệt về định nghĩa giữa doanh thu cước xe (Fare Revenue) và tổng doanh thu thanh toán (Total Revenue) cần hiển thị trên báo cáo.
- **Công thức tính Cước trung bình (Average Fare)**:
  - Phép tính cước trung bình của một chuyến đi sẽ dựa trên trường `fare_amount` hay `total_amount`?
- **Định nghĩa Doanh thu trên mỗi giờ hoạt động (Revenue per Hour)**:
  - Chỉ số này sẽ sử dụng tổng thời gian ca làm việc (`shift_duration_minutes`) làm mẫu số hay chỉ sử dụng thời gian thực tế xe có khách chở (`occupied_minutes`)?
- **Định nghĩa Tài xế/Phương tiện hoạt động (Active status)**:
  - Một tài xế/xe được coi là "hoạt động" trong kỳ báo cáo dựa trên trạng thái hồ sơ trong master (`dim_driver.employment_status = 'ACTIVE'`) hay bắt buộc phải có phát sinh hoạt động ghi nhận trong bảng fact (`fact_driver_shift` / `fact_driver_trip`)?
- **Cách xử lý các ca làm việc bị đánh dấu bất thường (Anomaly Shifts)**:
  - Khi tính toán các chỉ số trung bình của đội xe, có loại trừ các ca làm việc bị cờ `is_anomaly = true` ra khỏi tập dữ liệu phân tích hay không?
- **Unknown và Inferred Members**:
  - Có cho phép hiển thị các tài xế hoặc xe chưa hoàn thiện hồ sơ (inferred members dạng `Unknown` do late-arriving) trên các báo cáo hiệu suất nghiệp vụ hay không? Hay cần lọc bỏ và đưa vào danh sách chờ xử lý kỹ thuật?

---

## 4. Nội dung không được hỗ trợ bởi dữ liệu DDS hiện tại
*Trạng thái: NOT_SUPPORTED*

- **Số lượng chuyến đi không hợp lệ bị loại bỏ (`invalid_trip_count`)**:
  - *Lý do*: Tầng DDS chỉ chứa dữ liệu đã vượt qua DQ Gate 1 (Accepted). Các chuyến đi lỗi nặng bị cách ly (Quarantine) không đi vào DDS.
  - *Giải pháp*: Không thể tính chỉ số này trên DDS. Cần tạo một luồng báo cáo riêng kết nối trực tiếp vào schema `dq` hoặc bảng `audit.metadata_etl_batch` để đếm số dòng lỗi thô.
- **Chi phí vận hành, lương tài xế và lợi nhuận ròng**:
  - *Lý do*: Nằm ngoài phạm vi dự án (Out of scope) và không có trường thông tin tương ứng trong các hệ thống nguồn.

---

## 5. Đề xuất giải quyết bằng Analytics View (SQL View)

Các yêu cầu sau có thể được giải quyết bằng cách tạo các **Analytics Views** trên tầng DDS trước khi đưa vào công cụ BI để đơn giản hóa việc truy vấn:
- **View tổng hợp hiệu suất ca làm việc theo tuần/tháng**: Group by sẵn theo tài xế và tuần để tránh phép tính trung bình sai lệch trên Dashboard.
- **View phân tích luồng di chuyển giữa các quận (Borough-to-Borough matrix)**: Pivot sẵn tọa độ đón/trả để vẽ biểu đồ luồng dễ dàng.
- **View danh sách ca/chuyến bất thường (Anomaly Queue)**: Lọc sẵn các dòng có cờ `is_anomaly = true` kèm thông tin tài xế và xe hiện tại để đội vận hành tiện theo dõi và xử lý nhanh.

---

## 6. Đề xuất giải quyết bằng Certified Metric (Semantic Layer)

Các phép tính tỷ lệ phức tạp bắt buộc phải được khai báo dưới dạng **Certified Metrics** ở tầng semantic của công cụ BI để đảm bảo tính nhất quán:
- **Tỷ lệ tận dụng thời gian ca làm (Utilization Rate)**:
  - *Công thức*: `utilization_rate = SUM(occupied_minutes) / SUM(shift_duration_minutes)`
  - *Lưu ý*: Bắt buộc phải tính theo tổng tử số chia tổng mẫu số trên toàn bộ filter context, không được phép sử dụng hàm `AVERAGE(utilization_rate)` của các dòng.
- **Doanh thu bình quân mỗi dặm chạy (Revenue per Mile)**:
  - *Công thức*: `revenue_per_mile = SUM(total_amount) / SUM(trip_distance)`
- **Doanh thu bình quân trên giờ chạy có khách (Revenue per Occupied Hour)**:
  - *Công thức*: `revenue_per_occupied_hour = SUM(total_amount) / (SUM(occupied_minutes) / 60)`
