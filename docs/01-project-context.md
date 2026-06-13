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

- Dự án mới ở giai đoạn lập kế hoạch và thiết kế ban đầu.
- Báo cáo, slide và sơ đồ cũ là tài liệu nháp trước feedback, chưa phải thiết kế
  đã chốt.
- Chưa có pipeline ETL, database warehouse, cube, dashboard hoặc mô hình mining
  hoàn chỉnh.
- Dữ liệu local hiện có từ tháng 01/2020 đến tháng 07/2021, chưa đủ toàn bộ
  phạm vi 2020-2021 được mô tả trong bản nháp.

## Việc cần làm tiếp theo

Thu hẹp phạm vi theo một người dùng cuối, một nhóm quyết định nghiệp vụ và một
chủ đề DDS có thể triển khai đầy đủ.

