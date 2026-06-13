# ADR-005: Mô phỏng các hệ thống nguồn không đồng nhất

Status: Accepted

## Context

Synthetic data hiện được phân phối dưới dạng CSV, JSONL và TSV. Chỉ đổi định
dạng file không đủ chứng minh đây là các hệ thống nghiệp vụ độc lập. Tuy nhiên,
dựng quá nhiều hạ tầng như MinIO, streaming hoặc CDC sẽ làm lệch trọng tâm khỏi
DQ, NDS, DDS và analytics.

## Options

1. Giữ toàn bộ nguồn dưới dạng file.
2. Dùng MySQL, MongoDB, PostgreSQL nguồn và TLC file batch.
3. Bổ sung thêm MinIO/S3, message broker, CDC và streaming.

## Decision

Chọn phương án 2:

- Driver HR trên MySQL.
- Fleet trên MongoDB.
- Dispatch và Trip Assignment trên PostgreSQL nguồn.
- TLC trips và lookup tiếp tục là file batch.
- PostgreSQL warehouse là service đích độc lập.

Google Drive release là canonical seed package. Thành viên không tự generate
dữ liệu; họ tải cùng release và seed các source systems bằng quy trình
idempotent.

## Consequences

- Project chứng minh được file, relational và document ingestion.
- Source systems có thể xóa và dựng lại từ release đã kiểm checksum.
- Cần phân biệt rõ seed artifacts với operational source interfaces.
- Cần adapter riêng nhưng giữ chung staging contract.
- MinIO/S3, streaming và CDC nằm ngoài scope chính.
