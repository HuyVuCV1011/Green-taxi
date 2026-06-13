# Data Sources

## Nguyên tắc

Nhiều nguồn trong dự án là nhiều **hệ thống nghiệp vụ**, không phải cùng một
dataset được lưu dưới nhiều định dạng.

## Source inventory

| Hệ thống nguồn (Source System) | Phân loại dữ liệu | Giao tiếp triển khai (Interface) | Tệp tin trong Data Release | Tính chất nguồn | Vai trò nghiệp vụ chính |
|---|---|---|---|:---:|---|
| **TLC LPEP Trip System** | Chuyến đi Green Taxi (Trips) | Tệp CSV/Parquet theo tháng | CSV tháng | Thật | Ghi nhận chi tiết thời gian, vị trí và cước phí của chuyến đi. |
| **Driver HR System** | Hồ sơ tài xế & Lịch sử cập nhật | MySQL Database | CSV & JSONL | Giả lập | Quản lý thông tin tài xế, giấy phép lái taxi, trạng thái làm việc. |
| **Fleet Management** | Danh mục phương tiện (Vehicles) | MongoDB Collection | JSONL | Giả lập | Theo dõi danh sách xe, năm sản xuất và tình trạng đăng kiểm/kiểm định. |
| **Dispatch System** | Ca làm việc & Phân bổ chuyến đi | PostgreSQL Database (Source) | TSV & CSV tháng | Giả lập | Quản lý ca làm việc của tài xế và liên kết chuyến đi với tài xế/xe. |
| **TLC Taxi Zone** | Tra cứu khu vực (Taxi Zone) | Tệp CSV | CSV | Thật | Danh mục master địa lý để giải mã ID khu vực đón/trả khách. |
| **Vendor Lookup** | Tra cứu đối tác (Vendor) | Tệp CSV | CSV | Thật | Danh mục các nhà cung cấp công nghệ (ví dụ: VeriFone, CMT). |

### Data release và source systems

`green-taxi-full-v1` trên Google Drive là canonical data release để mọi thành
viên có cùng input và checksum. Các file Driver/Fleet/Dispatch trong release là
seed artifacts, không phải interface extract cuối cùng của pipeline.

File cần tải từ Drive là `green-taxi-full-v1.zip` và
`green-taxi-full-v1.zip.sha256`. Cách kiểm SHA-256, giải nén và copy vào
`data/raw/` được mô tả trong `docs/13-team-onboarding-and-data-setup.md`.

Sau khi tải release:

1. Driver files được seed idempotent vào MySQL.
2. Vehicle documents được seed idempotent vào MongoDB.
3. Shift và assignment files được seed idempotent vào PostgreSQL nguồn.
4. TLC trip và lookup files vẫn được ingest trực tiếp theo batch.
5. ETL extract từ từng interface và load vào PostgreSQL staging đích.

`assignment_exceptions.csv` được giữ như release audit artifact để reconciliation,
không được coi là transaction table của Dispatch.

### Vendor 0

TLC records có thể thiếu `VendorID` hoặc chứa giá trị không thuộc vendor pool đã
biết. Generator chuẩn hóa các trường hợp này thành `vendor_id = 0` và gán vào
synthetic Legacy/Unknown Pool để vẫn có thể assignment/reconcile mà không giả
định chúng thuộc CMT hoặc VeriFone.

`data/lookup/vendor.csv` phải luôn có dòng:

```text
0,Legacy / Unknown Pool
```

NDS/DDS load Vendor 0 như một member hợp lệ có nhãn rõ ràng, không để fact có
foreign key mồ côi và không gộp nó với unknown surrogate member kỹ thuật. Một
unknown surrogate member riêng vẫn có thể dùng cho lỗi lookup ngoài contract.

PostgreSQL nguồn Dispatch và PostgreSQL warehouse là hai service/database độc
lập. Việc tách này mô phỏng ranh giới sở hữu và vận hành giữa source system với
analytical platform.

## Bối cảnh nghiệp vụ thực tế (Real-World Business Context)

Trong mô hình vận hành của một hãng taxi truyền thống, dữ liệu không được tạo ra
tại một hệ thống duy nhất. Mỗi bộ phận sử dụng một hệ thống chuyên biệt để phục
vụ trách nhiệm nghiệp vụ riêng. Vì vậy, dữ liệu chuyến đi, tài xế, phương tiện,
ca làm việc và hoạt động điều phối thường bị phân mảnh theo nguồn, thời điểm cập
nhật và định danh nghiệp vụ.

