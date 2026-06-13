# Project Scope

Status: `APPROVED FOR IMPLEMENTATION`

## Tên đề tài

**Tích hợp dữ liệu đa nguồn phục vụ phân tích hiệu quả vận hành tài xế
NYC Green Taxi giai đoạn 2020-2021**

## Bài toán

Dữ liệu chuyến đi công khai của NYC TLC mô tả hành trình và doanh thu nhưng
không chứa tài xế, phương tiện, ca làm việc hoặc thông tin phân công. Trong một
doanh nghiệp vận tải, các đối tượng này thường do nhiều hệ thống nghiệp vụ quản
lý độc lập:

- Trip/LPEP System quản lý chuyến đi.
- Driver HR System quản lý hồ sơ tài xế.
- Fleet System quản lý phương tiện.
- Dispatch System quản lý ca làm và phân công chuyến.

Dự án mô phỏng các hệ thống còn thiếu bằng dữ liệu synthetic có ràng buộc, sau
đó seed dữ liệu vào các hệ thống nguồn có interface độc lập và tích hợp chúng
với TLC trip records để tạo một nguồn phân tích thống nhất.

Các nguồn vật lý trong scope:

- TLC trips và lookup: file batch CSV/Parquet.
- Driver HR: MySQL.
- Fleet Management: MongoDB.
- Dispatch và Trip Assignment: PostgreSQL nguồn độc lập.
- Staging, NDS và DDS: PostgreSQL warehouse đích.

Google Drive data release là gói phân phối/seed chuẩn của nhóm, không phải một
hệ thống nghiệp vụ trong logical architecture.

## Người dùng cuối

**Quản lý vận hành đội xe và tài xế** của đơn vị Green Taxi.

## Quyết định cần hỗ trợ

1. Khu vực và khung giờ nào cần ưu tiên năng lực tài xế?
2. Ca làm việc nào có hiệu suất, doanh thu và tỷ lệ sử dụng tốt?
3. Tài xế và phương tiện nào đang hoạt động dưới mức thông thường?
4. Thời gian có khách, thời gian nhàn rỗi và doanh thu trên giờ thay đổi ra sao?
5. Những trường hợp nào cần được kiểm tra do bất thường nghiệp vụ hoặc dữ liệu?

Hệ thống không tự động điều phối tài xế trong thời gian thực. Nó cung cấp dữ
liệu lịch sử và chỉ số để hỗ trợ lập kế hoạch vận hành.

## Chủ đề DDS

Chỉ xây dựng một data mart:

> **Driver Operations DDS**

Hai fact chính:

- `FactDriverTrip`: một dòng là một chuyến được gán cho tài xế và phương tiện.
- `FactDriverShift`: một dòng là một ca làm việc đã tổng hợp.

## Trong phạm vi

- Tích hợp trip, driver, vehicle, shift, assignment, vendor và location.
- Seed idempotent các source systems từ cùng một data release.
- Extract từ file, MySQL, MongoDB và PostgreSQL nguồn qua adapter riêng.
- Metadata, checksum, batch ID và row hash.
- Upsert và SCD cho master data.
- Late-arriving/inferred driver hoặc vehicle.
- Deduplication và kiểm tra quan hệ thời gian.
- Dashboard hiệu quả vận hành.
- Phát hiện bất thường nghiệp vụ ở mức driver/shift.

## Ngoài phạm vi

- Dữ liệu danh tính tài xế thật.
- Điều phối hoặc tracking GPS thời gian thực.
- Payroll, kế toán chi phí và lợi nhuận ròng.
- Marketing, customer segmentation và promotion.
- Xử lý khiếu nại khách hàng.
- Dự báo nhu cầu thời gian thực.
- Change Data Capture, streaming và đồng bộ gần thời gian thực.
- MinIO/S3 trong scope triển khai chính.
- High availability, cluster và vận hành production.

## Tiêu chí hoàn thành

- Pipeline tái lập được từ data release, qua source systems, đến DDS.
- Có ít nhất bốn hệ thống nguồn có vai trò nghiệp vụ rõ ràng.
- Source containers có thể xóa, dựng lại và seed ra cùng dữ liệu.
- Warehouse PostgreSQL tách biệt với PostgreSQL nguồn Dispatch.
- Synthetic data tuân thủ các ràng buộc được công bố.
- Có data-quality logs, rejected/quarantined records và reconciliation tests.
- Dashboard trả lời được các quyết định vận hành đã nêu.
- Báo cáo phân biệt rõ dữ liệu TLC thật và dữ liệu synthetic.
