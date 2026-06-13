# ADR-004: Technology stack

Status: Proposed

## Decision

- Python cho ingestion, generation, DQ và orchestration ban đầu.
- PostgreSQL cho Staging, NDS và DDS.
- SQL cho transformation và reconciliation.
- Power BI hoặc Apache Superset cho dashboard.
- GitHub cho code/docs; raw data không lưu trong Git.

## Rationale

Stack cross-platform, phù hợp kỹ năng nhóm và hỗ trợ CSV/JSON/TSV/Parquet,
relational warehouse và dashboard.

