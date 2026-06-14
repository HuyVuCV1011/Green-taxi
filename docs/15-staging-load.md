# Hướng dẫn Load Warehouse Staging (Source-to-Staging ETL)

Tài liệu này mô tả chi tiết kiến trúc, tham số cấu hình, logic ánh xạ, cơ chế kiểm soát chất lượng, idempotency và đối soát số liệu (reconciliation) của quá trình nạp dữ liệu từ các hệ thống nguồn vào tầng Staging của PostgreSQL Warehouse.

## 1. Kiến trúc Source Adapters

Quá trình ETL từ Source sang Staging được thực hiện thông qua bộ nạp `StagingLoader` (`src/ingestion/staging_loader.py`) và công cụ dòng lệnh `load_staging.py` (`scripts/load_staging.py`).

Bộ nạp kết nối và trích xuất dữ liệu từ 4 loại nguồn khác nhau:
- **MySQL HR Database**: Trích xuất bảng `drivers` và `driver_changes`.
- **MongoDB Fleet Database**: Trích xuất collection `vehicles`.
- **PostgreSQL Dispatch Database**: Trích xuất bảng `shifts` và `trip_assignments` sử dụng server-side cursors cho dữ liệu lớn.
- **TLC & Lookup Files**: Đọc các tệp tin CSV từ thư mục phát hành (`data/raw/tlc` và `data/lookup`).

```text
+-------------------+      +-------------------+
|     MySQL HR      | ---> |  stg_hr_drivers   |
| (drivers, changes)|      |  stg_hr_changes   |
+-------------------+      +-------------------+
+-------------------+      +-------------------+
|   MongoDB Fleet   | ---> | stg_fleet_vehicles|
|    (vehicles)     |      |                   |
+-------------------+      +-------------------+
+-------------------+      +-------------------+
|  Postgres Dispatch| ---> | stg_dispatch_...  |
| (shifts, assigns) |      | (shifts, assigns) |
+-------------------+      +-------------------+
+-------------------+      +-------------------+
| TLC Green Trips & | ---> | stg_tlc_green_... |
|   Lookup Files    |      | stg_lookup_...    |
+-------------------+      +-------------------+
```

## 2. Quy tắc Nạp và Ánh xạ dữ liệu (Loading & Mapping Rules)

### MySQL HR
- `drivers` -> `staging.stg_hr_drivers`
- `driver_changes` -> `staging.stg_hr_driver_changes`

### MongoDB Fleet
- `vehicles` -> `staging.stg_fleet_vehicles`
- Xử lý múi giờ: BSON Date lưu trữ dạng UTC. Khi nạp vào Staging, thời gian được chuyển đổi sang múi giờ nghiệp vụ (`America/New_York`) và lưu trữ dưới dạng naive date/timestamp để duy trì ngữ nghĩa nghiệp vụ:
  - `service_start_date` và `last_inspection_date`: Chuyển sang kiểu `DATE` (America/New_York).
  - `source_updated_at`: Chuyển sang kiểu `TIMESTAMP WITHOUT TIME ZONE` (America/New_York).

### PostgreSQL Dispatch
- `shifts` -> `staging.stg_dispatch_shifts`
- `trip_assignments` -> `staging.stg_dispatch_trip_assignments`
- Lưu ý: Không nạp bảng `assignment_exceptions` vào Staging do thực thể này không thuộc DDS fact nghiệp vụ mà chỉ đóng vai trò audit/reconciliation.

### TLC & Lookup Files
- `green_tripdata_*.csv` -> `staging.stg_tlc_green_trips`
- `vendor.csv` -> `staging.stg_lookup_vendor`
- `taxi_zone.csv` -> `staging.stg_lookup_taxi_zone`
- Với các tệp tin nguồn này, bộ nạp ghi nhận thêm thông tin audit: `source_file`, `source_row_number`, và `source_checksum`.

## 3. Siêu dữ liệu Staging (Staging Metadata Columns)

Mỗi hàng dữ liệu khi nạp vào Staging đều được bổ sung các cột metadata chuẩn để hỗ trợ việc audit và kiểm soát chất lượng dữ liệu ở các tầng sau:
- `batch_id`: UUID định danh duy nhất cho mỗi lượt chạy ETL.
- `release_id`: Định danh phiên bản dữ liệu phát hành (ví dụ: `green-taxi-full-v1`).
- `source_system`: Hệ thống nguồn dữ liệu (`HR_MYSQL`, `FLEET_MONGODB`, `DISPATCH_POSTGRES`, `TLC_FILE`, `LOOKUP_FILE`).
- `source_entity`: Tên thực thể nguồn (ví dụ: `drivers`, `vehicles`, v.v.).
- `source_locator`: URI định vị nguồn dữ liệu (ví dụ: `mysql://...` hoặc `file://...`).
- `source_record_id`: Định danh bản ghi phía nguồn (dạng chuỗi).
- `source_extract_at`: Thời điểm trích xuất dữ liệu (UTC).
- `load_timestamp`: Thời điểm nạp dữ liệu vào PostgreSQL Warehouse (mặc định lấy thời gian hệ thống tại database).
- `source_checksum`: Mã SHA-256 của tệp tin nguồn (chỉ áp dụng đối với file TLC/Lookup, null đối với DB sources).
- `extraction_watermark`: Watermark trích xuất (null do chạy chế độ Full).
- `row_hash`: Mã băm SHA-256 từ các trường dữ liệu nghiệp vụ đã được chuẩn hóa.