Phần dưới đây mô tả bối cảnh nghiệp vụ được sử dụng cho case study. Đây là mô
hình khái quát hóa hoạt động của một doanh nghiệp taxi, không phải khẳng định
rằng dữ liệu TLC công khai chứa đầy đủ các định danh nội bộ của hãng.

### Đồng hồ tính tiền và hệ thống ghi nhận chuyến đi (TLC Taximeter System)

Đồng hồ tính tiền là thiết bị được lắp trên xe và kết nối với các thành phần
ghi nhận chuyến đi. Khi một chuyến bắt đầu và kết thúc, hệ thống tạo giao dịch
thô gồm thời gian pickup/dropoff, vị trí, quãng đường, các thành phần cước phí
và tổng tiền. Trong thực tế, một số thông tin có thể được thiết bị hoặc hệ thống
trên xe truyền về nhà cung cấp công nghệ và sau đó được chuẩn hóa để báo cáo.

Thiết bị chủ yếu gắn với phương tiện hoặc thiết bị đã đăng ký, thay vì đóng vai
trò là hồ sơ nhân sự đầy đủ của người lái. Ngay cả khi hệ thống nội bộ có bước
đăng nhập tài xế, dữ liệu trip records công khai của TLC không cung cấp định
danh tài xế hay phương tiện cho mục đích phân tích của dự án. Do đó, riêng dữ
liệu chuyến đi không đủ để xác định tài xế nào đã thực hiện chuyến hoặc tài xế
đã nhận phương tiện nào trong một ca.

### Phòng Nhân sự (Driver HR System)

Driver HR System quản lý hồ sơ tài xế như mã nhân sự, ngày tuyển dụng, trạng
thái hợp đồng, thâm niên và tình trạng giấy phép lái taxi. Bộ phận nhân sự hoặc
compliance theo dõi thời hạn TLC Driver License và các trạng thái như đang hoạt
động, nghỉ phép, hết hạn hoặc bị đình chỉ.

Trước khi tài xế được bố trí ca, hệ thống vận hành cần đối chiếu với HR để bảo
đảm người đó đang có quan hệ làm việc hợp lệ và đủ điều kiện pháp lý. Các thay
đổi về trạng thái hoặc giấy phép có thể được gửi dưới dạng change feed và đến
muộn hơn thời điểm hiệu lực, tạo ra yêu cầu xử lý lịch sử và late-arriving data
trong kho dữ liệu.

### Phòng Kỹ thuật và Quản lý đội xe (Fleet System)

Fleet System quản lý vòng đời phương tiện, gồm loại xe, năm sản xuất, ngày bắt
đầu khai thác và trạng thái hoạt động, bảo dưỡng hoặc ngừng sử dụng. Bộ phận kỹ
thuật sử dụng hệ thống này để quyết định xe nào đủ điều kiện được bàn giao cho
tài xế trong ngày.

Một thuộc tính quan trọng là `last_inspection_date`, thể hiện lần kiểm định gần
nhất theo yêu cầu áp dụng đối với phương tiện khai thác tại New York. Thông tin
này hỗ trợ kiểm soát tuân thủ và ngăn việc phân ca cho xe chưa đủ điều kiện kỹ
thuật. Fleet System không tự biết xe đã tạo ra chuyến đi nào hoặc tài xế nào đã
lái xe nếu chưa được liên kết với dữ liệu bàn giao và điều phối.

### Trung tâm Điều phối (Dispatch & Assignment System)

Dispatch & Assignment System là trung tâm phối hợp hoạt động hàng ngày giữa tài
xế, phương tiện và nhu cầu chuyến đi. Trong mô hình case study, tài xế đến bãi
xe, đăng ký ca, nhận phương tiện và bàn giao chìa khóa. Một ca có thể kéo dài
nhiều giờ và bị giới hạn tối đa 10-12 giờ theo chính sách vận hành giả định.
Dispatch lưu thời gian bắt đầu/kết thúc ca, tài xế, phương tiện và khu vực hoạt
động đầu/cuối ca.

