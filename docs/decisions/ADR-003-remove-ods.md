# ADR-003: Không sử dụng ODS

Status: Accepted

## Context

ODS cần phục vụ operational decisions với độ trễ ngắn. Case study hiện xử lý dữ
liệu lịch sử theo batch và không có use case gần thời gian thực.

## Decision

Dùng Staging -> DQ/Audit -> NDS -> DDS. Không tạo ODS.

## Consequences

- Kiến trúc gọn hơn.
- NDS chịu trách nhiệm tích hợp và chuẩn hóa dữ liệu.
- Nếu sau này xuất hiện SLA vận hành hằng ngày, quyết định này phải được xem lại.

