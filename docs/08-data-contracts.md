# 📜 Hợp đồng Dữ liệu Nguồn (Synthetic Source Data Contracts)

Hợp đồng dữ liệu định nghĩa các cam kết kỹ thuật chặt chẽ về cấu trúc, kiểu dữ liệu, các business key và các ràng buộc thời gian đối với toàn bộ dữ liệu thô đầu vào.

---

## 🎛️ Các Tầng Hợp đồng (Contract Layers)

Mỗi nguồn dữ liệu mô phỏng (synthetic source) được biểu diễn qua hai tầng:

1.  **Release Contract:** Định dạng tệp tin phân phối chuẩn (CSV, JSONL, TSV) tải về từ Google Drive, dùng để checksum và seed dữ liệu thô ban đầu.
2.  **Operational Source Contract:** Cấu trúc bảng (Table) hoặc bộ sưu tập (Collection) thực tế mà Ingestion Adapter sẽ kết nối và trích xuất.

> [!IMPORTANT]
> Tiến trình seed dữ liệu từ Release Package vào cơ sở dữ liệu nguồn bắt buộc phải bảo toàn Natural Key, giá trị nghiệp vụ (business values) và ngữ nghĩa thời gian (temporal semantics). Thay đổi định dạng lưu trữ vật lý được chấp nhận nhưng không được làm biến dạng nội dung nghiệp vụ.

---

## 📌 Quy ước Chung (General Conventions)

*   **Ràng buộc bắt buộc:** Cột ghi `Required = Yes` tương đương với thuộc tính `NOT NULL` trong cơ sở dữ liệu quan hệ (PostgreSQL/MySQL) và trường bắt buộc trong MongoDB Document Validation.
*   **Chuẩn hóa chuỗi:** Tất cả các chuỗi ID bắt buộc phải được trim khoảng trắng, không được để trống và phải giữ nguyên định dạng ký tự hoa/thường từ release.
*   **Xử lý dữ liệu lỗi:** Các giá trị thuộc danh sách Enum không hợp lệ sẽ bị từ chối và đưa vào Quarantine; hệ thống không tự ý áp đặt giá trị mặc định để che giấu lỗi nguồn.
*   **Giá trị mặc định (Default):** Chỉ được áp dụng khi phát sinh bản ghi nghiệp vụ mới trong vận hành; tiến trình seed release không được tự điền các giá trị thiếu.
*   **Tính toàn vẹn của Release:** Gói dữ liệu `green-taxi-full-v1` được cam kết không chứa giá trị NULL ở các trường bắt buộc (`Required = Yes`).

---

## ⏰ Quy ước Thời gian (Temporal Conventions)

Toàn bộ timestamps nghiệp vụ trong TLC và synthetic release không chứa thông tin offset múi giờ. Chúng được quy ước hiểu theo giờ địa phương New York (`America/New_York`), tuân thủ quy tắc đổi giờ mùa hè/mùa đông (EST/EDT).

*   **MySQL Source:** Lưu trữ timestamp nghiệp vụ bằng kiểu dữ liệu `DATETIME`, độc lập với timezone của session kết nối.
*   **PostgreSQL Source & Staging:** Lưu trữ timestamp nghiệp vụ bằng kiểu dữ liệu `TIMESTAMP WITHOUT TIME ZONE`.
*   **MongoDB Source:** BSON Date lưu trữ thời gian theo UTC. Seed adapter có nhiệm vụ gắn múi giờ `America/New_York` vào chuỗi thời gian của release trước khi chuyển đổi sang UTC để ghi vào DB. Extract adapter phải thực hiện chuyển đổi ngược lại để bảo toàn đúng ngữ nghĩa thời gian địa phương.
*   **Timestamp kỹ thuật:** Toàn bộ mốc thời gian xử lý hệ thống (ví dụ: `seeded_at`, `source_extract_at`, `load_timestamp`, `batch_started_at`) dùng múi giờ UTC và lưu bằng kiểu `TIMESTAMP WITH TIME ZONE` (`TIMESTAMPTZ`) trong PostgreSQL.

> [!WARNING]
> Tuyệt đối không được parse các timestamp nghiệp vụ không chứa offset như giờ UTC. Các sai lệch múi giờ sẽ làm hỏng hoàn toàn kết quả đối soát ca làm việc và tính toán hiệu suất tài xế.

