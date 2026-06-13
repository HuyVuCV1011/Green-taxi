# Source-to-Target (S2T) Mapping Spec
**NYC Green Taxi Driver Operations BI - Warehouse Design Phase**

Tài liệu này đặc tả chi tiết ánh xạ và chuyển đổi dữ liệu (Source-to-Target Mapping) từ tầng **Staging** sang **NDS (Normalized Data Store)** và tiếp tục sang **DDS (Dimensional Data Store)** cho toàn bộ các thực thể dữ liệu trong hệ thống.

## Sơ đồ Tổng quan luồng dữ liệu DDS

![DDS Star Schema](../diagrams/dds_schema.png)

> 🔗 *Mã nguồn thiết kế Star Schema: [dds_schema.dbml](../diagrams/dds_schema.dbml).*

---

## 1. Nguyên tắc Ánh xạ & Chuyển đổi Chung

1. **Bảo toàn sematics thời gian**: Timestamps nghiệp vụ của Green Taxi và các nguồn giả lập được hiểu theo múi giờ địa phương New York (`America/New_York`). Khi nạp vào PostgreSQL, dùng kiểu dữ liệu `TIMESTAMP WITHOUT TIME ZONE` để tránh các rule tự động dịch giờ của database session.
2. **Surrogate Keys (Khóa thay thế)**:
   - Ở tầng NDS: Mọi bảng đều dùng khóa chính tự sinh kiểu số nguyên tăng dần (`SERIAL` hoặc `BIGSERIAL`) để làm khóa chính độc lập.
   - Ở tầng DDS: Tạo các surrogate key riêng cho DDS (ví dụ: `driver_key`, `vehicle_key`) độc lập với NDS SK để quản lý SCD.
3. **Idempotency**: Mọi câu lệnh insert/update phải dựa trên Business Key (Natural Key) và cờ trạng thái/watermark để khi chạy lại một batch, dữ liệu không bị nhân đôi và không bị sai lệch lịch sử.
4. **Xử lý Master Data đến trễ (Late-Arriving Master)**:
   - Khi dữ liệu giao dịch (trip/assignment) có tham chiếu đến tài xế/xe chưa tồn tại trong NDS master, một bản ghi **Inferred Member (Skeleton Row)** sẽ được tạo tự động với các giá trị thuộc tính mặc định (`Unknown`/`NULL`) và cờ `is_inferred = true`. Bản ghi này sẽ được cập nhật đầy đủ khi dữ liệu master thực sự đến ở batch sau.

---

## 2. Chi tiết Ánh xạ cho Thực thể Tài xế (Driver)

* **Physical Sources**:
  - MySQL `drivers` (Thông tin tài xế hiện tại)
  - MySQL `driver_changes` (Change feed lịch sử cập nhật thuộc tính)
* **Tài liệu hóa luồng di chuyển**:
  - `Staging.drivers` + `Staging.driver_changes` $\rightarrow$ `NDS.nds_driver` + `NDS.nds_driver_history` $\rightarrow$ `DDS.dim_driver`

### 2.1 Ánh xạ Staging $\rightarrow$ NDS

