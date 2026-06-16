# Superset Local Demo Runbook

Status: `IMPLEMENTED AND SMOKE-TESTED`

Runtime verified: 16/06/2026

Superset: `6.1.0`
Dashboard: `NYC Green Taxi - Driver Operations`

## 1. Deliverables

| Thành phần | Artifact |
|---|---|
| Superset + metadata PostgreSQL | `docker-compose.superset.yml` |
| PostgreSQL driver image | `docker/superset/Dockerfile` |
| Runtime config | `docker/superset/superset_config.py` |
| Local secret template | `configs/superset.env.example` |
| Analytics views | `sql/analytics/01_certified_datasets.sql` |
| Read-only grants | `sql/analytics/02_superset_readonly_role.sql` |
| Warehouse setup | `scripts/setup_superset_warehouse.py` |
| Dataset/metric/dashboard bootstrap | `scripts/provision_superset.py` |
| Health/permission/query tests | `scripts/smoke_test_superset.py` |

Superset metadata được lưu riêng trong volume
`green_taxi_superset_metadata_data`. BI login `superset_ro` chỉ có `USAGE` và
`SELECT` trên schema `analytics`; không có quyền trực tiếp trên
`staging`, `audit`, `dq`, `nds` hoặc `dds`.

## 2. First-time setup

Thực hiện đầy đủ
[Team Onboarding and Local Setup](../setup/local-reproducibility.md) trước.
Khi warehouse đã reconcile, phần Superset gồm:

```powershell
python -m scripts.init_superset_env
python -m scripts.setup_superset_warehouse
docker compose --env-file .env.superset -f docker-compose.superset.yml up -d --build
python -m scripts.smoke_test_superset
```

`.env.superset` bị Git ignore và không được chia sẻ. Xem login local khi cần:

```powershell
python -m scripts.show_superset_login
```

Không ghi hoặc chia sẻ output của lệnh trên.

Mở dashboard:

```text
http://localhost:8088/superset/dashboard/green-taxi-driver-operations/
```

## 3. Provisioned semantic layer

| Dataset | Default time | Default location | Certified metrics |
|---|---|---|---|
| `analytics.trip_pickup` | `pickup_datetime` | `pickup_*` | Trip, revenue, fare, tips, distance, duration, anomaly, active driver/vehicle |
| `analytics.trip_dropoff` | `dropoff_datetime` | `dropoff_*` | Cùng metric trip, nhưng role dropoff tường minh |
| `analytics.shift` | `shift_start` | `shift_start_*` | Shift count, trips/revenue per shift, revenue/hour, occupied/idle, utilization, avg_idle_minutes, anomaly |
| `analytics.pareto_pickup_zone` | *None* | `pickup_*` | Total trips, cumulative trips percentage, total revenue, cumulative revenue percentage |
| `analytics.driver_performance_summary` | *None* | Driver | Driver count, completed shifts, revenue/hour, utilization, idle minutes/shift, trips/shift, review driver count |

Mỗi dataset và metric chứa certification metadata:

- Certified by: `Analytics Semantic Contract Owner`
- Contract: `docs/analytics/semantic-contract.md`
- Metric source: `docs/analytics/metric-catalog.md`

Bootstrap idempotent tạo hoặc cập nhật 6 datasets, 51 metric instances
(trip metrics được khai báo riêng trên pickup/dropoff), 32 charts và 1
monitoring dashboard gồm 4 tabs.

Native time filter chưa được provision trên image Superset 6.1.0. Frontend của
phiên bản này gửi scalar Rison tới `/api/v1/time_range/`, trong khi backend từ
chối request đó và làm filter hiển thị `Network error`. Dashboard vì vậy chủ
động để `native_filter_configuration` rỗng; time grain và time range của từng
chart vẫn được khai báo trong chart contract. Chỉ bật lại native time filter sau
khi nâng image và xác nhận API tương thích bằng browser smoke test.

## 4. Dashboard demo flow

1. Mở dashboard và chỉ badge certified/published.
2. Tab **Operations Overview**: đọc KPI strip, monthly trend, pickup borough,
   top zone và weekday profile để nắm trạng thái toàn hệ thống trong một màn.
3. Tab **Demand Patterns**: dùng heatmap weekday/hour, hourly profile, zone
   concentration và pickup/dropoff borough charts để theo dõi nhu cầu theo thời
   gian và địa lý.
4. Tab **Driver & Fleet Performance**: dùng driver matrix, driver review queue,
   vehicle type và vehicle detail để ưu tiên điều phối/đào tạo.
