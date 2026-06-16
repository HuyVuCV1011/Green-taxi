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
- PostgreSQL warehouse đã triển khai đầy đủ `staging`, `audit`, `dq`, `nds`,
  `dds` và approved `analytics` views.
- Source-to-staging loader đã được bổ sung để extract từ source interfaces vào
  staging kèm audit metadata, row hash và row-count reconciliation.
- NDS, DDS, DQ rules và full-release reconciliation đã hoàn tất.
- Superset local demo đã triển khai với metadata PostgreSQL riêng, warehouse
  role read-only, 4 certified datasets, 39 certified metric instances,
  32 charts và monitoring dashboard BQ01-BQ05 trên 4 tabs.
- Báo cáo, slide và sơ đồ cũ trong `archive/` là tài liệu trước feedback, không
  phải thiết kế hiện hành.
- Data release hiện hành bao phủ 01/2020-07/2021, đúng phạm vi đã chốt cho
  Driver Operations case study.

## Việc cần làm tiếp theo

1. Hoàn thiện báo cáo học thuật và slide.
2. Chốt demo recording và contribution evidence.
3. Giữ pipeline/Superset reproducible bằng onboarding, runbook và smoke tests.