| Staging Source Field | NDS Target Column | Kiểu Dữ Liệu NDS | Quy tắc Chuyển đổi (Transformation Logic) |
|---|---|---|---|
| `driver_id` | `driver_nk` | `VARCHAR(50)` | Trim, viết hoa. Làm khóa Natural Key (UQ). |
| `vendor_id` | `vendor_sk` | `INT` | Lookup `nds_vendor` bằng `vendor_id` thô để lấy `vendor_sk`. |
| `driver_code` | `driver_code` | `VARCHAR(50)` | Trim. |
| `display_name` | `display_name` | `VARCHAR(100)`| Trim. |
| `hire_date` | `hire_date` | `DATE` | Cast sang kiểu DATE. |
| `employment_status` | `employment_status` | `VARCHAR(50)`| Trim, uppercase. Mặc định `ACTIVE`. |
| `license_status` | `license_status` | `VARCHAR(50)` | Trim, uppercase. Mặc định `ACTIVE`. |
| `license_expiry_date`| `license_expiry_date`| `DATE` | Cast sang kiểu DATE. |
| `experience_years` | `experience_years` | `INT` | Cast sang INT, kiểm tra `>= 0`. |
| `home_borough` | `home_borough` | `VARCHAR(100)`| Trim. Quận sinh sống hiện tại. |
| *Tự sinh* | `driver_sk` | `INT (PK)` | Khóa chính tự sinh (`SERIAL`). |
| *Tự sinh* | `is_inferred` | `BOOLEAN` | Mặc định `false`. Set `true` nếu là dòng skeleton do late-arriving. |
| `source_system` | `source_system_code`| `INT` | Gán mã nguồn định danh (e.g., 3 = MySQL HR). |

#### Xử lý Change Feed (`staging.driver_changes`) nạp vào `NDS.nds_driver_history`:
- Mỗi khi có sự kiện thay đổi (ví dụ: `HOME_BOROUGH_CHANGED`):
  - Ghi nhận một dòng lịch sử vào `nds_driver_history`: `driver_sk` (lookup từ `driver_id`), `event_id` (NK từ event), `effective_at`, `delivered_at`, `attribute_name` (e.g., 'home_borough'), `old_value`, `new_value`.
  - Cập nhật giá trị mới nhất của thuộc tính đó trực tiếp lên bảng chính `nds_driver`.
- Khi nạp `DDS.dim_driver`, các dòng `nds_driver_history` được xử lý theo thứ tự `effective_at`, `event_id`:
  - `home_borough` và `employment_status` là thuộc tính **SCD Type 2**: nếu giá trị mới khác dòng hiện hành, đóng dòng cũ bằng `end_date = effective_at`, `is_current = false`, sau đó insert dòng phiên bản mới với `start_date = effective_at`, `is_current = true`.
  - `driver_code`, `display_name`, `license_status`, `license_expiry_date` và `experience_years` là thuộc tính **SCD Type 1**: cập nhật trực tiếp trên dòng hiện hành, không tạo phiên bản mới.
  - `event_id` phải unique trong `nds_driver_history` để rerun không tạo trùng lịch sử.

### 2.2 Ánh xạ NDS $\rightarrow$ DDS (SCD Type 2)

Bảng chiều `dim_driver` áp dụng **SCD Type 2** để theo dõi lịch sử nơi cư trú (`home_borough`) và trạng thái công việc (`employment_status`) của tài xế.

| NDS Source Column | DDS Target Column | Kiểu Dữ Liệu DDS | SCD Type | Quy tắc nạp (Loading Rule) |
|---|---|---|---|---|
| `driver_nk` | `driver_id` | `VARCHAR(50)` | Type 0 | Natural Key để liên kết. |
| `driver_code` | `driver_code` | `VARCHAR(50)` | Type 1 | Ghi đè nếu đổi. |
| `display_name` | `display_name` | `VARCHAR(100)`| Type 1 | Ghi đè nếu đổi. |
| `home_borough` | `home_borough` | `VARCHAR(100)`| **Type 2**| Nếu đổi, đóng dòng cũ (`end_date = effective_at`, `is_current = false`) và thêm dòng mới với `start_date = effective_at`, `is_current = true`. |
| `employment_status` | `employment_status` | `VARCHAR(50)`| **Type 2**| Tương tự như `home_borough`. |
| `license_status` | `license_status` | `VARCHAR(50)` | Type 1 | Ghi đè. |
| `license_expiry_date`| `license_expiry_date`| `DATE` | Type 1 | Ghi đè. |
| `experience_years` | `experience_years` | `INT` | Type 1 | Ghi đè. |
| *Tự sinh* | `driver_key` | `INT (PK)` | | DDS Surrogate Key tự tăng (`SERIAL`). |
| *Tự sinh* | `start_date` | `TIMESTAMP` | | Thời điểm dòng phiên bản này bắt đầu có hiệu lực. |
| *Tự sinh* | `end_date` | `TIMESTAMP` | | Thời điểm dòng hết hiệu lực (để `NULL` nếu là dòng hiện hành). |
| *Tự sinh* | `is_current` | `BOOLEAN` | | `true` nếu là dòng phiên bản hiện hành, ngược lại `false`. |

