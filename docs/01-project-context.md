# Project Context

## Mục tiêu ban đầu

Nhóm đề xuất xây dựng kho dữ liệu cho NYC Green Taxi Trips giai đoạn 2020-2021,
phục vụ phân tích doanh thu, nhu cầu di chuyển, thanh toán, tiền tip, khu vực và
các bất thường.

Kiến trúc nháp ban đầu:

```text
Data Sources -> Staging -> ODS -> DQ/Audit -> NDS -> DDS -> BI/OLAP/Mining
```

## Trạng thái hiện tại

- Phạm vi Driver Operations, kiến trúc không ODS và data contracts đã được chốt.
- Synthetic source package đã được sinh, validation và đóng gói theo data release.
- Thiết kế nguồn đã được mở rộng thành các hệ thống mô phỏng không đồng nhất:
  MySQL cho Driver HR, MongoDB cho Fleet và PostgreSQL nguồn cho
  Dispatch/Assignment. TLC và lookup tiếp tục là nguồn file batch.
- PostgreSQL warehouse, source containers, ETL, NDS, DDS và dashboard chưa được
  triển khai.
- Báo cáo, slide và sơ đồ cũ trong `archive/` là tài liệu trước feedback, không
  phải thiết kế hiện hành.
- Dữ liệu local hiện có từ tháng 01/2020 đến tháng 07/2021, chưa đủ toàn bộ
  phạm vi 2020-2021 được mô tả trong bản nháp.

## Việc cần làm tiếp theo

Triển khai Milestone 2 theo tài liệu hiện hành:

1. Dựng PostgreSQL warehouse và staging contracts.
2. Dựng các source systems mô phỏng bằng Docker Compose.
3. Seed source systems từ cùng Google Drive data release.
4. Extract dữ liệu qua source adapters và load vào staging có audit/lineage.
