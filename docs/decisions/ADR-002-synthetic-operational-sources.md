# ADR-002: Sinh các nguồn vận hành synthetic

Status: Accepted

## Context

TLC trip records không chứa driver và vehicle identifiers. Đổi cùng dữ liệu qua
nhiều format không tạo ra bài toán tích hợp đa nguồn có ý nghĩa.

## Decision

Sinh bốn hệ thống nguồn độc lập: Driver HR, Fleet, Dispatch Shift và Trip
Assignment. Dữ liệu được tạo từ trip thật bằng thuật toán deterministic và
ràng buộc thời gian.

## Consequences

- Dữ liệu không đại diện tài xế thật.
- Generator, seed, config và validation phải được version-control.
- Kết luận chỉ áp dụng cho case study.

