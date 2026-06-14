# Superset Platform Readiness Audit
**NYC Green Taxi Driver Operations BI - Superset Integration Evaluation**

Tài liệu này đánh giá khả năng bổ sung Apache Superset vào môi trường local của dự án nhằm phục vụ khai thác phân tích dữ liệu trên tầng DDS (Dimensional Data Store).

---

## 1. Hiện trạng Repository (Existing State)

### Đánh giá dịch vụ và cấu hình hiện tại
- **Cấu hình Superset hiện hữu**: Repository hiện tại chưa có bất kỳ service, file cấu hình, hay tệp tin biến môi trường nào liên quan tới Apache Superset.
- **Docker Network hiện tại**:
  - Tên network: `green_taxi_net` (chế độ external hoặc được khai báo tự động bởi Docker Compose của dự án).
- **Docker Volumes hiện tại**:
  - `green_taxi_mysql_hr_data` (Driver HR MySQL data)
  - `green_taxi_mongodb_fleet_data` (Fleet MongoDB data)
  - `green_taxi_postgres_dispatch_data` (Dispatch PostgreSQL data)
  - `green_taxi_postgres_warehouse_data` (PostgreSQL DWH data)
- **Docker Services & Ports hiện tại**:
  - `mysql_hr`: Chạy MySQL 8.4, port public `3307`, port container `3306`.
  - `mongodb_fleet`: Chạy MongoDB 7.0, port public `27018`, port container `27017`.
  - `postgres_dispatch`: Chạy PostgreSQL 16, port public `5433`, port container `5432`.
  - `postgres_warehouse`: Chạy PostgreSQL 16 (Warehouse), port public `5434`, port container `5432`.

### Thông tin kết nối Warehouse cho container Superset
Khi Superset được triển khai dưới dạng container trong cùng mạng `green_taxi_net`, thông tin kết nối trực tiếp vào kho dữ liệu PostgreSQL (không đi qua port mapping local của host) như sau:
- **Hostname**: `postgres_warehouse` (độ phân giải DNS nội bộ của Docker).
- **Port trong mạng**: `5432`.
- **Database**: `green_taxi_warehouse`.
- **Mật khẩu & User**: Sử dụng tài khoản Read-Only đề xuất (xem Phần 3).

### Khảo sát xung đột Port
- Cổng mặc định của Apache Superset là `8088`. Qua khảo sát, cổng này hiện không bị chiếm dụng bởi bất kỳ dịch vụ nào trong cấu hình `docker-compose.yml` hiện tại của dự án.
- Streamlit Control Panel đang chạy trực tiếp trên host thông qua lệnh `streamlit run` (thường sử dụng cổng `8501`), do đó không gây ra xung đột cổng với container Superset.

---

## 2. Kiến trúc Superset tối thiểu (Proposed State)

Để phục vụ thử nghiệm local (Minimum Local Demo), dự án đề xuất cấu hình tinh giản tối đa nhằm tiết kiệm tài nguyên máy tính cá nhân.

### Các thành phần của Demo Môi trường Local
1.  **superset_app**: Container chạy image chính thức `apache/superset:4.0.1`. Đảm nhận vai trò webserver phục vụ giao diện người dùng và API truy vấn.
2.  **superset_metadata_db**: Một container cơ sở dữ liệu riêng chạy `postgres:16-alpine`. Container này hoàn toàn tách biệt với database DWH của dự án nhằm lưu trữ thông tin quản trị của Superset (thông tin đăng nhập, danh sách charts, dashboard metadata, các connection string).
3.  **superset_init**: Container phụ chạy chế độ một lần (one-shot bootstrap) để khởi tạo cấu trúc bảng quản trị (`superset db upgrade`), tạo tài khoản Admin và cấu hình phân quyền ban đầu (`superset init`), sau đó tự động tắt để giải phóng RAM.

### Quyết định về thành phần bổ trợ (Redis & Celery)
Dự án quyết định **KHÔNG** đưa Redis và Celery (Celery Worker, Celery Beat) vào kiến trúc local demo:
- **Lý do**: Redis và Celery chỉ thực sự cần thiết đối với môi trường production-like để hỗ trợ các truy vấn phi tuần tự (async queries) chạy ngầm, lưu cache kết quả truy vấn lớn, hoặc gửi email báo cáo định kỳ. Với quy mô thử nghiệm nội bộ, số lượng người dùng đồng thời bằng 1 và dung lượng dữ liệu DDS nhỏ, các truy vấn đồng bộ trực tiếp (synchronous queries) chạy trực tiếp trên webserver là hoàn toàn đủ đáp ứng và tối ưu tài nguyên nhất.

### Mối liên kết mạng và lưu trữ
- **Network**: Kết nối trực tiếp vào mạng ngoài `green_taxi_net`.
- **Persistence**: Tạo một volume định danh `green_taxi_superset_metadata_data` cho container metadata DB để giữ lại toàn bộ thiết kế dashboard khi khởi động lại docker.

---

## 3. Read-Only Warehouse Access (Read-only Access Proposal)

Nhằm tuân thủ nguyên tắc an toàn thông tin và bảo vệ tính toàn vẹn của kho dữ liệu, quyền truy cập từ Superset vào kho dữ liệu PostgreSQL được giới hạn nghiêm ngặt.

