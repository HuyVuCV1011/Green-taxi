# ADR-002: Sinh các nguồn vận hành synthetic

Status: Accepted

## Context

TLC trip records không chứa driver và vehicle identifiers. Đổi cùng dữ liệu qua
nhiều format không tạo ra bài toán tích hợp đa nguồn có ý nghĩa.

## Decision

Sinh bốn nhóm dữ liệu nghiệp vụ: Driver HR, Fleet, Dispatch Shift và Trip
Assignment. Dữ liệu được tạo từ trip thật bằng thuật toán deterministic và
ràng buộc thời gian.

Việc các nhóm dữ liệu này được triển khai trên source interface nào là quyết
định vật lý riêng trong ADR-005. Theo thiết kế hiện hành, Shift và Assignment
cùng thuộc PostgreSQL Dispatch source.

## Consequences

- Dữ liệu không đại diện tài xế thật.
- Generator, seed, config và validation phải được version-control.
- Release artifacts phải giữ được semantics khi seed vào source systems.
- Kết luận chỉ áp dụng cho case study.