### Quy tắc tạo Row Hash
`row_hash` được tạo ra một cách chi tiết và deterministic để kiểm tra sự thay đổi dữ liệu hoặc trùng lặp:
- Chỉ sử dụng các trường dữ liệu nghiệp vụ (loại bỏ toàn bộ các trường metadata và kỹ thuật như `load_timestamp`, `source_extract_at`).
- Định dạng chuẩn hóa các kiểu dữ liệu trước khi băm:
  - Giá trị `NULL` hoặc rỗng -> Chuỗi rỗng `""`.
  - Kiểu `datetime` -> Chuỗi `"YYYY-MM-DD HH:MM:SS"`.
  - Kiểu `date` -> Chuỗi `"YYYY-MM-DD"`.
  - Kiểu `Decimal` -> Chuỗi chuẩn hóa loại bỏ số 0 thừa ở cuối (ví dụ: `12.50` và `12.5` đều thành `"12.5"`).
  - Kiểu `bool` -> `"true"` hoặc `"false"`.
  - Đối tượng JSON/Dict/List -> Sắp xếp các khóa theo thứ tự bảng chữ cái trước khi chuyển sang chuỗi JSON.
- Mã băm SHA-256 được tính từ chuỗi JSON của payload nghiệp vụ đã chuẩn hóa.

## 4. Chiến lược Idempotency (Reload idempotent)

Để hỗ trợ việc chạy lại mà không gây trùng lặp dữ liệu, quy trình nạp sử dụng chiến lược **Delete-before-Insert**:
- Trước khi chèn bản ghi mới của một `release_id` và thực thể nguồn xác định, bộ nạp thực hiện lệnh `DELETE` các bản ghi cũ có cùng `release_id` trong bảng Staging tương ứng.
- Đối với TLC trips, do dữ liệu lớn chia thành nhiều tệp tin, việc xóa và nạp lại được phân mảnh theo cấp độ tệp tin (`release_id` + `source_file`).

## 5. Audit Logging và Đối soát (Reconciliation)

Quy trình ETL ghi nhận đầy đủ siêu dữ liệu kiểm toán vào schema `audit` của Warehouse:
1. **audit.metadata_etl_batch**: Lưu vết mỗi lượt chạy pipeline. Các thông tin gồm: `release_id`, `pipeline_name`, `batch_status` (`STARTED`, `SUCCEEDED`, `FAILED`), thời gian bắt đầu/kết thúc, số dòng dự kiến trích xuất, số dòng thực tế đã nạp, và thông điệp lỗi nếu có.
2. **audit.metadata_source_extract**: Lưu vết trích xuất cho từng thực thể nguồn cụ thể của batch. Ghi nhận số dòng trích xuất (`rows_extracted`) và số dòng nạp thành công (`rows_loaded`).
3. **audit.metadata_file_checksum**: Lưu thông tin kiểm chứng mã hash SHA-256 của các tệp tin nguồn (`TLC_FILE` và `LOOKUP_FILE`), kích thước tệp tin, và số lượng bản ghi kiểm đếm.

### Đối soát số dòng (Row Count Reconciliation)
Sau khi hoàn thành việc trích xuất và nạp cho mỗi thực thể, bộ nạp thực hiện so sánh số lượng dòng đọc được từ nguồn và số lượng dòng thực tế đã ghi nhận trong bảng Staging:
- Nếu số lượng dòng lệch nhau (`rows_extracted != rows_loaded`), trạng thái của thực thể nguồn đó được đánh dấu là `FAILED` và batch ETL sẽ dừng/báo lỗi.
- CLI hiển thị bảng tổng hợp chi tiết kết quả đối soát sau khi chạy.

## Trạng thái triển khai

Staging loader, source adapters và audit row count đã được triển khai. Có thể
chạy riêng bằng `scripts/load_staging.py` hoặc qua `PipelineRunner`. Tài liệu
này không khẳng định full release đã pass trên mọi môi trường; cần lưu riêng
smoke-test và reconciliation report từ một môi trường sạch trước khi nộp đồ án.