---

## 3. Chi tiết Ánh xạ cho Thực thể Phương tiện (Vehicle)

* **Physical Source**: MongoDB collection `vehicles` (Trích xuất dạng document snapshot).
* **Tài liệu hóa luồng di chuyển**:
  - `Staging.vehicles` $\rightarrow$ `NDS.nds_vehicle` $\rightarrow$ `DDS.dim_vehicle`

### 3.1 Ánh xạ Staging $\rightarrow$ NDS

| Staging Source Field | NDS Target Column | Kiểu Dữ Liệu NDS | Quy tắc Chuyển đổi (Transformation Logic) |
|---|---|---|---|
| `vehicle_id` | `vehicle_nk` | `VARCHAR(50)` | Natural Key của xe. |
| `vendor_id` | `vendor_sk` | `INT` | Lookup `nds_vendor` bằng `vendor_id` thô để lấy `vendor_sk`. |
| `plate_token` | `plate_token` | `VARCHAR(100)`| Trim. Mã hóa bảo mật biển số xe. |
| `model_year` | `model_year` | `INT` | Cast sang INT. |
| `vehicle_type` | `vehicle_type` | `VARCHAR(50)` | SEDAN/HYBRID/WAV. |
| `service_start_date` | `service_start_date`| `DATE` | Cast sang DATE. |
| `vehicle_status` | `vehicle_status` | `VARCHAR(50)` | Trim. ACTIVE/MAINTENANCE/RETIRED. |
| `last_inspection_date`| `last_inspection_date`| `DATE` | Cast sang DATE (phải `>= service_start_date`). |
| *Tự sinh* | `vehicle_sk` | `INT (PK)` | Khóa chính tự sinh (`SERIAL`). |
| *Tự sinh* | `is_inferred` | `BOOLEAN` | Mặc định `false`. Set `true` nếu là dòng skeleton do late-arriving. |
| `source_system` | `source_system_code`| `INT` | Gán mã nguồn định danh (4 = MongoDB Fleet). |

### 3.2 Ánh xạ NDS $\rightarrow$ DDS (SCD Type 2)

Bảng chiều `dim_vehicle` áp dụng **SCD Type 2** cho thuộc tính trạng thái hoạt động (`vehicle_status`) để phục vụ phân tích thời gian xe dừng bảo dưỡng.

| NDS Source Column | DDS Target Column | Kiểu Dữ Liệu DDS | SCD Type | Quy tắc nạp (Loading Rule) |
|---|---|---|---|---|
| `vehicle_nk` | `vehicle_id` | `VARCHAR(50)` | Type 0 | Natural Key để liên kết. |
| `plate_token` | `plate_token` | `VARCHAR(100)`| Type 1 | Ghi đè. |
| `model_year` | `model_year` | `INT` | Type 1 | Ghi đè. |
| `vehicle_type` | `vehicle_type` | `VARCHAR(50)` | Type 1 | Ghi đè. |
| `vehicle_status` | `vehicle_status` | `VARCHAR(50)` | **Type 2**| Nếu trạng thái đổi, đóng dòng cũ bằng cách set `end_date = effective_at`, `is_current = false`. Insert dòng mới với thuộc tính mới, `start_date = effective_at`, `is_current = true`. |
| `last_inspection_date`| `last_inspection_date`| `DATE` | Type 1 | Ghi đè. |
| *Tự sinh* | `vehicle_key` | `INT (PK)` | | DDS Surrogate Key tự tăng (`SERIAL`). |
| *Tự sinh* | `start_date` | `TIMESTAMP` | | Ngày có hiệu lực của dòng. |
| *Tự sinh* | `end_date` | `TIMESTAMP` | | Ngày hết hiệu lực của dòng. |
| *Tự sinh* | `is_current` | `BOOLEAN` | | Cờ dòng hiện hành. |

