# Superset and OLAP Proposals

Status: `SUPERSEDED / HISTORICAL INDEX`

Các proposal dưới đây từng tồn tại trong `docs/drafts/` và đã được loại khỏi cây
tài liệu hiện hành sau khi Superset local demo được triển khai:

- `27-superset-readiness-audit.md`
- `superset-compose-proposal.yml`
- `superset-env.example`
- `superset-readonly-role.sql`
- `olap_architecture_proposal.md`

Không dùng nội dung proposal từ Git history làm hướng dẫn triển khai.

## Current replacements

| Historical topic | Current source |
|---|---|
| Superset setup and operation | [../docs/analytics/superset-local-demo-runbook.md](../docs/analytics/superset-local-demo-runbook.md) |
| End-to-end onboarding | [../docs/setup/local-reproducibility.md](../docs/setup/local-reproducibility.md) |
| Runtime Compose | `../docker-compose.superset.yml` |
| Environment template | `../configs/superset.env.example` |
| Warehouse security grants | `../sql/analytics/02_superset_readonly_role.sql` |
| Architecture | [../docs/architecture/system-architecture.md](../docs/architecture/system-architecture.md) |

## Historical findings retained

- Superset metadata database phải tách khỏi business warehouse.
- Base image `apache/superset:6.1.0` không bundled PostgreSQL driver trong lần
  kiểm tra; runtime image bổ sung `psycopg2-binary==2.9.11`.
- BI role không được đọc trực tiếp DDS hoặc các implementation schemas.
- Redis/Celery không cần cho synchronous local demo.
- ClickHouse, DuckDB và Cube.js chỉ là phương án nghiên cứu, chưa được chấp nhận.
  Kiến trúc hiện hành là PostgreSQL ROLAP + approved analytics views + Superset.

Lịch sử chi tiết vẫn có thể truy xuất trong Git khi cần audit quyết định.
