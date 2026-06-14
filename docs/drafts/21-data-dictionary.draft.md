# Data Dictionary Draft
**NYC Green Taxi Driver Operations BI - Dimensional Data Store (DDS)**

Tài liệu này cung cấp chi tiết về cấu trúc các bảng chiều (dimensions) và bảng sự kiện (facts) trong tầng Dimensional Data Store (DDS). Đây là bản nháp phục vụ cho việc đối soát và hoàn thiện ở các workstream tiếp theo.

---

## Danh sách các bảng DDS

| Tên vật lý | Tên nghiệp vụ | Loại bảng | Hạt dữ liệu (Grain) |
|---|---|---|---|
| `dds.dim_date` | Chiều Ngày | Dimension | Mỗi dòng đại diện cho một ngày dương lịch duy nhất |
| `dds.dim_time` | Chiều Giờ | Dimension | Mỗi dòng đại diện cho một phút duy nhất trong ngày (1,440 dòng) |
| `dds.dim_driver` | Chiều Tài xế | Dimension | Mỗi dòng đại diện cho một phiên bản thông tin tài xế (SCD Type 2) |
| `dds.dim_vehicle` | Chiều Phương tiện | Dimension | Mỗi dòng đại diện cho một phiên bản thông tin xe (SCD Type 2) |
| `dds.dim_vendor` | Chiều Nhà cung cấp | Dimension | Mỗi dòng đại diện cho một đối tác vận hành/hãng xe |
| `dds.dim_location` | Chiều Địa bàn | Dimension | Mỗi dòng đại diện cho một khu vực/Taxi Zone duy nhất |
| `dds.dim_junk_trip` | Chiều Junk chuyến đi | Dimension | Tổ hợp các thuộc tính phân loại giao dịch của chuyến đi |
| `dds.fact_driver_trip` | Sự kiện Chuyến đi tài xế | Fact (Transactional) | Mỗi dòng đại diện cho một chuyến đi được ghi nhận |
| `dds.fact_driver_shift` | Sự kiện Ca làm việc tài xế | Fact (Periodic Summary) | Mỗi dòng đại diện cho một ca làm việc hoàn tất của tài xế |

---

## Chi tiết các bảng và cột

### 1. Chiều Ngày (dds.dim_date)

- **Business name**: Chiều Ngày
- **Physical name**: `dds.dim_date`
- **Grain**: Mỗi dòng đại diện cho một ngày dương lịch duy nhất.
- **Primary key**: `date_key`
- **Foreign keys**: Không có
- **Business key**: `date`
- **Source NDS**: Không có (được sinh tĩnh qua Calendar Generator / `LOOKUP_FILE`)
- **Analytics purpose**: Phân tích các xu hướng, đo lường hiệu suất vận hành và doanh thu theo các chiều thời gian khác nhau (ngày, tháng, quý, năm, cuối tuần, ngày lễ).

| Tên vật lý | Tên nghiệp vụ | Kiểu dữ liệu | Nullable | Loại khóa | Định nghĩa nghiệp vụ | Nguồn/Dòng dữ liệu | Quy tắc biến đổi | Giá trị cho phép | Hành vi SCD | Sử dụng trong Analytics | Ghi chú DQ | Phép gộp mặc định |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `date_key` | Khóa ngày | INT | No | PK | Khóa chính dạng số nguyên đại diện cho ngày | Tự sinh | Convert ngày dạng YYYYMMDD | Số nguyên | Type 0 | Liên kết với bảng fact | Không | None |
| `date` | Ngày dương lịch | DATE | No | Business Key | Ngày cụ thể | Tự sinh | Định dạng DATE chuẩn | Ngày hợp lệ | Type 0 | Trục thời gian báo cáo | Phải unique | None |
| `day` | Ngày trong tháng | INT | No | None | Thứ tự ngày trong tháng (1-31) | Tự sinh | EXTRACT(DAY FROM date) | 1 - 31 | Type 0 | Phân tích theo chu kỳ tháng | Ràng buộc CHECK 1-31 | None |
| `month` | Tháng | INT | No | None | Tháng trong năm (1-12) | Tự sinh | EXTRACT(MONTH FROM date) | 1 - 12 | Type 0 | Phân tích theo chu kỳ năm | Ràng buộc CHECK 1-12 | None |
| `month_name` | Tên tháng | VARCHAR(20) | No | None | Tên tiếng Anh đầy đủ của tháng | Tự sinh | TO_CHAR(date, 'Month') | January - December | Type 0 | Hiển thị trên nhãn báo cáo | Không | None |
| `quarter` | Quý | INT | No | None | Quý trong năm (1-4) | Tự sinh | EXTRACT(QUARTER FROM date) | 1 - 4 | Type 0 | Phân tích theo quý | Ràng buộc CHECK 1-4 | None |
| `year` | Năm | INT | No | None | Năm dương lịch | Tự sinh | EXTRACT(YEAR FROM date) | Số nguyên dương | Type 0 | Phân tích theo năm | Không | None |
| `day_of_week` | Thứ tự trong tuần | INT | No | None | Ngày trong tuần (1-7 đại diện cho Thứ 2 - Chủ nhật) | Tự sinh | EXTRACT(ISODOW FROM date) | 1 - 7 | Type 0 | Phân tích theo ngày thường/cuối tuần | Ràng buộc CHECK 1-7 | None |
| `day_name` | Tên thứ | VARCHAR(20) | No | None | Tên ngày trong tuần | Tự sinh | TO_CHAR(date, 'Day') | Monday - Sunday | Type 0 | Nhãn báo cáo | Không | None |
| `is_weekend` | Là cuối tuần | BOOLEAN | No | None | Cờ đánh dấu ngày thứ Bảy hoặc Chủ Nhật | Tự sinh | `day_of_week IN (6, 7)` | true, false | Type 0 | Lọc phân tích hiệu suất cuối tuần | Không | None |
| `is_holiday` | Là ngày lễ | BOOLEAN | No | None | Cờ đánh dấu ngày nghỉ lễ chính thức | Lookup file nghỉ lễ | So khớp danh sách nghỉ lễ | true, false | Type 0 | Phân tích biến động nhu cầu dịp lễ | Mặc định false | None |
| `week_of_year` | Tuần trong năm | INT | No | None | Số tuần theo tiêu chuẩn ISO (1-53) | Tự sinh | EXTRACT(WEEK FROM date) | 1 - 53 | Type 0 | Phân tích chu kỳ tuần | Ràng buộc CHECK 1-53 | None |