---

## 4. Chi tiết Ánh xạ cho Chiều Địa bàn (Taxi Zone / Location)

* **Physical Source**: CSV lookup file `taxi_zone.csv`.
* **Tài liệu hóa luồng di chuyển**:
  - `Staging.taxi_zone` $\rightarrow$ `NDS.nds_location` $\rightarrow$ `DDS.dim_location` (SCD Type 0)

| Staging Source Field | NDS Target Column | DDS Target Column | Kiểu Dữ Liệu DDS | Quy tắc chuyển đổi & SCD |
|---|---|---|---|---|
| `location_id` | `location_nk` | `location_id` | `INT` | Natural Key (Zone ID từ 1 - 265). |
| `borough` | `borough` | `borough` | `VARCHAR(50)` | Trim. Tên quận (SCD Type 0). |
| `zone` | `zone` | `zone` | `VARCHAR(100)`| Trim. Tên khu vực (SCD Type 0). |
| `service_zone` | `service_zone` | `service_zone` | `VARCHAR(50)` | Trim. Loại khu vực (SCD Type 0). |
| *Tự sinh* | `location_sk` | `location_key` | `INT (PK)` | DDS Surrogate Key tự tăng. |

> [!NOTE]
> `DimLocation` được thiết kế theo **SCD Type 0** (retroactive/tĩnh) cho trường hợp case study này vì địa giới hành chính các quận của NYC không đổi trong kỳ dữ liệu 2020-2021.

---

## 4.1 Chi tiết Ánh xạ cho Chiều Ngày và Giờ (Date / Time)

`dim_date` và `dim_time` là các chiều tĩnh, được sinh trước khi nạp fact để chuẩn hóa các truy vấn theo ngày, giờ và khung thời gian.

### `DDS.dim_date` (SCD Type 0)

| Source | DDS Target Column | Kiểu Dữ Liệu DDS | Quy tắc sinh dữ liệu |
|---|---|---|---|
| Calendar generator | `date_key` | `INT (PK)` | `YYYYMMDD`, ví dụ `20200131`. |
| Calendar generator | `date` | `DATE` | Ngày dương lịch trong khoảng phủ dữ liệu. |
| Calendar generator | `day` | `INT` | Ngày trong tháng. |
| Calendar generator | `month` | `INT` | Tháng từ 1 đến 12. |
| Calendar generator | `month_name` | `VARCHAR(20)` | Tên tháng dùng cho báo cáo. |
| Calendar generator | `quarter` | `INT` | Quý từ 1 đến 4. |
| Calendar generator | `year` | `INT` | Năm dương lịch. |
| Calendar generator | `day_of_week` | `INT` | Thứ trong tuần theo chuẩn báo cáo. |
| Calendar generator | `day_name` | `VARCHAR(20)` | Tên thứ. |
| Calendar generator | `is_weekend` | `BOOLEAN` | `true` nếu là Thứ 7 hoặc Chủ nhật. |
| Calendar generator | `is_holiday` | `BOOLEAN` | Mặc định `false`, chỉ set `true` nếu có holiday lookup được phê duyệt. |
| Calendar generator | `week_of_year` | `INT` | Tuần trong năm. |

### `DDS.dim_time` (SCD Type 0)

| Source | DDS Target Column | Kiểu Dữ Liệu DDS | Quy tắc sinh dữ liệu |
|---|---|---|---|
| Time generator | `time_key` | `INT (PK)` | `HHMM`, gồm 1,440 dòng từ `0000` đến `2359`. |
| Time generator | `time_of_day` | `TIME` | Thời điểm trong ngày ở độ mịn phút. |
| Time generator | `hour` | `INT` | Giờ từ 0 đến 23. |
| Time generator | `minute` | `INT` | Phút từ 0 đến 59. |
| Time generator | `time_bucket` | `VARCHAR(20)` | Nhóm thời gian báo cáo: `Morning`, `Afternoon`, `Evening`, `Night`. |
| Time generator | `is_peak_hour` | `BOOLEAN` | `true` nếu thuộc khung giờ cao điểm được định nghĩa cho báo cáo vận hành. |

