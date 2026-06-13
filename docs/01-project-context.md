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
- Docker Compose đã dựng bốn service local: `mysql_hr`, `mongodb_fleet`,
  `postgres_dispatch` và `postgres_warehouse`.
- Seed scripts đã nạp được release vào MySQL HR, MongoDB Fleet và PostgreSQL
  Dispatch theo cơ chế idempotent.
- PostgreSQL warehouse đã có baseline schemas/tables cho `staging`, `audit` và
  `dq`.
- Source-to-staging loader đã được bổ sung để extract từ source interfaces vào
  staging kèm audit metadata, row hash và row-count reconciliation.
- NDS, DDS, DQ rules đầy đủ và dashboard nghiệp vụ chưa được triển khai.
- Báo cáo, slide và sơ đồ cũ trong `archive/` là tài liệu trước feedback, không
  phải thiết kế hiện hành.
- Data release hiện hành bao phủ 01/2020-07/2021, đúng phạm vi đã chốt cho
  Driver Operations case study.

## Việc cần làm tiếp theo

Tiếp tục sau Milestone 2 baseline:

1. Review và harden source-to-staging loader trên fresh environment.
2. Triển khai DQ rules, quarantine và audit issue workflow.
3. Load dữ liệu đã qua DQ từ staging vào NDS.
4. Xây Driver Operations DDS và dashboard phân tích.