---

### 2. Chiều Giờ (dds.dim_time)

- **Business name**: Chiều Giờ
- **Physical name**: `dds.dim_time`
- **Grain**: Mỗi dòng đại diện cho một phút duy nhất trong ngày (1,440 dòng từ 00:00 đến 23:59).
- **Primary key**: `time_key`
- **Foreign keys**: Không có
- **Business key**: `time_of_day`
- **Source NDS**: Không có (được sinh tĩnh qua Time Generator)
- **Analytics purpose**: Phân tích mật độ chuyến đi, hiệu suất ca làm việc theo giờ trong ngày và các khung giờ cao điểm.

| Tên vật lý | Tên nghiệp vụ | Kiểu dữ liệu | Nullable | Loại khóa | Định nghĩa nghiệp vụ | Nguồn/Dòng dữ liệu | Quy tắc biến đổi | Giá trị cho phép | Hành vi SCD | Sử dụng trong Analytics | Ghi chú DQ | Phép gộp mặc định |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `time_key` | Khóa giờ | INT | No | PK | Khóa chính dạng số nguyên đại diện cho giờ:phút | Tự sinh | Convert time thành HHMM | 0 - 2359 | Type 0 | Liên kết với bảng fact | Ràng buộc CHECK 0-2359 | None |
| `time_of_day` | Thời điểm trong ngày | TIME | No | Business Key | Thời điểm cụ thể ở độ mịn phút | Tự sinh | Định dạng TIME | 00:00:00 - 23:59:00 | Type 0 | Nhãn báo cáo | Phải unique | None |
| `hour` | Giờ | INT | No | None | Giờ trong ngày (0-23) | Tự sinh | EXTRACT(HOUR FROM time_of_day) | 0 - 23 | Type 0 | Phân nhóm theo giờ | Ràng buộc CHECK 0-23 | None |
| `minute` | Phút | INT | No | None | Phút trong giờ (0-59) | Tự sinh | EXTRACT(MINUTE FROM time_of_day) | 0 - 59 | Type 0 | Phân tích chi tiết thời gian | Ràng buộc CHECK 0-59 | None |
| `time_bucket` | Khung giờ | VARCHAR(20) | No | None | Phân nhóm thời gian (Sáng, Chiều, Tối, Đêm) | Tự sinh | Phân nhóm dựa trên `hour` | Morning, Afternoon, Evening, Night | Type 0 | Phân tích năng lực theo khung giờ | Không | None |
| `is_peak_hour` | Khung giờ cao điểm | BOOLEAN | No | None | Cờ đánh dấu khung giờ cao điểm có lưu lượng lớn | Tự sinh | Logic phân định giờ cao điểm | true, false | Type 0 | Phân tích hiệu quả vận hành giờ cao điểm | Mặc định false | None |

---

### 3. Chiều Tài xế (dds.dim_driver)

- **Business name**: Chiều Tài xế
- **Physical name**: `dds.dim_driver`
- **Grain**: Mỗi dòng đại diện cho một phiên bản thông tin của tài xế. Áp dụng SCD Type 2 để theo dõi các thay đổi về quận cư trú (`home_borough`) và trạng thái làm việc (`employment_status`).
- **Primary key**: `driver_key`
- **Foreign keys**: `batch_id` liên kết với `audit.metadata_etl_batch`
- **Business key**: `driver_id` (Natural Key)
- **Source NDS**: `nds.nds_driver` & `nds.nds_driver_history`
- **Analytics purpose**: Phân tích hiệu suất của tài xế, doanh thu trung bình, tỷ lệ tận dụng xe và so sánh các nhóm tài xế theo thâm niên, quận cư trú.