---

## 5. Chi tiết Ánh xạ cho Thực thể Ca làm việc (Shift)

* **Physical Source**: PostgreSQL source table `shifts` (Dispatch System).
* **Tài liệu hóa luồng di chuyển**:
  - `Staging.shifts` $\rightarrow$ `NDS.nds_shift` $\rightarrow$ `DDS.dim_shift` + `DDS.fact_driver_shift`

### 5.1 Ánh xạ Staging $\rightarrow$ NDS

| Staging Source Field | NDS Target Column | Kiểu Dữ Liệu NDS | Quy tắc Chuyển đổi (Transformation Logic) |
|---|---|---|---|
| `shift_id` | `shift_nk` | `VARCHAR(50)` | Natural Key (`SHF##########`). |
| `driver_id` | `driver_sk` | `INT` | Lookup `nds_driver` để lấy `driver_sk` tương ứng. Nếu không thấy, tự động tạo dòng Inferred Driver trước rồi lấy key. |
| `vehicle_id` | `vehicle_sk` | `INT` | Lookup `nds_vehicle` để lấy `vehicle_sk` tương ứng. Nếu không thấy, tự động tạo dòng Inferred Vehicle trước. |
| `vendor_id` | `vendor_sk` | `INT` | Lookup `nds_vendor` để lấy `vendor_sk`. |
| `shift_start` | `shift_start` | `TIMESTAMP` | Thời điểm bắt đầu ca (giờ New York). |
| `shift_end` | `shift_end` | `TIMESTAMP` | Thời điểm kết thúc ca (giờ New York, phải `>= shift_start`). |
| `assigned_start_zone`| `assigned_start_zone`| `INT` | Lookup `nds_location` bằng ID thô để lấy `location_sk`. |
| `actual_end_zone` | `actual_end_zone` | `INT` | Lookup `nds_location` bằng ID thô để lấy `location_sk`. |
| `trip_count` | `trip_count_source` | `INT` | Đọc số lượng chuyến gốc của ca để đối soát. |
| `occupied_minutes` | `occupied_minutes_source`| `DECIMAL(12,2)` | Số phút có khách gốc để đối soát. |
| `idle_minutes` | `idle_minutes_source` | `DECIMAL(12,2)` | Số phút nhàn rỗi gốc để đối soát. |
| `shift_status` | `shift_status` | `VARCHAR(50)` | Trạng thái ca (mặc định `COMPLETED`). |
| *Tự sinh* | `shift_sk` | `BIGINT (PK)` | Khóa chính tự sinh. |

### 5.2 Ánh xạ NDS $\rightarrow$ DDS

Chiều `dim_shift` và bảng sự kiện `fact_driver_shift` được nạp song song để phục vụ phân tích.

#### Chiều `DDS.dim_shift` (SCD Type 1)
| NDS Source Column | DDS Target Column | Kiểu Dữ Liệu DDS | Quy tắc chuyển đổi |
|---|---|---|---|
| `shift_nk` | `shift_id` | `VARCHAR(50)` | Natural Key liên kết. |
| `shift_status` | `shift_status` | `VARCHAR(50)` | Trạng thái ca làm việc. |
| `shift_start` | `shift_start` | `TIMESTAMP` | Lưu thời điểm bắt đầu. |
| `shift_end` | `shift_end` | `TIMESTAMP` | Lưu thời điểm kết thúc. |
| *Tự sinh* | `duration_hours` | `DECIMAL(10,2)`| `(shift_end - shift_start)` quy ra giờ. |
| *DQ Gate 2* | `is_anomaly` | `BOOLEAN` | `true` nếu ca bị flag bởi luật overlap tài xế hoặc phương tiện. |
| *Tự sinh* | `shift_key` | `INT (PK)` | DDS Surrogate Key tự tăng. |

