# Analytics SQL

`01_certified_datasets.sql` tạo các PostgreSQL views read-only, deterministic:

| View | Grain | Purpose |
|---|---|---|
| `analytics.trip_pickup` | 1 row/trip | Default pickup date/location analysis |
| `analytics.trip_dropoff` | 1 row/trip | Explicit dropoff date/location analysis |
| `analytics.shift` | 1 row/completed shift | Shift metrics and start/end zone aliases |
| `analytics.shift_trip_aggregate` | 1 row/shift_id | Safe trip aggregate before any fact comparison |
| `analytics.dq_summary` | 1 row/DQ grouping | Issue/quarantine monitoring without fact joins |

`python -m scripts.setup_superset_warehouse` áp dụng views và security grants.
Các view không materialize hoặc sửa warehouse rows.

`02_superset_readonly_role.sql` cấp quyền tối thiểu cho `superset_ro`. Role và
password được tạo/cập nhật bởi `python -m scripts.setup_superset_warehouse`;
password chỉ đọc từ `.env.superset` local bị Git ignore.
