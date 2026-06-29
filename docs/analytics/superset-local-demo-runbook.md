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
| `analytics.dq_summary` | `event_date_utc` | *None* | DQ issue count, quarantine count |
| `analytics.pareto_pickup_zone` | *None* | `pickup_*` | Total trips, cumulative trips percentage, total revenue, cumulative revenue percentage |
| `analytics.driver_performance_summary` | *None* | Driver | Driver count, completed shifts, revenue/hour, utilization, idle minutes/shift, trips/shift, review driver count |

Mỗi dataset và metric chứa certification metadata:

- Certified by: `Analytics Semantic Contract Owner`
- Contract: `docs/analytics/semantic-contract.md`
- Metric source: `docs/analytics/metric-catalog.md`

Bootstrap idempotent tạo hoặc cập nhật 10 Superset datasets, 88 metric instances
(trip metrics được khai báo riêng trên pickup/dropoff), 42 charts và 1
operational monitoring dashboard gồm 6 tabs. `analytics.shift_trip_aggregate`
là view kỹ thuật chống fan-out để giữ semantic contract; view này không được
provision thành Superset dataset độc lập.

Native time filter chưa được provision trên image Superset 6.1.0. Frontend của
phiên bản này gửi scalar Rison tới `/api/v1/time_range/`, trong khi backend từ
chối request đó và làm filter hiển thị `Network error`. Dashboard vì vậy chủ
động để `native_filter_configuration` rỗng; time grain và time range của từng
chart vẫn được khai báo trong chart contract. Chỉ bật lại native time filter sau
khi nâng image và xác nhận API tương thích bằng browser smoke test.

## 4. Dashboard review and improvement log

Đánh giá hiện tại: dashboard đã bao phủ BQ01-BQ05, OLAP và Data Mining trên 6
tabs, dùng đúng certified datasets và không phá semantic grain. Các điểm cần ưu
tiên khi cải thiện là khả năng đọc nhanh theo câu hỏi nghiệp vụ, thứ tự thời
gian trên chart category, và hiệu năng của các chart distinct-count/OLAP nặng.

Đã cải thiện trong provisioning script:

- Thêm `CHART_DESCRIPTIONS` để mỗi chart ghi rõ BQ/OLAP/DM mà chart phục vụ.
- Dùng các nhãn `*_weekday_label` có tiền tố thứ tự trong analytics views cho
  weekday bar chart và weekday-hour heatmap, tránh Superset sắp xếp thứ theo
  chữ cái hoặc theo metric.
- Giữ nguyên số lượng chart/dataset/metric để dashboard vẫn tương thích smoke
  tests và benchmark artifact hiện có.

Backlog cải thiện an toàn:

- Bật native time filter sau khi nâng Superset image và browser smoke test xác
  nhận không còn lỗi `/api/v1/time_range/`.
- Nếu demo chạy chậm trên máy yếu, cân nhắc materialized summary cho
  `Active Drivers`, `Active Vehicles` và `OLAP Drill-down - Time Hierarchy`.
- Nếu cần đi sâu BQ01 hơn, bổ sung thêm view hoặc chart zone-hour theo top pickup
  zones rồi refresh benchmark đủ 42+ charts sau khi provision.

## 5. Dashboard demo flow

1. Mở dashboard và chỉ badge certified/published.
2. Tab **Operations Overview**: đọc KPI strip, monthly trend, pickup borough,
   top zone và ordered weekday profile để nắm trạng thái toàn hệ thống trong
   một màn.
3. Tab **Demand Patterns**: dùng heatmap weekday/hour đã có thứ tự ngày, hourly
   profile, zone concentration và pickup/dropoff borough charts để theo dõi nhu
   cầu theo thời gian và địa lý.
4. Tab **Driver & Fleet Performance**: dùng driver matrix, driver review queue,
   vehicle type và vehicle detail để ưu tiên điều phối/đào tạo.
5. Tab **Data Quality & Anomalies**: theo dõi DQ issues, quarantine, anomaly KPI,
   trend, severity/source breakdown và top rules. Không cộng DQ, quarantine,
   trip anomaly và shift anomaly thành một chỉ số chung.
6. Tab **OLAP Demo**: dùng ROLAP views để minh họa slice, dice, drill-down,
   roll-up và pivot trên Superset.
7. Tab **Data Mining Insights**: xem driver segments, segment profile và top
   route association rules theo lift.

Dashboard này ưu tiên tính reproducible và semantic correctness hơn dashboard
design tùy biến thủ công. Mọi chart/layout đang nằm trong
`scripts/provision_superset.py`; chỉnh trực tiếp trên UI chỉ nên dùng để thử
nghiệm rồi port lại vào bootstrap script.

Số expected của full release:

| Evidence | Expected |
|---|---:|
| Trip count | `2.304.276` |
| Completed shifts | `157.379` |
| Total revenue | `48.535.884,47 USD` |
| Active drivers | `795` |
| Shift utilization | khoảng `69,26%` |

## 6. Acceptance tests

```powershell
docker compose --env-file .env.superset -f docker-compose.superset.yml ps --all
python -m scripts.smoke_test_superset
python -m unittest discover -s tests -v
```

Smoke suite xác nhận:

- `/health` trả `OK`;
- admin REST login thành công;
- dashboard, 10 datasets, 88 metric instances và 42 charts tồn tại;
- dashboard không provision native time filter bị lỗi trên Superset 6.1.0;
- `superset_ro` query được approved analytics views;
- pickup/dropoff count khớp;
- truy cập trực tiếp DDS bị từ chối;
- `CREATE TABLE` và `INSERT` qua BI login bị từ chối.

## 7. Daily operation

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

## 8. Reset and backup

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

## 9. Known boundaries

- Đây là local synchronous demo: không có Redis, Celery, alerts hoặc reports.
- `TALISMAN_ENABLED=False` chỉ phù hợp local HTTP demo.
- Metadata rate-limit storage dùng memory; không phải production topology.
- Dashboard chỉ dùng approved analytics views. Tab 4 kết hợp business anomaly
  từ trip/shift với DQ summary, nhưng không join DQ events vào business facts.

## 10. Performance Benchmark

Quy trình benchmark tự động đo đạc thời gian tải của các charts thuộc dashboard qua REST API v1.

### 10.1. Lệnh thực hiện

Chạy script benchmark (chạy tối thiểu 20 lần cho mỗi chart sau 2 lần warm-up):

```powershell
python -m scripts.benchmark_superset
```

Kết quả đo đạc chi tiết của từng lượt chạy được xuất ra file JSON:
[superset_benchmark_results.json](../../deliverables/benchmark/superset_benchmark_results.json)

### 10.2. Tóm tắt kết quả đo đạc thực tế

- **Dashboard hiện tại sau provision**: 10 datasets, 88 metric instances,
  42 charts và 6 tabs.
- **Artifact benchmark hiện có**: đã refresh ngày 18/06/2026 với đủ 42 charts.
- **Trung bình các giá trị P95 của 42 charts**: `0.660` giây trong lần đo local.
  Đây không phải end-to-end dashboard P95.
- **Chart chậm nhất (P95)**: `OLAP Drill-down - Time Hierarchy` (`3.469` giây).
- **Các KPI distinct chậm nhất kế tiếp**: `Active Vehicles` (`1.770` giây) và
  `Active Drivers` (`1.756` giây), do `COUNT(DISTINCT ...)` trên hơn 2.3 triệu
  trip rows.
- **Các charts còn lại**: P95 khoảng `0.15` đến `0.90` giây trong môi trường đo.
  Kết quả phụ thuộc máy local, cache và tải đồng thời.