#### Bảng sự kiện `DDS.fact_driver_shift` (Grain: 1 row = 1 completed shift)
| NDS / DDS Source Column | DDS Target Column | Kiểu Dữ Liệu DDS | Quy tắc tính toán & Ghi nhận (Loading Rules) |
|---|---|---|---|
| `dim_shift.shift_key` | `shift_key` | `INT (FK)` | Surrogate key ca làm việc. |
| `nds_shift.shift_start`| `shift_start_date_key`| `INT (FK)` | Lấy ngày từ `shift_start`, convert sang `YYYYMMDD` để lookup `dim_date.date_key`. |
| `nds_shift.shift_start`| `shift_start_time_key`| `INT (FK)` | Lấy giờ:phút từ `shift_start`, convert sang `HHMM` để lookup `dim_time.time_key`. |
| `dim_driver.driver_key`| `driver_key` | `INT (FK)` | Lookup `driver_key` hiện hành từ `dim_driver` tại thời điểm `shift_start`. |
| `dim_vehicle.vehicle_key`| `vehicle_key`| `INT (FK)` | Lookup `vehicle_key` hiện hành từ `dim_vehicle` tại thời điểm `shift_start`. |
| `dim_vendor.vendor_key`| `vendor_key` | `INT (FK)` | Lookup `vendor_key` từ `dim_vendor`. |
| *Tính toán* | `shift_duration_minutes`| `DECIMAL(12,2)` | Tính duration ca làm việc: `(shift_end - shift_start)` tính bằng phút. |
| *Tính toán (NDS)* | `trip_count` | `INT` | Thực hiện câu lệnh SQL `COUNT(*)` các chuyến đi (`nds_trip`) thực tế thuộc về ca này (join qua bảng link `nds_trip_assignment` bằng `shift_sk`). |
| *Tính toán (NDS)* | `occupied_minutes` | `DECIMAL(12,2)` | `SUM(trip_duration_minutes)` của các chuyến đi thực tế thuộc ca này. |
| *Tính toán* | `idle_minutes` | `DECIMAL(12,2)` | `shift_duration_minutes - occupied_minutes`. |
| *Tính toán* | `utilization_rate` | `DECIMAL(5,4)` | `occupied_minutes / shift_duration_minutes` (check division by zero). |
| *Tính toán (NDS)* | `total_revenue` | `DECIMAL(12,2)` | `SUM(total_amount)` của tất cả chuyến đi thực tế thuộc ca. |
| *Tính toán (NDS)* | `total_tips` | `DECIMAL(12,2)` | `SUM(tip_amount)` của tất cả chuyến đi thực tế thuộc ca. |

---

## 6. Chi tiết Ánh xạ cho Thực thể Chuyến đi (Trip & Assignment)

* **Physical Sources**:
  - TLC monthly files (`staging.trip_data`)
  - PostgreSQL source `trip_assignments` (`staging.trip_assignments`)
* **Tài liệu hóa luồng di chuyển**:
  - `Staging` $\rightarrow$ `NDS.nds_trip` + `NDS.nds_trip_assignment` $\rightarrow$ `DDS.fact_driver_trip`

### 6.1 Ánh xạ Staging $\rightarrow$ NDS

Khi nạp vào NDS, dữ liệu từ TLC trip và Dispatch assignment được liên kết bằng natural key `trip_key`.