---

## 📋 Chi tiết Hợp đồng các Nguồn Dữ liệu

### 1. Driver HR - Tệp `drivers.csv`
*   **Operational Source:** MySQL table `drivers` thuộc database `green_taxi_hr`.

| Cột | Kiểu logic | Bắt buộc | Khóa / Giá trị mặc định | Mô tả chi tiết |
| :--- | :--- | :---: | :--- | :--- |
| `driver_id` | `string` | Yes | PK; Định dạng `DRV######` | Mã tự nhiên định danh tài xế |
| `vendor_id` | `integer` | Yes | FK vendor; Không default | `0` = Legacy Pool, `1` = CMT, `2` = VeriFone |
| `driver_code` | `string` | Yes | UNIQUE; Không default | Mã số nhân sự nội bộ |
| `display_name` | `string` | Yes | Không default | Tên hiển thị mô phỏng |
| `hire_date` | `date` | Yes | Không default | Ngày tuyển dụng |
| `employment_status` | `string` | Yes | Default `'ACTIVE'` | Trạng thái: `ACTIVE` / `LEAVE` / `INACTIVE` |
| `license_status` | `string` | Yes | Default `'ACTIVE'` | Trạng thái bằng lái: `ACTIVE` / `EXPIRED` / `SUSPENDED` |
| `license_expiry_date`| `date` | Yes | Không default | Ngày hết hạn bằng lái |
| `experience_years` | `integer` | Yes | Default `0`; Ràng buộc `>= 0` | Số năm kinh nghiệm tại đầu kỳ |
| `home_borough` | `string` | Yes | Không default | Quận cư trú mô phỏng |
| `source_updated_at` | `timestamp` | Yes | Không default | Thời điểm cập nhật nguồn (`America/New_York`) |

---

### 2. Fleet - Tệp `vehicles.jsonl`
*   **Operational Source:** MongoDB collection `vehicles` thuộc database `green_taxi_fleet`. Khóa tự nhiên định danh là `vehicle_id`.

| Trường | Kiểu logic | Bắt buộc | Khóa / Giá trị mặc định | Mô tả chi tiết |
| :--- | :--- | :---: | :--- | :--- |
| `vehicle_id` | `string` | Yes | UNIQUE; Định dạng `VEH######`| Mã tự nhiên định danh phương tiện |
| `vendor_id` | `integer` | Yes | FK-like; Không default | Nhà cung cấp sở hữu/quản lý |
| `plate_token` | `string` | Yes | UNIQUE; Không default | Token mã hóa biển số xe |
| `model_year` | `integer` | Yes | Không default | Năm sản xuất |
| `vehicle_type` | `string` | Yes | Không default | Loại xe: `SEDAN` / `HYBRID` / `WAV` (Hỗ trợ xe lăn) |
| `service_start_date` | `date` | Yes | Không default | Ngày bắt đầu đưa vào khai thác |
| `vehicle_status` | `string` | Yes | Default `'ACTIVE'` | Trạng thái: `ACTIVE` / `MAINTENANCE` / `RETIRED` |
| `last_inspection_date`| `date` | Yes | Ràng buộc `>= service_start_date`| Ngày đăng kiểm gần nhất |
| `source_updated_at` | `timestamp` | Yes | Không default | Thời điểm cập nhật nguồn (`America/New_York`) |

---

### 3. Dispatch - Tệp `shifts.tsv`
*   **Operational Source:** PostgreSQL source table `public.shifts` thuộc database `green_taxi_dispatch`.