| Tên vật lý | Tên nghiệp vụ | Kiểu dữ liệu | Nullable | Loại khóa | Định nghĩa nghiệp vụ | Nguồn/Dòng dữ liệu | Quy tắc biến đổi | Giá trị cho phép | Hành vi SCD | Sử dụng trong Analytics | Ghi chú DQ | Phép gộp mặc định |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `driver_key` | Khóa tài xế | INT | No | PK | Khóa chính surrogate key tự tăng của DDS | Tự sinh | IDENTITY | Số nguyên dương | Không áp dụng | Khóa liên kết chính | Không | None |
| `driver_id` | Mã tài xế (NK) | VARCHAR(50) | No | Business Key | Mã định danh duy nhất của tài xế | `nds.nds_driver.driver_nk` | Trim, uppercase | Định dạng DRVxxxxx | Type 0 | Định danh tài xế trên báo cáo | Không | None |
| `driver_code` | Mã nhân viên | VARCHAR(50) | No | None | Mã số nhân viên nội bộ | `nds.nds_driver.driver_code` | Trim | Chuỗi văn bản | Type 1 | Tra cứu, hiển thị | Không | None |
| `display_name` | Tên hiển thị | VARCHAR(100) | No | None | Tên đầy đủ của tài xế | `nds.nds_driver.display_name` | Trim | Chuỗi văn bản | Type 1 | Nhãn báo cáo tài xế | Không | None |
| `home_borough` | Quận cư trú | VARCHAR(100) | No | None | Quận nơi tài xế sinh sống | `nds.nds_driver.home_borough` | Trim | Tên các quận của NYC | **Type 2** | Phân nhóm tài xế theo khu vực | Thay đổi sẽ đóng version cũ, mở version mới | None |
| `employment_status` | Trạng thái công việc | VARCHAR(50) | No | None | Trạng thái làm việc của tài xế | `nds.nds_driver.employment_status` | Trim, uppercase | ACTIVE, INACTIVE, TBD_AFTER_RECONCILIATION | **Type 2** | Lọc và phân tích tài xế đang hoạt động | Thay đổi sẽ đóng version cũ, mở version mới | None |
| `license_status` | Trạng thái bằng lái | VARCHAR(50) | No | None | Trạng thái của giấy phép lái xe | `nds.nds_driver.license_status` | Trim, uppercase | ACTIVE, EXPIRED, ... | Type 1 | Theo dõi tính hợp lệ của tài xế | Không | None |
| `license_expiry_date` | Ngày hết hạn bằng lái | DATE | No | None | Ngày hết hạn giấy phép lái xe | `nds.nds_driver.license_expiry_date` | Cast sang DATE | Ngày hợp lệ | Type 1 | Lọc tài xế sắp hết hạn bằng lái | Không | None |
| `experience_years` | Số năm kinh nghiệm | INT | No | None | Số năm kinh nghiệm làm việc | `nds.nds_driver.experience_years` | Cast sang INT | `>= 0` | Type 1 | Phân lớp thâm niên tài xế | Ràng buộc CHECK >= 0 | None |
| `start_date` | Ngày bắt đầu hiệu lực | TIMESTAMP | No | None | Thời điểm phiên bản thông tin bắt đầu hiệu lực | Tự sinh | Timestamp sự kiện thay đổi hoặc ngày thuê | Timestamp | Không áp dụng | Xác định dòng phiên bản đúng thời điểm | Không | None |
| `end_date` | Ngày hết hiệu lực | TIMESTAMP | Yes | None | Thời điểm phiên bản thông tin hết hiệu lực | Tự sinh | Đóng khi có version mới | Timestamp hoặc NULL | Không áp dụng | Xác định dòng phiên bản đúng thời điểm | Để trống (NULL) với phiên bản hiện hành | None |
| `is_current` | Phiên bản hiện hành | BOOLEAN | No | None | Cờ đánh dấu phiên bản thông tin mới nhất | Tự sinh | Mặc định true, set false khi có version mới | true, false | Không áp dụng | Lọc lấy thông tin hiện tại của tài xế | Tối đa một dòng current cho mỗi driver_id | None |
| `source_event_id` | ID sự kiện nguồn | VARCHAR(50) | Yes | None | ID của change feed event gây ra sự thay đổi | `nds.nds_driver_history.event_id` | Giữ nguyên | ID sự kiện | Không áp dụng | Kiểm toán lineage | Không | None |
| `source_row_hash` | Hash dòng nguồn | CHAR(64) | No | None | Mã hash dùng để phát hiện thay đổi thuộc tính | Tự sinh | SHA-256 từ các thuộc tính SCD | Chuỗi 64 ký tự | Không áp dụng | Tránh chèn trùng và kiểm tra thay đổi | Không | None |
| `batch_id` | ID Batch nạp | UUID | No | FK | ID của batch ETL thực hiện nạp dòng này | `audit.metadata_etl_batch.batch_id` | Lấy từ ETL context | UUID hợp lệ | Không áp dụng | Đối soát, kiểm toán lineage | Không | None |

---

### 4. Chiều Phương tiện (dds.dim_vehicle)

- **Business name**: Chiều Phương tiện
- **Physical name**: `dds.dim_vehicle`
- **Grain**: Mỗi dòng đại diện cho một phiên bản thông tin của xe. Áp dụng SCD Type 2 để theo dõi trạng thái xe (`vehicle_status`).
- **Primary key**: `vehicle_key`
- **Foreign keys**: `batch_id` liên kết với `audit.metadata_etl_batch`
- **Business key**: `vehicle_id` (Natural Key)
- **Source NDS**: `nds.nds_vehicle`
- **Analytics purpose**: Phân tích hiệu quả sử dụng đội xe, thời gian dừng hoạt động để bảo dưỡng và phân loại xe (Sedan/Hybrid/Wav).

