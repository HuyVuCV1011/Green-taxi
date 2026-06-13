# Hướng dẫn và Đặc tả Data Pipeline Control Panel

Tài liệu này đặc tả chi tiết mục tiêu, kiến trúc, cách vận hành và các giới hạn kỹ thuật của ứng dụng **Data Pipeline Control Panel** được xây dựng bằng Streamlit.

---

## 1. Mục tiêu của ứng dụng

Ứng dụng Streamlit Control Panel (`app/streamlit_app.py`) được thiết kế nhằm phục vụ mục đích **giám sát kỹ thuật (ETL/ELT Monitoring)** và **đối soát dữ liệu (Data Reconciliation)** trong nội bộ đội ngũ phát triển.

### Các mục tiêu cốt lõi:
* **Kiểm tra sức khỏe kết nối (Connection Health Check):** Xác định nhanh xem các container dữ liệu nguồn (MySQL, MongoDB, PostgreSQL Source) và đích (PostgreSQL Warehouse) local có đang hoạt động hay không.
* **Đối soát seeding (Seed Reconciliation):** Đối chiếu số lượng bản ghi thực tế được nạp vào các database nguồn local so với số lượng dòng chuẩn của gói phân phối dữ liệu (`green-taxi-full-v1`).
* **Giám sát tải dữ liệu Staging (Staging Load Monitoring):** Truy vấn và hiển thị trạng thái của các batch trích xuất, nạp dữ liệu Staging và kiểm soát số dòng hiện có tại 8 bảng Staging trong Warehouse.
* **Hỗ trợ demo vận hành:** Giúp giảng viên và các thành viên dễ dàng hình dung luồng di chuyển dữ liệu từ các hệ thống thô vào kho staging.

> [!WARNING]
> **ỨNG DỤNG KHÔNG PHẢI LÀ DASHBOARD BI CUỐI CÙNG:**
> Giao diện này chỉ phục vụ mục đích giám sát kỹ thuật luồng di chuyển dữ liệu ở tầng thấp. Giao diện báo cáo phân tích BI (Power BI) và các biểu đồ hiệu năng tài xế sẽ được phát triển riêng ở các milestone sau.

---

## 2. Cách thức khởi chạy

### Điều kiện cần:
Đảm bảo bạn đã cài đặt đầy đủ các thư viện trong `requirements.txt` bằng cách chạy:
```powershell
python -m pip install -r requirements.txt
```

### Lệnh chạy:
Chạy lệnh sau tại thư mục gốc của repository:
```powershell
streamlit run app/streamlit_app.py
```
Ứng dụng sẽ tự động mở một tab mới trên trình duyệt mặc định tại địa chỉ: `http://localhost:8501`.

---

## 3. Kiến trúc các Tabs chức năng

Ứng dụng được tổ chức thành 5 Tabs chính giúp người xem dễ dàng theo dõi theo từng khía cạnh:

### Tab 1: Tổng quan & Luồng Dữ liệu
* **Mục đích:** Giới thiệu bối cảnh dự án, hiển thị phiên bản Release ID hiện hành và sơ đồ luồng dữ liệu.
* **Biểu đồ luồng (Data Flow Diagram):** Render trực quan bằng Mermaid.js qua CDN (và có sơ đồ fallback dạng văn bản ASCII đề phòng trường hợp offline). Luồng thể hiện rõ dữ liệu đi từ Simulated Sources -> Warehouse Staging và định hướng các tầng DQ/NDS/DDS trong tương lai.
* **Note:** Gói phân phối từ Google Drive chỉ đóng vai trò phân phối để thiết lập môi trường, không tham gia vào luồng runtime.

### Tab 2: Trạng thái Nguồn (Sources)
* **Mục đích:** Giám sát sức khỏe kết nối trực tiếp của 4 database container.
* **Cơ chế:** Thử kết nối đến các cổng local (`3307`, `27018`, `5433`, `5434`). Nếu kết nối thành công, hiển thị badge màu xanh lá và truy vấn đếm dòng của các thực thể chính. Nếu kết nối lỗi, hiển thị badge màu đỏ kèm thông báo lỗi chi tiết, không làm crash app Streamlit.

### Tab 3: Seed Reconciliation
* **Mục đích:** Đối soát số lượng dòng thô sau khi chạy các scripts seed.
* **Cơ chế:** So sánh số lượng dòng thực tế đếm được từ database nguồn với bộ hằng số kỳ vọng (`EXPECTED_COUNTS`) được định nghĩa rõ ràng cho từng Release ID.
* **Các thực thể đối soát:**
  - MySQL HR: `drivers` (860 dòng), `driver_changes` (77 dòng).
  - MongoDB Fleet: `vehicles` (860 tài liệu).
  - PostgreSQL Dispatch: `shifts` (157,379 dòng), `trip_assignments` (2,304,276 dòng), `assignment_exceptions` (241 dòng).
* **Kết quả:** Hiển thị chênh lệch (diff) và badge trạng thái (`OK`, `Warning` hoặc `Not Loaded` nếu bảng chưa tồn tại).

### Tab 4: Warehouse Staging Status
* **Mục đích:** Kiểm tra trạng thái nạp dữ liệu staging và lịch sử chạy batch.
* **Cơ chế:** Kết nối trực tiếp vào DWH, truy vấn 2 bảng audit `audit.metadata_etl_batch` (lịch sử 5 batch gần nhất) và `audit.metadata_source_extract` (kết quả trích xuất chi tiết của batch gần nhất).
* **Kiểm tra Staging Tables:** Đếm số dòng hiện có tại 8 bảng Staging (`staging.stg_*`). Nếu bảng chưa tồn tại, ứng dụng sẽ báo trạng thái "Not Loaded / Missing" một cách an toàn.
* **Lưu ý:** Thực thể `assignment_exceptions` không được load vào Staging schema do không đóng vai trò Fact nghiệp vụ DDS, nó chỉ xuất hiện ở bước đối soát nguồn (Reconciliation).

### Tab 5: Hướng dẫn Lệnh Chạy (Commands)
* **Mục đích:** Cung cấp tài liệu cẩm nang dòng lệnh PowerShell để thành viên mới có thể sao chép và thực hiện tuần tự việc dựng docker, seed nguồn, apply DDL, chạy staging loader và khởi chạy UI.

---

## 4. Các giới hạn kỹ thuật và Định hướng phát triển

### Các giới hạn hiện tại (Current Limitations):
1. **Read-only Monitoring:** Giao diện chỉ đóng vai trò giám sát, không có nút bấm để trigger hoặc chạy các script seed/ETL tự động nhằm bảo đảm an toàn cho dữ liệu local và blast radius hoạt động.
2. **Local Database Dependencies:** Streamlit app kết nối trực tiếp đến các cổng local của database container. Nếu các container chưa khởi động, dữ liệu hiển thị sẽ luôn ở trạng thái báo lỗi kết nối.
3. **Lookup & TLC Files:** Các tệp Lookup và TLC CSV được load trực tiếp vào staging mà không thông qua cơ sở dữ liệu nguồn trung gian, do đó trong Tab 2 (Source Status) chúng sẽ không hiển thị thông tin đếm dòng trực tiếp của tệp nguồn (bạn cần chạy `load_staging.py` và theo dõi ở Tab 4).

### Định hướng Milestone tiếp theo:
* Tích hợp thêm tab DQ/Audit report để thống kê số lượng bản ghi bị loại trừ và cô lập vào Quarantine table.
* Hiển thị tiến trình nạp dữ liệu từ Staging vào NDS và DDS sau khi các milestone này hoàn tất.