| Cột | Kiểu logic | Bắt buộc | Khóa / Giá trị mặc định | Mô tả chi tiết |
| :--- | :--- | :---: | :--- | :--- |
| `shift_id` | `string` | Yes | PK; Định dạng `SHF##########`| Mã định danh ca làm việc |
| `driver_id` | `string` | Yes | FK Driver; Không default | Tài xế nhận ca |
| `vehicle_id` | `string` | Yes | FK Vehicle; Không default | Phương tiện được bàn giao |
| `vendor_id` | `integer` | Yes | FK Vendor; Không default | Nhà cung cấp quản lý ca |
| `shift_start` | `timestamp` | Yes | Không default | Thời điểm nhận ca (`America/New_York`) |
| `shift_end` | `timestamp` | Yes | Ràng buộc `>= shift_start` | Thời điểm trả ca (`America/New_York`) |
| `assigned_start_zone`| `integer` | Yes | FK-like zone; Không default | Vùng bắt đầu ca |
| `actual_end_zone` | `integer` | Yes | FK-like zone; Không default | Vùng kết thúc ca |
| `trip_count` | `integer` | Yes | Default `0`; Ràng buộc `>= 0` | Số chuyến đi phát sinh trong ca |
| `occupied_minutes` | `decimal` | Yes | Default `0`; Ràng buộc `>= 0` | Tổng số phút chở khách |
| `idle_minutes` | `decimal` | Yes | Default `0`; Ràng buộc `>= 0` | Số phút trống ca làm việc |
| `shift_status` | `string` | Yes | Default `'COMPLETED'` | Trạng thái ca: `COMPLETED` |

---

### 4. Trip Assignment - Tệp CSV theo tháng
*   **Operational Source:** PostgreSQL source table `public.trip_assignments` thuộc database `green_taxi_dispatch`.

| Cột | Kiểu logic | Bắt buộc | Khóa / Giá trị mặc định | Mô tả chi tiết |
| :--- | :--- | :---: | :--- | :--- |
| `trip_key` | `string(24)` | Yes | PK; Chuỗi hex thường | Mã SHA-256 rút gọn định danh chuyến đi |
| `source_file` | `string` | Yes | UNIQUE Key phần 1 | Tên tệp tin nguồn chuyến đi TLC gốc |
| `source_row_number` | `integer` | Yes | UNIQUE Key phần 2; `>= 2` | Chỉ số dòng vật lý trong tệp CSV nguồn |
| `driver_id` | `string` | Yes | FK Driver; Không default | Tài xế được chỉ định |
| `vehicle_id` | `string` | Yes | FK Vehicle; Không default | Phương tiện được chỉ định |
| `shift_id` | `string` | Yes | FK Shift; Không default | Ca làm việc chứa chuyến đi |
| `assignment_timestamp`| `timestamp` | Yes | Không default | Thời điểm chỉ định chuyến đi |
| `assignment_method` | `string` | Yes | Không default | Cách thức: `CONTINUITY` / `AVAILABLE_POOL` |

> [!NOTE]
> Tệp `assignment_exceptions.csv` là tệp ghi nhận các trường hợp ngoại lệ (chuyến đi không được chỉ định tài xế) phục vụ kiểm toán chất lượng, được seed vào bảng `public.assignment_exceptions`. Đây không phải bảng nghiệp vụ chính của Dispatch và adapter không được kéo bảng này vào làm fact của DDS.

---

### 5. HR Change Feed - Tệp `driver_changes.jsonl`
*   **Operational Source:** MySQL table `driver_changes` thuộc database `green_taxi_hr`.
*   *Đặc thù:* Trường `changes` được lưu dưới dạng kiểu `JSON` trong MySQL để lưu giữ vết thay đổi. Việc xử lý thứ tự trích xuất dựa trên cột `delivered_at` thay vì thứ tự dòng vật lý.

| Trường | Kiểu logic | Bắt buộc | Khóa / Giá trị mặc định | Mô tả chi tiết |
| :--- | :--- | :---: | :--- | :--- |
| `event_id` | `string` | Yes | PK; Định dạng `DRVCHG######`| Mã định danh sự kiện thay đổi |
| `driver_id` | `string` | Yes | FK Driver; Không default | Tài xế chịu tác động |
| `event_type` | `string` | Yes | Không default | Loại sự kiện (Ví dụ: `HOME_BOROUGH_CHANGED`) |
| `effective_at` | `timestamp` | Yes | Không default | Thời điểm thay đổi có hiệu lực nghiệp vụ |
| `delivered_at` | `timestamp` | Yes | Ràng buộc `>= effective_at` | Thời điểm hệ thống nguồn ghi nhận |
| `changes` | `JSON` | Yes | Không default; Không rỗng | Payload thay đổi (Ví dụ: `{"home_borough": "Brooklyn"}`) |
| `is_late_arriving` | `boolean` | Yes | Default `false` | Đánh dấu sự kiện đến trễ (Late-arriving) |