| Tên vật lý | Tên nghiệp vụ | Kiểu dữ liệu | Nullable | Loại khóa | Định nghĩa nghiệp vụ | Nguồn/Dòng dữ liệu | Quy tắc biến đổi | Giá trị cho phép | Hành vi SCD | Sử dụng trong Analytics | Ghi chú DQ | Phép gộp mặc định |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `vehicle_key` | Khóa phương tiện | INT | No | PK | Khóa chính surrogate key tự tăng của DDS | Tự sinh | IDENTITY | Số nguyên dương | Không áp dụng | Khóa liên kết chính | Không | None |
| `vehicle_id` | Mã phương tiện (NK) | VARCHAR(50) | No | Business Key | Mã định danh duy nhất của xe | `nds.nds_vehicle.vehicle_nk` | Trim, uppercase | Định dạng VEHxxxxx | Type 0 | Định danh xe trên báo cáo | Không | None |
| `plate_token` | Token biển số xe | VARCHAR(100) | No | None | Biển số xe được mã hóa bảo mật | `nds.nds_vehicle.plate_token` | Giữ nguyên | Chuỗi tokenized | Type 1 | Nhận diện xe bảo mật | Không | None |
| `model_year` | Năm sản xuất | INT | No | None | Năm sản xuất của phương tiện | `nds.nds_vehicle.model_year` | Cast sang INT | Năm hợp lệ | Type 1 | Phân tích tuổi đời xe | Không | None |
| `vehicle_type` | Loại xe | VARCHAR(50) | No | None | Phân loại phương tiện | `nds.nds_vehicle.vehicle_type` | Trim, uppercase | SEDAN, HYBRID, WAV | Type 1 | Phân nhóm theo loại xe | Không | None |
| `vehicle_status` | Trạng thái xe | VARCHAR(50) | No | None | Trạng thái hoạt động hoặc bảo dưỡng | `nds.nds_vehicle.vehicle_status` | Trim, uppercase | ACTIVE, MAINTENANCE, RETIRED | **Type 2** | Thống kê số lượng xe sẵn sàng phục vụ | Thay đổi đóng version cũ, mở version mới | None |
| `last_inspection_date` | Ngày kiểm định gần nhất | DATE | No | None | Ngày thực hiện đăng kiểm gần đây nhất | `nds.nds_vehicle.last_inspection_date` | Cast sang DATE | Ngày hợp lệ | Type 1 | Lên lịch bảo dưỡng xe | Phải `>= service_start_date` trong NDS | None |
| `start_date` | Ngày bắt đầu hiệu lực | TIMESTAMP | No | None | Thời điểm phiên bản xe bắt đầu có hiệu lực | Tự sinh | Timestamp sự kiện thay đổi hoặc ngày nạp | Timestamp | Không áp dụng | Xác định dòng phiên bản đúng thời điểm | Không | None |
| `end_date` | Ngày hết hiệu lực | TIMESTAMP | Yes | None | Thời điểm phiên bản xe hết hiệu lực | Tự sinh | Đóng khi có version mới | Timestamp hoặc NULL | Không áp dụng | Xác định dòng phiên bản đúng thời điểm | Để trống (NULL) với phiên bản hiện hành | None |
| `is_current` | Phiên bản hiện hành | BOOLEAN | No | None | Cờ đánh dấu phiên bản thông tin mới nhất | Tự sinh | Mặc định true, set false khi có version mới | true, false | Không áp dụng | Lọc lấy thông tin hiện tại của xe | Tối đa một dòng current cho mỗi vehicle_id | None |
| `source_row_hash` | Hash dòng nguồn | CHAR(64) | No | None | Mã hash dùng để phát hiện thay đổi thuộc tính | Tự sinh | SHA-256 từ các thuộc tính SCD | Chuỗi 64 ký tự | Không áp dụng | Tránh chèn trùng và kiểm tra thay đổi | Không | None |
| `batch_id` | ID Batch nạp | UUID | No | FK | ID của batch ETL thực hiện nạp dòng này | `audit.metadata_etl_batch.batch_id` | Lấy từ ETL context | UUID hợp lệ | Không áp dụng | Đối soát, kiểm toán lineage | Không | None |

---

### 5. Chiều Nhà cung cấp (dds.dim_vendor)

- **Business name**: Chiều Nhà cung cấp
- **Physical name**: `dds.dim_vendor`
- **Grain**: Mỗi dòng đại diện cho một nhà cung cấp duy nhất.
- **Primary key**: `vendor_key`
- **Foreign keys**: `batch_id` liên kết với `audit.metadata_etl_batch`
- **Business key**: `vendor_id` (Natural Key)
- **Source NDS**: `nds.nds_vendor`
- **Analytics purpose**: Phân tích hiệu quả hoạt động và doanh thu theo nhà cung cấp (CMT, VeriFone, Legacy Pool).

| Tên vật lý | Tên nghiệp vụ | Kiểu dữ liệu | Nullable | Loại khóa | Định nghĩa nghiệp vụ | Nguồn/Dòng dữ liệu | Quy tắc biến đổi | Giá trị cho phép | Hành vi SCD | Sử dụng trong Analytics | Ghi chú DQ | Phép gộp mặc định |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `vendor_key` | Khóa nhà cung cấp | INT | No | PK | Khóa chính surrogate key tự tăng của DDS | Tự sinh | IDENTITY | Số nguyên dương | Không áp dụng | Khóa liên kết chính | Không | None |
| `vendor_id` | Mã nhà cung cấp (NK) | INT | No | Business Key | Mã định danh gốc của nhà cung cấp | `nds.nds_vendor.vendor_nk` | Giữ nguyên | 1 (CMT), 2 (VeriFone), ... | Type 1 | Phân loại báo cáo đối tác | Phải unique trong dim | None |
| `vendor_name` | Tên nhà cung cấp | VARCHAR(100) | No | None | Tên đầy đủ của nhà cung cấp | `nds.nds_vendor.vendor_name` | Trim | Creative Mobile Technologies, VeriFone Inc, ... | Type 1 | Nhãn báo cáo | Không | None |
| `batch_id` | ID Batch nạp | UUID | No | FK | ID của batch ETL thực hiện nạp dòng này | `audit.metadata_etl_batch.batch_id` | Lấy từ ETL context | UUID hợp lệ | Không áp dụng | Đối soát, lineage | Không | None |

---

### 6. Chiều Địa bàn (dds.dim_location)

- **Business name**: Chiều Địa bàn
- **Physical name**: `dds.dim_location`
- **Grain**: Mỗi dòng đại diện cho một khu vực đón/trả khách (Taxi Zone) duy nhất.
- **Primary key**: `location_key`
- **Foreign keys**: Không có
- **Business key**: `location_id` (Natural Key)
- **Source NDS**: `nds.nds_location`
- **Analytics purpose**: Phân tích biểu đồ nhiệt đón/trả khách, luồng di chuyển giữa các quận (Borough) và khu vực dịch vụ (Service Zone).