#### Bảng `NDS.nds_trip` (TLC Trip records)
| Staging Source Field | NDS Target Column | Kiểu Dữ Liệu NDS | Quy tắc chuyển đổi & DQ |
|---|---|---|---|
| `trip_key` | `trip_nk` | `VARCHAR(50)` | Truncated SHA-256 business key làm Natural Key (UQ). |
| `vendor_id` | `vendor_sk` | `INT` | Lookup `nds_vendor` lấy `vendor_sk`. |
| `lpep_pickup_datetime` | `pickup_datetime` | `TIMESTAMP` | Thời điểm đón khách (giờ New York). |
| `lpep_dropoff_datetime`| `dropoff_datetime`| `TIMESTAMP` | Thời điểm trả khách (giờ New York). |
| `passenger_count` | `passenger_count` | `INT` | Số khách. |
| `trip_distance` | `trip_distance` | `DECIMAL(9,4)` | Khoảng cách (mile). |
| `pu_location_id` | `pickup_location_sk`| `INT` | Lookup `nds_location` để lấy `location_sk`. |
| `do_location_id` | `dropoff_location_sk`| `INT` | Lookup `nds_location` để lấy `location_sk`. |
| `fare_amount` | `fare_amount` | `DECIMAL(9,2)` | Tiền cước. |
| `tip_amount` | `tip_amount` | `DECIMAL(9,2)` | Tiền tip. |
| `total_amount` | `total_amount` | `DECIMAL(9,2)` | Tổng tiền. |
| `source_file` | `source_file` | `VARCHAR(255)` | Phục vụ truy vết. |
| `source_row_number` | `source_row_number` | `INT` | Phục vụ truy vết. |
| *Tự sinh* | `trip_sk` | `BIGINT (PK)` | Khóa chính tự sinh (`BIGSERIAL`). |
| *DQ validation* | `is_anomaly` | `BOOLEAN` | Mặc định `false`. Set `true` nếu chuyến đi bị vi phạm luật nghiệp vụ (ví dụ: đón/trả ngoài ca). |

#### Bảng `NDS.nds_trip_assignment` (Dispatch Assignment)
| Staging Source Field | NDS Target Column | Kiểu Dữ Liệu NDS | Quy tắc chuyển đổi |
|---|---|---|---|
| `trip_key` | `trip_sk` | `BIGINT` | Lookup `nds_trip` bằng `trip_key` để lấy `trip_sk`. |
| `driver_id` | `driver_sk` | `INT` | Lookup `nds_driver` lấy `driver_sk` (Inferred logic áp dụng). |
| `vehicle_id` | `vehicle_sk` | `INT` | Lookup `nds_vehicle` lấy `vehicle_sk` (Inferred logic áp dụng). |
| `shift_id` | `shift_sk` | `BIGINT` | Lookup `nds_shift` lấy `shift_sk`. |
| `assignment_timestamp` | `assignment_timestamp` | `TIMESTAMP` | Giờ gán ca. |
| `assignment_method` | `assignment_method` | `VARCHAR(50)` | CONTINUITY/AVAILABLE_POOL. |

### 6.2 Ánh xạ NDS $\rightarrow$ DDS Bảng sự kiện `fact_driver_trip`

* **Độ mịn (Grain)**: Một dòng tương ứng với một chuyến đi (trip transaction).