---

## 🔒 Các Ràng buộc Hệ thống (System Invariants)

### Ràng buộc về Seed:
*   Bảng tra cứu `dim_vendor` chứa đầy đủ 3 thành viên: `0` (Legacy Pool), `1` (CMT), và `2` (VeriFone).
*   Số lượng dòng và metadata sau khi seed vào MySQL/PostgreSQL/MongoDB phải khớp chính xác với release package gốc.
*   Chạy lại tiến trình seed không sinh trùng lặp bản ghi và không tự động sinh timestamp kỹ thuật mới làm thay đổi mã hash của nguồn dữ liệu nghiệp vụ.

### Ràng buộc về Staging Lineage (Staging Lineage Contract):
Mọi bản ghi được nạp vào Staging bắt buộc phải có đầy đủ các trường lineage kỹ thuật sau để phục vụ truy vết (Auditability):

| Trường Metadata | Bắt buộc | Ý nghĩa và Quy chuẩn hiển thị |
| :--- | :---: | :--- |
| `release_id` | Yes | Mã phiên bản dữ liệu (Ví dụ: `green-taxi-full-v1`) |
| `batch_id` | Yes | ID duy nhất định danh lô ETL của Warehouse; là khóa bất biến |
| `source_system` | Yes | Tên hệ thống nguồn: `TLC_FILE` / `LOOKUP_FILE` / `HR_MYSQL` / `FLEET_MONGODB` / `DISPATCH_POSTGRES` |
| `source_entity` | Yes | Tên bảng/collection/file nghiệp vụ nguồn |
| `source_locator` | Yes | Chỉ vị trí vật lý (Đường dẫn tệp tin hoặc chuỗi kết nối database) |
| `source_record_id` | Yes | ID dòng của tệp tin hoặc khóa tự nhiên của dòng DB nguồn |
| `source_extract_at`| Yes | Mốc thời gian trích xuất dữ liệu (UTC) |
| `load_timestamp` | Yes | Mốc thời gian ghi nhận vào Staging (UTC) |
| `row_hash` | Yes | Mã băm SHA-256 đại diện cho dữ liệu nghiệp vụ của dòng |
| `source_checksum` | Conditional| Bắt buộc đối với nguồn File; để NULL đối với database/collection |
| `extraction_watermark`| Conditional| Bắt buộc khi sử dụng cơ chế kéo gia tăng (incremental); để NULL khi kéo snapshot |

---

## ⏰ Các Quy tắc logic Thời gian (Temporal Rules)

Hệ thống Warehouse bắt buộc phải kiểm tra và đảm bảo các quy tắc logic thời gian sau không bị vi phạm (DQ Gate 2):

1.  **Chồng lấp Chuyến đi:** Một tài xế hoặc một phương tiện không được phép có các chuyến đi chồng lấp thời gian hoạt động với nhau.
2.  **Chồng lấp Ca làm:** Một tài xế hoặc một phương tiện không được phép có các ca làm việc (`shift`) chồng lấp thời gian với nhau.
3.  **Quan hệ Chuyến đi - Ca làm:** Thời gian của chuyến đi (`pickup` và `dropoff`) bắt buộc phải nằm hoàn toàn trong khoảng thời gian hoạt động của ca làm việc (`shift_start` và `shift_end`).
4.  **Cân bằng ca làm:** Tổng thời gian chở khách (`occupied_minutes`) và thời gian trống (`idle_minutes`) phải khớp chính xác với tổng thời gian ca làm (`shift_end - shift_start`) trong sai số làm tròn cho phép.
5.  **Tính duy nhất của bàn giao:** Tại một thời điểm ca làm việc, một ca làm chỉ được phân bổ cho duy nhất một tài xế và một phương tiện.
6.  **Quy chuẩn Vendor:** Tài xế, phương tiện và chuyến đi trong cùng một ca làm phải có cùng một mã `vendor_id`, trừ trường hợp tài xế thuộc Vendor `0` (Legacy Pool - có thể ghép với bất kỳ vendor nào).
7.  **Logic Dispatch:** Thời điểm chỉ định chuyến đi (`assignment_timestamp`) không được muộn hơn thời điểm khách lên xe (`pickup_datetime`).