| Tên vật lý | Tên nghiệp vụ | Kiểu dữ liệu | Nullable | Loại khóa | Định nghĩa nghiệp vụ | Nguồn/Dòng dữ liệu | Quy tắc biến đổi | Giá trị cho phép | Hành vi SCD | Sử dụng trong Analytics | Ghi chú DQ | Phép gộp mặc định |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `location_key` | Khóa địa bàn | INT | No | PK | Khóa chính surrogate key tự tăng của DDS | Tự sinh | IDENTITY | Số nguyên dương | Không áp dụng | Khóa liên kết chính | Không | None |
| `location_id` | Mã địa bàn (NK) | INT | No | Business Key | Mã vùng đón trả khách (Taxi Zone ID) | `nds.nds_location.location_nk` | Giữ nguyên | 1 - 265 | Type 0 | Nhãn hiển thị, lọc vùng | Ràng buộc CHECK 1-265 | None |
| `borough` | Quận | VARCHAR(100) | No | None | Tên quận hành chính lớn | `nds.nds_location.borough` | Trim | Manhattan, Brooklyn, Queens, Bronx, Staten Island, EWR, Unknown | Type 0 | Phân tích địa bàn cấp cao | Không | None |
| `zone` | Khu vực | VARCHAR(100) | No | None | Tên khu vực cụ thể (Taxi Zone) | `nds.nds_location.zone` | Trim | Tên các zone cụ thể | Type 0 | Phân tích luồng đi chi tiết | Không | None |
| `service_zone` | Khu vực dịch vụ | VARCHAR(50) | Yes | None | Phân loại vùng dịch vụ (BoroZone, Yellow Zone, AirPorts...) | `nds.nds_location.service_zone` | Trim | BoroZone, Yellow Zone, Airports, N/A | Type 0 | Phân tích luồng theo vùng dịch vụ | Không | None |

---

### 7. Chiều Junk chuyến đi (dds.dim_junk_trip)

- **Business name**: Chiều Junk chuyến đi
- **Physical name**: `dds.dim_junk_trip`
- **Grain**: Các tổ hợp thuộc tính phân loại giao dịch của chuyến đi bao gồm hình thức thanh toán, loại cước, loại chuyến đi, phương thức gán ca và cờ anomaly.
- **Primary key**: `junk_trip_key`
- **Foreign keys**: Không có
- **Business key**: Tổ hợp `(payment_type_desc, ratecode_desc, trip_type_desc, assignment_method, is_anomaly)`
- **Source NDS**: Không có trực tiếp (được sinh từ việc tổ hợp các mã phân loại trong `nds.nds_trip` và `nds.nds_trip_assignment` trong quá trình ETL)
- **Analytics purpose**: Giảm bớt số lượng khóa ngoại trực tiếp trong Fact bằng cách gom các thuộc tính chiều dạng phân loại nhỏ vào một Junk Dimension, phục vụ lọc và phân tích đa chiều.

| Tên vật lý | Tên nghiệp vụ | Kiểu dữ liệu | Nullable | Loại khóa | Định nghĩa nghiệp vụ | Nguồn/Dòng dữ liệu | Quy tắc biến đổi | Giá trị cho phép | Hành vi SCD | Sử dụng trong Analytics | Ghi chú DQ | Phép gộp mặc định |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `junk_trip_key` | Khóa junk chuyến đi | INT | No | PK | Khóa chính surrogate key tự tăng của DDS | Tự sinh | IDENTITY | Số nguyên dương | Không áp dụng | Khóa liên kết chính | Không | None |
| `payment_type_desc` | Hình thức thanh toán | VARCHAR(50) | No | Business Key | Mô tả hình thức thanh toán | `nds.nds_trip.payment_type` | Giải mã từ mã số sang mô tả | Credit card, Cash, No charge, Dispute, Unknown, Voided trip | Type 1 | Phân tích hành vi thanh toán | Không | None |
| `ratecode_desc` | Loại cước áp dụng | VARCHAR(100) | No | Business Key | Mô tả biểu cước chuyến đi | `nds.nds_trip.ratecode_id` | Giải mã từ mã số sang mô tả | Standard rate, JFK, Newark, Nassau/Westchester, Negotiated, Group ride | Type 1 | Phân tích cơ cấu biểu giá | Không | None |
| `trip_type_desc` | Phân loại chuyến đi | VARCHAR(50) | No | Business Key | Mô tả loại chuyến đi (Vẫy khách hoặc Gán ca) | `nds.nds_trip.trip_type` | Giải mã từ mã số sang mô tả | Street-hail, Dispatch | Type 1 | So sánh doanh thu vẫy khách và gán ca | Không | None |
| `assignment_method` | Phương thức gán ca | VARCHAR(50) | No | Business Key | Phương thức gán chuyến cho tài xế | `nds.nds_trip_assignment.assignment_method` | Trim | CONTINUITY, AVAILABLE_POOL, UNASSIGNED | Type 1 | Phân tích hiệu quả thuật toán gán ca | Mặc định UNASSIGNED nếu không có assignment | None |
| `is_anomaly` | Cờ bất thường chuyến đi | BOOLEAN | No | Business Key | Đánh dấu chuyến đi vi phạm luật nghiệp vụ | `nds.nds_trip.is_anomaly` | Xác định từ DQ rules | true, false | Type 1 | Lọc các giao dịch lỗi/bất thường | Mặc định false | None |

---

### 8. Sự kiện Chuyến đi tài xế (dds.fact_driver_trip)

- **Business name**: Sự kiện Chuyến đi tài xế
- **Physical name**: `dds.fact_driver_trip`
- **Grain**: Mỗi dòng đại diện cho một chuyến đi được thực hiện (Grain: 1 row = 1 trip transaction).
- **Primary key**: `fact_trip_id`
- **Foreign keys**: 
  - `pickup_date_key` -> `dim_date.date_key`
  - `pickup_time_key` -> `dim_time.time_key`
  - `dropoff_date_key` -> `dim_date.date_key`
  - `dropoff_time_key` -> `dim_time.time_key`
  - `driver_key` -> `dim_driver.driver_key`
  - `vehicle_key` -> `dim_vehicle.vehicle_key`
  - `vendor_key` -> `dim_vendor.vendor_key`
  - `pickup_location_key` -> `dim_location.location_key`
  - `dropoff_location_key` -> `dim_location.location_key`
  - `junk_trip_key` -> `dim_junk_trip.junk_trip_key`
  - `batch_id` -> `audit.metadata_etl_batch.batch_id`