Trong ca, Trip Assignment ghi lại việc liên kết mỗi chuyến với tài xế, phương
tiện và shift tương ứng. Các lệnh điều phối có thể được truyền từ tổng đài đến
thiết bị trên xe. Project sử dụng hai nhãn phương thức:

- `CONTINUITY`: tài xế và phương tiện đang hoạt động tiếp tục nhận chuyến kế
  tiếp trong cùng chuỗi vận hành.
- `AVAILABLE_POOL`: hệ thống chọn một tài xế/phương tiện đang khả dụng, thường
  ưu tiên nguồn lực phù hợp với khu vực pickup.

Hai giá trị này là quy ước mô phỏng của generator để giải thích logic phân bổ
nguồn lực; chúng không phải mã phương thức có sẵn trong TLC trip records.

### Lý do cần tích hợp (Business Rationale)

Mỗi hệ thống riêng lẻ chỉ trả lời được một phần của hoạt động. Trip System cho
biết doanh thu và hành trình nhưng không xác định được người chịu trách nhiệm;
HR biết điều kiện làm việc của tài xế nhưng không biết hiệu suất chuyến; Fleet
biết tình trạng xe nhưng không biết xe được sử dụng trong ca nào; Dispatch biết
quan hệ bàn giao nhưng không chứa đầy đủ chi tiết cước phí của chuyến đi.

Nếu không tích hợp các nguồn này, quản lý vận hành không thể xác định đáng tin
cậy tài xế nào tạo ra bao nhiêu doanh thu trong ca, xe nào được sử dụng nhiều
hoặc phát sinh bất thường khi do ai điều khiển, và thời gian làm việc được phân
bổ giữa chở khách với chờ chuyến như thế nào. Việc tích hợp tạo ra chuỗi truy
vết `trip -> assignment -> shift -> driver/vehicle`, từ đó hỗ trợ đo hiệu suất
ca, utilization, doanh thu theo giờ, doanh thu theo quãng đường, tuân thủ nhân
sự/phương tiện và các trường hợp cần điều tra vận hành.

## Dữ liệu TLC

Theo NYC TLC, Green Taxi trip records chứa pickup/dropoff date-time và location,
trip distance, itemized fares, rate/payment type và passenger count. Dữ liệu
không chứa định danh tài xế hoặc phương tiện, nên các quan hệ vận hành phải được
mô phỏng và công bố rõ.

Nguồn tham khảo:

- https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page
- https://www.nyc.gov/assets/tlc/downloads/pdf/trip_record_user_guide.pdf
- https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_green.pdf

## Phạm vi dữ liệu local

Dữ liệu trip hiện có gồm 19 tháng từ 01/2020 đến 07/2021 với khoảng 2,3 triệu
dòng CSV. Đây là phạm vi triển khai hiện tại. Không mô tả là đủ 24 tháng cho đến
khi bổ sung 08/2021-12/2021.

## Synthetic data policy

- Không sử dụng tên, license number hay danh tính tài xế thật.
- ID synthetic có prefix rõ ràng như `DRV`, `VEH`, `SHF`.
- Thuật toán sinh, seed và config được version-control.
- Chỉ data owner sinh release; thành viên seed cùng release vào source systems.
- Source seeding không được thay đổi nội dung nghiệp vụ hoặc tạo record mới.
- Các ràng buộc và giới hạn được ghi trong data contract.
- Kết luận chỉ áp dụng cho case study, không suy diễn về tài xế thật.

## Authoritative source

| Entity | Authoritative source |
|---|---|
| Trip | TLC LPEP Trip System |
| Driver | Driver HR System |
| Vehicle | Fleet Management |
| Shift | Dispatch System |
| Assignment | Trip Assignment |
| Location | TLC Taxi Zone |
| Vendor | Vendor lookup |

## Ranh giới công nghệ

MySQL, MongoDB và PostgreSQL nguồn được dùng để mô phỏng các cơ chế lưu trữ và
extract khác nhau, không được mô tả như bằng chứng rằng một hãng taxi cụ thể
ngoài đời đang sử dụng đúng các sản phẩm này. MinIO/S3, streaming và CDC không
thuộc scope chính; TLC file batch đã đủ đại diện cho nguồn dữ liệu khối lượng
lớn trong project.