### Đặc tả phân quyền cho Role `superset_ro`
- **Quyền kết nối**: Chỉ được phép thực hiện lệnh `CONNECT` tới database `green_taxi_warehouse`.
- **Quyền lược đồ (Schema usage)**: Chỉ được phép thực hiện `USAGE` trên schema `dds`.
- **Quyền đọc dữ liệu**: Chỉ có quyền `SELECT` trên các bảng hiện tại và các bảng/views được tạo mới trong tương lai thuộc schema `dds` (sử dụng `ALTER DEFAULT PRIVILEGES`).
- **Giới hạn tuyệt đối**:
  - Không được cấp quyền `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`, `CREATE` trên bất kỳ bảng hay schema nào.
  - Không cấp quyền truy cập vào schema `staging` và `nds` nhằm tránh lộ lọt dữ liệu thô hoặc thực hiện các phép join sai grain của tầng chuẩn hóa.
  - Tuyệt đối không cấp quyền Superuser.

*Chi tiết câu lệnh SQL đề xuất cấu hình được lưu tại [superset-readonly-role.sql](superset-readonly-role.sql).*

---

## 4. Bảo mật và Quản lý Secret (Security and Secrets)

Để đảm bảo các thông tin nhạy cảm không bị lộ lọt vào Git:
- **Tập tin cấu hình**: Tất cả các credentials và mã khóa bảo mật của Superset được đưa ra ngoài file `.env.superset` cục bộ (sử dụng template an toàn từ [superset-env.example](superset-env.example)).
- **Cơ chế loại trừ**: Lược đồ `.gitignore` hiện tại đã bao phủ các quy tắc chặn `.env` và `.env.*`. Do đó, file `.env.superset` cấu hình thực tế trên máy local sẽ được bảo vệ an toàn khỏi Git.
- **Biến bảo mật cốt lõi**:
  - `SUPERSET_SECRET_KEY`: Khóa mật mã ký session cookie, bắt buộc phải sinh ngẫu nhiên trên local và không được sử dụng giá trị mặc định.
  - `ADMIN_PASSWORD`: Mật khẩu quản trị web của Superset.
  - `SUPERSET_METADATA_DB_PASSWORD`: Mật khẩu kết nối metadata DB nội bộ.
  - `SUPERSET_WAREHOUSE_PASSWORD`: Mật khẩu của tài khoản đọc dữ liệu DWH `superset_ro`.

---

## 5. Tài nguyên và Vận hành (Resource Estimate)

### Ước tính tài nguyên phần cứng local
- **RAM**:
  - Container Superset App: Cần tối thiểu `1.5 GB` RAM khi bắt đầu khởi chạy (do quá trình import thư viện Python lớn) và ổn định ở mức `800 MB - 1.2 GB` khi rảnh.
  - Container Metadata DB: Cần khoảng `100 MB - 200 MB` RAM.
  - *Tổng RAM đề xuất cho Docker host*: Tối thiểu `2.0 GB` khả dụng.
- **CPU**: Cần tối thiểu `1 Core CPU` cho việc khởi động và xử lý truy vấn thông thường.
- **Disk Space (Ổ đĩa)**:
  - Docker Image `apache/superset:4.0.1` giải nén chiếm khoảng `1.5 GB`.
  - Docker Image `postgres:16-alpine` giải nén chiếm khoảng `300 MB`.
  - *Tổng dung lượng ổ đĩa*: Khoảng `2.0 GB`.

### Quy trình Vận hành và Sao lưu
- **Thời gian khởi động (Startup Time)**: Dự kiến mất khoảng `30 - 45 giây` để dịch vụ hoàn thành khởi tạo lần đầu và lắng nghe trên port `8088`.
- **Persistent Metadata**: Toàn bộ cấu hình biểu đồ được ghi vào volume độc lập. Việc xóa container Superset không làm mất thiết kế dashboard.
- **Rủi ro nâng cấp/di cư (Upgrade Risk)**: Rủi ro trung bình-thấp. Cần thực hiện `pg_dump` volume dữ liệu metadata DB trước khi nâng cấp phiên bản image của Superset nhằm đảm bảo khả năng rollback khi gặp lỗi không tương thích schema.

---

## 6. Ranh giới Phân tích dữ liệu (Analytics Boundary)

Superset khi tích hợp vào dự án phải tuân thủ nghiêm ngặt ranh giới kiến trúc đã đồng thuận:
- **Chỉ truy cập DDS**: Superset chỉ được phép truy vấn dữ liệu từ schema `dds` (hoặc các analytics views được phê duyệt sau này). Tuyệt đối không kết nối trực tiếp đến schema `staging` hoặc `nds` trên các dashboard nghiệp vụ.
- **Hạt dữ liệu (Grain)**:
  - `fact_driver_trip`: Grain ở mức một chuyến đi (trip level).
  - `fact_driver_shift`: Grain ở mức một ca làm việc hoàn tất (shift level).
- **Cấm DimShift**: Không tạo bảng chiều `dim_shift` theo đúng DDL thực tế của kho. Thuộc tính `shift_id` hoạt động độc lập dưới dạng degenerate dimension trực tiếp trên các fact.
- **Trạng thái Metric**: Chưa thực hiện định nghĩa cố định các certified metrics trên giao diện Superset trong workstream này do các chỉ số đối soát ở Prompt 2 và 3A chưa được hoàn thiện.

---

## 7. Các điểm nghẽn và Rủi ro (Blockers)

- **Tài nguyên phần cứng máy local**: Việc chạy đồng thời 4 container nguồn/DWH hiện tại cùng với 2 container Superset và ứng dụng Streamlit có thể khiến RAM của hệ thống local vượt quá `8 GB`. Cần khuyến nghị RAM tối thiểu của máy chạy thử nghiệm là `16 GB`.
- **Trạng thái Dữ liệu DDS**: Cần đảm bảo pipeline chạy thành công và DWH được đánh dấu trạng thái `DDS Ready for BI` (qua Streamlit Control Panel hoặc metadata batch) trước khi thực hiện kết nối dữ liệu từ Superset để tránh lỗi truy vấn bảng trống.