- **Business key / Degenerate Dimension**: `trip_id` (giữ nguyên full business key dạng `TEXT` từ staging).
- **Source NDS**: `nds.nds_trip` kết hợp qua `nds.nds_trip_assignment` để kết nối với driver, vehicle, shift.
- **Analytics purpose**: Bảng sự kiện lõi chứa toàn bộ số liệu về cước phí, khoảng cách, thời gian của từng chuyến xe để tính toán doanh thu, số chuyến đi và các chỉ số hiệu suất của tài xế.

| Tên vật lý | Tên nghiệp vụ | Kiểu dữ liệu | Nullable | Loại khóa | Định nghĩa nghiệp vụ | Nguồn/Dòng dữ liệu | Quy tắc biến đổi | Giá trị cho phép | Hành vi SCD | Sử dụng trong Analytics | Ghi chú DQ | Phép gộp mặc định |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `fact_trip_id` | ID Sự kiện chuyến đi | BIGINT | No | PK | Khóa chính tự sinh của bảng fact | Tự sinh | IDENTITY | Số nguyên dương | Không áp dụng | Định danh dòng sự kiện | Không | None |
| `trip_id` | Mã chuyến đi (Degenerate) | TEXT | No | Business Key | Khóa nghiệp vụ duy nhất của chuyến đi | `nds.nds_trip.trip_nk` | Giữ nguyên TEXT gốc | Khóa văn bản | Không áp dụng | Đếm số lượng chuyến đi, đối soát giao dịch | Phải unique trong fact | None |
| `shift_id` | Mã ca làm việc (Degenerate) | VARCHAR(50) | No | Business Key | Khóa nghiệp vụ ca làm việc của chuyến đi | `nds.nds_shift.shift_nk` | Lookup qua `nds_trip_assignment` | Mã ca (SHFxxxxx) | Không áp dụng | Phân tích chuyến đi theo ca | Có thể có chuyến đi không gán ca | None |
| `pickup_date_key` | Khóa ngày đón khách | INT | No | FK | Khóa liên kết với ngày đón khách | `nds.nds_trip.pickup_datetime` | Convert ngày đón YYYYMMDD | Khóa ngày hợp lệ | Không áp dụng | Trục thời gian đón khách | Không | None |
| `pickup_time_key` | Khóa giờ đón khách | INT | No | FK | Khóa liên kết với giờ đón khách | `nds.nds_trip.pickup_datetime` | Convert giờ đón HHMM | Khóa giờ hợp lệ | Không áp dụng | Khung giờ đón khách | Ràng buộc CHECK 0-2359 | None |
| `dropoff_date_key` | Khóa ngày trả khách | INT | No | FK | Khóa liên kết với ngày trả khách | `nds.nds_trip.dropoff_datetime` | Convert ngày trả YYYYMMDD | Khóa ngày hợp lệ | Không áp dụng | Trục thời gian trả khách | Không | None |
| `dropoff_time_key` | Khóa giờ trả khách | INT | No | FK | Khóa liên kết với giờ trả khách | `nds.nds_trip.dropoff_datetime` | Convert giờ trả HHMM | Khóa giờ hợp lệ | Không áp dụng | Khung giờ trả khách | Ràng buộc CHECK 0-2359 | None |
| `driver_key` | Khóa tài xế | INT | No | FK | Khóa liên kết tài xế thực hiện chuyến đi | `nds.nds_trip_assignment.driver_sk` | SCD Type 2 Lookup tại thời điểm `pickup_datetime` | Khóa tài xế hợp lệ | Không áp dụng | Liên kết tài xế | Late-arriving tạo Inferred | None |
| `vehicle_key` | Khóa phương tiện | INT | No | FK | Khóa liên kết xe thực hiện chuyến đi | `nds.nds_trip_assignment.vehicle_sk` | SCD Type 2 Lookup tại thời điểm `pickup_datetime` | Khóa xe hợp lệ | Không áp dụng | Liên kết phương tiện | Late-arriving tạo Inferred | None |
| `vendor_key` | Khóa nhà cung cấp | INT | No | FK | Khóa liên kết nhà cung cấp | `nds.nds_trip.vendor_sk` | Lookup vendor_key tương ứng | Khóa vendor hợp lệ | Không áp dụng | Báo cáo theo đối tác | Không | None |
| `pickup_location_key` | Khóa địa bàn đón khách | INT | No | FK | Khóa liên kết với địa điểm đón khách | `nds.nds_trip.pickup_location_sk` | Lookup location_key | Khóa location hợp lệ | Không áp dụng | Phân tích khu vực xuất phát | Không | None |
| `dropoff_location_key` | Khóa địa bàn trả khách | INT | No | FK | Khóa liên kết với địa điểm trả khách | `nds.nds_trip.dropoff_location_sk` | Lookup location_key | Khóa location hợp lệ | Không áp dụng | Phân tích khu vực đến | Không | None |
| `junk_trip_key` | Khóa junk chuyến đi | INT | No | FK | Khóa liên kết với chiều junk chuyến đi | Tổ hợp các thuộc tính phân loại | Lookup junk_trip_key phù hợp | Khóa junk hợp lệ | Không áp dụng | Lọc nâng cao | Không | None |
| `passenger_count` | Số lượng hành khách | INT | Yes | None | Số lượng khách trên chuyến xe | `nds.nds_trip.passenger_count` | Giữ nguyên | Số nguyên dương | Không áp dụng | Phân tích mật độ khách | Có thể NULL | SUM |
| `trip_distance` | Khoảng cách di chuyển | DECIMAL(12,4) | Yes | None | Khoảng cách chuyến đi (mile) | `nds.nds_trip.trip_distance` | Giữ nguyên độ chính xác | Số thập phân dương | Không áp dụng | Phân tích cự ly chuyến đi, tính revenue_per_mile | Bảo toàn outlier nguồn | SUM |
| `trip_duration_minutes` | Thời lượng chuyến đi (phút) | DECIMAL(10,2) | Yes | None | Tổng thời gian thực hiện chuyến xe | `nds.nds_trip.pickup_datetime`, `nds.nds_trip.dropoff_datetime` | (dropoff_datetime - pickup_datetime) tính theo phút | Số thập phân dương | Không áp dụng | Tính tổng occupied_minutes và utilization_rate | Phục vụ đối soát ca | SUM |
| `fare_amount` | Tiền cước | DECIMAL(10,2) | No | None | Tiền cước tính theo biểu giá | `nds.nds_trip.fare_amount` | Cast sang DECIMAL(10,2) | Số thập phân | Không áp dụng | Thống kê cước phí | Không | SUM |
| `extra` | Phụ phí | DECIMAL(10,2) | No | None | Các khoản phụ phí khác | `nds.nds_trip.extra` | Cast sang DECIMAL(10,2) | Số thập phân | Không áp dụng | Phân tích doanh thu | Không | SUM |
| `mta_tax` | Thuế MTA | DECIMAL(10,2) | No | None | Thuế MTA áp dụng | `nds.nds_trip.mta_tax` | Cast sang DECIMAL(10,2) | Số thập phân | Không áp dụng | Nghĩa vụ thuế | Không | SUM |
| `tip_amount` | Tiền tip | DECIMAL(10,2) | No | None | Tiền tip tài xế nhận được | `nds.nds_trip.tip_amount` | Cast sang DECIMAL(10,2) | Số thập phân | Không áp dụng | Phân tích thu nhập thêm và mức độ hài lòng khách | Không | SUM |
| `tolls_amount` | Phí cầu đường | DECIMAL(10,2) | No | None | Các loại phí cầu đường phát sinh | `nds.nds_trip.tolls_amount` | Cast sang DECIMAL(10,2) | Số thập phân | Không áp dụng | Chi phí cầu đường | Không | SUM |
| `improvement_surcharge` | Phí cải thiện hạ tầng | DECIMAL(10,2) | No | None | Phí phụ thu cải thiện dịch vụ | `nds.nds_trip.improvement_surcharge` | Cast sang DECIMAL(10,2) | Số thập phân | Không áp dụng | Doanh thu phụ | Không | SUM |
| `total_amount` | Tổng tiền thanh toán | DECIMAL(10,2) | No | None | Tổng số tiền khách hàng thanh toán | `nds.nds_trip.total_amount` | Cast sang DECIMAL(10,2) | Số thập phân | Không áp dụng | Chỉ số doanh thu tổng | Không | SUM |
| `assignment_delay_minutes` | Thời gian trễ gán ca | DECIMAL(10,2) | Yes | None | Số phút chênh lệch giữa giờ đón khách và giờ gán ca | `nds.nds_trip.pickup_datetime`, `nds.nds_trip_assignment.assignment_timestamp` | (pickup_datetime - assignment_timestamp) tính theo phút | Số thập phân hoặc NULL | Không áp dụng | Đánh giá tốc độ phản hồi điều phối | NULL nếu là chuyến đi vẫy | SUM |
| `source_file` | File nguồn (Degenerate) | VARCHAR(255) | No | None | Tên file nguồn chứa bản ghi chuyến đi | `nds.nds_trip.source_file` | Giữ nguyên | Chuỗi tên file | Không áp dụng | Truy vết, đối soát dữ liệu | Không | None |
| `source_row_number` | Dòng nguồn (Degenerate) | INT | No | None | Thứ tự dòng trong file nguồn | `nds.nds_trip.source_row_number` | Giữ nguyên | Số nguyên >= 2 | Không áp dụng | Truy vết, đối soát dữ liệu | Không | None |
| `batch_id` | ID Batch nạp | UUID | No | FK | ID của batch ETL thực hiện nạp dòng này | `audit.metadata_etl_batch.batch_id` | Lấy từ ETL context | UUID hợp lệ | Không áp dụng | Phục vụ rollback và kiểm toán | Không | None |

