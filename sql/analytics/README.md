# Analytics SQL

`01_certified_datasets.sql` tạo các PostgreSQL views read-only, deterministic:

| View | Grain | Purpose |
|---|---|---|
| `analytics.trip_pickup` | 1 row/trip | Default pickup date/location analysis |
| `analytics.trip_dropoff` | 1 row/trip | Explicit dropoff date/location analysis |
| `analytics.shift` | 1 row/completed shift | Shift metrics and start/end zone aliases |
| `analytics.shift_trip_aggregate` | 1 row/shift_id | Safe trip aggregate before any fact comparison |
| `analytics.dq_summary` | 1 row/DQ grouping | Issue/quarantine monitoring without fact joins |
| `analytics.pareto_pickup_zone` | 1 row/pickup zone | Zone concentration and cumulative contribution analysis |
| `analytics.driver_performance_summary` | 1 row/driver | Peer comparison and driver review queue |
| `analytics.olap_trip_cube` | 1 row/trip | ROLAP slice, dice, drill-down and pivot over trip dimensions |
| `analytics.olap_shift_cube` | 1 row/shift | ROLAP roll-up and utilization analysis over shift dimensions |

The same script also creates exploratory Data Mining history tables and the
dashboard-safe current-run views:

| Table | Grain | Purpose |
|---|---|---|
| `analytics.model_runs` | 1 row/model run | Parameters, quality metrics and current-run flag |
| `analytics.driver_segments` | 1 row/driver/run | K-Means history; not a dashboard dataset |
| `analytics.route_association_rules` | 1 row/rule/run | Apriori history; not a dashboard dataset |
| `analytics.current_driver_segments` | 1 row/eligible driver | Current successful K-Means run for Superset |
| `analytics.current_route_association_rules` | 1 row/published rule | Current successful Apriori run for Superset |

`python -m scripts.setup_superset_warehouse` áp dụng views và security grants.
Các view không materialize hoặc sửa warehouse rows.

`02_superset_readonly_role.sql` cấp quyền tối thiểu cho `superset_ro`. Role và
password được tạo/cập nhật bởi `python -m scripts.setup_superset_warehouse`;
password chỉ đọc từ `.env.superset` local bị Git ignore.
