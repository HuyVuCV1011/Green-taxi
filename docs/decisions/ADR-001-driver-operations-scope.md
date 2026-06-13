# ADR-001: Chọn Driver Operations làm phạm vi

Status: Accepted

## Context

Plan cũ phục vụ đồng thời giám đốc, marketing, vận hành và QA, dẫn đến nhiều DDS
và không xác định được quyết định trọng tâm.

## Decision

Chọn quản lý vận hành tài xế/đội xe làm người dùng cuối và xây một Driver
Operations DDS.

## Consequences

- Loại customer marketing và profitability khỏi phạm vi.
- Cần synthetic driver, vehicle, shift và assignment.
- Dashboard tập trung utilization, revenue/hour, idle time và zone/hour.

