# ADR-004: Technology stack

Status: Accepted

## Decision

- Python cho source seeding, ingestion, generation, DQ và orchestration ban đầu.
- MySQL cho Driver HR source simulation.
- MongoDB cho Fleet source simulation.
- PostgreSQL nguồn riêng cho Dispatch và Trip Assignment.
- PostgreSQL warehouse riêng cho Staging, DQ/Audit, NDS và DDS.
- TLC trips và lookup được ingest từ file batch CSV/Parquet.
- SQL cho transformation và reconciliation.
- Apache Superset cho dashboard local trên approved PostgreSQL analytics views.
- GitHub cho code/docs; raw data không lưu trong Git.
- Google Drive cho canonical full-data release của nhóm.
- Docker Compose cho môi trường local có thể tái tạo.

## Rationale

Stack thể hiện tích hợp file, relational database và document database mà không
thay đổi mục tiêu Driver Operations. Source PostgreSQL và warehouse PostgreSQL
được tách để giữ đúng ranh giới operational/analytical.

MinIO/S3, streaming và CDC không được chọn vì TLC file batch đã đáp ứng phạm vi,
trong khi các công nghệ đó tăng chi phí triển khai nhưng chưa có use case tương
ứng.

## Consequences

- Cần Docker health checks, seed scripts và source-specific adapters.
- Thành viên phải tải cùng data release trước khi chạy full environment.
- Sample tests vẫn phải chạy được mà không cần tất cả containers.
- Downstream DQ/NDS/DDS không phụ thuộc trực tiếp vào source connector.
- Scope hiện tại dùng PostgreSQL ROLAP + Superset; không dùng Power BI, MDX
  hoặc MOLAP cube vật lý.
