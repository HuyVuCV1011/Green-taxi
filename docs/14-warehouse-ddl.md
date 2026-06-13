# Warehouse DDL Baseline

Status: `IMPLEMENTED BASELINE`

## Mục tiêu

Baseline này tạo các schema và bảng metadata cần thiết để bắt đầu nạp Staging
trong PostgreSQL warehouse. Phạm vi chỉ gồm `staging`, `audit` và placeholder
`dq`; chưa triển khai NDS, DDS hoặc loader full TLC.

## Điều kiện

- Docker Compose chạy từ root repo.
- Service warehouse giữ nguyên tên `postgres_warehouse`.
- Connection đọc từ `.env` hoặc environment variables, không hard-code password.
- Business timestamps giữ semantic `America/New_York` bằng
  `TIMESTAMP WITHOUT TIME ZONE`.
- Audit timestamps dùng UTC bằng `TIMESTAMPTZ`.

## Cách chạy

Tạo `.env` từ template nếu chưa có:

```powershell
Copy-Item configs\.env.example .env
```

Validate Compose:

```powershell
docker compose config
```

Khởi động warehouse hoặc toàn bộ stack:

```powershell
docker compose up -d postgres_warehouse
```

Apply DDL:

```powershell
python scripts\apply_warehouse_ddl.py --mode docker
```

Nếu môi trường Python đã có `psycopg`, có thể dùng direct connection:

```powershell
python scripts\apply_warehouse_ddl.py --mode psycopg
```

Mặc định `--mode auto` thử `psycopg` trước rồi fallback sang
`docker compose exec -T postgres_warehouse psql`. Verification dùng cùng mode
đã apply; `--mode psycopg` không phụ thuộc Docker Compose để verify.

## Kiểm tra thủ công

```powershell
docker compose exec -T postgres_warehouse psql `
  -U green_taxi_warehouse_app `
  -d green_taxi_warehouse `
  -c "SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema IN ('audit','dq','staging') ORDER BY 1,2;"
```

Với `.env.example`, user/database mặc định là:

- User: `green_taxi_warehouse_app`
- Database: `green_taxi_warehouse`
- Local port: `5434`

## Schemas

| Schema | Vai trò |
|---|---|
| `staging` | Bảng raw/source-aligned kèm lineage metadata |
| `audit` | Batch, extract, checksum và audit metadata |
| `dq` | Placeholder cho DQ issues/quarantine ở milestone sau |

## Tables

| Table | Vai trò |
|---|---|
| `audit.metadata_etl_batch` | Batch identity, release, status, row count và runtime audit |
| `audit.metadata_source_extract` | Một lần extract từ file/table/collection/source entity |
| `audit.metadata_file_checksum` | Checksum và row count cho TLC/lookup file |
| `dq.dq_issue` | Placeholder lưu DQ findings theo batch/rule |
| `staging.stg_tlc_green_trips` | TLC Green Taxi trips, sample-compatible |
| `staging.stg_lookup_vendor` | Vendor lookup |
| `staging.stg_lookup_taxi_zone` | Taxi zone/location lookup |
| `staging.stg_hr_drivers` | Driver HR snapshot từ MySQL |
| `staging.stg_hr_driver_changes` | Driver HR change feed từ MySQL |
| `staging.stg_fleet_vehicles` | Vehicle documents từ MongoDB |
| `staging.stg_dispatch_shifts` | Dispatch shifts từ PostgreSQL source |
| `staging.stg_dispatch_trip_assignments` | Trip assignment rows từ PostgreSQL source |

## Idempotency và reset

DDL dùng `CREATE SCHEMA IF NOT EXISTS`, `CREATE TABLE IF NOT EXISTS` và
`CREATE INDEX IF NOT EXISTS`, nên có thể chạy lại nhiều lần trên cùng database.

Khi cần reset sạch trong môi trường local, xóa volume warehouse rồi apply lại:

```powershell
docker compose down
docker volume rm green_taxi_postgres_warehouse_data
docker compose up -d postgres_warehouse
python scripts\apply_warehouse_ddl.py --mode docker
```

Chỉ reset warehouse volume khi không cần giữ dữ liệu staging/audit local.

## Ngoài phạm vi

- Không seed MySQL HR, MongoDB Fleet hoặc PostgreSQL Dispatch.
- Không load full TLC vào warehouse.
- Không triển khai NDS/DDS.
- Không chạy synthetic generator.