---

### 9. Sự kiện Ca làm việc tài xế (dds.fact_driver_shift)

- **Business name**: Sự kiện Ca làm việc tài xế
- **Physical name**: `dds.fact_driver_shift`
- **Grain**: Mỗi dòng đại diện cho một ca làm việc hoàn tất (Grain: 1 row = 1 completed shift).
- **Primary key**: `fact_shift_id`
- **Foreign keys**:
  - `shift_start_date_key` -> `dim_date.date_key`
  - `shift_start_time_key` -> `dim_time.time_key`
  - `driver_key` -> `dim_driver.driver_key`
  - `vehicle_key` -> `dim_vehicle.vehicle_key`
  - `vendor_key` -> `dim_vendor.vendor_key`
  - `batch_id` -> `audit.metadata_etl_batch.batch_id`
- **Business key / Degenerate Dimension**: `shift_id` (Natural Key `shift_nk` từ NDS)
- **Source NDS**: `nds.nds_shift` kết hợp với thông tin tổng hợp chuyến đi thực tế thuộc ca từ `nds.nds_trip` và `nds.nds_trip_assignment`.
- **Analytics purpose**: Đo lường hiệu suất ca làm việc, thời lượng hoạt động hiệu quả (occupied time), thời lượng chờ (idle time), tỷ lệ tận dụng tài xế/xe (utilization rate) và doanh thu bình quân mỗi ca làm việc.

