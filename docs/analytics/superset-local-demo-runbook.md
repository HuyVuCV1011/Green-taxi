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
| `analytics.dq_batch_summary` | `batch_completed_at` | *None* | Successful NDS run status, reconciliation, DQ/quarantine counts and recency |
| `analytics.pareto_pickup_zone` | *None* | `pickup_*` | Total trips, cumulative shares, total revenue and revenue/trip |
| `analytics.driver_performance_summary` | *None* | Driver | Driver count, completed shifts, revenue/hour, utilization, idle minutes/shift, trips/shift, review driver count |
| `analytics.driver_performance_monthly` | `reporting_month` | Driver/month | Latest-month action metrics calculated from additive components |
| `analytics.vehicle_performance_monthly` | `reporting_month` | Vehicle/month | Latest-month provisional peer-review queue, not a certified KPI |

Mỗi dataset và metric chứa certification metadata:

- Certified by: `Analytics Semantic Contract Owner`
- Contract: `docs/analytics/semantic-contract.md`
- Metric source: `docs/analytics/metric-catalog.md`

Bootstrap idempotent tạo hoặc cập nhật 14 Superset datasets, 109 metric instances
(trip metrics được khai báo riêng trên pickup/dropoff), 35 decision-focused visuals và 1
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

Dashboard đã được đánh giá clean-slate và rebuild theo decision flow, không giữ
inventory cũ chỉ để đạt số lượng chart. Các thay đổi chính:

- Buộc light theme ở cấp Superset (`THEME_DARK = None`) để chart engine, axis,
  header và dashboard CSS cùng một contrast system; không dùng dark shell.
- Tách revenue/trips thành aligned small multiples; loại mọi shared-axis
  mixed-unit chart.
- Thêm top-zone × hour view giữ đủ 12 × 24 cells và zone value profile thay
  ranking doanh thu lặp lại.
- Đồng nhất Workforce action center về latest reporting month; queue là hero,
  shift queue có priority rank và vehicle queue ghi rõ provisional.
- Sửa latest DQ run từ audit metadata để successful zero-event run không bị bỏ;
  thay distorted trend chart bằng successful-run health table.
- OLAP lab có đủ slice, dice, drill-down, roll-up và pivot ở các visual riêng.
- Tách model provenance/thresholds khỏi kết quả clustering/association rules.
- Chuẩn hóa English dashboard labels, table headers và metric display names.

Backlog có chủ đích chỉ còn native dashboard filter: bật lại sau khi nâng image
và browser smoke test xác nhận `/api/v1/time_range/` không còn lỗi. Không giả vờ
filter hoạt động trên phiên bản hiện tại.

## 5. Dashboard demo flow

1. Mở dashboard và chỉ badge certified/published cùng period/timezone context.
2. **Executive pulse**: đọc KPI strip và hai small multiples revenue/trips;
   không diễn giải scale giữa hai chart như cùng đơn vị.
3. **Demand patterns**: bắt đầu từ zone × hour hero, sau đó weekday/hour,
   concentration và zone value profile.
4. **Workforce actions**: đọc latest-month KPI, driver queue, ba-status peer
   matrix, vehicle queue và 30 ca utilization thấp nhất.
5. **Trust & data health**: xác nhận latest run có 0 issue/quarantine hay không,
   đối chiếu rows loaded, rồi mở historical rule findings khi cần.
6. **OLAP lab**: chỉ lần lượt slice, dice, drill-down, roll-up và pivot; member
   được ghi ngay trong chart title.
7. **Exploratory models**: xác nhận model run/training window/threshold trước,
   sau đó mới đọc segments, profiles và rules ranked by lift.

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
- dashboard, 14 datasets, 109 metric instances và 35 decision-focused visuals tồn tại;
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

- **Dashboard hiện tại sau provision**: 14 datasets, 109 metric instances,
  35 decision-focused visuals, 6 tabs và một context card mỗi tab.
- Benchmark artifact phải có đúng `total_charts = 35` và 35 chart entries mới
  được dùng làm bằng chứng hiệu năng cho bản clean-slate này.