| NDS / DDS Source Column | DDS Target Column | Kiểu Dữ Liệu DDS | Quy tắc chuyển đổi & Loading (Effective Lookup) |
|---|---|---|---|
| `nds_trip.trip_nk` | `trip_id` | `VARCHAR(50)` | Natural key của trip làm **Degenerate Dimension**. |
| `nds_trip.pickup_datetime`| `pickup_date_key`| `INT (FK)` | Lấy ngày từ `pickup_datetime`, convert sang `YYYYMMDD` để lookup `dim_date.date_key`. |
| `nds_trip.pickup_datetime`| `pickup_time_key`| `INT (FK)` | Lấy giờ:phút, convert sang `HHMM` để lookup `dim_time.time_key`. |
| `nds_trip.dropoff_datetime`| `dropoff_date_key`| `INT (FK)` | Tương tự pickup_date_key. |
| `nds_trip.dropoff_datetime`| `dropoff_time_key`| `INT (FK)` | Tương tự pickup_time_key. |
| `dim_driver.driver_key` | `driver_key` | `INT (FK)` | Lookup `driver_key` hiện hành từ `dim_driver` dựa trên `driver_sk` và điều kiện thời gian: `nds_trip.pickup_datetime BETWEEN start_date AND COALESCE(end_date, '9999-12-31')` (**SCD Type 2 Lookup**). |
| `dim_vehicle.vehicle_key` | `vehicle_key` | `INT (FK)` | Lookup `vehicle_key` từ `dim_vehicle` dựa trên `vehicle_sk` và điều kiện thời gian: `nds_trip.pickup_datetime BETWEEN start_date AND COALESCE(end_date, '9999-12-31')`. |
| `dim_vendor.vendor_key` | `vendor_key` | `INT (FK)` | Lookup `vendor_key` từ `dim_vendor`. |
| `nds_trip.pickup_location_sk`| `pickup_location_key`| `INT (FK)`| Lookup `location_key` từ `dim_location` bằng `location_sk` thô. |
| `nds_trip.dropoff_location_sk`| `dropoff_location_key`| `INT (FK)`| Tương tự pickup. |
| `nds_trip_assignment.shift_sk`| `shift_key` | `INT (FK)` | Lookup `shift_key` từ `dim_shift` bằng `shift_sk`. |
| *Tính toán* | `junk_trip_key` | `INT (FK)` | Lookup `junk_trip_key` từ `dim_junk_trip` bằng cách kết hợp các trường phân loại (`payment_type`, `ratecode`, `trip_type`, `assignment_method`, `is_anomaly`). |
| `nds_trip.passenger_count`| `passenger_count` | `INT` | Lưu trực tiếp measure. |
| `nds_trip.trip_distance` | `trip_distance` | `DECIMAL(10,2)`| Lưu trực tiếp measure. |
| *Tính toán* | `trip_duration_minutes`| `DECIMAL(10,2)`| `(dropoff_datetime - pickup_datetime)` quy ra phút. |
| `nds_trip.total_amount` | `total_amount` | `DECIMAL(10,2)`| Doanh thu (Measure cộng dồn). |
| *Tính toán* | `assignment_delay_minutes`| `DECIMAL(10,2)`| `(pickup_datetime - assignment_timestamp)` quy ra phút. Set `NULL` nếu là chuyến đi không được gán (unassigned). |
| `nds_trip.source_file` | `source_file` | `VARCHAR(255)` | Degenerate Dimension để kiểm toán. |
| `nds_trip.source_row_number`| `source_row_number`| `INT` | Degenerate Dimension để kiểm toán. |

---

## 7. Các Luật Đối Soát Dữ Liệu (Reconciliation Rules)

Để kiểm chứng tính chính xác của dữ liệu sau quá trình chạy batch, các báo cáo đối soát (reconciliation) phải được lập cấu trúc đẹp mắt dựa trên các công thức sau:

1. **Đối soát Dữ liệu nguồn**:
   $$\text{Extracted Source Rows} = \text{Staging Accepted Records} + \text{Staging Rejected (Quarantine) Records}$$
2. **Đối soát TLC Trips & Assignments**:
   $$\text{Total TLC Trips Accepted} = \text{Trip Assignments} + \text{Assignment Exceptions}$$
3. **Đối soát Doanh thu (DDS vs NDS)**:
   $$\sum(\text{fact\_driver\_trip.total\_amount}) = \sum(\text{nds\_trip.total\_amount (accepted)})$$
4. **Đối soát Số chuyến ca làm việc (Shift vs Trip)**:
   $$\sum(\text{fact\_driver\_shift.trip\_count}) = \text{Total records in } \text{fact\_driver\_trip } \text{linked to a valid shift\_key}$$
5. **Đối soát Inferred Members**:
   $$\text{Count of } \text{is\_inferred = true } \text{in NDS} = \text{Number of unique late-arriving driver/vehicle keys logged in DQ}$$