| Tên vật lý | Tên nghiệp vụ | Kiểu dữ liệu | Nullable | Loại khóa | Định nghĩa nghiệp vụ | Nguồn/Dòng dữ liệu | Quy tắc biến đổi | Giá trị cho phép | Hành vi SCD | Sử dụng trong Analytics | Ghi chú DQ | Phép gộp mặc định |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `fact_shift_id` | ID Sự kiện ca | BIGINT | No | PK | Khóa chính tự sinh của bảng fact ca | Tự sinh | IDENTITY | Số nguyên dương | Không áp dụng | Định danh ca | Không | None |
| `shift_id` | Mã ca làm việc (Degenerate) | VARCHAR(50) | No | Business Key | Khóa nghiệp vụ duy nhất của ca làm việc | `nds.nds_shift.shift_nk` | Giữ nguyên làm Degenerate Dimension | SHFxxxxx | Không áp dụng | Đối soát, phân tích ca | Phải unique trong fact | None |
| `shift_start_date_key` | Khóa ngày bắt đầu ca | INT | No | FK | Khóa ngày bắt đầu ca làm việc | `nds.nds_shift.shift_start` | Convert YYYYMMDD | Khóa ngày hợp lệ | Không áp dụng | Trục thời gian ca | Không | None |
| `shift_start_time_key` | Khóa giờ bắt đầu ca | INT | No | FK | Khóa giờ bắt đầu ca làm việc | `nds.nds_shift.shift_start` | Convert HHMM | Khóa giờ hợp lệ | Không áp dụng | Khung giờ bắt đầu ca | Ràng buộc CHECK 0-2359 | None |
| `driver_key` | Khóa tài xế | INT | No | FK | Khóa liên kết tài xế thực hiện ca | `nds.nds_shift.driver_sk` | SCD Type 2 Lookup tại thời điểm `shift_start` | Khóa tài xế hợp lệ | Không áp dụng | Liên kết tài xế | Không | None |
| `vehicle_key` | Khóa phương tiện | INT | No | FK | Khóa liên kết xe sử dụng trong ca | `nds.nds_shift.vehicle_sk` | SCD Type 2 Lookup tại thời điểm `shift_start` | Khóa xe hợp lệ | Không áp dụng | Liên kết phương tiện | Không | None |
| `vendor_key` | Khóa nhà cung cấp | INT | No | FK | Khóa liên kết nhà cung cấp quản lý ca | `nds.nds_shift.vendor_sk` | Lookup vendor_key tương ứng | Khóa vendor hợp lệ | Không áp dụng | Báo cáo theo đối tác | Không | None |
| `shift_status` | Trạng thái ca | VARCHAR(50) | No | None | Trạng thái ghi nhận của ca làm việc | `nds.nds_shift.shift_status` | Trim, uppercase | COMPLETED, ... | Không áp dụng | Lọc ca thành công | Không | None |
| `shift_start` | Thời điểm bắt đầu ca | TIMESTAMP | No | None | Thời điểm tài xế bắt đầu ca (giờ NY) | `nds.nds_shift.shift_start` | Giữ nguyên | TIMESTAMP | Không áp dụng | Tính toán thời gian | Không | None |
| `shift_end` | Thời điểm kết thúc ca | TIMESTAMP | No | None | Thời điểm tài xế kết thúc ca (giờ NY) | `nds.nds_shift.shift_end` | Giữ nguyên | TIMESTAMP | Không áp dụng | Tính toán thời gian | Ràng buộc CHECK >= shift_start | None |
| `is_anomaly` | Cờ ca bất thường | BOOLEAN | No | None | Cờ đánh dấu ca làm việc vi phạm luật nghiệp vụ | TBD_AFTER_RECONCILIATION | Xác định dựa trên quy tắc đối soát gối ca (overlap) | true, false | Không áp dụng | Lọc ca lỗi | Mặc định false | None |
| `shift_duration_minutes` | Tổng thời lượng ca (phút) | DECIMAL(12,2) | No | None | Tổng thời gian ca làm việc tính bằng phút | `nds.nds_shift.shift_start`, `nds.nds_shift.shift_end` | (shift_end - shift_start) tính theo phút | `>= 0` | Không áp dụng | Mẫu số tính utilization_rate | Ràng buộc CHECK >= 0 | SUM |
| `trip_count` | Số lượng chuyến đi thực tế | INT | No | None | Tổng số chuyến đi hợp lệ phát sinh trong ca | `nds.nds_trip` & `nds.nds_trip_assignment` | COUNT(*) các trip thực tế gán cho ca này | `>= 0` | Không áp dụng | Tính số chuyến trung bình mỗi ca | Phải đối soát với tổng trip của ca | SUM |
| `occupied_minutes` | Số phút có khách | DECIMAL(12,2) | No | None | Tổng thời gian chở khách thực tế của ca | `nds.nds_trip` | SUM(trip_duration_minutes) của các trip thuộc ca | `>= 0.00` | Không áp dụng | Đo lường hiệu suất chạy xe | Ràng buộc CHECK >= 0 | SUM |
| `idle_minutes` | Số phút trống | DECIMAL(12,2) | No | None | Số phút tài xế rảnh hoặc đợi khách | Tính toán | `shift_duration_minutes - occupied_minutes` | `>= 0.00` | Không áp dụng | Đo lường thời gian hao phí | Ràng buộc CHECK >= 0 | SUM |
| `utilization_rate` | Tỷ lệ tận dụng | DECIMAL(5,4) | No | None | Hiệu suất sử dụng thời gian của tài xế trong ca | Tính toán | `occupied_minutes / shift_duration_minutes` | `0.0000 - 1.0000` | Không áp dụng | Đánh giá hiệu suất tổng quan | Ràng buộc CHECK >= 0 | TBD_AFTER_RECONCILIATION (Phép gộp tổng tử/mẫu) |
| `total_revenue` | Tổng doanh thu ca | DECIMAL(12,2) | No | None | Tổng số tiền thu được từ các chuyến đi của ca | `nds.nds_trip` | SUM(total_amount) của các trip thuộc ca | Số thập phân | Không áp dụng | Doanh thu tổng của ca | Phải đối soát với tổng trip | SUM |
| `total_tips` | Tổng tiền tip ca | DECIMAL(12,2) | No | None | Tổng tiền tip tài xế nhận trong ca | `nds.nds_trip` | SUM(tip_amount) của các trip thuộc ca | Số thập phân | Không áp dụng | Thống kê thu nhập thêm của tài xế | Không | SUM |
| `batch_id` | ID Batch nạp | UUID | No | FK | ID của batch ETL thực hiện nạp dòng này | `audit.metadata_etl_batch.batch_id` | Lấy từ ETL context | UUID hợp lệ | Không áp dụng | Đối soát và lineage | Không | None |

---