5. Tab **Data Quality & Anomalies**: theo dõi DQ issues, quarantine, anomaly KPI,
   trend, severity/source breakdown và top rules. Không cộng DQ, quarantine,
   trip anomaly và shift anomaly thành một chỉ số chung.

Số expected của full release:

| Evidence | Expected |
|---|---:|
| Trip count | `2.304.276` |
| Completed shifts | `157.379` |
| Total revenue | `48.535.884,47 USD` |
| Active drivers | `795` |
| Shift utilization | khoảng `69,26%` |

## 5. Acceptance tests

```powershell
docker compose --env-file .env.superset -f docker-compose.superset.yml ps --all
python -m scripts.smoke_test_superset
python -m unittest discover -s tests -v
```

Smoke suite xác nhận:

- `/health` trả `OK`;
- admin REST login thành công;
- dashboard, 6 datasets, 51 metric instances và 32 charts tồn tại;
- dashboard không provision native time filter bị lỗi trên Superset 6.1.0;
- `superset_ro` query được approved analytics views;
- pickup/dropoff count khớp;
- truy cập trực tiếp DDS bị từ chối;
- `CREATE TABLE` và `INSERT` qua BI login bị từ chối.

## 6. Daily operation

Start:

```powershell
docker compose up -d postgres_warehouse
docker compose --env-file .env.superset -f docker-compose.superset.yml up -d
```

Stop Superset nhưng giữ metadata:

```powershell
docker compose --env-file .env.superset -f docker-compose.superset.yml down
```

Reapply semantic metadata sau khi đổi metric/chart code:

```powershell
docker compose --env-file .env.superset -f docker-compose.superset.yml up -d --force-recreate superset_init superset_app
```

## 7. Reset and backup

Reset toàn bộ Superset metadata local:

```powershell
docker compose --env-file .env.superset -f docker-compose.superset.yml down
docker volume rm green_taxi_superset_metadata_data
docker compose --env-file .env.superset -f docker-compose.superset.yml up -d
```

Lệnh reset xóa dashboard edits local. Không dùng khi chưa chủ động chấp nhận mất
metadata. Trước khi nâng version, backup metadata DB:

```powershell
docker compose --env-file .env.superset -f docker-compose.superset.yml exec -T superset_metadata_db `
  pg_dump -U superset_metadata_app superset_metadata > superset_metadata_backup.sql
```

File dump chứa metadata nhạy cảm và không được commit.

### Rotate exposed credentials

Nếu credential đã bị lộ/chia sẻ, dùng full local rotation trong
[onboarding](../setup/local-reproducibility.md#credential-rotation). Quy
trình xóa metadata volume và bootstrap lại để admin password, metadata DB
password, warehouse role password và Superset secret key đồng bộ. Backup trước
nếu có dashboard edits local cần giữ.

## 8. Known boundaries

- Đây là local synchronous demo: không có Redis, Celery, alerts hoặc reports.
- `TALISMAN_ENABLED=False` chỉ phù hợp local HTTP demo.
- Metadata rate-limit storage dùng memory; không phải production topology.
- Dashboard chỉ dùng approved analytics views. Tab 4 kết hợp business anomaly
  từ trip/shift với DQ summary, nhưng không join DQ events vào business facts.

## 9. Performance Benchmark

Quy trình benchmark tự động đo đạc thời gian tải của 32 charts thuộc dashboard qua REST API v1.

### 9.1. Lệnh thực hiện

Chạy script benchmark (chạy tối thiểu 20 lần cho mỗi chart sau 2 lần warm-up):

```powershell
python -m scripts.benchmark_superset
```

Kết quả đo đạc chi tiết của từng lượt chạy được xuất ra file JSON:
[superset_benchmark_results.json](../../deliverables/benchmark/superset_benchmark_results.json)

### 9.2. Tóm tắt kết quả đo đạc thực tế

- **Tổng số charts kiểm thử**: 32 charts.
- **Trung bình các giá trị P95 của 32 charts**: `0.615` giây trong lần đo local
  ngày 16/06/2026. Đây không phải end-to-end dashboard P95.
- **Charts chậm nhất (P95)**: `Active Drivers` (`1.833` giây) và
  `Active Vehicles` (`1.722` giây), do `COUNT(DISTINCT ...)` trên hơn
  2.3 triệu trip rows.
- **Các charts còn lại**: P95 khoảng `0.15` đến `0.90` giây trong môi trường đo.
  Kết quả phụ thuộc máy local, cache và tải đồng thời.
